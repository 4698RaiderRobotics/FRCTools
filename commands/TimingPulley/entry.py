import adsk.core
import adsk.fusion
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config

from ..TimingBelt.geometry import *

app = adsk.core.Application.get()
ui = app.userInterface


# *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_TimingPulleyDialog'
CMD_NAME = 'Create Pulley/Belt'
CMD_Description = 'Create a Circular Timing Belt or Pulley'

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
    belt_type = inputs.addDropDownCommandInput('belt_type', 'Belt/Pulley Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    belt_type.listItems.add('HTD-5M Pulley', True, '')
    belt_type.listItems.add('GT2-3M Pulley', False, '')
    belt_type.listItems.add('HTD-5M Circluar Belt', False, '')
    belt_type.listItems.add('GT2-3M Circluar Belt', False, '')

    # Create a value input field for the number of teeth.
    defaultLengthUnits = ""
    default_value = adsk.core.ValueInput.createByString('18')
    inputs.addValueInput('tooth_count', 'Tooth Count', defaultLengthUnits, default_value)

    # Create a value input field for the belt width.
    defaultLengthUnits = "mm"
    default_value = adsk.core.ValueInput.createByString('11')
    inputs.addValueInput('belt_width', 'Belt Width', defaultLengthUnits, default_value)

    use_root = inputs.addBoolValueInput( "use_root", "Use Root Component", True )

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

    # Disable 'use_root' if a Part Design
    if design.designIntent == adsk.fusion.DesignIntentTypes.PartDesignIntentType:
        use_root.value = True
        use_root.isEnabled = False


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
    UseRoot: adsk.core.BoolValueCommandInput = inputs.itemById( "use_root" )

    sketchPlane = planeSelection.selection(0).entity

    try:

        # Create a new component to put the sketches and geometry into
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent
        workingComp = rootComp
        workingOcc = design.activeOccurrence
        if design.designIntent == adsk.fusion.DesignIntentTypes.HybridDesignIntentType and not UseRoot.value:
            workingOcc = rootComp.occurrences.addNewComponent( adsk.core.Matrix3D.create() )
            workingComp = workingOcc.component
        elif design.designIntent == adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType:
            raise Exception("Timing Pulleys Cannot be created in an Assembly Design.")

        # Create a new sketch for the pulley
        sketch = workingComp.sketches.add( sketchPlane, workingOcc )


        if beltType.selectedItem.index == 0 :
            if workingComp != rootComp :
                workingComp.name = f"Pulley_HTD-5M-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
            createHTDPulleyGeometry( sketch, toothCount.value )
            toothExtrude, axisEdge = extrudePulley( workingComp, sketch, beltWidth.value )
        elif beltType.selectedItem.index == 1 :
            if workingComp != rootComp :
                workingComp.name = f"Pulley_GT2-3M-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
            createGT2PulleyGeometry( sketch, toothCount.value )
            toothExtrude, axisEdge = extrudePulley( workingComp, sketch, beltWidth.value )
        elif beltType.selectedItem.index == 2 :
            if workingComp != rootComp :
                workingComp.name = f"Belt_HTD-5M-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
            createHTDPulleyGeometry( sketch, toothCount.value )
            addOuterBeltCircle( sketch, belt_geometry[0] )
            toothExtrude, axisEdge = extrudeBelt( workingComp, sketch, beltWidth.value )
        else:
            if workingComp != rootComp :
                workingComp.name = f"Belt_GT2-3M-{toothCount.value}Tx{int(beltWidth.value*10)}mm"
            createGT2PulleyGeometry( sketch, toothCount.value )
            addOuterBeltCircle( sketch, belt_geometry[1] )
            toothExtrude, axisEdge = extrudeBelt( workingComp, sketch, beltWidth.value )

        # # Extrude the pulley sketch 
        # if sketch.profiles.count != 2 :
        #     futil.popup_error(f'Sketch does not have 2 profiles, has {sketch.profiles.count} profiles.')
        #     return

        # plug_prof = sketch.profiles.item(0)
        # tooth_prof = sketch.profiles.item(1)
        # if plug_prof.face.area < tooth_prof.face.area :
        #     plug_prof = sketch.profiles.item(1)
        #     tooth_prof = sketch.profiles.item(0)

        # extrudes = workingComp.features.extrudeFeatures
        # beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth.value )
        # profiles = adsk.core.ObjectCollection.createWithArray( [plug_prof, tooth_prof] )
        # cylExtrude = extrudes.addSimple(profiles, beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

        # cutTooth = extrudes.addSimple(tooth_prof, beltWidthValue, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # # Find the axis of the circular pattern
        # pitch_circle = None
        # cyl_edge = None
        # for edge in cylExtrude.bodies.item(0).edges:
        #     if edge.geometry.classType() == adsk.core.Arc3D.classType() :
        #         arc: adsk.core.Arc3D = edge.geometry
        #         if not pitch_circle:
        #             pitch_circle = arc
        #             cyl_edge = edge
        #         else:
        #             if arc.radius > pitch_circle.radius:
        #                 pitch_circle = arc
        #                 cyl_edge = edge


        # Pattern the tooth Feature around the pulley
        patObj = adsk.core.ObjectCollection.createWithArray( [ toothExtrude ] )
        circPat = workingComp.features.circularPatternFeatures.createInput( patObj, axisEdge )
        circPat.quantity = adsk.core.ValueInput.createByString( 'n' )
        circPat.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        workingComp.features.circularPatternFeatures.add( circPat )

    except:
        futil.handle_error( '        ============  Timing Pulley Extrude Failed  ============\n\n', True )

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

def createParameters( geom: TimingBeltGeom, toothCount: int ) :
    design: adsk.fusion.Design = app.activeProduct

    parameters = design.userParameters

    teethVI = adsk.core.ValueInput.createByReal( toothCount )
    parameters.add( 'n', teethVI, '', 'Number Of Teeth' )

    widthVI = adsk.core.ValueInput.createByReal( geom.width / 10 )
    parameters.add( 'width', widthVI, 'mm', 'Belt Width' )

    pitchVI = adsk.core.ValueInput.createByReal( geom.pitchLength / 10 )
    parameters.add( 'p', pitchVI, 'mm', 'Belt Pitch' )

    pitchDiaVI = adsk.core.ValueInput.createByString( 'n * p / 3.14159' ) # in CM
    pd_param = parameters.add( 'PD', pitchDiaVI, 'mm', 'Pitch Diameter' )

def createHTDPulleyGeometry( sketch: adsk.fusion.Sketch, toothCount: int ) :
    geoConstraints = sketch.geometricConstraints

    # Only setup for HTD-5M belts
    geom = belt_geometry[0]

    createParameters( geom, toothCount )

    # Create a single tooth of the pulley
    pitch_diameter = toothCount * geom.pitchLength / math.pi

    # Create pitch diameter circle
    centerPt = adsk.core.Point3D.create()
    pitchCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, pitch_diameter/2 )
    geoConstraints.addCoincident( pitchCircle.centerSketchPoint, sketch.originPoint )

    textPoint = adsk.core.Point3D.create( pitch_diameter / 40, pitch_diameter / 40, 0 )
    diameter = sketch.sketchDimensions.addDiameterDimension( pitchCircle, textPoint )

    # get ModelParameter
    modelPrm: adsk.fusion.ModelParameter = diameter.parameter
    modelPrm.expression = 'PD'

    # Create Vertical line from center to outerCircle
    endPt = adsk.core.Point3D.create( 0, pitch_diameter/20, 0 )
    vertLine = sketch.sketchCurves.sketchLines.addByTwoPoints( pitchCircle.centerSketchPoint, endPt )
    vertLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( vertLine.endSketchPoint, pitchCircle )
    geoConstraints.addVertical( vertLine )

    # Create Pie line from center to outerCircle
    endPt = adsk.core.Point3D.create( pitch_diameter/20, 0, 0 )
    pieLine = sketch.sketchCurves.sketchLines.addByTwoPoints( pitchCircle.centerSketchPoint, endPt )
    pieLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( pieLine.endSketchPoint, pitchCircle )
    textPoint = adsk.core.Point3D.create( geom.toothBumpRadius / 10, pitch_diameter / 30, 0 )
    angleDim = sketch.sketchDimensions.addAngularDimension( vertLine, pieLine, textPoint )
    # angleDim.value = math.pi / toothCount # in radians

    # get ModelParameter
    modelPrm = angleDim.parameter
    modelPrm.expression = '180 / n'

    # Create the line from the Pitch Line down PLD distance
    endPt = vertLine.endSketchPoint.geometry.copy()
    endPt.translateBy( adsk.core.Vector3D.create(0,-geom.pitchLineDepth/10,0) )
    beltLine = sketch.sketchCurves.sketchLines.addByTwoPoints( vertLine.endSketchPoint, endPt )
    geoConstraints.addCoincident( beltLine.endSketchPoint, vertLine )
    textPoint = futil.offsetPoint3D( beltLine.startSketchPoint.geometry, -0.005, -0.0250, 0 )
    dist = sketch.sketchDimensions.addDistanceDimension( 
        beltLine.startSketchPoint, beltLine.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPoint 
    )
    dist.value = geom.pitchLineDepth / 10 # in cm

    # Create the tooth top arc
    topArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        pitchCircle.centerSketchPoint, beltLine.endSketchPoint, -math.pi / toothCount / 4 )
    # geoConstraints.addCoincident( topArc.startSketchPoint, outerCircle )
    geoConstraints.addConcentric( topArc, pitchCircle )

    # Create the tooth top radius
    centerPt = futil.offsetPoint3D( topArc.startSketchPoint.geometry, 0, -geom.filletRadius/10, 0 )
    topRadiusArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArc.startSketchPoint, -math.pi / 4 )
    geoConstraints.addTangent( topArc, topRadiusArc )
    textPoint = centerPt
    radius = sketch.sketchDimensions.addRadialDimension( topRadiusArc, textPoint )
    radius.value = geom.filletRadius / 10 # in cm
    
    # Create the linear segment
    endPt = futil.offsetPoint3D( topRadiusArc.startSketchPoint.geometry, geom.filletRadius/20, -geom.filletRadius/20, 0 )
    toothLine = sketch.sketchCurves.sketchLines.addByTwoPoints( 
        topRadiusArc.startSketchPoint, endPt )
    geoConstraints.addTangent( toothLine, topRadiusArc )
    textPoint = futil.offsetPoint3D( toothLine.startSketchPoint.geometry, geom.transitionDim / 40, 0, 0 )
    dist = sketch.sketchDimensions.addOffsetDimension( 
        pieLine, toothLine.startSketchPoint, textPoint )
    dist.value = geom.transitionDim / 20 # in cm

    # Create the root arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -geom.filletRadius/10, -geom.filletRadius/10, 0 )
    rootArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        pieLine.endSketchPoint, toothLine.endSketchPoint, math.pi / 4 )
    geoConstraints.addTangent( rootArc, toothLine )
    textPoint = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -0.05, -0.05, 0 )
    radius = sketch.sketchDimensions.addRadialDimension( rootArc, textPoint )
    radius.value = geom.toothBumpRadius / 10 # in cm
    geoConstraints.addCoincident( rootArc.endSketchPoint, pieLine )
    geoConstraints.addCoincident( rootArc.centerSketchPoint, pieLine )

    textPoint = pieLine.endSketchPoint.geometry.copy()
    textPoint.translateBy( adsk.core.Vector3D.create(geom.pitchLineDepth/10,-geom.pitchLineDepth/10,0) )
    rootDist = sketch.sketchDimensions.addDistanceDimension( 
        pieLine.endSketchPoint, rootArc.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        textPoint )
    rootDist.value = ( geom.toothHeight + geom.pitchLineDepth ) / 10 # in cm

    # Mirror the half tooth about the pie line
    MirrorEntities = [ beltLine, topArc, topRadiusArc, toothLine, rootArc ]
    sketch.mirror( MirrorEntities, pieLine )

def createGT2PulleyGeometry( sketch: adsk.fusion.Sketch, toothCount: int ) :
    geoConstraints = sketch.geometricConstraints

    # Only setup for GT2-3M belts
    geom = belt_geometry[1]

    createParameters( geom, toothCount )

    # Create a single tooth of the pulley
    pitch_diameter = toothCount * geom.pitchLength / math.pi

    # Create pitch diameter circle
    centerPt = adsk.core.Point3D.create()
    pitchCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, pitch_diameter/2 )
    geoConstraints.addCoincident( pitchCircle.centerSketchPoint, sketch.originPoint )

    textPoint = adsk.core.Point3D.create( -pitch_diameter / 40, -pitch_diameter / 40, 0 )
    diameter = sketch.sketchDimensions.addDiameterDimension( pitchCircle, textPoint )

    # get ModelParameter
    modelPrm = diameter.parameter
    modelPrm.expression = 'PD'

    # Create Vertical line from center to outerCircle
    endPt = adsk.core.Point3D.create( 0, pitch_diameter/20, 0 )
    vertLine = sketch.sketchCurves.sketchLines.addByTwoPoints( pitchCircle.centerSketchPoint, endPt )
    vertLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( vertLine.endSketchPoint, pitchCircle )
    geoConstraints.addVertical( vertLine )

    # Create Pie line from center to outerCircle
    endPt = adsk.core.Point3D.create( pitch_diameter/20, 0, 0 )
    pieLine = sketch.sketchCurves.sketchLines.addByTwoPoints( pitchCircle.centerSketchPoint, endPt )
    pieLine.isConstruction = True
    # geoConstraints.addCoincident( vertLine.startSketchPoint, outerCircle.centerSketchPoint )
    geoConstraints.addCoincident( pieLine.endSketchPoint, pitchCircle )
    textPoint = adsk.core.Point3D.create( pitch_diameter / 40, pitch_diameter / 40, 0 )
    angleDim = sketch.sketchDimensions.addAngularDimension( vertLine, pieLine, textPoint )
    # angleDim.value = math.pi / toothCount # in radians

    # get ModelParameter
    modelPrm = angleDim.parameter
    modelPrm.expression = '180 / n'

    # Create the line from the Pitch Line down PLD distance
    endPt = vertLine.endSketchPoint.geometry.copy()
    endPt.translateBy( adsk.core.Vector3D.create(0,-geom.pitchLineDepth/10,0) )
    beltLine = sketch.sketchCurves.sketchLines.addByTwoPoints( vertLine.endSketchPoint, endPt )
    geoConstraints.addCoincident( beltLine.endSketchPoint, vertLine )
    textPoint = futil.offsetPoint3D( beltLine.startSketchPoint.geometry, -0.005, -0.0250, 0 )
    dist = sketch.sketchDimensions.addDistanceDimension( 
        beltLine.startSketchPoint, beltLine.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPoint 
    )
    dist.value = geom.pitchLineDepth / 10 # in cm

    # Create the tooth top arc
    topArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep( 
        pitchCircle.centerSketchPoint, beltLine.endSketchPoint, -math.pi / toothCount / 4 )
    # geoConstraints.addCoincident( topArc.startSketchPoint, outerCircle )
    geoConstraints.addConcentric( topArc, pitchCircle )

    # Create the tooth top radius
    centerPt = futil.offsetPoint3D( topArc.startSketchPoint.geometry, 0, -geom.filletRadius/10, 0 )
    topRadiusArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        centerPt, topArc.startSketchPoint, -math.pi / 2 )
    geoConstraints.addTangent( topArc, topRadiusArc )
    textPoint = centerPt
    textPoint.translateBy( adsk.core.Vector3D.create(geom.filletRadius / 20, geom.filletRadius / 20, 0 ))
    radius = sketch.sketchDimensions.addRadialDimension( topRadiusArc, textPoint )
    radius.value = geom.filletRadius / 10 # in cm
    
    # Create the transistion arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, geom.transitionDim / 10, -geom.transitionDim/100, 0 )
    endPt = futil.offsetPoint3D( topRadiusArc.startSketchPoint.geometry, geom.filletRadius/20, -geom.filletRadius/10, 0 )
    transistionArc = sketch.sketchCurves.sketchArcs.addByCenterStartEnd( 
        centerPt, topRadiusArc.startSketchPoint, endPt )
    geoConstraints.addTangent( transistionArc, topRadiusArc )

    # textPoint = futil.midPoint3D( centerPt, transistionArc.startSketchPoint.geometry )
    # textPoint.translateBy( -geom.filletRadius/20, geom.filletRadius, 0 )

    textPoint = futil.Arc3DTextPoint( transistionArc )
    radius = sketch.sketchDimensions.addRadialDimension( transistionArc, textPoint )
    radius.value = geom.transitionRadius / 10 # in cm

    textPoint = transistionArc.centerSketchPoint.geometry.copy()
    textPoint.translateBy( adsk.core.Vector3D.create(-geom.transitionDim / 20, geom.transitionDim / 50, 0 ))
    dist = sketch.sketchDimensions.addOffsetDimension( 
        pieLine, transistionArc.centerSketchPoint, textPoint )
    dist.value = geom.transitionDim / 10 # in cm
    radius.textPosition = futil.Arc3DTextPoint( transistionArc )

    # Create the root arc
    centerPt = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -geom.filletRadius/10, -geom.filletRadius/10, 0 )
    rootArc = sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
        pieLine.endSketchPoint, transistionArc.endSketchPoint, math.pi / 4 )
    geoConstraints.addTangent( rootArc, transistionArc )
    # textPoint = futil.offsetPoint3D( pieLine.endSketchPoint.geometry, -0.05, -0.05, 0 )
    textPoint = futil.Arc3DTextPoint( rootArc )
    radius = sketch.sketchDimensions.addRadialDimension( rootArc, textPoint )
    radius.value = geom.toothBumpRadius / 10 # in cm
    geoConstraints.addCoincident( rootArc.endSketchPoint, pieLine )
    geoConstraints.addCoincident( rootArc.centerSketchPoint, pieLine )

    textPoint = rootArc.centerSketchPoint.geometry.copy()
    textPoint.translateBy( adsk.core.Vector3D.create(geom.transitionDim / 50, 0, 0 ))
    rootDist = sketch.sketchDimensions.addDistanceDimension( 
        pieLine.endSketchPoint, rootArc.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        textPoint )
    rootDist.value = ( geom.toothHeight + geom.pitchLineDepth ) / 10 # in cm

    # Mirror the half tooth about the pie line
    MirrorEntities = [ beltLine, topArc, topRadiusArc, transistionArc, rootArc ]
    sketch.mirror( MirrorEntities, pieLine )

def addOuterBeltCircle( sketch: adsk.fusion.Sketch, geom: TimingBeltGeom ):

    # Find the pitch circle
    circles = sketch.sketchCurves.sketchCircles
    pitch_cir = None
    for cir in circles:
        if not pitch_cir or pitch_cir.radius < cir.radius:
            pitch_cir = cir

    if not pitch_cir:
        raise Exception( 'Cannot find the Pitch Circle!' )

    # Add the belt OD circle
    centerPt = adsk.core.Point3D.create()
    beltODCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, pitch_cir.radius + 0.1 )
    sketch.geometricConstraints.addCoincident( beltODCircle.centerSketchPoint, pitch_cir.centerSketchPoint )

    textPoint = adsk.core.Point3D.create( pitch_cir.radius, pitch_cir.radius/4, 0 )
    diameter = sketch.sketchDimensions.addDiameterDimension( beltODCircle, textPoint )

    # get ModelParameter
    modelPrm = diameter.parameter
    modelPrm.expression = f'PD + {geom.thickness-geom.pitchLineDepth}mm'
    
def extrudePulley( workingComp: adsk.fusion.Component, 
                  sketch: adsk.fusion.Sketch, 
                  beltWidth: float ) -> tuple[adsk.fusion.ExtrudeFeature, adsk.fusion.BRepEdge]:
    # Extrude the pulley sketch 
    if sketch.profiles.count != 2 :
        futil.popup_error(f'Sketch does not have 2 profiles, has {sketch.profiles.count} profiles.')
        return

    plug_prof = sketch.profiles.item(0)
    tooth_prof = sketch.profiles.item(1)
    if plug_prof.face.area < tooth_prof.face.area :
        plug_prof = sketch.profiles.item(1)
        tooth_prof = sketch.profiles.item(0)

    extrudes = workingComp.features.extrudeFeatures
    beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth )
    profiles = adsk.core.ObjectCollection.createWithArray( [plug_prof, tooth_prof] )
    cylExtrude = extrudes.addSimple(profiles, beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    cutTooth = extrudes.addSimple(tooth_prof, beltWidthValue, adsk.fusion.FeatureOperations.CutFeatureOperation)

    # Find the axis of the circular pattern
    pitch_circle = None
    cyl_edge = None
    for edge in cylExtrude.bodies.item(0).edges:
        if edge.geometry.classType() == adsk.core.Arc3D.classType() :
            arc: adsk.core.Arc3D = edge.geometry
            if not pitch_circle:
                pitch_circle = arc
                cyl_edge = edge
            else:
                if arc.radius > pitch_circle.radius:
                    pitch_circle = arc
                    cyl_edge = edge

    return [ cutTooth, cyl_edge ]

def extrudeBelt( workingComp: adsk.fusion.Component, 
                 sketch: adsk.fusion.Sketch, 
                 beltWidth: float ) -> tuple[adsk.fusion.ExtrudeFeature, adsk.fusion.BRepEdge]:
    # Extrude the pulley sketch 
    if sketch.profiles.count != 3 :
        futil.popup_error(f'Sketch does not have 3 profiles, has {sketch.profiles.count} profiles.')
        return

    # Find the plug profile which has the largest area
    plug_idx = 0
    plug_area = 0
    for idx in range( sketch.profiles.count ):
        prof = sketch.profiles.item( idx )
        if prof.face.area > plug_area:
            plug_idx = idx
            plug_area = prof.face.area

    plug_prof = sketch.profiles.item(plug_idx)
    plug_centroid = plug_prof.face.centroid

    # Find the belt OD profile which will have a centroid closest to the plug centroid
    beltOD_idx = -1
    min_centroid_dist = 99999999
    for idx in range( sketch.profiles.count ):
        if idx == plug_idx:
            continue
        prof_centroid = sketch.profiles.item( idx ).face.centroid
        centroid_dist = prof_centroid.distanceTo( plug_prof.face.centroid )
        if centroid_dist < min_centroid_dist:
            beltOD_idx = idx
            min_centroid_dist = centroid_dist

    if beltOD_idx < 0 :
        raise Exception( 'Cannot find the Belt OD Profile!')

    belt_prof = sketch.profiles.item(beltOD_idx)

    # Determine the tooth profile based on the plug and belt indices
    match plug_idx + beltOD_idx:
        case 1:
            tooth_idx = 2
        case 2:
            tooth_idx = 1
        case _:
            tooth_idx = 0

    tooth_prof = sketch.profiles.item(tooth_idx)

    extrudes = workingComp.features.extrudeFeatures
    beltWidthValue = adsk.core.ValueInput.createByReal( beltWidth )
    cylExtrude = extrudes.addSimple(belt_prof, beltWidthValue, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    toothFeat = extrudes.addSimple(tooth_prof, beltWidthValue, adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # Find the axis of the circular pattern
    pitch_circle = None
    cyl_edge = None
    for edge in cylExtrude.bodies.item(0).edges:
        if edge.geometry.classType() == adsk.core.Arc3D.classType() :
            arc: adsk.core.Arc3D = edge.geometry
            if not pitch_circle:
                pitch_circle = arc
                cyl_edge = edge
            else:
                if arc.radius > pitch_circle.radius:
                    pitch_circle = arc
                    cyl_edge = edge

    return [ toothFeat, cyl_edge ]