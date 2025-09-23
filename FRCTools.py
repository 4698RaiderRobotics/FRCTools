# Assuming you have not changed the general structure of the template no modification is needed in this file.
import adsk.core
from . import commands
from .lib import fusionAddInUtils as futil
from . import config

app = adsk.core.Application.get()
ui = app.userInterface

def run(context):
    try:

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        workspace = ui.workspaces.itemById( config.WORKSPACE_ID )

        # Get the panel the button will be created in.
        solidpanel = workspace.toolbarPanels.itemById( config.SOLID_CREATE_ID )
        sketchpanel = workspace.toolbarPanels.itemById( config.SKETCH_CREATE_ID )

        # Create the the FRCTool submenu in sketch and solid panels.
        submenu = solidpanel.controls.addDropDown( "FRCTools", "", config.FRC_TOOLS_DROPDOWN_ID )
        submenu = sketchpanel.controls.addDropDown( "FRCTools", "", config.FRC_TOOLS_DROPDOWN_ID )

        # This will run the start function in each of your commands as defined in commands/__init__.py
        commands.start()

    except:
        futil.handle_error('run', True)


def stop(context):
    try:
        # Remove all of the event handlers your app has created
        futil.clear_handlers()

        # This will run the stop function in each of your commands as defined in commands/__init__.py
        commands.stop()

        workspace = ui.workspaces.itemById(config.WORKSPACE_ID)
        solidpanel = workspace.toolbarPanels.itemById(config.SOLID_CREATE_ID)
        submenu = solidpanel.controls.itemById( config.FRC_TOOLS_DROPDOWN_ID )

        # Delete the FRCTools submenu
        if submenu:
            submenu.deleteMe()

        sketchpanel = workspace.toolbarPanels.itemById(config.SKETCH_CREATE_ID)
        submenu = sketchpanel.controls.itemById( config.FRC_TOOLS_DROPDOWN_ID )

        # Delete the FRCTools submenu
        if submenu:
            submenu.deleteMe()

    except:
        futil.handle_error('stop')