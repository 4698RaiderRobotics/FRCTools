import adsk.core
import adsk.fusion
from adsk.core import Vector3D as v3
import os
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Elevator'
CMD_NAME = 'Elevator Generator'
CMD_Description = 'A Fusion Add-in Command with a dialog'

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
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.


    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

    stagesSliderInput = inputs.addIntegerSliderCommandInput("stages", "Stages", 1, 6)
    
    inputs.addValueInput("max_extension", "Max Extension", 'in', adsk.core.ValueInput.createByReal(48*2.54))
    inputs.addValueInput("carriage_height", "Carriage Height", 'in', adsk.core.ValueInput.createByReal(5*2.54))
    inputs.addValueInput("carriage_width", "Carriage Width", 'in', adsk.core.ValueInput.createByReal(5*2.54))


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
    root = design.rootComponent
    startIndex = design.timeline.count

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs

    stagesValueCommandInput : adsk.core.IntegerSliderCommandInput = inputs.itemById('stages')
    stages = stagesValueCommandInput.valueOne
    maxExtensionValueCommandInput: adsk.core.ValueCommandInput = inputs.itemById('max_extension')
    maxExtension = maxExtensionValueCommandInput.value
    carriageWidthCommandInput : adsk.core.ValueCommandInput = inputs.itemById('carriage_width')
    carriageWidth = carriageWidthCommandInput.value
    carriageHeightCommandInput : adsk.core.ValueCommandInput = inputs.itemById('carriage_height')
    carriageHeight = carriageHeightCommandInput.value

    carriageWidth /= 2.54
    carriageHeight /= 2.54
    maxExtension /= 2.54
    maxExtension -= 7
    stageHeight = maxExtension / stages + 6

    if stageHeight < carriageHeight - 2:
        ui.messageBox('Stages are too short! Either decrease Carriage Height or Number of Stages or Increase Extension Length')
        return
    if carriageHeight < 2 or carriageWidth < 2:
        ui.messageBox(f"Carriage Height of {carriageHeight} in or Carriage Width of {carriageWidth} in is too small! Please increase its size")
        return
    

    stageReferencePoint = adsk.core.Point3D.create(0,0,0)

    workingOcc = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    workingComp = workingOcc.component
    workingOcc.activate()

    
    

    instantiatedStages = []
    try:
        carriageOcc = workingComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        carriageComp = carriageOcc.component
        carriageOcc.activate()
        carriageSketch = carriageComp.sketches.add(root.xYConstructionPlane)
        carriageTopLeft = pointFromOffset(stageReferencePoint, 0.5, carriageHeight)
        carriageSketch.sketchCurves.sketchLines.addTwoPointRectangle(carriageTopLeft, pointFromOffset(carriageTopLeft, carriageWidth, -carriageHeight))
        carriageExtrudeInput = carriageComp.features.extrudeFeatures.createInput(carriageSketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        carriageExtrudeInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(2.54 * 2)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        carriageComp.features.extrudeFeatures.add(carriageExtrudeInput)
        instantiatedStages.append(carriageOcc)
        
        for stage in range(stages):
            currentOcc = workingComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            currentComp = currentOcc.component
            currentOcc.activate()
            currentSketch = currentComp.sketches.add(root.xYConstructionPlane, currentOcc)
            bottomRailLeftTopPoint = stageReferencePoint.copy()
            bottomRailLeftTopPoint.translateBy(v3.create(-1.5*2.54*stage, -2.54*stage, 0))
            currentSketch.sketchCurves.sketchLines.addTwoPointRectangle(bottomRailLeftTopPoint, pointFromOffset(bottomRailLeftTopPoint, carriageWidth + 1 + (3 * stage), -1))
            currentSketch.sketchCurves.sketchLines.addTwoPointRectangle(pointFromOffset(bottomRailLeftTopPoint, -1, -1), pointFromOffset(bottomRailLeftTopPoint, 0, stageHeight - 1)) 
            bottomRailTopRightPoint = pointFromOffset(bottomRailLeftTopPoint, carriageWidth + 1 + 3*stage, 0 )
            currentSketch.sketchCurves.sketchLines.addTwoPointRectangle(pointFromOffset(bottomRailTopRightPoint, 1, -1), pointFromOffset(bottomRailTopRightPoint, 0, stageHeight - 1))
            profileCollection = adsk.core.ObjectCollection.create()
            for profile in currentSketch.profiles:
                profileCollection.add(profile)
            extrudedInput = currentComp.features.extrudeFeatures.createInput(profileCollection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            extrudedInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(2.54*2)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
            currentComp.features.extrudeFeatures.add(extrudedInput)
            instantiatedStages.append(currentOcc)
        for i in range(len(instantiatedStages )-1):
            weirdShit:adsk.fusion.Occurrence = instantiatedStages[i]
            sliderJointInput = workingComp.asBuiltJoints.createInput(instantiatedStages[i], instantiatedStages[i+1], adsk.fusion.JointGeometry.createByPoint(weirdShit.bRepBodies.item(0).faces.item(0).vertices.item(0)))
            sliderJointInput.setAsSliderJointMotion(adsk.fusion.JointDirections.YAxisJointDirection)
            
            limits : adsk.fusion.SliderJointMotion  = currentComp.asBuiltJoints.add(sliderJointInput).jointMotion
            
            limits.slideLimits.isMaximumValueEnabled = True
            limits.slideLimits.isMinimumValueEnabled = True
            limits.slideLimits.maximumValue = (stageHeight - 6  - 1) * 2.54
            limits.slideLimits.minimumValue = 0
            if i == 0: limits.slideLimits.maximumValue = (stageHeight - 1 - carriageHeight) * 2.54
        futil.get_random_flat_color(workingOcc, design, app)
        workingComp.name = f"Elevator"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
    except Exception as ex:
        ui.messageBox(str(ex.__cause__) + ' ' + str(ex))
        

        

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
