import adsk.core
import adsk.fusion
from adsk.core import Vector3D as v3
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Rollers'
CMD_NAME = 'Rollers Renderer'
CMD_Description = 'Creates a pair (or a single) of rollers with a plate joining them'

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

  
    
    inputs.addValueInput("roller_diameter", "Roller Diameter", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*2))
    inputs.addValueInput("c_c", "Center To Center", defaultLengthUnits, adsk.core.ValueInput.createByReal(3*2.54))
    inputs.addValueInput("plate_thickness", "Plate Thickness", defaultLengthUnits, adsk.core.ValueInput.createByReal(0.125*2.54))
    inputs.addValueInput('roller_length', "Roller Length", defaultLengthUnits, adsk.core.ValueInput.createByReal(10*2.54))
    inputs.addBoolValueInput('two_rollers', "Use Second Roller?", True)
    inputs.addBoolValueInput('two_plates', "Plates on Both Sides", True)


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

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    ui.messageBox('execute')
    try:
        rollerDiamaterCmdInput:adsk.core.ValueCommandInput = inputs.itemById('roller_diameter')
        rollerDiamaterInches = rollerDiamaterCmdInput.value
        centerToCenterCommandInput:adsk.core.ValueCommandInput = inputs.itemById('c_c')
        centerToCenterInches = centerToCenterCommandInput.value
        plateThicknessCommandInput : adsk.core.ValueCommandInput = inputs.itemById('plate_thickness')
        plateThicknessInches = plateThicknessCommandInput.value 
        rollerLengthCommandInput : adsk.core.ValueCommandInput = inputs.itemById('roller_length')
        rollerLengthInches = rollerLengthCommandInput.value
        twoRollersCommandInput : adsk.core.BoolValueCommandInput = inputs.itemById('two_rollers')
        twoRollers = twoRollersCommandInput.value
        twoPlatesCmdInput : adsk.core.BoolValueCommandInput = inputs.itemById('two_plates')
        twoPlates = twoPlatesCmdInput.value
    except Exception as ex:
        ui.messageBox("Failed to fetch inputs " + str(ex))
    try:
        workingOcc = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        workingComp = workingOcc.component
        rollerSketch = workingComp.sketches.add(root.xYConstructionPlane, workingOcc)
        basePoint = adsk.core.Point3D.create(0,0,0)
        secondRollerCenter = pointFromOffset(basePoint, centerToCenterInches/2.54, 0)
        rollerSketch.sketchCurves.sketchCircles.addByCenterRadius(basePoint, rollerDiamaterInches/2)
        if (twoRollers): rollerSketch.sketchCurves.sketchCircles.addByCenterRadius(pointFromOffset(basePoint, centerToCenterInches/2.54, 0), rollerDiamaterInches/2)
        profilesCollection = adsk.core.ObjectCollection.create()
        for profile in rollerSketch.profiles:
            profilesCollection.add(profile)
        rollersExtrudeInput = workingComp.features.extrudeFeatures.createInput(profilesCollection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        rollersExtrudeInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(rollerLengthInches)), adsk.fusion.ExtentDirections.NegativeExtentDirection)
        workingComp.features.extrudeFeatures.add(rollersExtrudeInput)
        rollerFaceOne = next(face for face in workingComp.bRepBodies.item(0).faces if face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType)
        rollerFaceTwo = None
        for face in workingComp.bRepBodies.item(0).faces:
            if (face.evaluator.getNormalAtPoint(face.pointOnFace)[1].angleTo(rollerFaceOne.evaluator.getNormalAtPoint(rollerFaceOne.pointOnFace)[1]) == math.pi):
                rollerFaceTwo = face
                break
        plateSketch = workingComp.sketches.add(rollerFaceOne)
        plateSketch.sketchCurves.sketchCircles.addByCenterRadius(pointFromOffset(basePoint, centerToCenterInches/2.54, 0), rollerDiamaterInches/2)
        plateSketch.sketchCurves.sketchCircles.addByCenterRadius(basePoint, rollerDiamaterInches/2)
        plateSketch.sketchCurves.sketchLines.addTwoPointRectangle(pointFromOffset(basePoint, 0, 0.5* rollerDiamaterInches/2.54), pointFromOffset(secondRollerCenter , 0 ,0.5* -rollerDiamaterInches/2.54))
        profilesCollection.clear()
        for profile in plateSketch.profiles:
            profilesCollection.add(profile)
        plate1ExtrudeInput = workingComp.features.extrudeFeatures.createInput(profilesCollection, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        plate1ExtrudeInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(plateThicknessInches)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        workingComp.features.extrudeFeatures.add(plate1ExtrudeInput)
        if twoPlates:
            plateSketch = workingComp.sketches.add(rollerFaceTwo)
            plateSketch.sketchCurves.sketchCircles.addByCenterRadius(pointFromOffset(basePoint, -centerToCenterInches/2.54, 0), rollerDiamaterInches/2)
            plateSketch.sketchCurves.sketchCircles.addByCenterRadius(basePoint, rollerDiamaterInches/2)
            plateSketch.sketchCurves.sketchLines.addTwoPointRectangle(pointFromOffset(basePoint, 0, rollerDiamaterInches*0.5/2.54), pointFromOffset(basePoint , -centerToCenterInches/2.54 , -rollerDiamaterInches*0.5/2.54))
            profilesCollection.clear()
            for profile in plateSketch.profiles:
                profilesCollection.add(profile)
            plate1ExtrudeInput = workingComp.features.extrudeFeatures.createInput(profilesCollection, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            plate1ExtrudeInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(plateThicknessInches)), adsk.fusion.ExtentDirections.NegativeExtentDirection)
            workingComp.features.extrudeFeatures.add(plate1ExtrudeInput)
        futil.get_random_flat_color(workingOcc, design, app)
        workingComp.name = f"Horizontal Roller"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
    except Exception as ex:
        ui.messageBox(str(ex) + ' ' + str(ex.args))
    
    

    
        

        

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
    
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
