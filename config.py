# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

import os
import adsk.core

app = adsk.core.Application.get()
ui = app.userInterface

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Generally, it's useful
# to set this to True while developing an add-in and set it to False when you
# are ready to distribute it.
DEBUG = True

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements 
# that need a unique name. It's also recommended to use a company name as 
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = 'FRCTools'
COMPANY_NAME = 'Team4698'

# Palettes
# sample_palette_id = f'{COMPANY_NAME}_{ADDIN_NAME}_palette_id'

# Toolbar stuff
WORKSPACE_ID = 'FusionSolidEnvironment'
SOLID_CREATE_ID = 'SolidCreatePanel'
SKETCH_CREATE_ID = 'SketchCreatePanel'
FRC_TOOLS_DROPDOWN_ID = 'FRCToolsSubMenu'

def get_sketch_submenu() -> adsk.core.ToolbarControl:
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById( WORKSPACE_ID )

    # Get the sketch panel the button will be created in.
    panel = workspace.toolbarPanels.itemById( SKETCH_CREATE_ID )

    # Find the the FRCTools submenu.
    return panel.controls.itemById( FRC_TOOLS_DROPDOWN_ID )

def get_solid_submenu() -> adsk.core.ToolbarControl:
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById( WORKSPACE_ID )

    # Get the solid panel the button will be created in.
    panel = workspace.toolbarPanels.itemById( SOLID_CREATE_ID )

    # Find the the FRCTools submenu.
    return panel.controls.itemById( FRC_TOOLS_DROPDOWN_ID )
