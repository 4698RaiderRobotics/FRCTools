import adsk.core
import adsk.fusion
import os
import math
import time
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface

#  *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_LightenDialog'
CMD_NAME = 'Lighten'
CMD_Description = 'Lighten a solid by pocketing'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []
ControlKeyHeldDown = False


# Class to hold lighten profile info
class LightenProfile:
    profile: adsk.fusion.Profile = None
    offsetDist: float = 0.0
    filletRadius: float = 0.0
    outerLoop: adsk.fusion.ProfileLoop = None
    centroid: adsk.core.Point3D = None
    area: float = 0.0

    isComputed: bool = False
    filletedLoop: adsk.core.ObjectCollection = None

    def __init__(self, profile: adsk.fusion.Profile, offset: float, radius: float ):
        self.profile = profile
        self.offsetDist = offset
        self.filletRadius = radius
        for loop in self.profile.profileLoops:
            if loop.isOuter:
                self.outerLoop = loop
                break
        
        self.centroid = self.profile.areaProperties().centroid
        self.area = self.profile.areaProperties().area

# Global list of the lighten profiles
lightenProfileList: list[LightenProfile] = []
lightenSketch: adsk.fusion.Sketch = None

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(config.WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(config.PANEL_ID)

    # Create the the FRCTool submenu.
    submenu = panel.controls.itemById( config.DROPDOWN_ID )

    # # Create the button command control in the UI.
    control = submenu.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

# Executed when add-in is stopped.
def stop():

    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(config.WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(config.PANEL_ID)
    submenu = panel.controls.itemById( config.DROPDOWN_ID )
    command_control = submenu.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.isPromoted = False
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    global ui_handlers
    ui_handlers = []

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):

    # General logging for debug.
    futil.log(f'{CMD_NAME} command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create a solid selection input.
    solidSelection = inputs.addSelectionInput('solid_selection', 'Solid', 
                                              'Select the solid body to pocket.')
    solidSelection.addSelectionFilter( "SolidBodies" )
    solidSelection.setSelectionLimits( 1, 1 )

    # Create a profile selection input.
    profileSelection = inputs.addSelectionInput('profile_selection', 'Profiles', 
                    'Select the profiles to use for pocketing. Hold Ctrl-Key to delay update.')
    profileSelection.addSelectionFilter( "Profiles" )
    profileSelection.setSelectionLimits( 1, 0 )

    # Create a offset distance.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.125')
    offsetDist = inputs.addValueInput('offset_distance', 'Offset Distance', defaultLengthUnits, default_value)

    # Create a corner radius value input.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.125')
    cornerRadius = inputs.addValueInput('corner_radius', 'Corner Radius', defaultLengthUnits, default_value)

    # Create a pocket depth value input.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.25')
    pocketDepth = inputs.addValueInput('pocket_depth', 'Pocket Depth', defaultLengthUnits, default_value)

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.keyDown, command_keydown, local_handlers=local_handlers)
    futil.add_handler(args.command.keyUp, command_keyup, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    global lightenProfileList
    lightenProfileList = []

# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    global lightenProfileList

    inputs = args.command.commandInputs
    solidSelection: adsk.core.SelectionCommandInput = inputs.itemById('solid_selection')
    profileSelection: adsk.core.SelectionCommandInput = inputs.itemById('profile_selection')
    pocketDepth: adsk.core.ValueCommandInput = inputs.itemById('pocket_depth')

    solid: adsk.fusion.BRepBody = solidSelection.selection(0).entity

    ComputesNeeded = 0
    for profile in lightenProfileList:
        if not profile.isComputed :
            ComputesNeeded += 1
    
    ui.progressBar.show( '%p Done. Processing Profile %v of %m', 0, ComputesNeeded + 1 )

    i = 0
    for profile in lightenProfileList:
        if not profile.isComputed :
            i += 1
            ui.progressBar.progressValue = i
            adsk.doEvents()
            offsetProfile( profile )

    workingComp = solid.parentComponent
    sketch: adsk.fusion.Sketch = workingComp.sketches.add( profileSelection.selection(0).entity )
    sketch.isComputeDeferred = True
    sketch.name = 'Lighten'

    for profile in lightenProfileList:
        if profile.isComputed:
            Curves3DToSketch( sketch, profile.filletedLoop )
    
    ui.progressBar.progressValue = i + 1
    adsk.doEvents()

    sketch.isComputeDeferred = False
    if sketch.profiles.count > 0 :
        extrudeProfiles( solid, sketch, pocketDepth.value )

    ui.progressBar.hide()

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')

    if not ControlKeyHeldDown :
        command_execute( args )
        args.isValidResult = True

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    global lightenProfileList

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    solidSelection: adsk.core.SelectionCommandInput = inputs.itemById('solid_selection')
    profileSelection: adsk.core.SelectionCommandInput = inputs.itemById('profile_selection')
    cornerRadius: adsk.core.ValueCommandInput = inputs.itemById('corner_radius')
    offsetDist: adsk.core.ValueCommandInput = inputs.itemById('offset_distance')

    if changed_input.id == 'solid_selection' :
        profileSelection.clearSelection()
        lightenProfileList = []


    if changed_input.id == 'profile_selection' :
        if profileSelection.selectionCount == 0:
            lightenProfileList = []
        elif profileSelection.selectionCount > len(lightenProfileList) :
            # We added a profile selection
            i = 0
            while i < profileSelection.selectionCount:
                profile = profileSelection.selection(i).entity
                existingSelection = False
                for liteProf in lightenProfileList:
                    if liteProf.profile == profile :
                        futil.log(f'Found existing profile!!!')
                        existingSelection = True
                        break
                if not existingSelection:
                    futil.log(f'Adding new profile to global list .. .. .')
                    lightenProfileList.append( LightenProfile( profile, offsetDist.value, cornerRadius.value ))
                i += 1
        elif profileSelection.selectionCount < len(lightenProfileList) :
            # We removed a profile selection
            newLPlist = []
            for liteProf in lightenProfileList :
                foundProfile = False
                i = 0
                while i < profileSelection.selectionCount:
                    selProf = profileSelection.selection(i).entity
                    if liteProf.profile == selProf :
                        foundProfile = True
                        break
                    i += 1
                if foundProfile :
                    newLPlist.append( liteProf )
                else:
                    futil.log(f'Removing profile from global list .. .. .')
            lightenProfileList = newLPlist

    if changed_input.id == 'corner_radius' :
        # Force recompute of the profiles
        for lp in lightenProfileList:
            lp.filletRadius = cornerRadius.value
            lp.isComputed = False

    if changed_input.id == 'offset_distance' :
        # Force recompute of the profiles
        for lp in lightenProfileList:
            lp.offsetDist = offsetDist.value
            lp.isComputed = False

# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    # futil.log(f'{CMD_NAME} Command Validate Event')

    inputs = args.inputs

def command_keydown(args: adsk.core.KeyboardEventArgs):
    global ControlKeyHeldDown

    futil.log(f'{CMD_NAME} KeyDown Event, code={args.keyCode}, mask={bin(args.modifierMask)}, isCtrl={args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier}')
 
    if args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier :
        ControlKeyHeldDown = True

def command_keyup(args: adsk.core.KeyboardEventArgs):
    global ControlKeyHeldDown

    futil.log(f'{CMD_NAME} KeyUp Event, code={args.keyCode}, mask={bin(args.modifierMask)}, isCtrl={args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier}')

    if not args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier :
        if ControlKeyHeldDown :
            # Ctrl key was held down.  Now it has been released
            ControlKeyHeldDown = False
            cmd: adsk.core.Command = args.firingEvent.sender
            cmd.doExecutePreview()

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []

# def offsetProfile( solid: adsk.fusion.BRepBody, profile: LightenProfile ) :
def offsetProfile( profile: LightenProfile ) :

    # Create a temporary sketch
    workingComp = profile.profile.parentSketch.parentComponent
    sketch: adsk.fusion.Sketch = workingComp.sketches.add( profile.profile )
    sketch.isComputeDeferred = True
    sketch.name = 'TempSketch'

    outline: list[adsk.fusion.SketchCurve] = []
    for curve in profile.outerLoop.profileCurves :
        newEntity = Curve3DToSketch( sketch, curve.geometry )
        outline.append( newEntity )

    offset = adsk.core.ValueInput.createByReal( -profile.offsetDist )
    offsetInput = sketch.geometricConstraints.createOffsetInput( outline, offset )
    offsetInput.isTopologyMatched = False
    try :
        offsetConstr = sketch.geometricConstraints.addOffset2( offsetInput )
    except :
        None

    failedOffset = False
    offsetProfile = sketch.profiles.item(0)
    offsetProfArea = offsetProfile.areaProperties().area
    if( offsetProfArea > profile.area ) :
        deleteList = []
        for c in offsetProfile.profileLoops.item(0).profileCurves:
            deleteList.append( c.sketchEntity )
        for c in deleteList :
            c.deleteMe()
        offset = adsk.core.ValueInput.createByReal( profile.offsetDist )
        offsetInput = sketch.geometricConstraints.createOffsetInput( outline, offset )
        offsetInput.isTopologyMatched = False
        try:
            offsetConstr = sketch.geometricConstraints.addOffset2( offsetInput )
        except:
            failedOffset = True


    if failedOffset :
        sketch.deleteMe()
        return

    offsetLoop = sketch.findConnectedCurves( offsetConstr.childCurves[0] )
    futil.log(f'Found {len(offsetLoop)} Offset curves')

    loopRadii = findCurvesMaximumRadii( profile, offsetLoop )

    # sketch2: adsk.fusion.Sketch = workingComp.sketches.add( profile.profile )
    # sketch2.isComputeDeferred = True
    # sketch2.name = 'CopyOffsetLoop'

    # for c in offsetLoop:
    #     sketch2.include( c )

    singlefillet = filletConnectedCurve( offsetLoop, loopRadii, profile.filletRadius )
    
    try:
        filletLoop = sketch.findConnectedCurves( singlefillet )
    except:
        filletLoop = None

    if filletLoop :
        profile.filletedLoop = SketchCurveToCurve3D( filletLoop )
        profile.isComputed = True

    # Delete the temporary sketch
    sketch.deleteMe()

    return

def extrudeProfiles( solid: adsk.fusion.BRepBody, sketch: adsk.fusion.Sketch, depth: float ) :

    extrudeProfiles = adsk.core.ObjectCollection.create()
    for p in sketch.profiles :
        extrudeProfiles.add( p )
    extrudes = sketch.parentComponent.features.extrudeFeatures
    cutDistance = adsk.core.ValueInput.createByReal( depth )
    extrudeCut = extrudes.createInput( extrudeProfiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    distance = adsk.fusion.DistanceExtentDefinition.create( cutDistance )
    extrudeCut.setOneSideExtent( distance, adsk.fusion.ExtentDirections.NegativeExtentDirection )
    extrudeCut.participantBodies = [ solid ]
    extrudes.add( extrudeCut )

    return


def filletConnectedCurve( rawloop: adsk.core.ObjectCollection, 
    loopRadii: list[float], radius: float ) -> adsk.fusion.SketchCurve :

    # Trim off all curve segments that are too short for the fillet radius
    loop = []
    i = 0
    while i < len(rawloop):
        if loopRadii[i] > radius :
            loop.append( rawloop[i] )
        i += 1

    if len(loop) < 2 :
        return None 
    
    i = 0
    while i < len(loop) - 1:
        filletBetweenTwoCurves( loop[i], loop[i+1], radius )
        i += 1

    return filletBetweenTwoCurves( loop[ len(loop)-1 ], loop[0], radius )


def filletBetweenTwoCurves( 
    curve1: adsk.fusion.SketchCurve, 
    curve2: adsk.fusion.SketchCurve, radius: float ) -> adsk.fusion.SketchCurve :

    sketch = curve1.parentSketch

    futil.log(f'Filleting between :::')
    futil.print_SketchCurve( curve1 )
    futil.print_SketchCurve( curve2 )
    dist = curve1.startSketchPoint.geometry.distanceTo( curve2.endSketchPoint.geometry )
    startPt = curve1.startSketchPoint.geometry
    endPt = curve2.endSketchPoint.geometry
    dist2 = curve1.endSketchPoint.geometry.distanceTo( curve2.endSketchPoint.geometry ) 
    if dist2 < dist :
        startPt = curve1.endSketchPoint.geometry
        endPt = curve2.endSketchPoint.geometry
        dist = dist2
    dist2 = curve1.endSketchPoint.geometry.distanceTo( curve2.startSketchPoint.geometry ) 
    if dist2 < dist :
        startPt = curve1.endSketchPoint.geometry
        endPt = curve2.startSketchPoint.geometry
        dist = dist2
    dist2 = curve1.startSketchPoint.geometry.distanceTo( curve2.startSketchPoint.geometry ) 
    if dist2 < dist :
        startPt = curve1.startSketchPoint.geometry
        endPt = curve2.startSketchPoint.geometry

    futil.log(f'Filleting with input pts {futil.format_Point3D(startPt)} and {futil.format_Point3D(endPt)}')
    fillet = None
    try :
        fillet = sketch.sketchCurves.sketchArcs.addFillet( curve1, startPt, curve2, endPt, radius )
    except Exception as e:
        futil.handle_error( e )

    return fillet

def findCurvesMaximumRadii( profile: LightenProfile, loop: adsk.core.ObjectCollection ) -> list[float] :

    sketch: adsk.fusion.Sketch = loop[0].parentSketch

    curve: adsk.fusion.SketchCurve = loop[0]
    bbox = curve.boundingBox
    for c in loop:
        bbox.combine( c.boundingBox )

    shortestBBside = bbox.maxPoint.x - bbox.minPoint.x
    if bbox.maxPoint.y - bbox.minPoint.y < shortestBBside :
        shortestBBside = bbox.maxPoint.y - bbox.minPoint.y

    startCircleRadius = min( shortestBBside/2, profile.filletRadius )
    futil.log(f'  findCurvesMaximumRadii() --- starting Circle radius = {startCircleRadius} ')

    maxRadii = []
    i = 0
    while i < len(loop) :
        prev = i - 1
        if prev < 0 :
            prev = len(loop) - 1
        next = i + 1
        if next == len(loop):
            next = 0

        prevCurve: adsk.fusion.SketchCurve = loop[prev]
        curve: adsk.fusion.SketchCurve = loop[i]
        nextCurve: adsk.fusion.SketchCurve = loop[next]

        concaveArc = False
        if curve.objectType == adsk.fusion.SketchArc.classType() :
            if isConcaveInward( curve.geometry, profile.centroid ) :
                futil.log(f'Curve is a Concave Inward Arc, R = {curve.radius}')
                maxRadii.append( curve.radius )
                concaveArc = True

        if not concaveArc :
            # Construct a circle tangent to all three curves
            circ = sketch.sketchCurves.sketchCircles.addByCenterRadius( profile.centroid, startCircleRadius )
            reorderTangents = False
            try:
                sketch.geometricConstraints.addTangent( curve, circ )
                sketch.geometricConstraints.addTangent( prevCurve, circ )
                sketch.geometricConstraints.addTangent( nextCurve, circ )
            except:
                reorderTangents = True

            if reorderTangents:
                try :
                    circ.deleteMe()
                    circ = sketch.sketchCurves.sketchCircles.addByCenterRadius( profile.centroid, startCircleRadius )
                    sketch.geometricConstraints.addTangent( curve, circ )
                    sketch.geometricConstraints.addTangent( nextCurve, circ )
                    sketch.geometricConstraints.addTangent( prevCurve, circ )
                except Exception as e:
                    futil.handle_error( e )
            
            if not circ.isFullyConstrained:
                maxRadii.append( 1000000 )
            else:
                maxRadii.append( circ.radius )

        futil.log(f'Max Fillet Radius = {maxRadii[len(maxRadii)-1]}')

        # try:
        #     circ.deleteMe()
        # except:
        #     None

        i += 1

    return maxRadii

def SketchCurveToCurve3D( coll: adsk.core.ObjectCollection ) -> list[adsk.core.Curve3D] :

    curves = []
    for obj in coll :
        curves.append( obj.geometry )

    return curves

def Curves3DToSketch( sketch: adsk.fusion.Sketch, curves: list[adsk.core.Curve3D] ) :

    for curve in curves:
        if curve.objectType == adsk.core.Line3D.classType() :
            line: adsk.core.Line3D = curve
            sketchCurve = sketch.sketchCurves.sketchLines.addByTwoPoints( line.startPoint, line.endPoint )
        elif curve.objectType == adsk.core.Arc3D.classType() :
            arc: adsk.core.Arc3D = curve
            sketchCurve = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( arc.center, arc.startPoint, arc.endPoint )
        sketchCurve.isFixed = True

def Curve3DToSketch( sketch: adsk.fusion.Sketch, curve: adsk.core.Curve3D ) -> adsk.fusion.SketchCurve :

    sketchCurve = adsk.fusion.SketchCurve.cast(None)
    if curve.objectType == adsk.core.Line3D.classType() :
        line: adsk.core.Line3D = curve
        sketchCurve = sketch.sketchCurves.sketchLines.addByTwoPoints( line.startPoint, line.endPoint )
    elif curve.objectType == adsk.core.Arc3D.classType() :
        arc: adsk.core.Arc3D = curve
        sketchCurve = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( arc.center, arc.startPoint, arc.endPoint )
    else :
        futil.log(f' Curve3DToSketch() -- Unhandled object "{curve.objectType}"')

    if sketchCurve:
        sketchCurve.isFixed = True
        sketchCurve.isConstruction = True

    return sketchCurve

def isConcaveInward( arc: adsk.core.Arc3D, centroid: adsk.core.Point3D ) -> bool :
            # Create a unit vector from the center of the arc to the centroid of the profile
    centroidVec = futil.twoPointUnitVector( arc.center, centroid )
    angle = centroidVec.angleTo( futil.toVector2D(arc.referenceVector) )

    futil.log(f'**************  Centroid to Reference Angle = {angle * 180 / math.pi}')

    if angle > math.pi / 2 :
        return True
    
    return False

def isLoopFlowPositive( profile: LightenProfile ) -> bool :

    curves = profile.outerLoop.profileCurves

    for c in curves:
        if c.geometry.objectType == adsk.core.Line3D.classType() :
            line: adsk.core.Line3D = c.geometry
            startPt2D = futil.toPoint2D( line.startPoint )
            endPt2D = futil.toPoint2D( line.endPoint )
            normal = futil.lineNormal(startPt2D, endPt2D)
            centroidVec = futil.twoPointUnitVector( line.startPoint, profile.centroid )
            angle = centroidVec.angleTo( normal )
            futil.log(f'  isLoopFlowPositive() ------ {angle < math.pi / 2 }')
            futil.print_Curve3D( line )
            futil.log(f' centroid = {futil.format_Point3D( profile.centroid )}, normal = ({normal.x}, {normal.y})')
            futil.log(f'     Inside left angle = {angle * 180 / math.pi}')
    if angle < math.pi / 2:
        return True
    else :
        return False
