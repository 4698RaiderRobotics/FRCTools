import adsk.core
import adsk.fusion
import os
import math
import typing
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_BoltPatternDialog'
CMD_NAME = 'FRC Bolt Pattern'
CMD_Description = 'Create a bolt pattern for common FRC motors'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Local list of ui event handlers used to maintain a reference so
# they are not released and garbage collected.
ui_handlers = []

# Bolt Pattern struct
class BoltPattern(typing.NamedTuple) :
    name: str = ""
    centerDia: float = 0.0
    patternDia: float = 0.0
    holeSize: float = 0.0
    numberOfHoles: int = 0
    suppression: list[int] = []

# Selection of Bolt Patterns
bolt_patterns: list[BoltPattern] = [
    # Name, center hole radius, pattern radius, hole size, # of holes, suppression
    BoltPattern('Kraken X60', 0.75, 2.0, 0.196, 12, [0,0,0,0,0,0,0,0,0,0,0,1]),
    BoltPattern('Kraken X44', 0.75, 1.375, 0.196, 12, [0,0,0,0,0,0,0,0,0,0,0,1]),
    BoltPattern('NEO Vortex', 0.75, 2.0, 0.196, 8, [0,0,0,1,0,0,0,1]),
    BoltPattern('NEO 550', 0.5118, 0.9843, 0.125, 4, []),
    BoltPattern('REV MAXPlanetary', 1.125, 2.0, 0.196, 8, [0,0,1,1,0,0,1,1]),
    BoltPattern('2" MultiMotor', 0.75, 2.0, 0.196, 24, [0,1,0,0,0,1, 0,1,0,0,0,1, 0,1,0,0,0,1, 0,1,0,0,0,1]),
]

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Find the the FRCTools submenu.
    submenu = config.get_sketch_submenu()

    # Create the button command control in the UI.
    control = submenu.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

# Executed when add-in is stopped.
def stop():
    global edit_cmd_def

    # Get the various UI elements for this command
    submenu = config.get_sketch_submenu()
    command_control = submenu.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.isPromoted = False
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    global ui_handlers
    ui_handlers = []

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):

    # General logging for debug.
    # futil.log(f'{CMD_NAME} command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create a selection input.
    centerSelection = inputs.addSelectionInput('center_selection', 'Center', 'Select the center of the bolt pattern')
    centerSelection.addSelectionFilter( "SketchPoints" )
    centerSelection.addSelectionFilter( "SketchCircles" )
    centerSelection.setSelectionLimits( 1, 1 )

    # Bolt Patterns
    boltPattern = inputs.addDropDownCommandInput('bolt_pattern', 'Bolt Pattern', adsk.core.DropDownStyles.TextListDropDownStyle)
    for bp in bolt_patterns:
        boltPattern.listItems.add( bp.name, True, '')
    boltPattern.listItems.item( 0 ).isSelected = True


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
    # futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    boltPatternInp: adsk.core.DropDownCommandInput = inputs.itemById('bolt_pattern')
    centerSelection: adsk.core.SelectionCommandInput = inputs.itemById('center_selection')

    centerPt: adsk.fusion.SketchPoint = None
    selectedEntity = centerSelection.selection(0).entity
    if selectedEntity.objectType == adsk.fusion.SketchCircle.classType() :
        centerPt = selectedEntity.centerSketchPoint
    elif selectedEntity.objectType == adsk.fusion.SketchPoint.classType() :
        centerPt = selectedEntity
    else :
        futil.popup_error( f'  Cannot handle object type = {selectedEntity.objectType}')
        return
    
    boltPattern = bolt_patterns[ boltPatternInp.selectedItem.index ]
    sketch = centerPt.parentSketch

    # Create the bolt pattern center hole
    centerHole = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, boltPattern.centerDia * 2.54 / 2 )
    textPt = futil.offsetPoint3D( centerHole.centerSketchPoint.geometry, boltPattern.centerDia/4, boltPattern.centerDia/4, 0 )
    centerDim = sketch.sketchDimensions.addDiameterDimension( centerHole, textPt )
    centerDim.value = boltPattern.centerDia * 2.54

    # Create the bolt pattern bolt circle
    boltCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( centerPt, boltPattern.patternDia * 2.54 / 2 )
    boltCircle.isConstruction = True
    textPt = futil.offsetPoint3D( boltCircle.centerSketchPoint.geometry, -boltPattern.patternDia/4, boltPattern.patternDia/4, 0 )
    boltCirDim = sketch.sketchDimensions.addDiameterDimension( boltCircle, textPt )
    boltCirDim.value = boltPattern.patternDia * 2.54

    # Create a single bolt hole
    boltCenter = adsk.core.Point3D.create( boltPattern.patternDia * 2.54 / 2, boltPattern.patternDia/4, 0 )
    boltHole = sketch.sketchCurves.sketchCircles.addByCenterRadius( boltCenter, boltPattern.holeSize * 2.54 / 2 )
    sketch.geometricConstraints.addCoincident( boltHole.centerSketchPoint, boltCircle )
    textPt = futil.offsetPoint3D( boltHole.centerSketchPoint.geometry, boltPattern.holeSize/4, boltPattern.holeSize/4, 0 )
    boltDim = sketch.sketchDimensions.addDiameterDimension( boltHole, textPt )
    boltDim.value = boltPattern.holeSize * 2.54

    # Create the hole pattern
    cirPattern = sketch.geometricConstraints.createCircularPatternInput( [boltHole], centerPt )
    # cirPattern.totalAngle = 2 * math.pi
    cirPattern.quantity = futil.Value(boltPattern.numberOfHoles)

    if len(boltPattern.suppression) > 0:
        boolSuppression = []
        for s in boltPattern.suppression :
            boolSuppression.append( s == 1 )
        # Remove first element bc it cannot be suppressed
        boolSuppression.pop(0)
        cirPattern.isSuppressed = boolSuppression

    sketch.geometricConstraints.addCircularPattern( cirPattern )

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Preview Event')

    command_execute( args )
    args.isValidResult = True


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    # futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')



# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    # futil.log(f'{CMD_NAME} Command Validate Event')

    inputs = args.inputs

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
