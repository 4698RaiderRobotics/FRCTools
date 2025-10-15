import adsk.core
import adsk.fusion
# import os
from ...lib import fusionAddInUtils as futil
from .entry import motionTypes, motionTypesDefault, pinionCenters, pinionGears, pinionTeeth
# from ... import config
from . import CCLine
from . import CCLineUtils as ccutil
from . import dialog

app = adsk.core.Application.get()
ui = app.userInterface

CCDialog = None
SelectedLine = None

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# ===========
# ===========   Edit Command ROUTINES
# ===========

# Creating the edit command dialog
def edit_command_created(args: adsk.core.CommandCreatedEventArgs):
    global CCDialog, SelectedLine
    
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

    CCDialog = dialog.Dialog( inputs, False )

    SelectedLine = None
    CCDialog.disable_dialog( inputs )


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
    global CCDialog, SelectedLine

    futil.log( f'edit_command_select - selected = {args.activeInput.selectionCount}' )
    
    SelectedLine = CCLine.getCCLineFromEntity(args.selection.entity)
    if not SelectedLine:
        return
 
    args.activeInput.clearSelection()
    cc_objs = [ SelectedLine.line, SelectedLine.ODCircle1, SelectedLine.ODCircle2 ]
    for cc_obj in cc_objs:
        args.activeInput.addSelection( cc_obj )

    CCDialog.initialize_dialog( args.activeInput.parentCommand.commandInputs, SelectedLine.data )


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def edit_command_input_changed(args: adsk.core.InputChangedEventArgs):
    global CCDialog

    CCDialog.input_changed( args )


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def edit_command_execute(args: adsk.core.CommandEventArgs):
    global CCDialog, SelectedLine

    # General logging for debug.
    futil.log(f'{args.command.parentCommandDefinition.name} Edit Command Execute Event ---  Start...')

    if not SelectedLine:
        return

    SelectedLine.data = CCDialog.generate_ccline_data( args.command.commandInputs )

    ccutil.calcCCLineData( SelectedLine.data )
    if SelectedLine.data.ccDistIN < 0.001:
        return

    ccutil.modifyCCLine( SelectedLine )
    if args.firingEvent.name == "OnExecute" :
        CCLine.setCCLineAttributes( SelectedLine )

    # This was needed once debugging output was turned off....
    app.activeViewport.refresh()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def edit_command_preview(args: adsk.core.CommandEventArgs):

    edit_command_execute( args )


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def edit_command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    global CCDialog

    CCDialog.validate_input( args )


# This event handler is called when the create or edit commands terminate.
def edit_command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers, CCDialog, SelectedLine

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []
    CCDialog = None
    SelectedLine = None

