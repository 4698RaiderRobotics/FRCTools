import adsk.core
import adsk.fusion
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config
from ...lib.CCLine import *

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
    '8T (10TCD)',
    '9T (10TCD)',
    '10T (12TCD)',
    '11T (12TCD)',
    '12T',
    '12T (14TCD)',
    '13T (14TCD)',
    '14T',
    '14T (16TCD)',
    '15T (16TCD)',
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

# Executed when add-in is run.
def start():

    # Create a command Definition.
    create_cmd_def = ui.commandDefinitions.addButtonDefinition(CREATE_CMD_ID, CREATE_CMD_NAME, CREATE_CMD_Description, ICON_FOLDER)
    edit_cmd_def = ui.commandDefinitions.addButtonDefinition(EDIT_CMD_ID, EDIT_CMD_NAME, EDIT_CMD_Description, ICON_FOLDER)
    delete_cmd_def = ui.commandDefinitions.addButtonDefinition(DELETE_CMD_ID, DELETE_CMD_NAME, "Delete CCLine", ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(create_cmd_def.commandCreated, command_created)
    futil.add_handler(edit_cmd_def.commandCreated, edit_command_created)
    futil.add_handler(delete_cmd_def.commandCreated, delete_command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Find the the FRCTools sketch submenu.
    submenu = config.get_sketch_submenu()

    # Create the button command control in the UI.
    control = submenu.controls.addCommand(create_cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

    # Listen for activeSelectionChanged events
    futil.add_handler( ui.commandStarting, ui_command_starting, local_handlers=ui_handlers )
    futil.add_handler( ui.activeSelectionChanged, ui_selection_changed, local_handlers=ui_handlers )
    futil.add_handler( ui.markingMenuDisplaying, ui_marking_menu, local_handlers=ui_handlers )

# Executed when add-in is stopped.
def stop():

    # Get the various UI elements for this command
    submenu = config.get_sketch_submenu()
    command_control = submenu.controls.itemById(CREATE_CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CREATE_CMD_ID)
    edit_cmd_def = ui.commandDefinitions.itemById(EDIT_CMD_ID)
    delete_cmd_def = ui.commandDefinitions.itemById(DELETE_CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.isPromoted = False
        command_control.deleteMe()

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

# Function that is called when a active selection is changed in the UI.
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
def ui_selection_changed(args: adsk.core.ActiveSelectionEventArgs):

    global selected_CCLine

    # futil.log(f' Selection Changed: at start ccLine={selected_CCLine}')
    args.firingEvent.name
    selected_CCLine = None
    if len( args.currentSelection ) > 0:
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

    if len(args.selectedEntities) > 0 :
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

# 
def edit_command_created(args: adsk.core.CommandCreatedEventArgs):
    global target_CCLine

    # futil.log(f'{args.command.parentCommandDefinition.name} edit_command_created()')

    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    # if target_CCLine.line.isFullyConstrained :
    #     futil.popup_error( 'CC Line is Fully Constrained and cannot be edited.  Remove some constraints to edit.')
    #     return

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Motion Component Type
    motionType = inputs.addDropDownCommandInput('motion_type', 'Motion Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    for mtype in motionTypes:
        motionType.listItems.add( mtype, True, '')
    motionType.listItems.item( motionTypesDefault ).isSelected = True

    # Create a separator.
    inputs.addSeparatorCommandInput( "selection_cog1_sep")

    # Create a integer spinners for cog1 and pinion options.
    cog1Teeth = inputs.addIntegerSpinnerCommandInput('cog1_teeth', 'Cog #1 Teeth', 8, 100, 1, 36)
    group1CmdInput = inputs.addGroupCommandInput('use_pinion_cog1', 'Use Pinion')
    group1CmdInput.isExpanded = False
    group1CmdInput.isEnabledCheckBoxDisplayed = True
    group1CmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = group1CmdInput.children
    pinion_cog1 = groupChildInputs.addDropDownCommandInput('pinion_cog1', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog1.listItems.add( gear, True, '')


     # Create a integer spinners for cog1 and pinion options.
    cog2Teeth = inputs.addIntegerSpinnerCommandInput('cog2_teeth', 'Cog #2 Teeth', 8, 100, 1, 24)
    group2CmdInput = inputs.addGroupCommandInput('use_pinion_cog2', 'Use Pinion')
    group2CmdInput.isExpanded = False
    group2CmdInput.isEnabledCheckBoxDisplayed = True
    group2CmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = group2CmdInput.children
    pinion_cog2 = groupChildInputs.addDropDownCommandInput('pinion_cog2', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog2.listItems.add( gear, True, '')

    # Addendum Gear Overrides

    inputs.addBoolValueInput( "swap_cogs", "Swap Cogs", True )

    beltTeeth = inputs.addIntegerSpinnerCommandInput( "belt_teeth", "Belt Teeth", 35, 400, 1, 70 )
    beltTeeth.isVisible = False

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.003')
    extraCenter = inputs.addValueInput('extra_center', 'Extra Center', defaultLengthUnits, default_value)

    # Fill the inputs with the ccLine info
    lineData = target_CCLine.data
    cog1Teeth.value = lineData.N1
    cog2Teeth.value = lineData.N2
    if lineData.PIN1 > 0 :
        group1CmdInput.isEnabledCheckBoxChecked = True
        cog1Teeth.isVisible = False
        if lineData.N1 < 14:
            idx = lineData.PIN1 - 8
        elif lineData.N1 < 16:
            idx = lineData.PIN1 - 7
        else:
            idx = lineData.PIN1 - 6
        pinion_cog1.listItems.item( idx ).isSelected = True

    if lineData.PIN2 > 0 :
        group2CmdInput.isEnabledCheckBoxChecked = True
        cog2Teeth.isVisible = False
        if lineData.N2 < 14:
            idx = lineData.PIN2 - 8
        elif lineData.N2 < 16:
            idx = lineData.PIN2 - 7
        else:
            idx = lineData.PIN2 - 6
        pinion_cog2.listItems.item( idx ).isSelected = True

    if lineData.motion != 0 :
        beltTeeth.value = lineData.Teeth
        beltTeeth.isVisible = True
        group1CmdInput.isVisible = False
        group2CmdInput.isVisible = False
        
    extraCenter.value = lineData.ExtraCenterIN * 2.54
    motionType.listItems.item( lineData.motion ).isSelected = True

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

def delete_command_created(args: adsk.core.CommandCreatedEventArgs):

    # futil.log(f'{args.command.parentCommandDefinition.name} Delete Command Created Event')

    futil.add_handler(args.command.execute, delete_command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, delete_command_destroy, local_handlers=local_handlers)

def delete_command_execute(args: adsk.core.CommandEventArgs):
    global target_CCLine

    futil.log(f'Delete Command Executed Event ccLine={target_CCLine}')
    deleteCCLine( target_CCLine )

def delete_command_destroy(args: adsk.core.CommandEventArgs):
    global target_CCLine

    target_CCLine = None


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
    inputs.addIntegerSpinnerCommandInput('cog1_teeth', 'Cog #1 Teeth', 8, 100, 1, 36)
    groupCmdInput = inputs.addGroupCommandInput('use_pinion_cog1', 'Use Pinion')
    groupCmdInput.isExpanded = False
    groupCmdInput.isEnabledCheckBoxDisplayed = True
    groupCmdInput.isEnabledCheckBoxChecked = False
    groupChildInputs = groupCmdInput.children
    pinion_cog1 = groupChildInputs.addDropDownCommandInput('pinion_cog1', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
    for gear in pinionGears:
        pinion_cog1.listItems.add( gear, True, '')


     # Create a integer spinners for cog1 and pinion options.
    inputs.addIntegerSpinnerCommandInput('cog2_teeth', 'Cog #2 Teeth', 8, 100, 1, 24)
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

    # TODO Connect to the events that are needed by this command.
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

    startSketchPt = None
    endSketchPt = None

    if not curveSelection:
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
        ccLine.line = createCCLine( startSketchPt, endSketchPt )
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
        calcCCLineData( ccLine.data )
        dimAndLabelCCLine( ccLine )
        createEndCircles( ccLine )
    else:
        calcCCLineData( ccLine.data )
        modifyCCLine( ccLine )

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
    futil.log(f'{args.firingEvent.name} Input Changed Event fired from a change to {changed_input.id}')

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

    if changed_input.id == 'curve_selection':
        # if curveSelection.selectionCount == 2:
        #     # We have selected two entitites
        #     if curveSelection.selection(0).entity.objectType == adsk.fusion.SketchLine.classType() or\
        #     curveSelection.selection(1).entity.objectType == adsk.fusion.SketchLine.classType() :
        #         # If either the first entity selected was a line or the newly selected entity
        #         # is a line the only keep the newly selected item.  Don't allow a line with something else.
        #         newSel = curveSelection.selection(1).entity
        #         curveSelection.clearSelection()
        #         curveSelection.addSelection( newSel )

        # Check if we have a previously configured CCLine selected or one of its children entities
        ccLine = None
        if curveSelection.selectionCount == 1:
            ccLine = getParentLine( curveSelection.selection(0).entity )
            
        if ccLine and isCCLine( ccLine ):
            curveSelection.clearSelection()
            curveSelection.addSelection( ccLine )

            swapCogsInp.value = False
            # futil.log(f'    ==========  Selected an existing CCLine.')
            lineData = getLineData( ccLine )
            cog1Teeth.value = lineData.N1
            cog2Teeth.value = lineData.N2
            if lineData.motion != 0 :
                beltTeeth.value = lineData.Teeth
            extraCenter.value = lineData.ExtraCenterIN * 2.54
            motionType.listItems.item( lineData.motion ).isSelected = True
            # if motionType.selectedItem.index == 0 :
            #     beltTeeth.isVisible = False
            # else:
            #     beltTeeth.isVisible = True

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

    # futil.log(f'{args.firingEvent.name} Command Validate Event')

    inputs = args.inputs
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')

    if not (cog1Teeth.value >= 8 and cog1Teeth.value < 100 and cog2Teeth.value >= 8 and cog1Teeth.value < 100 ):
        args.areInputsValid = False
        return
    
    args.areInputsValid = True        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers, target_CCLine

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []
    target_CCLine = None


def calcCCLineData( ld: CCLineData ):
    if ld.motion == 0:
        # 20DP Gears
        ld.Teeth = 0
        ld.ccDistIN = GearsCCDistanceIN( ld.N1, ld.N2, 20 )
        ld.PD1 = GearsPitchDiameterIN( ld.N1, 20 )
        ld.PD2 = GearsPitchDiameterIN( ld.N2, 20 )
        ld.OD1 = GearsOuterDiameterIN( ld.N1, 20 )
        ld.OD2 = GearsOuterDiameterIN( ld.N2, 20 )
    else :
        if ld.motion == 1:
            # HTD 5mm Belt
            beltPitchMM = 5
        else :
            # HTD 3mm Belt
            beltPitchMM = 3
        ld.ccDistIN = BeltCCDistanceIN( ld.N1, ld.N2, ld.Teeth, beltPitchMM )
        ld.PD1 = BeltPitchDiameterIN( ld.N1, beltPitchMM )
        ld.PD2 = BeltPitchDiameterIN( ld.N2, beltPitchMM )
        ld.OD1 = BeltOuterDiameterIN( ld.N1, beltPitchMM )
        ld.OD2 = BeltOuterDiameterIN( ld.N2, beltPitchMM )


def GearsCCDistanceIN( N1: int, N2: int, dp: int ) -> float:
    pitch_diameter1 = N1 / (1.0 * dp)
    pitch_diameter2 = N2 / (1.0 * dp)

    return (pitch_diameter1 + pitch_diameter2) / 2

def GearsPitchDiameterIN( NT: int, dp: int ) -> float:
    return NT / (1.0 * dp)

def GearsOuterDiameterIN( NT: int, dp: int ) -> float:
    return NT / (1.0 * dp) + 0.1

def BeltCCDistanceIN( N1: int, N2: int, beltTeeth: int, pitchMM: int ) -> float:
    PL = beltTeeth * pitchMM / 25.4 # in inches
    if N1 > N2:
        PD1 = BeltPitchDiameterIN( N1, pitchMM )
        PD2 = BeltPitchDiameterIN( N2, pitchMM )
    else:
        PD1 = BeltPitchDiameterIN( N2, pitchMM )
        PD2 = BeltPitchDiameterIN( N1, pitchMM )

    b = 2 * PL - math.pi * ( PD1 + PD2 )
    fourAC = 8 * (PD1 - PD2)*(PD1 - PD2)

    return ( b + math.sqrt( b*b - fourAC) ) / 8

def BeltPitchDiameterIN( NT: int, pitchMM: int ) -> float:
    return NT * pitchMM / ( 25.4 * math.pi )

def BeltOuterDiameterIN( NT: int, pitchMM: int ) -> float:
        # Approximation of the OD of the flanges on the pulleys
    return BeltPitchDiameterIN(NT, pitchMM) + 0.15

def createCCLine( 
    startpt: adsk.fusion.SketchPoint, 
    endpt: adsk.fusion.SketchPoint ) -> adsk.fusion.SketchLine :

    if startpt == None:
        design = adsk.fusion.Design.cast(app.activeProduct)
        sketch = design.activeEditObject
        startpt = sketch.sketchPoints.add( adsk.core.Point3D.create( 0, 0, 0 ) )
    
    sketch = startpt.parentSketch

    if endpt == None:
        endpt3D = futil.offsetPoint3D( startpt.geometry, 2 * 2.54, 0, 0 )
        endpt = sketch.sketchPoints.add( endpt3D )

    futil.log( f' createCCLine() points = {futil.format_Point3D(startpt.geometry)} -- {futil.format_Point3D(endpt.geometry)}')

    # Create C-C line a midpoint for it and dimension it
    ccLine = sketch.sketchCurves.sketchLines.addByTwoPoints( startpt, endpt )
    ccLine.isConstruction = True

    return ccLine

def dimAndLabelCCLine( ccLine: CCLine ) :

    sketch = ccLine.line.parentSketch
    line = ccLine.line
    ld = ccLine.data

    midPt = futil.midPoint3D( line.startSketchPoint.geometry, line.endSketchPoint.geometry )
    normal = futil.sketchLineNormal( line )
    normal = futil.multVector2D( normal, ld.ccDistIN / 4 )

    # Dimension C-C line
    if abs(normal.y) < 0.001  :
        textPt = futil.offsetPoint3D( midPt, normal.x, normal.y, 0 )
    elif normal.y < 0 :
        textPt = futil.offsetPoint3D( midPt, normal.x, normal.y, 0 )
    else:
        textPt = futil.offsetPoint3D( midPt, -normal.x, -normal.y, 0 )
    
    ccLine.lengthDim = sketch.sketchDimensions.addDistanceDimension( 
        line.startSketchPoint, line.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPt )
    ccLine.lengthDim.value = (ld.ccDistIN + ld.ExtraCenterIN) * 2.54

    # Create SketchText and attach it to the C-C Line
    label = createLabelString( ld )
    textHeight = computeTextSizeIN( ld ) * 2.54 # in cm

    # futil.log( f'ccDist = {ld.ccDistIN}in, Text Height = {textHeight}in')
    cornerPt = line.startSketchPoint.geometry
    diagPt =  futil.addPoint3D( cornerPt, adsk.core.Point3D.create( line.length, textHeight, 0 ) )
    textInput = sketch.sketchTexts.createInput2( label, textHeight )
    textInput.setAsMultiLine( cornerPt, diagPt, 
                        adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                        adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0 )
    ccLine.textBox = sketch.sketchTexts.add( textInput )
    textDef: adsk.fusion.MultiLineTextDefinition = ccLine.textBox.definition
    textBoxLines = textDef.rectangleLines
    textBaseLine = textBoxLines[0]
    TextHeightLine = textBoxLines[1]
    # midPt3D = futil.midPoint3D(textBaseLine.startSketchPoint.geometry, textBaseLine.endSketchPoint.geometry )
    # ccLine.midPt = sketch.sketchPoints.add( midPt3D )

    textPoint = futil.offsetPoint3D( TextHeightLine.startSketchPoint.geometry, -textHeight/2, textHeight/2, 0 )
    ccLine.textHeight = sketch.sketchDimensions.addDistanceDimension( TextHeightLine.startSketchPoint, TextHeightLine.endSketchPoint,
                                                              adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                              textPoint  )
    ccLine.textHeight.value = textHeight * 2.0

    # sketch.geometricConstraints.addMidPoint( ccLine.midPt, textBaseLine  )
    # sketch.geometricConstraints.addMidPoint( ccLine.midPt, line  )
    # sketch.geometricConstraints.addParallel( textBaseLine, line  )
    if textBaseLine.startSketchPoint.geometry.distanceTo(line.startSketchPoint.geometry) < \
        textBaseLine.startSketchPoint.geometry.distanceTo(line.endSketchPoint.geometry) :
        sketch.geometricConstraints.addCoincident( textBaseLine.startSketchPoint, line.startSketchPoint )
        sketch.geometricConstraints.addCoincident( textBaseLine.endSketchPoint, line.endSketchPoint )
    else:
        sketch.geometricConstraints.addCoincident( textBaseLine.startSketchPoint, line.endSketchPoint )
        sketch.geometricConstraints.addCoincident( textBaseLine.endSketchPoint, line.startSketchPoint )


def createLabelString( ld: CCLineData ) -> str:
    if ld.motion == 0:
        if ld.PIN1 > 0 and ld.PIN1 != ld.N1 :
            lineLabel = f'Gear 20DP {ld.PIN1}T({ld.N1}T-CD)+{ld.N2}T'
        elif ld.PIN2 > 0 and ld.PIN2 != ld.N2 :
            lineLabel = f'Gear 20DP {ld.N1}T+{ld.PIN2}T({ld.N2}T-CD)'
        else:
            lineLabel = f'Gear 20DP {ld.N1}T+{ld.N2}T'
    else :
        if ld.motion == 1:
    #         # HTD 5mm Belt
            lineLabel = f'{ld.Teeth}T HTD 5mm ({ld.N1}Tx{ld.N2}T)'
        else :
    #         # HTD 3mm Belt
            lineLabel = f'{ld.Teeth}T GT2 3mm ({ld.N1}Tx{ld.N2}T)'
    
    if abs(ld.ExtraCenterIN) > 0.0005 :
        lineLabel += f' EC({ld.ExtraCenterIN:.3})'

    return lineLabel

def createEndCircles( ccLine: CCLine ) :
    PDcircleData = createCirclePair( ccLine.line, ccLine.data.PD1, ccLine.data.PD2, 45.0 )
    ccLine.pitchCircle1 = PDcircleData[0][0]
    ccLine.pitchCircle2 = PDcircleData[0][1]
    ccLine.PD1Dim = PDcircleData[1][0]
    ccLine.PD2Dim = PDcircleData[1][1]
    ODcircleData = createCirclePair( ccLine.line, ccLine.data.OD1, ccLine.data.OD2, 135.0 )
    ccLine.ODCircle1 = ODcircleData[0][0]
    ccLine.ODCircle2 = ODcircleData[0][1]
    ccLine.OD1Dim = ODcircleData[1][0]
    ccLine.OD2Dim = ODcircleData[1][1]

def createCirclePair( line: adsk.fusion.SketchLine, 
                      dia1IN: float, dia2IN: float, dimAngleDeg: float ) :

    sketch = line.parentSketch

    # Create Start point centered circle and dimension it
    startCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( line.startSketchPoint, dia1IN * 2.54 / 2 )
    startCircle.isConstruction = True

    dimDir = adsk.core.Vector2D.create( dia1IN * 2.54 / 5, 0 )
    rotMatrix = adsk.core.Matrix2D.create()
    rotMatrix.setToRotation( dimAngleDeg * math.pi / 180, adsk.core.Point2D.create() )
    dimDir.transformBy( rotMatrix )
    textPoint = futil.offsetPoint3D( startCircle.centerSketchPoint.geometry, dimDir.x, dimDir.y, 0 )
    diaDim1 = sketch.sketchDimensions.addDiameterDimension( startCircle, textPoint )
    diaDim1.value = dia1IN * 2.54
    # sketch.geometricConstraints.addCoincident( startCircle.centerSketchPoint, line.startSketchPoint )

    # Create End point centered circle and dimension it
    endCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( line.endSketchPoint, dia2IN * 2.54 / 2 )
    endCircle.isConstruction = True

    dimDir = adsk.core.Vector2D.create( dia2IN * 2.54 / 5, 0 )
    rotMatrix = adsk.core.Matrix2D.create()
    rotMatrix.setToRotation( dimAngleDeg * math.pi / 180, adsk.core.Point2D.create() )
    dimDir.transformBy( rotMatrix )
    textPoint = futil.offsetPoint3D( endCircle.centerSketchPoint.geometry, dimDir.x, dimDir.y, 0 )
    diaDim2 = sketch.sketchDimensions.addDiameterDimension( endCircle, textPoint )
    diaDim2.value = dia2IN * 2.54
    # sketch.geometricConstraints.addCoincident( endCircle.centerSketchPoint, line.endSketchPoint )

    return ([ startCircle, endCircle ], [diaDim1, diaDim2])

def computeTextSizeIN( ld: CCLineData ) -> float:
    textHeight = ld.ccDistIN / 28.0
    if textHeight < 0.025:
        textHeight = 0.025

    return textHeight

def modifyCCLine( ccLine: CCLine ):

    ld = ccLine.data

    try:
        ccLine.lengthDim.value = (ld.ccDistIN + ld.ExtraCenterIN) * 2.54
    except:
        futil.popup_error( 'Failed to resize centerline!  Are both ends of C-C Distance constrained?', True )
        return

    label = createLabelString( ld )
    ccLine.textBox.text = label
    ccLine.textBox.height = computeTextSizeIN( ld ) * 2.54
    ccLine.textHeight.value = ccLine.textBox.height * 2.0

    ccLine.PD1Dim.value = ld.PD1 * 2.54
    ccLine.PD2Dim.value = ld.PD2 * 2.54
    ccLine.OD1Dim.value = ld.OD1 * 2.54
    ccLine.OD2Dim.value = ld.OD2 * 2.54

