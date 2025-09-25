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

        # Get the panel the FRCTools dropdown will be created in.
        solid_panel = workspace.toolbarPanels.itemById( config.SOLID_CREATE_ID )
        sketch_create_panel = workspace.toolbarPanels.itemById( config.SKETCH_CREATE_ID )
        sketch_modify_panel = workspace.toolbarPanels.itemById( config.SKETCH_MODIFY_ID )

        # Create the the FRCTool submenu in the solid-create, sketch-create, and sketch-modify panels.
        solid_panel.controls.addDropDown( "FRCTools", "", config.FRC_TOOLS_DROPDOWN_ID )
        sketch_create_panel.controls.addDropDown( "FRCTools", "", config.FRC_TOOLS_DROPDOWN_ID )
        sketch_modify_panel.controls.addDropDown( "FRCTools", "", config.FRC_TOOLS_DROPDOWN_ID )

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
        solid_panel = workspace.toolbarPanels.itemById( config.SOLID_CREATE_ID )
        sketch_create_panel = workspace.toolbarPanels.itemById( config.SKETCH_CREATE_ID )
        sketch_modify_panel = workspace.toolbarPanels.itemById( config.SKETCH_MODIFY_ID )

        solid_submenu = solid_panel.controls.itemById( config.FRC_TOOLS_DROPDOWN_ID )
        # Delete the Solid->Create FRCTools submenu
        if solid_submenu:
            solid_submenu.deleteMe()

        sketch_create_submenu = sketch_create_panel.controls.itemById( config.FRC_TOOLS_DROPDOWN_ID )
        # Delete Sketch->Create FRCTools submenu
        if sketch_create_submenu:
            sketch_create_submenu.deleteMe()

        sketch_modify_submenu = sketch_modify_panel.controls.itemById( config.FRC_TOOLS_DROPDOWN_ID )
        # Delete Sketch->Modify FRCTools submenu
        if sketch_modify_submenu:
            sketch_modify_submenu.deleteMe()

    except:
        futil.handle_error('stop')