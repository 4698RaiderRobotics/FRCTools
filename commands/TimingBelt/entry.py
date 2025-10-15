import adsk.core
import adsk.fusion
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config
from ..CCDistance import CCLine
from ..CCDistance.entry import motionTypes
from .geometry import *


app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_TimingBeltDialog'
CMD_NAME = 'Extrude Belt/Chain'
CMD_Description = 'Extrude a Timing Belt or Chain from a C-C Line'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

SelectedLine: CCLine.CCLine = None

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the FRCTool submenu.
    submenu = config.get_solid_submenu()

    # Create the button command control in the UI.
    control = submenu.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    submenu = config.get_solid_submenu()
    command_control = submenu.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.isPromoted = False
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Created Event')

    inputs = args.command.commandInputs

    # Create a Sketch Curve selection input.
    pitchLineSelection = inputs.addSelectionInput('belt_pitch_circles', 'C-C Line', 'Select a C-C Line')
    # pitchLineSelection.addSelectionFilter( "SketchCurves" )
    pitchLineSelection.setSelectionLimits( 3, 3 )

    # Create a simple text box input.
    belt_type = inputs.addTextBoxCommandInput('belt_type', 'Extruding :', '', 1, True )

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = "mm"
    default_value = adsk.core.ValueInput.createByString('9')
    inputs.addValueInput('belt_width', 'Belt Width', defaultLengthUnits, default_value)

    inputs.addBoolValueInput( 'suppress_teeth', 'Toothless Belt', True, '', True )

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.preSelect, command_preselect, local_handlers=local_handlers)
    futil.add_handler(args.command.select, command_select, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

# This event is fired when the user is hovering over an entity
# but has not yet clicked on it.
def command_preselect(args: adsk.core.SelectionEventArgs):
    global SelectedLine

    SelectedLine = CCLine.getCCLineFromEntity(args.selection.entity)
    # Allow selection if this is a ccline and not gears
    if SelectedLine and SelectedLine.data.motion != 0:
        obj = adsk.core.ObjectCollection.create()
        cc_objs = [ SelectedLine.line, SelectedLine.ODCircle1, SelectedLine.ODCircle2 ]
        for cc_obj in cc_objs:
            if cc_obj != args.selection.entity:
                obj.add( cc_obj )

        args.additionalEntities = obj

    else:
        args.isSelectable = False


# This event is fired when the user clicks on an entity
# to select it.
def command_select(args: adsk.core.SelectionEventArgs):
    # global SelectedLine

    futil.log( f'command_select - selected = {args.activeInput.selectionCount}' )
    
    # SelectedLine = CCLine.getCCLineFromEntity( args.selection.entity )
    if not SelectedLine:
        return
 
    args.activeInput.clearSelection()
    cc_objs = [ SelectedLine.line, SelectedLine.ODCircle1, SelectedLine.ODCircle2 ]
    for cc_obj in cc_objs:
        args.activeInput.addSelection( cc_obj )


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    global SelectedLine

    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to the command's inputs.
    inputs = args.command.commandInputs
    belt_width: adsk.core.ValueCommandInput = inputs.itemById('belt_width')
    belt_type: adsk.core.TextBoxCommandInput = inputs.itemById('belt_type')
    suppressTeeth = inputs.itemById('suppress_teeth')


    # originalSketch: adsk.fusion.Sketch = pitchLineSelection.selection(0).entity.parentSketch
    originalSketch: adsk.fusion.Sketch = SelectedLine.line.parentSketch
    timeline = originalSketch.parentComponent.parentDesign.timeline
    start_timeline_pos = timeline.markerPosition

    # Create a new component to put the sketches and geometry into
    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent
    trans = adsk.core.Matrix3D.create()
    workingOcc = rootComp.occurrences.addNewComponent( trans )
    workingComp = workingOcc.component
    # Create a new sketch for the belt on the same plane
    sketch = workingComp.sketches.add( originalSketch.referencePlane, workingOcc )
    sketch.name = 'TimingBelt'

    belt_type.formattedText = motionTypes[ SelectedLine.data.motion ]
    belt_geom = get_belt_geometry( SelectedLine.data.motion )


    PitchLoop = createPitchLoop( sketch, SelectedLine, suppressTeeth.value )
    # PitchLoop = createPitchLoopFromCircles( sketch, SelectedLine.pitchCircle1.worldGeometry, SelectedLine.pitchCircle2.worldGeometry )

    pathCurves = adsk.core.ObjectCollection.create()
    for curve in PitchLoop:
        pathCurves.add( curve.createForAssemblyContext(workingOcc))

    curveLength = 0.0
    for curve in pathCurves:
        curveLength += curve.length

    toothCount = int( (curveLength * 10 / belt_geom.pitchLength) + 0.5 )
    futil.log(f'Loop length is {curveLength} number of teeth is {toothCount}...')

    comp_name = get_component_name( SelectedLine.data.motion, toothCount, belt_width.value * 10 )
    workingComp.name = comp_name

    # Create the Offsets for the belt thickness.
    if args.firingEvent.name == "OnExecutePreview":
        if belt_geom.toothHeight > 0:
            inward_offset = adsk.core.ValueInput.createByReal( - (belt_geom.pitchLineDepth + belt_geom.toothHeight) / 10 )
        else :
            inward_offset = adsk.core.ValueInput.createByReal( -belt_geom.thickness / 20 )
    else:
        inward_offset = adsk.core.ValueInput.createByReal( -belt_geom.pitchLineDepth / 10 )

    if belt_geom.toothHeight > 0:
        outward_offset = adsk.core.ValueInput.createByReal( (belt_geom.thickness - belt_geom.pitchLineDepth) / 10 )
    else:
        outward_offset = adsk.core.ValueInput.createByReal( belt_geom.thickness / 20 )

    geoConstraints = sketch.geometricConstraints
    curves = []
    for curve in PitchLoop:
        curves.append( curve )

    offsetInput = geoConstraints.createOffsetInput( curves, inward_offset )
    geoConstraints.addOffset2( offsetInput )
    offsetInput = geoConstraints.createOffsetInput( curves, outward_offset )
    geoConstraints.addOffset2( offsetInput )

    futil.log(f'Offsetting created {sketch.profiles.count} profiles..')
    if sketch.profiles.count < 2 :
        futil.popup_error(f'offset profiles not created correctly.')

    if args.firingEvent.name == "OnExecutePreview" :
        # Don't extrude and pattern on path if previewing just do the belt outline.
        extrudeBeltPreview( sketch, pathCurves, belt_width.value )

        end_timeline_pos = timeline.markerPosition - 1
        grp = timeline.timelineGroups.add( start_timeline_pos, end_timeline_pos )
        grp.name = "Extrude Belt"
        return

    maxArea = 0
    insideLoop = None
    i = 0
    while i < sketch.profiles.count:
        profile = sketch.profiles.item(i)
        if profile.areaProperties().area > maxArea:
            maxArea = profile.areaProperties().area
            insideLoop = profile.profileLoops.item(0)
        i += 1

    # futil.log(f'Inside loop has {insideLoop.profileCurves.count} curves in it.')
  
    (lineCurve, lineNormal, toothAnchorPoint) = findToothAnchor( insideLoop )

    baseLine = createToothProfile( sketch, belt_geom )

    geoConstraints.addCoincident( baseLine.startSketchPoint, toothAnchorPoint )
    # Rotating the tooth profile did not work so a dimension is used instead.
    # Create a dimension between the tooth profile baseline and the line Curve
    # and set it to a small angle.  Then delete the dimension and make line collinear
    angleDim = sketch.sketchDimensions.addAngularDimension( baseLine, lineCurve, baseLine.startSketchPoint.geometry )
    angleDim.value = 0.1 #radians
    angleDim.deleteMe()
    geoConstraints.addCollinear( baseLine, lineCurve )
    
    extrudeBelt( sketch, pathCurves, belt_width.value, toothCount, belt_geom.pitchLength )

    end_timeline_pos = timeline.markerPosition - 1
    grp = timeline.timelineGroups.add( start_timeline_pos, end_timeline_pos )
    grp.name = "Extrude Belt"


def extrudeBeltPreview( sketch: adsk.fusion.Sketch, path: adsk.core.ObjectCollection, beltWidth: float ) :

    workingComp = sketch.parentComponent

    # Determine the profile of the belt
    maxArea = 0
    minArea = 9999999
    i = 0
    while i < sketch.profiles.count:
        profile = sketch.profiles.item(i)
        if profile.areaProperties().area > maxArea:
            maxArea = profile.areaProperties().area
        if profile.areaProperties().area < minArea:
            minArea = profile.areaProperties().area
        i += 1

    beltLoop = None
    i = 0
    while i < sketch.profiles.count:
        profile = sketch.profiles.item(i)
        if profile.areaProperties().area < maxArea:
            beltLoop = profile
        i += 1

    extrudes = workingComp.features.extrudeFeatures
    beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth )
    extrudes.addSimple(beltLoop, beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

def extrudeBelt( sketch: adsk.fusion.Sketch, path: adsk.core.ObjectCollection,
                beltWidth: float, toothCount: int, beltPitchMM: int ) :

    workingComp = sketch.parentComponent

    # Determine the profiles of the belt and tooth
    maxArea = 0
    minArea = 9999999
    i = 0
    while i < sketch.profiles.count:
        profile = sketch.profiles.item(i)
        if profile.areaProperties().area > maxArea:
            maxArea = profile.areaProperties().area
        if profile.areaProperties().area < minArea:
            minArea = profile.areaProperties().area
        i += 1

    beltLoop = None
    profileLoop = None
    i = 0
    while i < sketch.profiles.count:
        profile = sketch.profiles.item(i)
        if profile.areaProperties().area > minArea and profile.areaProperties().area < maxArea:
            beltLoop = profile
        elif profile.areaProperties().area < maxArea:
            profileLoop = profile
        i += 1

    extrudes = workingComp.features.extrudeFeatures
    beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth )
    extrudeBelt = extrudes.addSimple(beltLoop, beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrudeTooth = extrudes.addSimple(profileLoop, beltWidthValue, adsk.fusion.FeatureOperations.JoinFeatureOperation)


    pathPatterns = workingComp.features.pathPatternFeatures
    beltPitch = adsk.core.ValueInput.createByReal( beltPitchMM / 10.0 )  # mm -> cm
    toothCountVI = adsk.core.ValueInput.createByReal( toothCount )
    patternCollection = adsk.core.ObjectCollection.create()
    patternCollection.add( extrudeTooth )

#    pathCurves = sketch.findConnectedCurves( originalConnectedCurves.item(0) )
    # futil.print_SketchObjectCollection( path )
    patternPath = adsk.fusion.Path.create( path, adsk.fusion.ChainedCurveOptions.noChainedCurves )
#    patternPath = adsk.fusion.Path.create( originalConnectedCurves.item(0), adsk.fusion.ChainedCurveOptions.connectedChainedCurves )
    toothPatternInput = pathPatterns.createInput( 
        patternCollection, patternPath, toothCountVI, beltPitch, adsk.fusion.PatternDistanceType.SpacingPatternDistanceType )
    toothPatternInput.isOrientationAlongPath = True
    toothPatternInput.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
    toothPattern = pathPatterns.add( toothPatternInput )


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs
    suppressTeeth = inputs.itemById('suppress_teeth')

    command_execute( args )
    if suppressTeeth.value :
        args.isValidResult = True

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global SelectedLine

    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    pitchLineSelection: adsk.core.SelectionCommandInput = inputs.itemById('belt_pitch_circles')
    belt_width: adsk.core.ValueCommandInput = inputs.itemById( 'belt_width' )
    suppress_teeth: adsk.core.BoolValueCommandInput = inputs.itemById('suppress_teeth')

    if changed_input.id == 'belt_pitch_circles' :
        if pitchLineSelection.selectionCount > 0 :
            geom = get_belt_geometry( SelectedLine.data.motion )
            belt_width.value = geom.width / 10
            if SelectedLine.data.motion > 3 :
                belt_width.isEnabled = False
                suppress_teeth.value = True
                suppress_teeth.isEnabled = False
            else :
                belt_width.isEnabled = True
                suppress_teeth.isEnabled = True
        else:
            belt_width.isEnabled = True
            suppress_teeth.isEnabled = True

# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    inputs = args.inputs

    pitchLineSelection: adsk.core.SelectionCommandInput = inputs.itemById('belt_pitch_circles')
    beltWidth = inputs.itemById('belt_width')
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.

    # futil.log(f'{CMD_NAME} Validate:: num selected = {pitchLineSelection.selectionCount}')

    if beltWidth.value > 0.001 and pitchLineSelection.selectionCount > 0 :
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


# Create a simplified HTD style profile.
def createToothProfile( sketch: adsk.fusion.Sketch, belt_geom: TimingBeltGeom ):
    geoConstraints = sketch.geometricConstraints
    sketchCurves = sketch.sketchCurves
    sketchDims = sketch.sketchDimensions

    # Create the tooth profile at the origin then it get moved to the pitch line

    # Create the base line for the profile
    baseLineLength = (belt_geom.toothBumpRadius + belt_geom.filletRadius) * 2
    originPt = adsk.core.Point3D.create( 0, 0, 0)
    baseLine = sketchCurves.sketchLines.addByTwoPoints( 
        originPt, adsk.core.Point3D.create( baseLineLength/10, 0, 0) )
    
    # Create the construction line for the center of the first root fillet
    startpt = baseLine.startSketchPoint
    endpt = adsk.core.Point3D.create( 0, belt_geom.filletRadius/10, 0)
    firstFilletConst = sketchCurves.sketchLines.addByTwoPoints( startpt, endpt )
    firstFilletConst.isConstruction = True
    geoConstraints.addPerpendicular( firstFilletConst, baseLine )
    textPoint = adsk.core.Point3D.create(-0.01, 0.02, 0)
    linearDim = sketchDims.addDistanceDimension(firstFilletConst.startSketchPoint, firstFilletConst.endSketchPoint, 
                                                       adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                       textPoint )
    linearDim.value = belt_geom.filletRadius/10

    # Create the construction line for the center of the second root fillet
    startpt = baseLine.endSketchPoint
    endpt = futil.offsetPoint3D( baseLine.endSketchPoint.geometry, 0, belt_geom.filletRadius/10, 0)
    secondFilletConst = sketchCurves.sketchLines.addByTwoPoints( startpt, endpt )
    secondFilletConst.isConstruction = True
    geoConstraints.addPerpendicular( secondFilletConst, baseLine )
    textPoint = adsk.core.Point3D.create( baseLineLength/10 + 0.05, 0.02, 0)
    linearDim = sketchDims.addDistanceDimension(secondFilletConst.startSketchPoint, secondFilletConst.endSketchPoint, 
                                                       adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                       textPoint )
    linearDim.value = belt_geom.filletRadius/10

    # Create the construction line for the center of the main tooth bump
    toothBumpOffset = ( belt_geom.toothHeight - belt_geom.toothBumpRadius ) / 10
    toothline = sketchCurves.sketchLines.addByTwoPoints( 
        adsk.core.Point3D.create( baseLineLength/20, 0, 0), 
        adsk.core.Point3D.create( baseLineLength/20, toothBumpOffset, 0) )
    toothline.isConstruction = True
    geoConstraints.addPerpendicular( toothline, baseLine )
    geoConstraints.addMidPoint( toothline.startSketchPoint, baseLine )
    textPoint = adsk.core.Point3D.create( baseLineLength/20, toothBumpOffset, 0)
    textPoint.translateBy( adsk.core.Vector3D.create( -0.02, 0, 0) )
    linearDim = sketchDims.addDistanceDimension(toothline.startSketchPoint, toothline.endSketchPoint, 
                                                       adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                       textPoint )
    linearDim.value = toothBumpOffset

    firstFillet = sketchCurves.sketchArcs.addByCenterStartSweep( 
        firstFilletConst.endSketchPoint, baseLine.startSketchPoint, 1.57 )
        # firstFilletConst.endSketchPoint, baseLine.startSketchPoint, belt_geom.filletSweepAngle )
    # geoConstraints.addTangent( firstFillet, baseLine )
    geoConstraints.addCoincident( firstFillet.centerSketchPoint, firstFilletConst.endSketchPoint )

    secondFillet = sketchCurves.sketchArcs.addByCenterStartSweep( 
        secondFilletConst.endSketchPoint, baseLine.endSketchPoint, -1.57 )
        # secondFilletConst.endSketchPoint, baseLine.endSketchPoint, -belt_geom.filletSweepAngle )
    geoConstraints.addCoincident( secondFillet.centerSketchPoint, secondFilletConst.endSketchPoint )
    # geoConstraints.addCoincident( secondFillet.startSketchPoint, toothBump.endSketchPoint )
    # geoConstraints.addCoincident( secondFillet.endSketchPoint, baseLine.endSketchPoint )

    toothBump = sketchCurves.sketchArcs.addByCenterStartEnd( 
        toothline.endSketchPoint, secondFillet.startSketchPoint, firstFillet.endSketchPoint )
    geoConstraints.addCoincident(toothBump.centerSketchPoint, toothline.endSketchPoint )
    textPoint = toothline.startSketchPoint.geometry.copy()
    textPoint.translateBy( adsk.core.Vector3D.create( -.05, .05, 0) )
    cirDim = sketchDims.addRadialDimension( toothBump, textPoint )
    cirDim.value = belt_geom.toothBumpRadius/10

    geoConstraints.addTangent( firstFillet, toothBump )

    return baseLine



def createPitchLoop( sketch: adsk.fusion.Sketch, ccLine: CCLine.CCLine, isLinked:bool = False ) -> adsk.core.ObjectCollection :

    geoConstraints = sketch.geometricConstraints

    # Project the pitch circles into the sketch
    circle1, circle2 = sketch.project2( [ccLine.pitchCircle1, ccLine.pitchCircle2], isLinked )
    circle1.isConstruction = True
    circle2.isConstruction = True

    # Create pitch line curves from two circles
    CLstartPt = futil.toPoint2D( circle1.centerSketchPoint.geometry )
    CLendPt = futil.toPoint2D( circle2.centerSketchPoint.geometry )
    CLnormal = futil.lineNormal( CLstartPt, CLendPt )

    T1startPt = futil.addPoint2D( CLstartPt, futil.multVector2D( CLnormal, circle1.radius ) )
    T1endPt = futil.addPoint2D( CLendPt, futil.multVector2D( CLnormal, circle2.radius ) )
    tangentLine1 = sketch.sketchCurves.sketchLines.addByTwoPoints( futil.toPoint3D(T1startPt), futil.toPoint3D(T1endPt) )
    tangentLine1.isConstruction = True
    geoConstraints.addCoincident( tangentLine1.startSketchPoint, circle1 )
    geoConstraints.addCoincident( tangentLine1.endSketchPoint, circle2 )
    geoConstraints.addTangent( tangentLine1, circle1 )
    geoConstraints.addTangent( tangentLine1, circle2 )

    T2startPt = futil.addPoint2D( CLstartPt, futil.multVector2D( CLnormal, -circle1.radius ) )
    T2endPt = futil.addPoint2D( CLendPt, futil.multVector2D( CLnormal, -circle2.radius ) )
    tangentLine2 = sketch.sketchCurves.sketchLines.addByTwoPoints( futil.toPoint3D(T2startPt), futil.toPoint3D(T2endPt) )
    tangentLine2.isConstruction = True
    geoConstraints.addCoincident( tangentLine2.startSketchPoint, circle1 )
    geoConstraints.addCoincident( tangentLine2.endSketchPoint, circle2 )
    geoConstraints.addTangent( tangentLine2, circle1 )
    geoConstraints.addTangent( tangentLine2, circle2 )

    arc1 = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( 
        circle1.centerSketchPoint, tangentLine1.startSketchPoint, tangentLine2.startSketchPoint )
    arc1.isConstruction = True
#    geoConstraints.addConcentric( arc1, circle1 )
    try :
        geoConstraints.addTangent( arc1, tangentLine1 )
    except:
        None

    arc2 = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( 
        circle2.centerSketchPoint, tangentLine2.endSketchPoint, tangentLine1.endSketchPoint )
    arc2.isConstruction = True
#    geoConstraints.addConcentric( arc2, circle2 )
    try:
        geoConstraints.addTangent( arc2, tangentLine2 )
    except:
        None

    connectedCurves = sketch.findConnectedCurves( tangentLine1 )
    # curves = []
    # for curve in connectedCurves:
    #     curves.append( curve )

    return connectedCurves


# Find the anchor line and endpoint on that line to use for the tooth starting point
def findToothAnchor( insideLoop: adsk.fusion.ProfileLoop ) :

    # Determine the centroid of the profile loop
    bbox = insideLoop.profileCurves.item(0).sketchEntity.boundingBox
    i = 0
    while i < insideLoop.profileCurves.count:
        curve = insideLoop.profileCurves.item(i).sketchEntity
        bbox.combine( curve.boundingBox )
        i += 1

    centroid = futil.BBCentroid( bbox )
 
    lineCurve: adsk.fusion.SketchLine = None
    lineNormal = adsk.core.Vector2D.create()
    toothAnchorPoint = adsk.fusion.SketchPoint = None
    i = 0
    while i < insideLoop.profileCurves.count:
        curve = insideLoop.profileCurves.item(i).sketchEntity
        futil.print_SketchCurve( curve )
        if curve.objectType == adsk.fusion.SketchLine.classType():
            curve: adsk.fusion.SketchLine = curve
            insideNormal = futil.sketchLineNormal( curve, centroid )
            if futil.toTheRightOf( futil.toLine2D( curve.geometry), centroid ) :
                lineCurve = curve
                lineNormal = insideNormal
                toothAnchorPoint = lineCurve.endSketchPoint
            else:
                lineCurve = curve
                lineNormal = insideNormal
                toothAnchorPoint = lineCurve.startSketchPoint

            futil.log(f'    Using Line with Normal=({insideNormal.x:.3},{insideNormal.y:.3})...')
            futil.log(f'     toothAnchor =  ({toothAnchorPoint.geometry.x:.3},{toothAnchorPoint.geometry.y:.3}).')
            break
        i += 1

    return (lineCurve, lineNormal, toothAnchorPoint)


def get_belt_geometry( motion: int ) -> TimingBeltGeom:

    return belt_geometry[ motion - 1 ]

    # if motion == 1:
    #     # HTD 5mm
    #     return belt_geometry[0]
    #     # beltPitchLength = 5
    #     # beltThickness = 0.174
    # elif motion == 2:
    #     # GT2 3mm
    #     reutrn belt_geometry[1]
    # else:
    #     # RT25
    #     return belt_geometry[2]
    #     # beltPitchLength = 3
    #     # beltThickness = 0.126

def get_component_name( motion: int, toothCount: int, widthMM: float ) -> str:

    if motion == 1:
        comp_name = f"Belt HTD_5mm-{toothCount}Tx{int(widthMM)}mm"
    elif motion == 2:
        comp_name = f"Belt GT2_3mm-{toothCount}Tx{int(widthMM)}mm"
    elif motion == 3:
        comp_name = "Belt RT25-{}Tx{:.3f}in".format( toothCount, widthMM / 25.4 )
    elif motion == 4:
        comp_name = f"Chain #25H {toothCount} Links"
    elif motion == 5:
        comp_name = f"Chain #35 {toothCount} Links"
    else:
        comp_name = f'Unknown Motion Type {motion}'

    return comp_name