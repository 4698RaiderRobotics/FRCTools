import adsk.core
import adsk.fusion
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
    inputs.addTextBoxCommandInput( "status_msg", "", "Select", 1, True )

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Execute Event')

    ccLine = CCLine.CCLine()

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


    if curveSelection.selectionCount == 1 :
        selEntity = curveSelection.selection(0).entity
        if selEntity.objectType == adsk.fusion.SketchCircle.classType() :
            startSketchPt = selEntity.centerSketchPoint
        elif selEntity.objectType == adsk.fusion.SketchLine.classType() :
            if CCLine.isCCLine( selEntity ) :
                ccLine.line = selEntity
            else :
                startSketchPt = selEntity.startSketchPoint
        else :
            startSketchPt = selEntity

    if ccLine.line == None:
        ccLine.line = ccutil.createCCLine( startSketchPt, endSketchPt )
    elif CCLine.isCCLine( ccLine.line ):
        ccLine = CCLine.getCCLineFromEntity( ccLine.line )

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
            curveSelection.clearSelection()
            curveSelection.setSelectionLimits( 0, 2 )

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
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []

