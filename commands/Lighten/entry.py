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
IS_PROMOTED = False

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
    filletedLoops = []

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
    # futil.log(f'{CMD_NAME} command Created Event')

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


    # Create a pocket depth value input.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.25')
    pocketDepth = inputs.addValueInput('pocket_depth', 'Pocket Depth', defaultLengthUnits, default_value)

    # Disable filleting
    inputs.addBoolValueInput( "disable_fillet", "Disable Filleting", True )

    # Create a corner radius value input.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.125')
    cornerRadius = inputs.addValueInput('corner_radius', 'Corner Radius', defaultLengthUnits, default_value)
    cornerRadius.isEnabled = True

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
    # futil.log(f'{CMD_NAME} Command Execute Event')

    global lightenProfileList

    inputs = args.command.commandInputs
    solidSelection: adsk.core.SelectionCommandInput = inputs.itemById('solid_selection')
    profileSelection: adsk.core.SelectionCommandInput = inputs.itemById('profile_selection')
    pocketDepth: adsk.core.ValueCommandInput = inputs.itemById('pocket_depth')
    disableFillet: adsk.core.BoolValueCommandInput = inputs.itemById('disable_fillet')
    cornerRadius: adsk.core.ValueCommandInput = inputs.itemById('corner_radius')

    solid: adsk.fusion.BRepBody = solidSelection.selection(0).entity

    ComputesNeeded = 0
    for profile in lightenProfileList:
        if not profile.isComputed :
            ComputesNeeded += 1
    
    ui.progressBar.show( '%p Done. Processing Profile %v of %m', 0, ComputesNeeded + 1 )
    try:
        i = 0
        # If the profile is not computed then calculate the offset
        # and store it as Curve3D objects in the LightenProfile object
        for profile in lightenProfileList:
            if not profile.isComputed :
                i += 1
                ui.progressBar.progressValue = i
                adsk.doEvents()
                offsetProfile( profile )

        # Create a sketch for the offset profiles.
        workingComp = solid.parentComponent
        sketch: adsk.fusion.Sketch = workingComp.sketches.add( profileSelection.selection(0).entity )
        sketch.name = 'Lighten'

        # Draw the Curve3D objects in the sketch
        for profile in lightenProfileList:
            if profile.isComputed:
                for loop in profile.filletedLoops:
                    Curves3DToSketch( sketch, loop )

        ui.progressBar.progressValue = i + 1
        adsk.doEvents()

        # Extrude and fillet the profiles in the sketch
        if sketch.profiles.count > 0 :
            extrudeFeat = extrudeProfiles( solid, sketch, pocketDepth.value )
            if not disableFillet.value:
                filletProfiles( solid, extrudeFeat, cornerRadius.value )

    except Exception as e:
        futil.handle_error( '        ============  Lighten Failed  ============\n\n', True )

    ui.progressBar.hide()

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Preview Event')

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
    # futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    solidSelection: adsk.core.SelectionCommandInput = inputs.itemById('solid_selection')
    profileSelection: adsk.core.SelectionCommandInput = inputs.itemById('profile_selection')
    offsetDist: adsk.core.ValueCommandInput = inputs.itemById('offset_distance')
    disableFillet: adsk.core.BoolValueCommandInput = inputs.itemById('disable_fillet')
    cornerRadius: adsk.core.ValueCommandInput = inputs.itemById('corner_radius')

    if changed_input.id == 'solid_selection' :
        profileSelection.clearSelection()
        lightenProfileList = []


    if changed_input.id == 'profile_selection' :
        if profileSelection.selectionCount == 0:
            lightenProfileList = []
            # futil.log(f'Cleared global list')
        elif profileSelection.selectionCount > len(lightenProfileList) :
            # We added a profile selection
            i = 0
            while i < profileSelection.selectionCount:
                profile: adsk.fusion.Profile = profileSelection.selection(i).entity
                existingSelection = False
                for liteProf in lightenProfileList:
                    if liteProf.profile == profile :
                        # futil.log(f'Found existing profile!!!')
                        existingSelection = True
                        break
                if not existingSelection:
                    futil.log(f'Attempting to add new profile to global list .. .. .')
                    if len(lightenProfileList) > 0 :
                        existingPlane = lightenProfileList[0].profile.plane
                        existingPlane.transformBy( lightenProfileList[0].profile.parentSketch.transform )
                        newPlane = profile.plane
                        newPlane.transformBy( profile.parentSketch.transform )
                        if existingPlane.isCoPlanarTo( newPlane ) :
                            futil.log(f'Adding new profile to global list .. .. .')
                            lightenProfileList.append( LightenProfile( profile, offsetDist.value, cornerRadius.value ))
                        else:
                            futil.popup_error( f'Selected profile is not coplanar with other selected profiles.')
                            profileSelection.clearSelection()
                            for liteProf in lightenProfileList:
                                profileSelection.addSelection( liteProf.profile )
                    else:
                        futil.log(f'Adding new profile to empty global list .. .. .')
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
                # else:
                    # futil.log(f'Removing profile from global list .. .. .')
                    
            lightenProfileList = newLPlist
                    
        # futil.log(f'Global list has {len(lightenProfileList)} items....')


    if changed_input.id == 'disable_fillet' :
        for lp in lightenProfileList:
            lp.isComputed = False
        if disableFillet.value :
            cornerRadius.isEnabled = False
        else:
            cornerRadius.isEnabled = True

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

    # futil.log(f'{CMD_NAME} KeyDown Event, code={args.keyCode}, mask={bin(args.modifierMask)}, isCtrl={args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier}')
 
    if args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier :
        ControlKeyHeldDown = True

def command_keyup(args: adsk.core.KeyboardEventArgs):
    global ControlKeyHeldDown

    # futil.log(f'{CMD_NAME} KeyUp Event, code={args.keyCode}, mask={bin(args.modifierMask)}, isCtrl={args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier}')

    if not args.modifierMask & adsk.core.KeyboardModifiers.CtrlKeyboardModifier :
        if ControlKeyHeldDown :
            # Ctrl key was held down.  Now it has been released
            ControlKeyHeldDown = False
            cmd: adsk.core.Command = args.firingEvent.sender
            cmd.doExecutePreview()

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []

# def offsetProfile( solid: adsk.fusion.BRepBody, profile: LightenProfile ) :
def offsetProfile( profile: LightenProfile ) :

    # Create a temporary sketch
    workingComp = profile.profile.parentSketch.parentComponent
    sketch: adsk.fusion.Sketch = workingComp.sketches.add( profile.profile )
    sketch.isComputeDeferred = True
    sketch.name = 'LightenOffset'

    # Convert the profile edges to Sketch geometry
    outline: list[adsk.fusion.SketchCurve] = []
    for curve in profile.outerLoop.profileCurves :
        newEntity = Curve3DToSketch( sketch, curve.geometry )
        outline.append( newEntity )

    # Offset the profile geometry
    offset = adsk.core.ValueInput.createByReal( -profile.offsetDist )
    offsetInput = sketch.geometricConstraints.createOffsetInput( outline, offset )
    offsetInput.isTopologyMatched = False
    try :
        offsetConstr = sketch.geometricConstraints.addOffset2( offsetInput )
    except :
        None

    # If the offset profile has a larger area than the original
    # profile, then delete it and offset the other way.
    # This was neccesary because a reliable way to determine
    # which way to offset could not be determined.
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

    # If the offset fails then just delete the sketch and return
    if failedOffset :
        sketch.deleteMe()
        return
    
    # futil.print_Profiles( sketch.profiles )

    # Create lists of Curve3D object for each profile in the sketch.
    profile.filletedLoops = []
    for prof in sketch.profiles:
        profloop = []
        for e in prof.profileLoops.item(0).profileCurves:
            profloop.append( e.geometry )
        profile.filletedLoops.append( profloop )

    # Set computed to true and delete the sketch
    # The geometry is saved in the filletedLoops member of LightenProfile class
    profile.isComputed = True
    sketch.deleteMe()
    return

def extrudeProfiles( solid: adsk.fusion.BRepBody, sketch: adsk.fusion.Sketch, depth: float ) -> adsk.fusion.ExtrudeFeature :

    extrudeProfiles = adsk.core.ObjectCollection.create()
    for p in sketch.profiles :
        extrudeProfiles.add( p )
    extrudes = sketch.parentComponent.features.extrudeFeatures
    cutDistance = adsk.core.ValueInput.createByReal( depth )
    extrudeCut = extrudes.createInput( extrudeProfiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    distance = adsk.fusion.DistanceExtentDefinition.create( cutDistance )
    extrudeCut.setOneSideExtent( distance, adsk.fusion.ExtentDirections.NegativeExtentDirection )
    extrudeCut.participantBodies = [ solid ]
    extrudeFeature = extrudes.add( extrudeCut )
    extrudeFeature

    return extrudeFeature

def filletProfiles( solid: adsk.fusion.BRepBody, extrudeFeat: adsk.fusion.ExtrudeFeature, cornerRadius: float ) :

    # futil.log(f'   Number of Extrude side Faces = {extrudeFeat.sideFaces.count}')

    # Get one of the profiles making up the extrude feature input profiles
    if extrudeFeat.profile.objectType == adsk.core.ObjectCollection.classType():
        profOrPlane = extrudeFeat.profile.item(0)
    else :
        profOrPlane = extrudeFeat.profile

    # Get the plane defining the profile, transform it into model coordinates
    # and get the normal vector (also in model coordinates)
    if profOrPlane.objectType == adsk.fusion.Profile.classType():
        prof: adsk.fusion.Profile = profOrPlane
        sketch = prof.parentSketch
        sketchToModelTransform = sketch.transform
        plane = prof.plane
        # planeNormal = prof.plane.normal
        # planeNormal.transformBy( sketchToModelTransform )
        plane.transformBy( sketchToModelTransform )
        planeNormal = plane.normal
    else :
        futil.popup_error( f'Unhandled planar entity {extrudeFeat.profile.objectType}')
        planeNormal = adsk.core.Vector3D.create( 0, 0, 1 )
        plane = adsk.core.Plane.create( adsk.core.Point3D.create(), planeNormal)

    # futil.log(f'  Extrude profile plane normal = {futil.format_Vector3D( planeNormal )}')

    # Determine the edges that are perpendicular to the profile plane and touch it
    i = 0
    perpendicularEdges = adsk.core.ObjectCollection.create()
    for s in extrudeFeat.sideFaces:
        for edge in s.edges:
            i += 1
            if edge.geometry.objectType == adsk.core.Line3D.classType():
                line:adsk.core.Line3D = edge.geometry
                if plane.isPerpendicularToLine( line ) and len(plane.intersectWithCurve(line)) > 0 :
                    if not perpendicularEdges.contains( edge ) :
                        perpendicularEdges.add( edge )
    
    # Now add in any edges that are colinear with the perpendicular and touching edges.
    # This happens when the extrude is interrupted by a void
    perpAndTouchingEdges = adsk.core.ObjectCollection.createWithArray( perpendicularEdges.asArray() )
    for s in extrudeFeat.sideFaces:
        for edge in s.edges:
            if edge.geometry.objectType == adsk.core.Line3D.classType():
                line:adsk.core.Line3D = edge.geometry
                if not perpendicularEdges.contains( edge ) and plane.isPerpendicularToLine( line ) :
                    for perpEdge in perpAndTouchingEdges:
                        if line.isColinearTo(perpEdge.geometry):
                            perpendicularEdges.add( edge )
                            break

    futil.log(f'Processed edges = {i}, PerpAndTouching = {perpAndTouchingEdges.count}, perp edges = {perpendicularEdges.count}')

    fillets = solid.parentComponent.features.filletFeatures
    filletFeatureInput = fillets.createInput()
    filletRadius = adsk.core.ValueInput.createByReal( cornerRadius )
    edgeSet = filletFeatureInput.edgeSetInputs.addConstantRadiusEdgeSet( perpendicularEdges, filletRadius, False)
    fillets.add( filletFeatureInput )

    return


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
