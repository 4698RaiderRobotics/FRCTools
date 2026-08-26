import adsk.core
import adsk.fusion
from adsk.core import Vector3D as v3
import math
import os
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Swerve'
CMD_NAME = 'Drivetrain Drawer'
CMD_Description = 'Creates a swerve drvetrain'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

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
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = config.get_marker_submenu()

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = config.get_marker_submenu()
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    ui.messageBox("created")
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.


    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    try: 
        inputs.addValueInput('length', 'Chassis Length', defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54* 26))
        inputs.addValueInput('width', "Chassis Width", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 * 26))
        inputs.addValueInput('front_bumper_gap', "Front Bumper Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('right_bumper_gap', "Right Bumper Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('left_bumper_gap', "Left Bumper Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('back_bumper_gap', "Back Bumper Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('bumper_height', "Bumper Height", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*4.5))
        inputs.addValueInput('bumper_width', "Bumper Width", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*3.125))
        inputs.addValueInput('bumper_ground_clearance', "Bumper Ground Clearance", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*2.5))
        inputs.addValueInput('frame_ground_clearance', "Frame Ground Clearance", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*0.75))
        inputs.addValueInput('front_frame_gap', "Front Frame Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('right_frame_gap', "Right Frame Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('left_frame_gap', "Left Frame Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addValueInput('back_frame_gap', "Back Frame Gap", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        inputs.addBoolValueInput('use_bellypan', "Use Bellypan?", True)
        inputs.addValueInput('bellypan_thickness', "Bellypan Thickness", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 * 0.125))


    except Exception as ex:
        ui.messageBox(ex)
    


    

    

    # TODO Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    # TODO ******************************** Your code here ********************************

    design = adsk.fusion.Design.cast(app.activeProduct)
    startIndex = design.timeline.count
    root = design.rootComponent

    inputs = args.command.commandInputs

    # Get a reference to your command's inputs.
    length = inputs.itemById('length').value
    width = inputs.itemById('width').value
    front_bumper_gap = inputs.itemById('front_bumper_gap').value
    right_bumper_gap = inputs.itemById('right_bumper_gap').value
    left_bumper_gap = inputs.itemById('left_bumper_gap').value
    back_bumper_gap = inputs.itemById('back_bumper_gap').value
    bumper_height = inputs.itemById('bumper_height').value
    bumper_width = inputs.itemById('bumper_width').value
    bumper_ground_clearance = inputs.itemById('bumper_ground_clearance').value
    frame_ground_clearance = inputs.itemById('frame_ground_clearance').value
    front_frame_gap = inputs.itemById('front_frame_gap').value
    right_frame_gap = inputs.itemById('right_frame_gap').value
    left_frame_gap = inputs.itemById('left_frame_gap').value
    back_frame_gap = inputs.itemById('back_frame_gap').value
    use_bellypan : adsk.core.BoolValueCommandInput = inputs.itemById('use_bellypan')
    bellypan_thickness : adsk.core.ValueCommandInput = inputs.itemById('bellypan_thickness')


    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    try:
        bumperOcc = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        bumperPlaneInput = bumperOcc.component.constructionPlanes.createInput()
        bumperPlaneInput.setByOffset(bumperOcc.component.xYConstructionPlane, adsk.core.ValueInput.createByReal(bumper_ground_clearance))
        bumperSketch = bumperOcc.component.sketches.add(bumperOcc.component.constructionPlanes.add(bumperPlaneInput))

        bumperSketch.sketchCurves.sketchLines.addCenterPointRectangle(futil.pZero, futil.pointFromOffset(futil.pZero, 0.5*length/2.54 + bumper_width/2.54,0.5* width/2.54 + bumper_width/2.54))

        bumperInput = bumperOcc.component.features.extrudeFeatures.createInput(bumperSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        bumperInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(bumper_height)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        bumperOcc.component.features.extrudeFeatures.add(bumperInput)

       

        bumperChamferCollection= adsk.core.ObjectCollection.create()
        for face in bumperOcc.component.bRepBodies.item(0).faces:
                if face.evaluator.getNormalAtPoint(face.pointOnFace)[1].isPerpendicularTo(adsk.core.Vector3D.create(0,0,1)):
                    bumperChamferCollection.add(face)
        ui.messageBox(f'{bumperChamferCollection.count}')
        filletInput = bumperOcc.component.features.filletFeatures.createInput()
        filletInput.edgeSetInputs.addConstantRadiusEdgeSet(bumperChamferCollection, adsk.core.ValueInput.createByReal(bumper_height/3), False)
        bumperOcc.component.features.filletFeatures.add(filletInput)


        bumperShellObjectCollection = adsk.core.ObjectCollection.create()
        
        for face in bumperOcc.component.bRepBodies.item(0).faces:
            if face.evaluator.getNormalAtPoint(face.pointOnFace)[1].isParallelTo(adsk.core.Vector3D.create(0,0,1)) and face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
                bumperShellObjectCollection.add(face)

        bumperShellInput = bumperOcc.component.features.shellFeatures.createInput(bumperShellObjectCollection, False)
        bumperShellInput.insideThickness = adsk.core.ValueInput.createByReal(bumper_width)
        bumperOcc.component.features.shellFeatures.add(bumperShellInput)

        cuttingSketch = bumperOcc.component.sketches.add(bumperSketch.referencePlane)
        if left_bumper_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, 0, left_bumper_gap/2.54 * 0.5), futil.pointFromOffset(futil.pZero, 0.5*width/2.54 + bumper_width/2.54, -left_bumper_gap/2.54 * 0.5))
        if right_bumper_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, 0, right_bumper_gap/2.54 * 0.5), futil.pointFromOffset(futil.pZero, -0.5*width/2.54 + -bumper_width/2.54, -right_bumper_gap/2.54 * 0.5))
        if front_bumper_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, front_bumper_gap/2.54 * 0.5, 0), futil.pointFromOffset(futil.pZero, -front_bumper_gap/2.54 * 0.5, 0.5 * length/2.54 + bumper_width/2.54))
        if back_bumper_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, back_bumper_gap/2.54 * 0.5, 0), futil.pointFromOffset(futil.pZero, -back_bumper_gap/2.54 * 0.5, -0.5 * length/2.54 + -bumper_width/2.54))

        cuttingCollection = adsk.core.ObjectCollection.create()
        for profile in cuttingSketch.profiles:
            cuttingCollection.add(profile)

        if cuttingCollection.count > 0:
            bumperOcc.component.features.extrudeFeatures.addSimple(cuttingCollection, adsk.core.ValueInput.createByReal(bumper_height), adsk.fusion.FeatureOperations.CutFeatureOperation)

        frameOcc = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        frameComp = frameOcc.component
        framePlaneInput = frameComp.constructionPlanes.createInput()
        framePlaneInput.setByOffset(frameComp.xYConstructionPlane, adsk.core.ValueInput.createByReal(frame_ground_clearance))
        frameSketch = frameComp.sketches.add(frameComp.constructionPlanes.add(framePlaneInput))
        frameSketch.sketchCurves.sketchLines.addCenterPointRectangle(futil.pZero, futil.pointFromOffset(futil.pZero, 0.5*width/2.54, 0.5*length/2.54))
        frameComp.features.extrudeFeatures.addSimple(frameSketch.profiles.item(0), adsk.core.ValueInput.createByReal(2*2.54), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

        frameShellObjectCollection = adsk.core.ObjectCollection.create()
                
        for face in frameComp.bRepBodies.item(0).faces:
            if face.evaluator.getNormalAtPoint(face.pointOnFace)[1].isParallelTo(adsk.core.Vector3D.create(0,0,1)) and face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
                frameShellObjectCollection.add(face)

        frameShellInput = frameComp.features.shellFeatures.createInput(frameShellObjectCollection, False)
        frameShellInput.insideThickness = adsk.core.ValueInput.createByReal(2.54)
        frameComp.features.shellFeatures.add(frameShellInput)

        cuttingSketch = frameComp.sketches.add(frameSketch.referencePlane)

        if left_frame_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, 0, left_frame_gap/2.54 * 0.5), futil.pointFromOffset(futil.pZero, 0.5*width/2.54, -left_frame_gap/2.54 * 0.5))
        if right_frame_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, 0, right_frame_gap/2.54 * 0.5), futil.pointFromOffset(futil.pZero, -0.5*width/2.54, -right_frame_gap/2.54 * 0.5))
        if front_frame_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, front_frame_gap/2.54 * 0.5, 0), futil.pointFromOffset(futil.pZero, -front_frame_gap/2.54 * 0.5, 0.5 * length/2.54))
        if back_frame_gap != 0:
            cuttingSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, back_frame_gap/2.54 * 0.5, 0), futil.pointFromOffset(futil.pZero, -back_frame_gap/2.54 * 0.5, -0.5 * length/2.54))

        cuttingCollection = adsk.core.ObjectCollection.create()
        for profile in cuttingSketch.profiles:
            cuttingCollection.add(profile)

        if cuttingCollection.count > 0:
            frameComp.features.extrudeFeatures.addSimple(cuttingCollection, adsk.core.ValueInput.createByReal(2.54*2), adsk.fusion.FeatureOperations.CutFeatureOperation)
        if use_bellypan.value:
            bellypanSketch = frameComp.sketches.add(frameSketch.referencePlane)
            bellypanSketch.sketchCurves.sketchLines.addCenterPointRectangle(futil.pZero, futil.pointFromOffset(futil.pZero, 0.5*width/2.54, 0.5*length/2.54))
            frameComp.features.extrudeFeatures.addSimple(bellypanSketch.profiles.item(0), adsk.core.ValueInput.createByReal(-bellypan_thickness.value), adsk.fusion.FeatureOperations.JoinFeatureOperation)
        comp.asBuiltJoints.add(comp.asBuiltJoints.createInput(frameOcc, bumperOcc,None))
        futil.get_random_flat_color(occ, design, app)
        comp.name = f"Drivetrain"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
    except Exception as ex:
        ui.messageBox(f'{ex} {ex.__traceback__.tb_lineno} {ex.__context__}')


        

        

def pointFromOffset(reference:adsk.core.Point3D, offsetXInches, offsetYInches):
    copy = reference.copy()
    copy.translateBy(v3.create(offsetXInches*2.54, offsetYInches*2.54, 0))
    return copy



# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs


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
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    valueInput = inputs.itemById('value_input')
    if valueInput.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
