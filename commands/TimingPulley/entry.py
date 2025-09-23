import adsk.core
import adsk.fusion
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_TimingPulleyDialog'
CMD_NAME = 'Timing Pulley'
CMD_Description = 'Create a Timing Belt Pulley'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


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
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.

    # Create a Build plane selection input.
    planeSelection = inputs.addSelectionInput('build_plane', 'Sketch Plane', 'Select the sketch plane for Pulley')
    planeSelection.addSelectionFilter( "ConstructionPlanes" )
    planeSelection.addSelectionFilter( "PlanarFaces" )
    planeSelection.setSelectionLimits( 1, 1 )

    # Create a simple text box input.
    belt_type = inputs.addDropDownCommandInput('belt_type', 'Timing Belt Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    belt_type.listItems.add('HTD 5mm Pitch', True, '')
    belt_type.listItems.add('GT2 3mm Pitch', False, '')

    # Create a value input field for the number of teeth.
    defaultLengthUnits = ""
    default_value = adsk.core.ValueInput.createByString('18')
    inputs.addValueInput('tooth_count', 'Tooth Count', defaultLengthUnits, default_value)

    # Create a value input field for the belt width.
    defaultLengthUnits = "mm"
    default_value = adsk.core.ValueInput.createByString('11')
    inputs.addValueInput('belt_width', 'Belt Width', defaultLengthUnits, default_value)

    # TODO Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    # Turn on the origin planes
    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent
    rootComp.isOriginFolderLightBulbOn = True


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    planeSelection: adsk.core.SelectionCommandInput = inputs.itemById('build_plane')
    beltType: adsk.core.DropDownCommandInput = inputs.itemById('belt_type')
    toothCount: adsk.core.ValueCommandInput = inputs.itemById('tooth_count')
    beltWidth: adsk.core.ValueCommandInput = inputs.itemById('belt_width')

    futil.print_Selection( planeSelection )

    sketchPlane = planeSelection.selection(0).entity

   # Create a new component to put the sketches and geometry into
    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent
    trans = adsk.core.Matrix3D.create()
    workingOcc = rootComp.occurrences.addNewComponent( trans )
    workingComp = workingOcc.component
    # Create a new sketch for the belt
    sketch = workingComp.sketches.add( sketchPlane, workingOcc )


    if beltType.selectedItem.index == 0 :
        workingComp.name = f"Pulley_HTD_5mm-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
        beltPitch = 5
        createHTDPulleyGeometry( sketch, beltPitch, toothCount.value )
    else:
        workingComp.name = f"Pulley_GT2_3mm-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
        beltPitch = 3
        createGT2PulleyGeometry( sketch, beltPitch, toothCount.value )

    # Extrude the pulley sketch 
    if sketch.profiles.count != 1 :
        futil.popup_error(f'Sketch does not have one profile, returned {sketch.profiles.count}.')
        return
    
    extrudes = workingComp.features.extrudeFeatures
    beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth.value )
    extrudes.addSimple(sketch.profiles.item(0), beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs

    command_execute( args )
    args.isValidResult = True

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    inputs = args.inputs

    toothCount: adsk.core.ValueCommandInput = inputs.itemById('tooth_count')
    beltWidth: adsk.core.ValueCommandInput = inputs.itemById('belt_width')
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.

    if beltWidth.value >= 0 and toothCount.value >= 8 :
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []

    # Turn off the origin planes
    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent
    rootComp.isOriginFolderLightBulbOn = False


def createHTDPulleyGeometry( sketch: adsk.fusion.Sketch, beltPitchMM: float, toothCount: int ) :
    geoConstraints = sketch.geometricConstraints

    beltThickness = 1.74
    topRadius = 0.43
    rootRadius = 1.49
    rootHeight = 2.06
    rootWidth = 3.05

    # Create a single tooth of the pulley
    pitch_diameter = toothCount * beltPitchMM / math.pi
    outer_diameter = pitch_diameter - beltThickness

    # Create outer diameter circle
    centerPt = adsk.core.Point3D.create()
    outerCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, outer_diameter )
    outerCircle.isConstruction = True
    geoConstraints.addCoincident( outerCircle.centerSketchPoint, sketch.originPoint )

    textPoint = adsk.core.Point3D.create( -outer_diameter / 40, 0, 0 )
    diameter = sketch.sketchDimensions.addDiameterDimension( outerCircle, textPoint )
    diameter.value = outer_diameter / 10 # in cm

    # Create Vertical line from center to outerCircle
    endPt = adsk.core.Point3D.create( 0, outer_diameter/20, 0 )
    vertLine = sketch.sketchCurves.sketchLines.addByTwoPoints( outerCircle.centerSketchPoint, endPt )
    vertLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( vertLine.endSketchPoint, outerCircle )
    geoConstraints.addVertical( vertLine )

    # Create Pie line from center to outerCircle
    endPt = adsk.core.Point3D.create( outer_diameter/20, 0, 0 )
    pieLine = sketch.sketchCurves.sketchLines.addByTwoPoints( outerCircle.centerSketchPoint, endPt )
    pieLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( pieLine.endSketchPoint, outerCircle )
    textPoint = adsk.core.Point3D.create( outer_diameter / 40, outer_diameter / 40, 0 )
    angleDim = sketch.sketchDimensions.addAngularDimension( vertLine, pieLine, textPoint )
    angleDim.value = math.pi / toothCount # in radians

    # Create the tooth top arc
    topArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        outerCircle.centerSketchPoint, vertLine.endSketchPoint, -math.pi / toothCount / 4 )
    # geoConstraints.addCoincident( topArc.startSketchPoint, outerCircle )
    geoConstraints.addConcentric( topArc, outerCircle )

    # Create the tooth top arc mirror
    topArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        outerCircle.centerSketchPoint, vertLine.endSketchPoint, math.pi / toothCount / 4 )
    geoConstraints.addConcentric( topArcMirror, outerCircle )
    geoConstraints.addSymmetry( topArc.startSketchPoint, topArcMirror.endSketchPoint, vertLine )

    # Create the tooth top radius
    centerPt = futil.offsetPoint3D( topArc.startSketchPoint.geometry, 0, -topRadius/10, 0 )
    topRadiusArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArc.startSketchPoint, -math.pi / 4 )
    geoConstraints.addTangent( topArc, topRadiusArc )
    textPoint = centerPt
    radius = sketch.sketchDimensions.addRadialDimension( topRadiusArc, textPoint )
    radius.value = topRadius / 10 # in cm

    # Create the tooth top radius mirror
    centerPt = futil.offsetPoint3D( topArcMirror.endSketchPoint.geometry, 0, -topRadius/10, 0 )
    topRadiusArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArcMirror.endSketchPoint, math.pi / 4 )
    geoConstraints.addTangent( topArcMirror, topRadiusArcMirror )
    geoConstraints.addSymmetry( topRadiusArc.startSketchPoint, topRadiusArcMirror.endSketchPoint, vertLine )
    
    # Create the linear segment
    endPt = futil.offsetPoint3D( topRadiusArc.startSketchPoint.geometry, topRadius/20, -topRadius/20, 0 )
    toothLine = sketch.sketchCurves.sketchLines.addByTwoPoints( 
        topRadiusArc.startSketchPoint, endPt )
    geoConstraints.addTangent( toothLine, topRadiusArc )
    textPoint = futil.offsetPoint3D( toothLine.startSketchPoint.geometry, rootWidth / 40, 0, 0 )
    dist = sketch.sketchDimensions.addOffsetDimension( 
        pieLine, toothLine.startSketchPoint, textPoint )
    dist.value = rootWidth / 20 # in cm

    # Create the linear segment mirror
    endPt = futil.offsetPoint3D( topRadiusArcMirror.startSketchPoint.geometry, -topRadius/20, -topRadius/20, 0 )
    toothLineMirror = sketch.sketchCurves.sketchLines.addByTwoPoints( 
        topRadiusArcMirror.endSketchPoint, endPt )
    geoConstraints.addTangent( toothLineMirror, topRadiusArcMirror )
    geoConstraints.addSymmetry( toothLineMirror.endSketchPoint, toothLine.endSketchPoint, vertLine )

    # Create the root arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -topRadius/10, -topRadius/10, 0 )
    rootArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        pieLine.endSketchPoint, toothLine.endSketchPoint, math.pi / 4 )
    geoConstraints.addTangent( rootArc, toothLine )
    textPoint = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -0.05, -0.05, 0 )
    radius = sketch.sketchDimensions.addRadialDimension( rootArc, textPoint )
    radius.value = rootRadius / 10 # in cm
    geoConstraints.addCoincident( rootArc.endSketchPoint, pieLine )
    geoConstraints.addCoincident( rootArc.centerSketchPoint, pieLine )

    textPoint = adsk.core.Point3D.create( outer_diameter / 40, outer_diameter / 40, 0 )
    rootDist = sketch.sketchDimensions.addDistanceDimension( 
        outerCircle.centerSketchPoint, rootArc.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        textPoint )
    rootDist.value = ( outer_diameter / 2 - rootHeight ) / 10 # in cm

    # Create the root arc mirror
    centerPt = rootArc.centerSketchPoint.geometry
    centerPt.x = centerPt.x * -1.0
    rootArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, toothLineMirror.endSketchPoint, -math.pi / 4 )
    geoConstraints.addTangent( toothLineMirror, rootArcMirror )
    geoConstraints.addSymmetry( rootArcMirror.startSketchPoint, rootArc.endSketchPoint, vertLine )

    # Create the circular pattern of the tooth profile
    toothEntities = [ rootArcMirror, toothLineMirror, topRadiusArcMirror, topArcMirror, topArc, topRadiusArc, toothLine, rootArc ]
    circularPattern = geoConstraints.createCircularPatternInput( toothEntities, outerCircle.centerSketchPoint )
    circularPattern.quantity = adsk.core.ValueInput.createByReal( toothCount )
    geoConstraints.addCircularPattern( circularPattern )


def createGT2PulleyGeometry( sketch: adsk.fusion.Sketch, beltPitchMM: float, toothCount: int ) :
    geoConstraints = sketch.geometricConstraints

    # beltThickness = 1.26
    pitchLineOffset = 0.381
    topRadius = 0.25
    rootRadius = 0.85
    rootHeight = 1.14
    transitionRadius = 1.52
    transitionOffset = 0.61

    # Create a single tooth of the pulley
    pitch_diameter = toothCount * beltPitchMM / math.pi
    outer_diameter = pitch_diameter - 2 * pitchLineOffset

    # Create outer diameter circle
    centerPt = adsk.core.Point3D.create()
    outerCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, outer_diameter )
    outerCircle.isConstruction = True
    geoConstraints.addCoincident( outerCircle.centerSketchPoint, sketch.originPoint )

    textPoint = adsk.core.Point3D.create( -outer_diameter / 40, 0, 0 )
    diameter = sketch.sketchDimensions.addDiameterDimension( outerCircle, textPoint )
    diameter.value = outer_diameter / 10 # in cm

    # Create Vertical line from center to outerCircle
    endPt = adsk.core.Point3D.create( 0, outer_diameter/20, 0 )
    vertLine = sketch.sketchCurves.sketchLines.addByTwoPoints( outerCircle.centerSketchPoint, endPt )
    vertLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( vertLine.endSketchPoint, outerCircle )
    geoConstraints.addVertical( vertLine )

    # Create Pie line from center to outerCircle
    endPt = adsk.core.Point3D.create( outer_diameter/20, 0, 0 )
    pieLine = sketch.sketchCurves.sketchLines.addByTwoPoints( outerCircle.centerSketchPoint, endPt )
    pieLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( pieLine.endSketchPoint, outerCircle )
    textPoint = adsk.core.Point3D.create( outer_diameter / 40, outer_diameter / 40, 0 )
    angleDim = sketch.sketchDimensions.addAngularDimension( vertLine, pieLine, textPoint )
    angleDim.value = math.pi / toothCount # in radians

    # Create the tooth top arc
    topArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        outerCircle.centerSketchPoint, vertLine.endSketchPoint, -math.pi / toothCount / 4 )
    # geoConstraints.addCoincident( topArc.startSketchPoint, outerCircle )
    geoConstraints.addConcentric( topArc, outerCircle )

    # Create the tooth top arc mirror
    topArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        outerCircle.centerSketchPoint, vertLine.endSketchPoint, math.pi / toothCount / 4 )
    geoConstraints.addConcentric( topArcMirror, outerCircle )
    geoConstraints.addSymmetry( topArc.startSketchPoint, topArcMirror.endSketchPoint, vertLine )

    # Create the tooth top radius
    centerPt = futil.offsetPoint3D( topArc.startSketchPoint.geometry, 0, -topRadius/10, 0 )
    topRadiusArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArc.startSketchPoint, -math.pi / 2 )
    geoConstraints.addTangent( topArc, topRadiusArc )
    textPoint = centerPt
    radius = sketch.sketchDimensions.addRadialDimension( topRadiusArc, textPoint )
    radius.value = topRadius / 10 # in cm

    # Create the tooth top radius mirror
    centerPt = futil.offsetPoint3D( topArcMirror.endSketchPoint.geometry, 0, -topRadius/10, 0 )
    topRadiusArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArcMirror.endSketchPoint, math.pi / 2 )
    geoConstraints.addTangent( topArcMirror, topRadiusArcMirror )
    geoConstraints.addSymmetry( topRadiusArc.startSketchPoint, topRadiusArcMirror.endSketchPoint, vertLine )
    
    # Create the transistion arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, transitionOffset / 10, -transitionOffset/100, 0 )
    endPt = futil.offsetPoint3D( topRadiusArc.startSketchPoint.geometry, topRadius/20, -topRadius/10, 0 )
    transistionArc = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( 
        centerPt, topRadiusArc.startSketchPoint, endPt )
    geoConstraints.addTangent( transistionArc, topRadiusArc )
    textPoint = futil.midPoint3D( centerPt, transistionArc.startSketchPoint.geometry )
    radius = sketch.sketchDimensions.addRadialDimension( transistionArc, textPoint )
    radius.value = transitionRadius / 10 # in cm
    textPoint = futil.midPoint3D( centerPt, transistionArc.endSketchPoint.geometry )
    dist = sketch.sketchDimensions.addOffsetDimension( 
        pieLine, transistionArc.centerSketchPoint, textPoint )
    dist.value = transitionOffset / 10 # in cm

    # Create the transistion arc mirror
    centerPt = transistionArc.centerSketchPoint.geometry
    centerPt.x = centerPt.x * -1.0
    endPt = transistionArc.endSketchPoint.geometry
    endPt.x = endPt.x * -1.0
    transistionArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( 
        centerPt, endPt, topRadiusArcMirror.endSketchPoint )
    geoConstraints.addTangent( transistionArcMirror, topRadiusArcMirror )
    geoConstraints.addSymmetry( transistionArc.endSketchPoint, transistionArcMirror.startSketchPoint, vertLine )

    # Create the root arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -topRadius/10, -topRadius/10, 0 )
    rootArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        pieLine.endSketchPoint, transistionArc.endSketchPoint, math.pi / 4 )
    geoConstraints.addTangent( rootArc, transistionArc )
    textPoint = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -0.05, -0.05, 0 )
    radius = sketch.sketchDimensions.addRadialDimension( rootArc, textPoint )
    radius.value = rootRadius / 10 # in cm
    geoConstraints.addCoincident( rootArc.endSketchPoint, pieLine )
    geoConstraints.addCoincident( rootArc.centerSketchPoint, pieLine )

    textPoint = adsk.core.Point3D.create( outer_diameter / 40, outer_diameter / 40, 0 )
    rootDist = sketch.sketchDimensions.addDistanceDimension( 
        outerCircle.centerSketchPoint, rootArc.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        textPoint )
    rootDist.value = ( outer_diameter / 2 - rootHeight ) / 10 # in cm

    # Create the root arc mirror
    centerPt = rootArc.centerSketchPoint.geometry
    centerPt.x = centerPt.x * -1.0
    rootArcMirror = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, transistionArcMirror.startSketchPoint, -math.pi / 4 )
    geoConstraints.addSymmetry( rootArcMirror.centerSketchPoint, rootArc.centerSketchPoint, vertLine )
    geoConstraints.addSymmetry( rootArcMirror.startSketchPoint, rootArc.endSketchPoint, vertLine )

    # Create the circular pattern of the tooth profile
    toothEntities = [ rootArcMirror, transistionArcMirror, topRadiusArcMirror, topArcMirror, topArc, topRadiusArc, transistionArc, rootArc ]
    circularPattern = geoConstraints.createCircularPatternInput( toothEntities, outerCircle.centerSketchPoint )
    circularPattern.quantity = adsk.core.ValueInput.createByReal( toothCount )
    geoConstraints.addCircularPattern( circularPattern )
