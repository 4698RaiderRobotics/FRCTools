import adsk.core
import adsk.fusion

from ..lib import fusionAddInUtils as futil
from .CCDistance import CCLine
from .CCDistance.entry import EDIT_CMD_ID as CCDISTANCE_EDIT_CMD_ID
from .TimingBelt.entry import CMD_ID as TIMINGBELT_CMD_ID

app = adsk.core.Application.get()
ui = app.userInterface

# Here you define the commands that will be added to your add-in.

# If you want to add an additional command, duplicate one of the existing directories and import it here.
# You need to use aliases (import "entry" as "my_module") assuming you have the default module named "entry".
from .BoltPattern import entry as BoltPattern
from .CCDistance import entry as CCDistance
from .ShaftEndings import entry as ShaftEndings
from .Lighten import entry as Lighten
from .TimingBelt import entry as TimingBelt
from .TimingPulley import entry as TimingPulley
from .Tubify import entry as Tubify

# Fusion will automatically call the start() and stop() functions.
commands = [
    BoltPattern,
    CCDistance,
    ShaftEndings,
    Lighten,
    TimingBelt,
    TimingPulley,
    Tubify
]

ui_handlers = []

# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start():
    global ui_handlers

    for command in commands:
        command.start()
    futil.add_handler( ui.markingMenuDisplaying, ui_marking_menu, local_handlers=ui_handlers )


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop():
    global ui_handlers

    for command in commands:
        command.stop()
        
    ui_handlers = []


# Function that is called when the marking menu is going to be displayed.
def ui_marking_menu(args: adsk.core.MarkingMenuEventArgs):

    controls = args.linearMarkingMenu.controls

    # futil.log(f' ui_marking_menu() --  Workspace = {app.activeProduct.objectType}, edit = {app.activeEditObject.objectType}')
    if app.activeProduct.objectType != adsk.fusion.Design.classType() :
        return

    # Gather the Mtext command
    editMTextCmd = controls.itemById( 'EditMTextCmd' )

    # Make a list of the controls to turn off
    hideCtrls = [editMTextCmd]
    hideCtrls.append( controls.itemById( 'ExplodeTextCmd' ) )
    hideCtrls.append( controls.itemById( 'ToggleDrivenDimCmd' ) )
    hideCtrls.append( controls.itemById( 'ToggleRadialDimCmd' ) )

    editCCLineMenuItem = controls.itemById( CCDISTANCE_EDIT_CMD_ID )
    if not editCCLineMenuItem:
        ccedit_cmd_def = ui.commandDefinitions.itemById( CCDISTANCE_EDIT_CMD_ID )
        timingBelt_cmd_def = ui.commandDefinitions.itemById( TIMINGBELT_CMD_ID )
        # Find the separator before the "Edit Text" command and add our commands after it
        i = editMTextCmd.index - 1
        while i > 0:
            control = controls.item( i )
            if control.objectType == adsk.core.SeparatorControl.classType():
                control = controls.item( i + 1 )
                break
            i -= 1
        editCCLineMenuItem = controls.addCommand( ccedit_cmd_def, control.id, True )
        tb_ctrl = controls.addCommand( timingBelt_cmd_def, editCCLineMenuItem.id, False )
        controls.addSeparator( "EditCCLineSeparator", tb_ctrl.id, False )

    timingBeltMenuItem = controls.itemById( TIMINGBELT_CMD_ID )
    editCCLineSep = controls.itemById( "EditCCLineSeparator" )

    if len(args.selectedEntities) == 1:
        ccLine = CCLine.getParentLine( args.selectedEntities[0] )
        if ccLine:
            editCCLineMenuItem.isVisible = True
            editCCLineSep.isVisible = True

            if app.activeEditObject.objectType != adsk.fusion.Sketch.classType() :
                timingBeltMenuItem.isVisible = True
            else:
                timingBeltMenuItem.isVisible = False

            for ctrl in hideCtrls:
                try:
                    ctrl.isVisible = False
                except:
                    None
            return
        
    editCCLineMenuItem.isVisible = False
    timingBeltMenuItem.isVisible = False
    editCCLineSep.isVisible = False
