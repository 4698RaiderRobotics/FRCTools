import adsk.core
import adsk.fusion
# import os
from ...lib import fusionAddInUtils as futil
from .entry import motionTypes, motionTypesDefault, pinionCenters, pinionGears, pinionTeeth
# from ... import config
from . import CCLine
from . import CCLineUtils as ccutil

app = adsk.core.Application.get()
ui = app.userInterface

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# ===========
# ===========   Edit Command ROUTINES
# ===========

# Creating the edit command dialog
def edit_command_created(args: adsk.core.CommandCreatedEventArgs):
    # global target_CCLine
    
    futil.log(f'{args.command.parentCommandDefinition.name} edit_command_created()')

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, edit_command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.preSelect, edit_command_preselect, local_handlers=local_handlers)
    futil.add_handler(args.command.select, edit_command_select, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, edit_command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, edit_command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, edit_command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, edit_command_destroy, local_handlers=local_handlers)

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Motion Component Type
    motionType: adsk.core.DropDownCommandInput = inputs.addDropDownCommandInput('motion_type', 'Motion Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    for mtype in motionTypes:
        motionType.listItems.add( mtype, True, '')
    motionType.listItems.item( motionTypesDefault ).isSelected = True

    # Create a selection input.
    curveSelection = inputs.addSelectionInput('curve_selection', 'Selection', 'Select a C-C Distance object')
    # curveSelection.addSelectionFilter( "SketchCircles" )
    # curveSelection.addSelectionFilter( "SketchLines" )
    # curveSelection.addSelectionFilter( "SketchConstraints" )
    # curveSelection.addSelectionFilter( "Texts" )
    curveSelection.setSelectionLimits( 3, 3 )

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
    status = inputs.addTextBoxCommandInput( "status_msg", "", "status", 1, True )

    status.formattedText = '<div align="center">Select a C-C Distance object.</div>'
    disable_edit_inputs( inputs )


# This event is fired when the user is hovering over an entity
# but has not yet clicked on it.
def edit_command_preselect(args: adsk.core.SelectionEventArgs):

    ccLine = CCLine.getCCLineFromEntity(args.selection.entity)
    if ccLine:
        obj = adsk.core.ObjectCollection.create()
        cc_objs = [ ccLine.line, ccLine.ODCircle1, ccLine.ODCircle2 ]
        for cc_obj in cc_objs:
            if cc_obj != args.selection.entity:
                obj.add( cc_obj )

        args.additionalEntities = obj

    else:
        args.isSelectable = False


# This event is fired when the user clicks on an entity
# to select it.
def edit_command_select(args: adsk.core.SelectionEventArgs):

    futil.log( f'edit_command_select - selected = {args.activeInput.selectionCount}' )
    
    ccLine = CCLine.getCCLineFromEntity(args.selection.entity)
    if not ccLine:
        return
 
    args.activeInput.clearSelection()
    cc_objs = [ ccLine.line, ccLine.ODCircle1, ccLine.ODCircle2 ]
    for cc_obj in cc_objs:
        args.activeInput.addSelection( cc_obj )

    initialize_input_state( args.activeInput.parentCommand.commandInputs, ccLine.data )


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def edit_command_input_changed(args: adsk.core.InputChangedEventArgs):

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
        # Check if nothing is selected and disable if true.
        # This gets re-enabled in the edit_command_select() function
        if curveSelection.selectionCount == 0:
            status.formattedText = '<div align="center">Select a C-C Distance object.</div>'
            disable_edit_inputs( inputs )

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

def initialize_input_state( inputs: adsk.core.CommandInputs, lineData: CCLine.CCLineData ):
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


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def edit_command_execute(args: adsk.core.CommandEventArgs):

    # General logging for debug.
    futil.log(f'{args.command.parentCommandDefinition.name} Edit Command Execute Event')

    ccLine = None

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

    if curveSelection.selectionCount > 0:
        # Editing an existing CCLine
        ccLine = CCLine.getCCLineFromEntity( curveSelection.selection(0).entity )
 
    if not ccLine:
        return

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

    ccutil.calcCCLineData( ccLine.data )
    if ccLine.data.ccDistIN < 0.001:
        return

    if not ccutil.isCCLine( ccLine.line ):
        # ccutil.calcCCLineData( ccLine.data )
        # if ccLine.data.ccDistIN < 0.001:
        #     return
        ccutil.dimAndLabelCCLine( ccLine )
        ccutil.createEndCircles( ccLine )
    else:
        # ccutil.calcCCLineData( ccLine.data )
        # if ccLine.data.ccDistIN < 0.001:
        #     return
        ccutil.modifyCCLine( ccLine )

    msg = f'<div align="center">{ccutil.createLabelString( ccLine.data )}</div>'
    status.formattedText = msg
    if not preview :
        CCLine.setCCLineAttributes( ccLine )

    # This was needed once debugging output was turned off....
    app.activeViewport.refresh()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def edit_command_preview(args: adsk.core.CommandEventArgs):

    edit_command_execute( args )


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def edit_command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    inputs = args.inputs
    motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
    cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
    cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
    beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
    status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

    # futil.log(f'{args.firingEvent.name} Command Validate Event, Motion={motionType.selectedItem.index}, N1={cog1Teeth.value}, N2={cog2Teeth.value}, T={beltTeeth.value}')
    args.areInputsValid = True        

    if not (cog1Teeth.value >= 6 and cog1Teeth.value < 100 and cog2Teeth.value >= 6 and cog1Teeth.value < 100 ):
        status.formattedText = '<div align="center"><font color="red">Invalid Number of cog teeth! [6-100]</font></div>'
        args.areInputsValid = False
        return
    
    if motionType.selectedItem.index != 0:
        ld = CCLine.CCLineData()
        ld.motion = motionType.selectedItem.index
        ld.N1 = cog1Teeth.value
        ld.N2 = cog2Teeth.value
        ld.Teeth = beltTeeth.value
        ccutil.calcCCLineData( ld )

        if ld.ccDistIN < (ld.OD1 + ld.OD2) / 2.0 :
            # belt is too short
            status.formattedText = '<div align="center"><font color="red">Belt is too short!</font></div>'
            args.areInputsValid = False
            return


# This event handler is called when the create or edit commands terminate.
def edit_command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []

