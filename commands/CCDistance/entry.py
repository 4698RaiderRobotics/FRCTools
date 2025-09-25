import adsk.core
import adsk.fusion
import os
from ...lib import fusionAddInUtils as futil
from ... import config
from ...lib.CCLine import *
from . import CCLineUtils as ccutil

app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CREATE_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_CCDistanceDialog'
CREATE_CMD_NAME = 'C-C Distance'
CREATE_CMD_Description = 'Determine C-C distances for Gears and Belts'

EDIT_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_CCDistanceEdit'
EDIT_CMD_NAME = 'Edit C-C Distance'
EDIT_CMD_Description = 'Edit existing C-C Distance Object'

DELETE_CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_CCDistanceDelete'
DELETE_CMD_NAME = 'Delete C-C Distance'
DELETE_CMD_Description = 'Delete C-C Distance Object'

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

# Global variable to hold the selected CCLine in the UI and the command target CCLine
selected_CCLine = None
target_CCLine = None

motionTypes = ( 
    'Gears 20DP',
    'HTD 5mm Belt',
    'GT2 3mm Belt',
)
motionTypesDefault = motionTypes.index( 'Gears 20DP' )

pinionGears = (
    '8T (10T-CD)',
    '9T (10T-CD)',
    '10T (12T-CD)',
    '11T (12T-CD)',
    '12T',
    '12T (14T-CD)',
    '13T (14T-CD)',
    '14T',
    '14T (16T-CD)',
    '15T (16T-CD)',
    '16T'
)

pinionCenters = [ 10, 10, 12, 12, 12, 14, 14, 14, 16, 16, 16 ]
pinionTeeth   = [  8,  9, 10, 11, 12, 12, 13, 14, 14, 15, 16 ]
# idx              0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10
# idx => if center < 14:
#           idx = pinionTeeth - 8
#        elif center < 16:
#           idx = pinionTeeth - 7
#        else:
#           idx = pinionTeeth - 6
# used in edit_command_created()



# ===========
# ===========   START / STOP ROUTINES
# ===========

# Executed when add-in is run.
def start():

    # Create a command Definition.
    create_cmd_def = ui.commandDefinitions.addButtonDefinition(CREATE_CMD_ID, CREATE_CMD_NAME, CREATE_CMD_Description, ICON_FOLDER)
    edit_cmd_def = ui.commandDefinitions.addButtonDefinition(EDIT_CMD_ID, EDIT_CMD_NAME, EDIT_CMD_Description, ICON_FOLDER)
    delete_cmd_def = ui.commandDefinitions.addButtonDefinition(DELETE_CMD_ID, DELETE_CMD_NAME, DELETE_CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(create_cmd_def.commandCreated, command_created)
    futil.add_handler(edit_cmd_def.commandCreated, edit_command_created)
    futil.add_handler(delete_cmd_def.commandCreated, delete_command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Find the the FRCTools sketch create and modify submenus.
    create_submenu = config.get_sketch_create_submenu()
    modify_submenu = config.get_sketch_modify_submenu()

    # Create the button command control in the UI for creating a CCDistance.
    control = create_submenu.controls.addCommand(create_cmd_def)
    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

    # Create the button command control in the UI for editing a CCDistance.
    control = modify_submenu.controls.addCommand(edit_cmd_def)
    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

    # Listen for commandStarting, activeSelectionChanged, and markingMenuDisplaying events
    futil.add_handler( ui.commandStarting, ui_command_starting, local_handlers=ui_handlers )
    futil.add_handler( ui.activeSelectionChanged, ui_selection_changed, local_handlers=ui_handlers )
    futil.add_handler( ui.markingMenuDisplaying, ui_marking_menu, local_handlers=ui_handlers )

# Executed when add-in is stopped.
def stop():

    # Get the various UI elements for this command
    create_submenu = config.get_sketch_create_submenu()
    modify_submenu = config.get_sketch_modify_submenu()

    create_control = create_submenu.controls.itemById(CREATE_CMD_ID)
    edit_control = modify_submenu.controls.itemById(EDIT_CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CREATE_CMD_ID)
    edit_cmd_def = ui.commandDefinitions.itemById(EDIT_CMD_ID)
    delete_cmd_def = ui.commandDefinitions.itemById(DELETE_CMD_ID)

    # Delete the create CCDistance button control
    if create_control:
        create_control.isPromoted = False
        create_control.deleteMe()

    # Delete the edit CCDistance button control
    if edit_control:
        edit_control.isPromoted = False
        edit_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    # Delete the edit command definition
    if edit_cmd_def:
        edit_cmd_def.deleteMe()

    # Delete the delete command definition
    if delete_cmd_def:
        delete_cmd_def.deleteMe()

    global ui_handlers
    ui_handlers = []



# ===========
# ===========   User Interface ROUTINES
# ===========

# Function that is called right before a command starts.
# This functions does the following:
#   1. Keeps track of a selected CCLine for editing purposes.
#   2. Quietly discards any attempt to edit a sketch dimension on a CCLine.
#   3. Redirects any delete command to delete the entire CCLine.
#
def ui_command_starting(args: adsk.core.ApplicationCommandEventArgs):

    global selected_CCLine, target_CCLine
    # futil.log(f' Command Starting={args.commandDefinition.name}, selected_CCLine ={selected_CCLine}')

    # If a CCLine is not selected then just return
    if not selected_CCLine :
        return

    # Move the selected_CCLine into the target_CCLine for possible use by this command
    # because firing a command clears the SelectCommand so the current selection
    # must be kept or it will be set to None in ui_selection_changed()
    # This variable is set to None in the destroy() callback of the commands
    target_CCLine = selected_CCLine

    # Kill the editing of the dimensions within the CCLine
    if args.commandDefinition.name == 'Edit Sketch Dimension' :
        args.isCanceled = True

    # Redirect the deleting of the CCLine to the deleteCCLine() command
    if args.commandDefinition.name == 'Delete' :
        args.isCanceled = True
        delete_cmd_def = ui.commandDefinitions.itemById( DELETE_CMD_ID )
        delete_cmd_def.execute()

# Function that is called when a active selection is changed in the UI.
# Set selected_CCLine if the current selection is part of a CCLine or None if not.
def ui_selection_changed(args: adsk.core.ActiveSelectionEventArgs):

    global selected_CCLine

    # futil.log(f' Selection Changed: at start ccLine={selected_CCLine}')
#    args.firingEvent.name
    selected_CCLine = None
    if len( args.currentSelection ) == 1:
        selected_CCLine = getCCLineFromEntity( args.currentSelection[0].entity )
    
    # futil.log(f'                    at end ccLine={selected_CCLine}')

# Function that is called when the marking menu is going to be displayed.
def ui_marking_menu(args: adsk.core.MarkingMenuEventArgs):

    controls = args.linearMarkingMenu.controls

    # futil.log(f' Active Workspace = {app.activeProduct}')
    if app.activeProduct.objectType != adsk.fusion.Design.classType() :
        return

    # Gather the Mtext command
    editMTextCmd = controls.itemById( 'EditMTextCmd' )

    # Make a list of the controls to turn off
    hideCtrls = [editMTextCmd]
    hideCtrls.append( controls.itemById( 'ExplodeTextCmd' ) )
    hideCtrls.append( controls.itemById( 'ToggleDrivenDimCmd' ) )
    hideCtrls.append( controls.itemById( 'ToggleRadialDimCmd' ) )

    editCCLineMenuItem = controls.itemById( EDIT_CMD_ID )
    if not editCCLineMenuItem:
        edit_cmd_def = ui.commandDefinitions.itemById(EDIT_CMD_ID)
        # Find the separator before the "Edit Text" command and add our commands after it
        i = editMTextCmd.index - 1
        while i > 0:
            control = controls.item( i )
            if control.objectType == adsk.core.SeparatorControl.classType():
                control = controls.item( i + 1 )
                break
            i -= 1
        editCCLineMenuItem = controls.addCommand( edit_cmd_def, control.id, True )
        editCCLineSep = controls.addSeparator( "EditCCLineSeparator", editCCLineMenuItem.id, False )

    editCCLineSep = controls.itemById( "EditCCLineSeparator" )

    if len(args.selectedEntities) == 1:
        ccLine = getCCLineFromEntity( args.selectedEntities[0] )
        # for control in controls:
        #     if control.objectType == adsk.core.SeparatorControl.classType():
        #         sep: adsk.core.SeparatorControl = control
        #         # futil.log(f'Separator = {sep.id} at index {sep.index}')
        #     elif control.isVisible :
        #         futil.log(f'marking menu = {control.id} ,{control.isVisible}')
        if ccLine:
            editCCLineMenuItem.isVisible = True
            editCCLineSep.isVisible = True
            for ctrl in hideCtrls:
                try:
                    ctrl.isVisible = False
                except:
                    None
            return
        
    editCCLineMenuItem.isVisible = False
    editCCLineSep.isVisible = False



# ===========
# ===========   Edit Command ROUTINES
# ===========

# Creating the edit command dialog
def edit_command_created(args: adsk.core.CommandCreatedEventArgs):
    global target_CCLine
    
    # futil.log(f'{args.command.parentCommandDefinition.name} edit_command_created()')

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, edit_command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, edit_command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Motion Component Type
    motionType: adsk.core.DropDownCommandInput = inputs.addDropDownCommandInput('motion_type', 'Motion Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    for mtype in motionTypes:
        motionType.listItems.add( mtype, True, '')
    motionType.listItems.item( motionTypesDefault ).isSelected = True

    # Create a selection input.
    curveSelection = inputs.addSelectionInput('curve_selection', 'Selection', 'Select a C-C Distance object')
    curveSelection.addSelectionFilter( "SketchCircles" )
    curveSelection.addSelectionFilter( "SketchLines" )
    curveSelection.addSelectionFilter( "SketchConstraints" )
    curveSelection.addSelectionFilter( "Texts" )
    curveSelection.setSelectionLimits( 1, 1 )

    # Create a separator.
    inputs.addSeparatorCommandInput( "selection_cog1_sep")

    # Create a integer spinners for cog1 and pinion options.
    cog1Teeth = inputs.addIntegerSpinnerCommandInput('cog1_teeth', 'Cog #1 Teeth', 6, 100, 1, 36)
    group1CmdInput = inputs.addGroupCommandInput('use_pinion_cog1', 'Use Pinion')
    group1CmdInput.isExpanded = False
    group1CmdInput.isEnabledCheckBoxDisplayed = True
    group1CmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = group1CmdInput.children
    pinion_cog1 = groupChildInputs.addDropDownCommandInput('pinion_cog1', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog1.listItems.add( gear, True, '')

     # Create a integer spinners for cog1 and pinion options.
    cog2Teeth = inputs.addIntegerSpinnerCommandInput('cog2_teeth', 'Cog #2 Teeth', 6, 100, 1, 24)
    group2CmdInput = inputs.addGroupCommandInput('use_pinion_cog2', 'Use Pinion')
    group2CmdInput.isExpanded = False
    group2CmdInput.isEnabledCheckBoxDisplayed = True
    group2CmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = group2CmdInput.children
    pinion_cog2 = groupChildInputs.addDropDownCommandInput('pinion_cog2', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog2.listItems.add( gear, True, '')

    # Addendum Gear Overrides

    swap_cogs = inputs.addBoolValueInput( "swap_cogs", "Swap Cogs", True )

    beltTeeth = inputs.addIntegerSpinnerCommandInput( "belt_teeth", "Belt Teeth", 35, 400, 1, 70 )
    beltTeeth.isVisible = False

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.003')
    extraCenter = inputs.addValueInput('extra_center', 'Extra Center', defaultLengthUnits, default_value)
    extraCenter.isVisible = False

    # Create a separator.
    inputs.addSeparatorCommandInput( "message_sep")
    status = inputs.addTextBoxCommandInput( "status_msg", "", "Gear", 1, True )

    if not target_CCLine:
        status.formattedText = '<div align="center">Select a C-C Distance object.</div>'
        disable_edit_inputs( inputs )
        return 
    
    initialize_input_state( inputs, target_CCLine.data )
    set_ccline_selection( curveSelection, target_CCLine )


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def edit_command_input_changed(args: adsk.core.InputChangedEventArgs):
    global target_CCLine

    changed_input = args.input
    # inputs = args.inputs
    inputs = args.input.parentCommand.commandInputs

    # General logging for debug.
    # futil.log(f'{args.firingEvent.name} Input Changed Event fired from a change to {changed_input.id}')

    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    curveSelection: adsk.core.SelectionCommandInput = inputs.itemById('curve_selection')
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
    cog1Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog1')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
    cog2Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog2')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    extraCenter: adsk.core.ValueInput = inputs.itemById('extra_center')
    swapCogsInp = inputs.itemById( "swap_cogs" )
    status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

    if changed_input.id == 'motion_type':
        if motionType.selectedItem.index == 0:  
            # Gear type is selected
            extraCenter.value = 0.003 * 2.54
            cog1Group.isVisible = True
            cog2Group.isVisible = True
            beltTeeth.isVisible = False
        else:
            # Non-gear type is selected
            extraCenter.value = 0
            cog1Teeth.isVisible = True
            cog1Group.isVisible = False
            cog1Group.isEnabledCheckBoxChecked = False
            cog2Teeth.isVisible = True
            cog2Group.isVisible = False
            cog2Group.isEnabledCheckBoxChecked = False
            if beltTeeth.value == 0 :
                beltTeeth.value = 70
            beltTeeth.isVisible = True

    if changed_input.id == 'curve_selection':
        # Check if we have a previously configured CCLine selected or one of its children entities
        ccLine = None
        if curveSelection.selectionCount == 1 or curveSelection.selectionCount == 4:
            if curveSelection.selectionCount == 4:
                lastSelected = curveSelection.selection(3).entity
                curveSelection.clearSelection()
                curveSelection.addSelection( lastSelected )
                target_CCLine = None

            ccLine = getParentLine( curveSelection.selection(0).entity )
            
            if ccLine:
                swapCogsInp.value = False
                # futil.log(f'    ==========  Selected an existing CCLine.')
                target_CCLine = getCCLineFromEntity( ccLine )
                initialize_input_state( inputs, target_CCLine.data )
                
            else:
                disable_edit_inputs( inputs )
                target_CCLine = None
                status.formattedText = '<div align="center"><font color="red">Not a C-C Distance object!!</font></div>'

        else:
            disable_edit_inputs( inputs )
            target_CCLine = None
            status.formattedText = '<div align="center">Select a C-C Distance object.</div>'

        set_ccline_selection( curveSelection, target_CCLine )

    if changed_input.id == 'use_pinion_cog1':
        if cog1Group.isEnabledCheckBoxChecked:
            # We are using a pinion for cog 1
            cog1Teeth.isVisible = False
            cog1Teeth.value = pinionCenters[ cog1Pinion.selectedItem.index ]
        else:
            # We are not using a pinion 
            cog1Teeth.isVisible = True

    if changed_input.id == 'pinion_cog1':
        cog1Teeth.value = pinionCenters[ cog1Pinion.selectedItem.index ]


    if changed_input.id == 'use_pinion_cog2':
        if cog2Group.isEnabledCheckBoxChecked:
            # We are using a pinion for cog 2
            cog2Teeth.isVisible = False
            cog2Teeth.value = pinionCenters[ cog2Pinion.selectedItem.index ]
        else:
            # We are not using a pinion 
            cog2Teeth.isVisible = True

    if changed_input.id == 'pinion_cog2':
        cog2Teeth.value = pinionCenters[ cog2Pinion.selectedItem.index ]

# This event handler is called when the command needs to compute a new preview in the graphics window.
def edit_command_preview(args: adsk.core.CommandEventArgs):
    global target_CCLine

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Preview Event')

    if not target_CCLine:
        return

    command_execute( args )


def disable_edit_inputs( inputs: adsk.core.CommandInputs ):

    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    select_sep: adsk.core.SeparatorCommandInput = inputs.itemById( "selection_cog1_sep")
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    extraCenter: adsk.core.ValueInput = inputs.itemById('extra_center')
    swap_cogs = inputs.itemById( "swap_cogs" )

    motionType.isVisible = False
    select_sep.isVisible = False
    cog1Teeth.isVisible = False
    cog1Group.isVisible = False
    cog2Teeth.isVisible = False
    cog2Group.isVisible = False
    beltTeeth.isVisible = False
    extraCenter.isVisible = False
    swap_cogs.isVisible = False

def initialize_input_state( inputs: adsk.core.CommandInputs, lineData: CCLineData ):
        # Fill the inputs with the ccLine info

    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    select_sep: adsk.core.SeparatorCommandInput = inputs.itemById( "selection_cog1_sep")
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
    cog1Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog1')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
    cog2Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog2')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    extraCenter: adsk.core.ValueInput = inputs.itemById('extra_center')
    swap_cogs = inputs.itemById( "swap_cogs" )
    status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

    motionType.isVisible = True
    select_sep.isVisible = True
    swap_cogs.isVisible = True
    extraCenter.isVisible = True
    cog1Teeth.isVisible = True
    cog2Teeth.isVisible = True

    cog1Teeth.value = lineData.N1
    cog2Teeth.value = lineData.N2
    if lineData.PIN1 > 0 :
        cog1Group.isEnabledCheckBoxChecked = True
        cog1Teeth.isVisible = False
        if lineData.N1 < 14:
            idx = lineData.PIN1 - 8
        elif lineData.N1 < 16:
            idx = lineData.PIN1 - 7
        else:
            idx = lineData.PIN1 - 6
        cog1Pinion.listItems.item( idx ).isSelected = True

    if lineData.PIN2 > 0 :
        cog2Group.isEnabledCheckBoxChecked = True
        cog2Teeth.isVisible = False
        if lineData.N2 < 14:
            idx = lineData.PIN2 - 8
        elif lineData.N2 < 16:
            idx = lineData.PIN2 - 7
        else:
            idx = lineData.PIN2 - 6
        cog2Pinion.listItems.item( idx ).isSelected = True

    if lineData.motion == 0 :
        beltTeeth.isVisible = False
        cog1Group.isVisible = True
        cog2Group.isVisible = True
    else:
        beltTeeth.value = lineData.Teeth
        beltTeeth.isVisible = True
        cog1Group.isVisible = False
        cog2Group.isVisible = False

    extraCenter.value = lineData.ExtraCenterIN * 2.54
    motionType.listItems.item( lineData.motion ).isSelected = True

    msg = f'<div align="center">{ccutil.createLabelString( lineData )}</div>'
    status.formattedText = msg


def set_ccline_selection( sel: adsk.core.SelectionCommandInput, ccline: CCLine ):

    if not ccline:
        sel.setSelectionLimits( 1, 1 )
        return

    sel.clearSelection()
    sel.setSelectionLimits( 3, 4 )
    sel.addSelection( ccline.line )
    sel.addSelection( ccline.ODCircle1 )
    sel.addSelection( ccline.ODCircle2 )


# ===========
# ===========   Create Command ROUTINES
# ===========

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Motion Component Type
    motionType = inputs.addDropDownCommandInput('motion_type', 'Motion Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    for mtype in motionTypes:
        motionType.listItems.add( mtype, True, '')
    motionType.listItems.item( motionTypesDefault ).isSelected = True

    # Create a selection input.
    curveSelection = inputs.addSelectionInput('curve_selection', 'Selection', 'Select a circle, or a center point')
    curveSelection.addSelectionFilter( "SketchCircles" )
    curveSelection.addSelectionFilter( "SketchLines" )
    curveSelection.addSelectionFilter( "SketchPoints" )
    curveSelection.setSelectionLimits( 1, 1 )

    inputs.addBoolValueInput( "require_selection", "Require Selection", True, "", True )

    # Create a separator.
    inputs.addSeparatorCommandInput( "selection_cog1_sep")

    # Create a integer spinners for cog1 and pinion options.
    inputs.addIntegerSpinnerCommandInput('cog1_teeth', 'Cog #1 Teeth', 6, 100, 1, 24)
    groupCmdInput = inputs.addGroupCommandInput('use_pinion_cog1', 'Use Pinion')
    groupCmdInput.isExpanded = False
    groupCmdInput.isEnabledCheckBoxDisplayed = True
    groupCmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = groupCmdInput.children
    pinion_cog1 = groupChildInputs.addDropDownCommandInput('pinion_cog1', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog1.listItems.add( gear, True, '')


     # Create a integer spinners for cog1 and pinion options.
    inputs.addIntegerSpinnerCommandInput('cog2_teeth', 'Cog #2 Teeth', 6, 100, 1, 36)
    groupCmdInput = inputs.addGroupCommandInput('use_pinion_cog2', 'Use Pinion')
    groupCmdInput.isExpanded = False
    groupCmdInput.isEnabledCheckBoxDisplayed = True
    groupCmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = groupCmdInput.children
    pinion_cog2 = groupChildInputs.addDropDownCommandInput('pinion_cog2', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog2.listItems.add( gear, True, '')

    inputs.addBoolValueInput( "swap_cogs", "Swap Cogs", True )

    beltTeeth = inputs.addIntegerSpinnerCommandInput( "belt_teeth", "Belt Teeth", 35, 400, 1, 70 )
    beltTeeth.isVisible = False

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.003')
    inputs.addValueInput('extra_center', 'Extra Center', defaultLengthUnits, default_value)

    # Create a separator.
    inputs.addSeparatorCommandInput( "message_sep")
    inputs.addTextBoxCommandInput( "status_msg", "", "Gear 20DP 24T+36T EC(0.003)", 1, True )

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    global target_CCLine

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Execute Event')

    ccLine = CCLine()

    # Get a reference to the command's inputs.
    inputs = args.command.commandInputs
    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type' )
    curveSelection: adsk.core.SelectionCommandInput = inputs.itemById('curve_selection')
    cog1TeethInp: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
    cog1Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog1')
    cog2TeethInp: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
    cog2Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog2')
    swapCogs = inputs.itemById( "swap_cogs" ).value
    beltTeethInp: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    extraCenterInp: adsk.core.ValueInput = inputs.itemById('extra_center')
    status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

    startSketchPt = None
    endSketchPt = None

    if not curveSelection or curveSelection.selectionCount == 3:
        ccLine = target_CCLine
    elif curveSelection.selectionCount == 1 :
        selEntity = curveSelection.selection(0).entity
        if selEntity.objectType == adsk.fusion.SketchCircle.classType() :
            startSketchPt = selEntity.centerSketchPoint
        elif selEntity.objectType == adsk.fusion.SketchLine.classType() :
            if isCCLine( selEntity ) :
                ccLine.line = selEntity
            else :
                startSketchPt = selEntity.startSketchPoint
        else :
            startSketchPt = selEntity

    if ccLine.line == None:
        ccLine.line = ccutil.createCCLine( startSketchPt, endSketchPt )
    elif isCCLine( ccLine.line ):
        ccLine = getCCLineFromEntity( ccLine.line )

    ccLine.data.ExtraCenterIN = extraCenterInp.value / 2.54
    ccLine.data.Teeth = int(beltTeethInp.value)
    ccLine.data.N1 = int(cog1TeethInp.value)
    if cog1Group.isEnabledCheckBoxChecked :
        ccLine.data.PIN1 = pinionTeeth[ cog1Pinion.selectedItem.index ]
    else:
        ccLine.data.PIN1 = 0
    ccLine.data.N2 = int(cog2TeethInp.value)
    if cog2Group.isEnabledCheckBoxChecked :
        ccLine.data.PIN2 = pinionTeeth[ cog2Pinion.selectedItem.index ]
    else:
        ccLine.data.PIN2 = 0
    ccLine.data.motion = motionType.selectedItem.index

    if swapCogs :
        tempN = ccLine.data.N1
        ccLine.data.N1 = ccLine.data.N2
        ccLine.data.N2 = tempN
        tempN = ccLine.data.PIN1
        ccLine.data.PIN1 = ccLine.data.PIN2
        ccLine.data.PIN2 = tempN

    preview = False
    if args.firingEvent.name == "OnExecutePreview" :
        preview = True

    if not isCCLine( ccLine.line ):
        ccutil.calcCCLineData( ccLine.data )
        if ccLine.data.ccDistIN < 0.001:
            return
        ccutil.dimAndLabelCCLine( ccLine )
        ccutil.createEndCircles( ccLine )
    else:
        ccutil.calcCCLineData( ccLine.data )
        if ccLine.data.ccDistIN < 0.001:
            return
        ccutil.modifyCCLine( ccLine )

    msg = f'<div align="center">{ccutil.createLabelString( ccLine.data )}</div>'
    status.formattedText = msg
    if not preview :
        setCCLineAttributes( ccLine )


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Preview Event')

    command_execute( args )

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    # inputs = args.inputs
    inputs = args.input.parentCommand.commandInputs

    # General logging for debug.
    # futil.log(f'{args.firingEvent.name} command_input_changed() from a change to {changed_input.id}')

    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    curveSelection: adsk.core.SelectionCommandInput = inputs.itemById('curve_selection')
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
    cog1Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog1')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
    cog2Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog2')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    extraCenter: adsk.core.ValueInput = inputs.itemById('extra_center')
    swapCogsInp = inputs.itemById( "swap_cogs" )
    requireSelectionInp = inputs.itemById( "require_selection" )

    if changed_input.id == 'motion_type':
        if motionType.selectedItem.index == 0:  
            # Gear type is selected
            extraCenter.value = 0.003 * 2.54
            cog1Group.isVisible = True
            cog2Group.isVisible = True
            beltTeeth.isVisible = False
        else:
            # Non-gear type is selected
            extraCenter.value = 0
            cog1Teeth.isVisible = True
            cog1Group.isVisible = False
            cog1Group.isEnabledCheckBoxChecked = False
            cog2Teeth.isVisible = True
            cog2Group.isVisible = False
            cog2Group.isEnabledCheckBoxChecked = False
            if beltTeeth.value == 0 :
                beltTeeth.value = 70
            beltTeeth.isVisible = True


    if changed_input.id == 'require_selection':
        if requireSelectionInp.value:
            curveSelection.isVisible = True
            curveSelection.setSelectionLimits( 1, 2 )
        else:
            curveSelection.isVisible = False
            curveSelection.setSelectionLimits( 0, 2 )
            curveSelection.clearSelection()

    if changed_input.id == 'use_pinion_cog1':
        if cog1Group.isEnabledCheckBoxChecked:
            # We are using a pinion for cog 1
            cog1Teeth.isVisible = False
            cog1Teeth.value = pinionCenters[ cog1Pinion.selectedItem.index ]
        else:
            # We are not using a pinion 
            cog1Teeth.isVisible = True

    if changed_input.id == 'pinion_cog1':
        cog1Teeth.value = pinionCenters[ cog1Pinion.selectedItem.index ]


    if changed_input.id == 'use_pinion_cog2':
        if cog2Group.isEnabledCheckBoxChecked:
            # We are using a pinion for cog 2
            cog2Teeth.isVisible = False
            cog2Teeth.value = pinionCenters[ cog2Pinion.selectedItem.index ]
        else:
            # We are not using a pinion 
            cog2Teeth.isVisible = True

    if changed_input.id == 'pinion_cog2':
        cog2Teeth.value = pinionCenters[ cog2Pinion.selectedItem.index ]


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    inputs = args.inputs
    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

#    futil.log(f'{args.firingEvent.name} Command Validate Event, Motion={motionType.selectedItem.index}, N1={cog1Teeth.value}, N2={cog2Teeth.value}, T={beltTeeth.value}')

    if not (cog1Teeth.value >= 6 and cog1Teeth.value < 100 and cog2Teeth.value >= 6 and cog1Teeth.value < 100 ):
        status.formattedText = '<div align="center"><font color="red">Invalid Number of cog teeth! [6-100]</font></div>'
        args.areInputsValid = False
        return
    
    ld = CCLineData()
    ld.motion = motionType.selectedItem.index
    ld.N1 = cog1Teeth.value
    ld.N2 = cog2Teeth.value
    ld.Teeth = beltTeeth.value
    ccutil.calcCCLineData( ld )
    if ld.motion != 0 and ld.ccDistIN < (ld.OD1 + ld.OD2) / 2.0 :
        # belt is too short
        status.formattedText = '<div align="center"><font color="red">Belt is too short!</font></div>'
        args.areInputsValid = False
        return

    args.areInputsValid = True        

# This event handler is called when the create or edit commands terminate.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers, target_CCLine

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []
    target_CCLine = None



# ===========
# ===========   Delete Command ROUTINES
# ===========

#  Setup the delete command handlers
def delete_command_created(args: adsk.core.CommandCreatedEventArgs):

    # futil.log(f'{args.command.parentCommandDefinition.name} Delete Command Created Event')

    futil.add_handler(args.command.execute, delete_command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, delete_command_destroy, local_handlers=local_handlers)

def delete_command_execute(args: adsk.core.CommandEventArgs):
    global target_CCLine

#    futil.log(f'Delete Command Executed Event ccLine={target_CCLine}')
    deleteCCLine( target_CCLine )

def delete_command_destroy(args: adsk.core.CommandEventArgs):
    global target_CCLine

    target_CCLine = None



