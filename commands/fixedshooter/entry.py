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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Fixed'
CMD_NAME = 'Fixed Hood Shooter'
CMD_Description = 'Creates a fixed hood shooter'

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
        inputs.addValueInput('diameter', 'Flywheel Diameter', defaultLengthUnits, adsk.core.ValueInput.createByString('4 in'))
        inputs.addValueInput('compression', 'Gamepiece Compression', defaultLengthUnits, adsk.core.ValueInput.createByString('0.5 in'))
        inputs.addValueInput('ball_diameter', 'Game Piece Diameter', defaultLengthUnits, adsk.core.ValueInput.createByString('9.5 in'))
        inputs.addValueInput('width', "Shooter Width", defaultLengthUnits, adsk.core.ValueInput.createByString('10 in'))
        inputs.addAngleValueCommandInput('angle', 'Release Angle from Horizontal', adsk.core.ValueInput.createByReal(math.radians(45)))
        inputs.addValueInput('roller_diameter', "Hood Roller Diameter", defaultLengthUnits, adsk.core.ValueInput.createByString('2 in'))
        inputs.addIntegerSliderListCommandInput('count', "Hood Roller Count", [0,1,2,3])

        
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
    try:
        inputs = args.command.commandInputs
        diameter_input = inputs.itemById('diameter')
        diameter = diameter_input.value  # cm

        compression_input = inputs.itemById('compression')
        compression = compression_input.value  # cm
        compression_inches = compression/2.54

        ball_diameter_input = inputs.itemById('ball_diameter')
        ball_diameter = ball_diameter_input.value  # cm
        ball_diameter_inches = ball_diameter/2.54
        width_input = inputs.itemById('width')
        width = width_input.value  # cm

        # AngleValueCommandInput — .value is in radians
        angle_input = inputs.itemById('angle')
        angle = angle_input.value  # radians
        angle_deg = math.degrees(angle)

        roller_diameter_input = inputs.itemById('roller_diameter')
        roller_diameter = roller_diameter_input.value  # cm

        # IntegerSliderListCommandInput — .valueOne gives the selected value from the list
        count_input = inputs.itemById('count')
        roller_count = count_input.valueOne  # int, one of [0,1,2,3]
        diameter_inches = diameter/2.54
        offset_inches = 0 if roller_count == 0 else roller_diameter/2.54
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        comp = occ.component
        plate_sketch = comp.sketches.add(comp.xYConstructionPlane)
        circle = plate_sketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pZero, diameter/2 + 0.0625*2.54)
        p1 = futil.pointFromOffset(futil.pZero, diameter_inches/2 + 0.0625, 0)
        plate_sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches + 0.5 + offset_inches), -diameter_inches/2 - 0.0625))
        arc = plate_sketch.sketchCurves.sketchArcs.addByCenterStartSweep(futil.pZero, futil.pointFromOffset(futil.pZero, -(offset_inches + diameter_inches/2 + ball_diameter_inches - compression_inches + 0.5),0 ), -angle)
        line = plate_sketch.sketchCurves.sketchLines.addByTwoPoints(futil.pointFromOffset(futil.pZero, 0, ball_diameter_inches/2), arc.startSketchPoint.worldGeometry)
        circle.isFixed = True
        arc.isFixed = True
        plate_sketch.geometricConstraints.addCoincident(line.endSketchPoint, arc.startSketchPoint)
        plate_sketch.geometricConstraints.addTangent(line, circle)
        plate_sketch.geometricConstraints.addCoincident(line.startSketchPoint, circle)
        collection = adsk.core.ObjectCollection.create()
        for profile in plate_sketch.profiles:
            collection.add(profile)
        extrude = comp.features.extrudeFeatures.createInput(collection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extrude.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(2.54*0.125)), adsk.fusion.ExtentDirections.NegativeExtentDirection)
        feature = comp.features.extrudeFeatures.add(extrude)
        middle_sketch = comp.sketches.add(comp.xYConstructionPlane)
        middle_sketch.sketchCurves.sketchCircles.addByCenterRadius(futil.pZero, diameter/2)
        middle_sketch.sketchCurves.sketchLines.addTwoPointRectangle(futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches + offset_inches), 0), futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches + 0.5 + offset_inches), -diameter_inches/2 - 0.0625))
        startPoint = futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches + offset_inches/2), 0)
        if roller_count == 0:
            arc1 = middle_sketch.sketchCurves.sketchArcs.addByCenterStartSweep(futil.pZero, futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches + 0.5),0 ), -angle)
            arc2 = middle_sketch.sketchCurves.sketchArcs.addByCenterStartSweep(futil.pZero, futil.pointFromOffset(futil.pZero, -(diameter_inches/2 + ball_diameter_inches - compression_inches),0 ), -angle)
            middle_sketch.sketchCurves.sketchLines.addByTwoPoints(arc1.startSketchPoint, arc2.startSketchPoint)
        else:
            
            spacing = angle/(roller_count-1)
            rotationMatrix = adsk.core.Matrix3D.create()
            
            for i in range (roller_count):
                rotationMatrix.setToRotation(-(spacing * i), adsk.core.Vector3D.create(0,0,1), futil.pZero)
                copyPoint = startPoint.copy()
                copyPoint.transformBy(rotationMatrix)
                middle_sketch.sketchCurves.sketchCircles.addByCenterRadius(copyPoint, roller_diameter/2)
            
        collection.clear()
        for profile in middle_sketch.profiles:
            collection.add(profile)
        extrude = comp.features.extrudeFeatures.createInput(collection, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        extrude.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(width)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        comp.features.extrudeFeatures.add(extrude)
        plane = comp.constructionPlanes.createInput()
        plane.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(width/2))
        realPlane = comp.constructionPlanes.add(plane)
        featureCollection = adsk.core.ObjectCollection.create()
        featureCollection.add(feature)
        mirrorInput = comp.features.mirrorFeatures.createInput(featureCollection, realPlane)
        comp.features.mirrorFeatures.add(mirrorInput)
        futil.get_random_flat_color(occ, design, app)
        comp.name = f"Fixed Shooter"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
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
