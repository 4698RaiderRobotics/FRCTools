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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Gamepiece'
CMD_NAME = 'Generic Game Piece'
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
    ui.messageBox("created")
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.


    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    try: 
        ddc = inputs.addDropDownCommandInput('type', "Type", adsk.core.DropDownStyles.TextListDropDownStyle)
        ddc.listItems.add("Ball", False)
        ddc.listItems.add('Cube', True)
        ddc.listItems.add('Cylinder', False)
        inputs.addValueInput('length', "Length", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*2 ))
        inputs.addValueInput('width', "Width", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*2 ))
        inputs.addValueInput('height', "Height", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 * 2))
     
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

    
    type_input = inputs.itemById('type')
    selected_type = type_input.selectedItem.name  # 'Ball', 'Cube', or 'Cylinder'

    length_input = inputs.itemById('length')
    length = length_input.value  # cm

    width_input = inputs.itemById('width')
    width = width_input.value  # cm, "Pulley Diameter"  

    height_input = inputs.itemById('height')
    height = height_input.value  # cm, "Belt Thickness"
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    # Now use the values, e.g. branch on type
    if selected_type == 'Ball':
       create_sphere(comp, futil.pZero, length)
    elif selected_type == 'Cube':
        futil.create_tube(width, length, height, comp.xYConstructionPlane, occ)
    elif selected_type == 'Cylinder':
        create_cylinder(comp, futil.pZero, adsk.core.Vector3D.create(0, 1, 0), height, length)
    futil.get_random_flat_color(occ, design, app)
    comp.name = f"Generic Gamepiece"
    endIndex = design.timeline.count - 1
    design.timeline.timelineGroups.add(startIndex, endIndex)
def create_cylinder(comp: adsk.fusion.Component, origin: adsk.core.Point3D,
                     axis: adsk.core.Vector3D, height: float, radius: float):
    tbm = adsk.fusion.TemporaryBRepManager.get()

    # createCylinderOrCone(pointAtStartOfAxis, startRadius, pointAtEndOfAxis, endRadius)
    end_point = origin.copy()
    end_point.translateBy(adsk.core.Vector3D.create(
        axis.x * height, axis.y * height, axis.z * height))

    temp_body = tbm.createCylinderOrCone(origin, radius, end_point, radius)

    # Add the temp BRep into the actual component as a real body
    base_feats = comp.features.baseFeatures
    base_feat = base_feats.add()
    base_feat.startEdit()
    real_body = comp.bRepBodies.add(temp_body, base_feat)
    base_feat.finishEdit()

    return real_body


def create_sphere(comp: adsk.fusion.Component, center: adsk.core.Point3D, radius: float):
    tbm = adsk.fusion.TemporaryBRepManager.get()

    temp_body = tbm.createSphere(center, radius)

    base_feats = comp.features.baseFeatures
    base_feat = base_feats.add()
    base_feat.startEdit()
    real_body = comp.bRepBodies.add(temp_body, base_feat)
    base_feat.finishEdit()

    return real_body
        

        

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
    type_input = inputs.itemById('type')
    selected_type = type_input.selectedItem.name  # 'Ball', 'Cube', or 'Cylinder'

   # if selected_type == 'Ball' or selected_type == 'Cylinder':
      #  inputs.itemById('length').name = "Radius"
      #  inputs.itemById('width').isVisible = False
   # else:
      #  inputs.itemById('length').name = "Width"
       # inputs.itemById('width').isVisible = True
    

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
