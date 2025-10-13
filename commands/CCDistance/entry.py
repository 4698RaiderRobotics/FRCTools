import adsk.core
import adsk.fusion
import os
from ...lib import fusionAddInUtils as futil
from ... import config
from . import CCLine
from . import CCLineUtils as ccutil

app = adsk.core.Application.get()
ui = app.userInterface


#  *** Specify the command identity information. ***
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


# Local list of ui event handlers used to maintain a reference so
# they are not released and garbage collected.
ui_handlers = []

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Global variable to hold the selected CCLine in the UI and the command target CCLine
selected_CCLine = []
target_CCLine = []

motionTypes = ( 
    'Gears 20DP',
    'HTD 5mm Belt',
    'GT2 3mm Belt',
    'RT25 Belt',
    '#25 Chain',
    '#35 Chain',
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
    from .create_cmd import command_created
    from .edit_cmd import edit_command_created

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
    # futil.log(f' Command Starting={args.commandDefinition.name}, selected_CCLine len ={len(selected_CCLine)}')

    # If a CCLine is not selected then just return
    if len(selected_CCLine) == 0:
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

    # futil.log(f' Selection Changed num={len( args.currentSelection )}: at start ccLine len={len(selected_CCLine)}')

    selected_CCLine = []
    centerLines = []
    for sel in args.currentSelection:
        cline = CCLine.getParentLine( sel.entity )
        if cline and not cline in centerLines:
            centerLines.append( cline )
    
    if len(centerLines) > 0:
        for cline in centerLines:
            selected_CCLine.append( CCLine.getCCLineFromEntity( cline) )
    
    # futil.log(f'                    at end ccLine len={len(selected_CCLine)}')

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
        ccLine = CCLine.getCCLineFromEntity( args.selectedEntities[0] )
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
    for line in target_CCLine:
        CCLine.deleteCCLine( line )

def delete_command_destroy(args: adsk.core.CommandEventArgs):
    global target_CCLine

    target_CCLine = []



