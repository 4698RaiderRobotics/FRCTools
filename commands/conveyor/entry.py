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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Conveyor'
CMD_NAME = 'Conveyor Creator'
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
   
        inputs.addValueInput('length', "Length", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*20 ))
        inputs.addValueInput('width', "Width", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*20 ))
        inputs.addValueInput('roller_diameter', "Roller Diameter", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*2 ))
        inputs.addValueInput('belt_width', "Belt Thickness", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 ))
        inputs.addIntegerSliderListCommandInput('belt_count', "Number of Belts", [1,3,5,7,9,11])
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
    root = design.rootComponent
    startIndex = design.timeline.count

    inputs = args.command.commandInputs

    # Get a reference to your command's inputs.
    length = inputs.itemById('length').value
    width = inputs.itemById('width').value
   
    roller_diameter = inputs.itemById('roller_diameter').value
   
    belt_width = inputs.itemById('belt_width').value

    # DropDownCommandInputs — get selected item
   
   

    # IntegerSpinnerCommandInput
    belt_count = inputs.itemById('belt_count').valueOne

    # (optional) if you need the index instead of the name:
  
    
    
    eighth = 2.54 * 0.125

    #ok so my thought process is create everything then mirror it!

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component


    #use xy for everything 
    rollerSketch = comp.sketches.add(comp.xYConstructionPlane)

    rollerSketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pZero, roller_diameter/2 - eighth)
    rollerSketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pointFromOffset(futil.pZero, length/2.54 - 2, 0), roller_diameter/2 - eighth)

    
    rollerExtrudeInput = comp.features.extrudeFeatures.createInput(futil.collectionFromProfiles(rollerSketch.profiles), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    rollerExtrudeInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(width - 2.54*2)), adsk.fusion.ExtentDirections.PositiveExtentDirection)

    comp.features.extrudeFeatures.add(rollerExtrudeInput)

  

    beltStart = 0.5 * 2.54
    beltEnd = width - 1.5*2.54 - belt_width
    
    
    if belt_count == 1:
        interval = 0
        beltStart = (beltEnd - beltStart) / 2
    else:
        interval = (beltEnd - beltStart)/(belt_count - 1)
    for i in range(belt_count):
        ui.messageBox(f"creating belt {i} of {belt_count}")
        planeInput = comp.constructionPlanes.createInput(occ)
        planeInput.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(beltStart + i * interval))
        plane = comp.constructionPlanes.add(planeInput)
        futil.createBelt(roller_diameter, belt_width, length - 2 * 2.54, plane, occ)
   


    futil.get_random_flat_color(occ, design, app)
    comp.name = f"Conveyor"
    endIndex = design.timeline.count - 1
    design.timeline.timelineGroups.add(startIndex, endIndex)

        

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
