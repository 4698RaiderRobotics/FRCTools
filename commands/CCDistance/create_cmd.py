import adsk.core
import adsk.fusion
from ...lib import fusionAddInUtils as futil
from .entry import motionTypes, motionTypesDefault, pinionCenters, pinionGears, pinionTeeth
# from ... import config
from . import CCLine
from . import CCLineUtils as ccutil
from . import dialog

app = adsk.core.Application.get()
ui = app.userInterface

CCDialog = None

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# ===========
# ===========   Create Command ROUTINES
# ===========

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    global CCDialog

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    CCDialog = dialog.Dialog( inputs, True )

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    global CCDialog
    
    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Execute Event')

    ccLine = CCLine.CCLine()

    startSketchPt = None
    endSketchPt = None

    if CCDialog.curveSelection.selectionCount == 1 :
        selEntity = CCDialog.curveSelection.selection(0).entity
        if selEntity.objectType == adsk.fusion.SketchCircle.classType() :
            startSketchPt = selEntity.centerSketchPoint
        # elif selEntity.objectType == adsk.fusion.SketchLine.classType() :
        #     if CCLine.isCCLine( selEntity ) :
        #         ccLine.line = selEntity
        #     else :
        #         startSketchPt = selEntity.startSketchPoint
        else :
            startSketchPt = selEntity

    ccLine.line = ccutil.createCCLine( startSketchPt, endSketchPt )

    ccLine.data = CCDialog.generate_ccline_data()

    ccutil.calcCCLineData( ccLine.data )
    if ccLine.data.ccDistIN < 0.001:
        return

    # if not ccutil.isCCLine( ccLine.line ):
    ccutil.dimAndLabelCCLine( ccLine )
    ccutil.createEndCircles( ccLine )
    # else:
    #     ccutil.modifyCCLine( ccLine )

    # msg = f'<div align="center">{ccutil.createLabelString( ccLine.data )}</div>'
    # CCDialog.status.formattedText = msg
    if args.firingEvent.name == "OnExecute" :
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
    global CCDialog

    CCDialog.input_changed( args )


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    global CCDialog

    CCDialog.validate_input( args )



# This event handler is called when the create or edit commands terminate.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers, CCDialog

    # General logging for debug.
    # futil.log(f'{args.command.parentCommandDefinition.name} Command Destroy Event')

    local_handlers = []
    CCDialog = None
