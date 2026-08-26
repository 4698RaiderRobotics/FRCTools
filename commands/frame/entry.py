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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Frame'
CMD_NAME = 'Frame'
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

        typeDropdown = inputs.addDropDownCommandInput('frame_type', "Tubing Type", adsk.core.DropDownStyles.TextListDropDownStyle)
        typeDropdown.listItems.add('1x1 Box Tube', True)
        typeDropdown.listItems.add('2x1 Box Tube', True)
        typeDropdown.listItems.add('2x2 Box Tube', True)
        inputs.addValueInput('length', "Length", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*6 ))
        inputs.addValueInput('height', "Height", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*6 ))
        inputs.addValueInput('width', "Width", defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54*6 ))
        inputs.addBoolValueInput('3d', "3d", True)
        inputs.addBoolValueInput('crossbeams', "Crossbeams", True)
        inputs.addBoolValueInput('triangular', "Triangular Frame", True)
        inputs.addValueInput('offset', "Triangular Frame Offset", defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
        
     
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

    frame_type_input : adsk.core.DropDownCommandInput = inputs.itemById('frame_type')
    frame_type = frame_type_input.selectedItem.index  # e.g. '2x1 Box Tube'

    length_input = inputs.itemById('length')
    length = length_input.value  # cm
    length_inches = length / 2.54

    height_input = inputs.itemById('height')
    height = height_input.value  # cm
    height_inches = height/2.54
    width_input = inputs.itemById('width')
    width = width_input.value  # cm

    # BoolValueCommandInput — .value is a plain bool
    is_3d_input = inputs.itemById('3d')
    is_3d = is_3d_input.value

    crossbeams_input = inputs.itemById('crossbeams')
    crossbeams = crossbeams_input.value

    triangular_input = inputs.itemById('triangular')
    triangular = triangular_input.value

    offset_input = inputs.itemById('offset')
    offset = offset_input.value
    offset_inches = offset/2.54

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())

    comp = occ.component

    frameSketch = comp.sketches.add(comp.xYConstructionPlane)
    extrudeProfile = None
    bottom_right = futil.pointFromOffset(futil.pZero, length_inches, 0)
    if triangular:
        depth = 2 if frame_type != 0 else 1
        corner_point = futil.pointFromOffset(futil.pZero, 0 , depth)
        apex_point = futil.pointFromOffset(futil.pZero, offset_inches, height_inches - depth)  #
        final_point = futil.pointFromOffset(futil.pZero, length_inches, depth)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(corner_point, apex_point)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(final_point, apex_point)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(corner_point, final_point)
        far_left = final_point.copy()
        far_right = corner_point.copy()
        top_left = apex_point.copy()
        vector = final_point.vectorTo(apex_point)
        vector = adsk.core.Vector3D.create(vector.y, -vector.x, 0)
        vector.normalize()
        vector.scaleBy(depth * 2.54)
        top_left.translateBy(vector)
        far_left.translateBy(vector)
        top_right = apex_point.copy()
        vector = corner_point.vectorTo(apex_point)
        vector = adsk.core.Vector3D.create(-vector.y, vector.x, 0)
        vector.normalize()
        vector.scaleBy(depth * 2.54)
        top_right.translateBy(vector)
        far_right.translateBy(vector)

        
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(futil.pZero, far_right)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(far_right, top_right)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(top_right, top_left)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(far_left, bottom_right)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(top_left, far_left)
        frameSketch.sketchCurves.sketchLines.addByTwoPoints(bottom_right, futil.pZero)


    else:
        frameSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pZero, futil.pointFromOffset(futil.pZero, length_inches, height_inches))
        depth = 2 if frame_type != 0 else 1
        frameSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, depth,  depth), futil.pointFromOffset(futil.pZero, length_inches - depth, height_inches - depth))
    extrudeProfile = frameSketch.profiles.item(0) if futil.bbox_area(frameSketch.profiles.item(0)) > futil.bbox_area(frameSketch.profiles.item(1)) else frameSketch.profiles.item(1)
    depth_inches = 1 if frame_type != 2 else 2
    plateExtrude = comp.features.extrudeFeatures.addSimple(extrudeProfile, adsk.core.ValueInput.createByReal(2.54 * (depth_inches)), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    if is_3d:
        mirrorPlaneInput = comp.constructionPlanes.createInput()
        mirrorPlaneInput.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(width/2))
        mirrorPlane= comp.constructionPlanes.add(mirrorPlaneInput)
        collection = adsk.core.ObjectCollection.create()
        collection.add(plateExtrude)
        comp.features.mirrorFeatures.add(comp.features.mirrorFeatures.createInput(collection, mirrorPlane))
    if crossbeams:
        crossbeamSketch = comp.sketches.add(comp.xYConstructionPlane)
        depth = 2 if frame_type != 0 else 1
        crossbeamSketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pZero, futil.pointFromOffset(futil.pZero, depth_inches, depth))
        crossbeamSketch.sketchCurves.sketchLines.addTwoPointRectangle(bottom_right, futil.pointFromOffset(bottom_right, -depth_inches, depth))
        collection = adsk.core.ObjectCollection.create()
        for profile in crossbeamSketch.profiles:
            collection.add(profile)
        comp.features.extrudeFeatures.addSimple(collection, adsk.core.ValueInput.createByReal(width), adsk.fusion.FeatureOperations.JoinFeatureOperation)

    futil.get_random_flat_color(occ, design, app)
    comp.name = f"Frame"
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
