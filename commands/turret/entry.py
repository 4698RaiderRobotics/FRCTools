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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Turret'
CMD_NAME = 'Turret'
CMD_Description = 'Creates a Turret'

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
        inputs.addBoolValueInput('tubes', "Mounting Tubes?", True)
        inputs.addValueInput('hole', "Inner Diameter", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*6))
        inputs.addValueInput('top_diameter', "Top Plate Outer Diameter", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*12))
        inputs.addValueInput('bottom_diameter', "Bottom Plate Outer Diameter", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*15))

        
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
    try:
        inputs = args.command.commandInputs
        id_command : adsk.core.ValueCommandInput = inputs.itemById('hole')
        top_diameter_command : adsk.core.IntegerSliderCommandInput = inputs.itemById('top_diameter')
        bottom_diameter_command : adsk.core.ValueCommandInput = inputs.itemById('bottom_diameter')
        tubes_command : adsk.core.BoolValueCommandInput = inputs.itemById('tubes')

        hole_diameter = id_command.value
        top_od = top_diameter_command.value
        bottom_od = bottom_diameter_command.value

        tubes = tubes_command.value

        workingOcc = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        workingComp = workingOcc.component

        bottom = make_plate(bottom_od, hole_diameter, 0, workingOcc)
        top = make_plate(top_od, hole_diameter, 0.25 * 2.54, workingOcc)
        middle = make_plate(hole_diameter + 2.54, hole_diameter, 0.125 * 2.54, workingOcc, True)

        workingComp.asBuiltJoints.add(workingComp.asBuiltJoints.createInput(bottom, middle, None))
        spinnyThing = workingComp.asBuiltJoints.createInput(middle, top, adsk.fusion.JointGeometry.createByCurve(middle.bRepBodies.item(0).edges.item(0), adsk.fusion.JointKeyPointTypes.CenterKeyPoint))
        spinnyThing.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
        workingComp.asBuiltJoints.add(spinnyThing)
        futil.get_random_flat_color(workingOcc, design, app)
        workingComp.name = f"Turret"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
        
    except Exception as ex:
        ui.messageBox(f"{ex} {ex.__traceback__.tb_lineno}")
def make_plate(diameter_cm : float, hole_diameter : float,  plane_offset : float, occurance : adsk.fusion.Occurrence, circular : bool = False):
    try:
        plane_input = occurance.component.constructionPlanes.createInput(occurance)
        plane_input.setByOffset(occurance.component.xYConstructionPlane, adsk.core.ValueInput.createByReal(plane_offset))
        bottomSketch = occurance.component.sketches.add(occurance.component.constructionPlanes.add(plane_input))
        if circular:
            bottomSketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pZero, diameter_cm/2)
        else:
            rectangle = bottomSketch.sketchCurves.sketchLines.addCenterPointRectangle(futil.pZero, pointFromOffset(futil.pZero, diameter_cm/2/2.54, diameter_cm * 0.5/2.54))
            for i in range(rectangle.count - 1):
                bottomSketch.sketchCurves.sketchArcs.addFillet(rectangle.item(i), rectangle.item(i).startSketchPoint.geometry, rectangle.item(i+1), rectangle.item(i+1).startSketchPoint.geometry, diameter_cm/8)
            bottomSketch.sketchCurves.sketchArcs.addFillet(rectangle.item(0), rectangle.item(0).startSketchPoint.geometry, rectangle.item(3), rectangle.item(3).startSketchPoint.geometry, diameter_cm/8)
        bottomSketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pZero, hole_diameter/2)
        profileExtrude = bottomSketch.profiles.item(0) if futil.bbox_area(bottomSketch.profiles.item(0)) > futil.bbox_area(bottomSketch.profiles.item(1)) else bottomSketch.profiles.item(1)
        occurance.component.features.extrudeFeatures.addSimple(profileExtrude, adsk.core.ValueInput.createByReal(2.54*0.125), adsk.fusion.FeatureOperations.NewComponentFeatureOperation)
        return occurance.component.occurrences.item(occurance.component.occurrences.count - 1)
    except Exception as ex:
        ui.messageBox(f"{ex} {ex.__traceback__.tb_lineno}")

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
