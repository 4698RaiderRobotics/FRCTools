import adsk.core
import adsk.fusion
import os
import math
import typing
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ShaftEndings'
CMD_NAME = 'ShaftEndings'
CMD_Description = 'Create Shaft End Operations (e.g. Snap Ring Groove)'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

class RingGroove :
    def __init__(self, shaft_dia, width, groove_dia, margin):
        self.shaft_dia = shaft_dia
        self.width = width
        self.diameter = groove_dia
        self.end_margin = margin
        self.offset = 0.0

class EClipGroove(RingGroove):
    pass

class SnapRingGroove(RingGroove):
    pass

class EndTreatment :
    groove: RingGroove = None
    hole_dia: float = 0.0
    hole_depth: float = 0.0

class EClipCollection:
    e_clips: list[EClipGroove] = [
        # shaft_diameter, groove_width, groove_diameter, end_margin
        EClipGroove(0.000, 0.000, 0.000, 0.000),  # Null eclip
        EClipGroove(0.250, 0.030, 0.212, 0.040),
        EClipGroove(0.375, 0.040, 0.305, 0.072),
        EClipGroove(0.500, 0.047, 0.398, 0.104),
    ]

    def get(diameter: float) -> EClipGroove:
        for ec in EClipCollection.e_clips:
            if abs(diameter-ec.shaft_dia) < 0.001:
                return ec
        return EClipCollection.e_clips[0]

class SnapRingCollection:
    snap_rings: list[SnapRingGroove] = [
        # shaft_diameter, groove_width, groove_diameter, end_margin
        SnapRingGroove(0.000, 0.000, 0.000, 0.000),  # Null snapring
        SnapRingGroove(0.250, 0.030, 0.230, 0.030),
        SnapRingGroove(0.375, 0.030, 0.352, 0.036),
        SnapRingGroove(0.500, 0.040, 0.468, 0.048),
    ]

    def get(diameter: float) -> SnapRingGroove:
        for sr in SnapRingCollection.snap_rings:
            if abs(diameter-sr.shaft_dia) < 0.001:
                return sr
        return SnapRingCollection.snap_rings[0]
    

hole_diameters = {
    'None' : 0,
    '#8-32 Thread': 0.136,
    '#10-32 Thread': 0.159,
    '1/4"-20 Thread': 0.201,
    '5/16"-18 Thread': 0.257,
    '3/8"-16 Thread': 0.3125,
    '7/16"-14 Thread': 0.368,
    'Hole': -1
}

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the FRCTool submenu.
    submenu = config.get_solid_submenu()

    # Create the button command control in the UI.
    control = submenu.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    submenu = config.get_solid_submenu()
    command_control = submenu.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.isPromoted = False
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):

    # General logging for debug.
    futil.log(f'{CMD_NAME} command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    select = inputs.addSelectionInput('shaft_selection', 'Shaft', 
                                              'Select the end of a shaft to modify.')
    select.addSelectionFilter( "PlanarFaces" )
    select.setSelectionLimits( 1, 1 )

    extTreatments = inputs.addDropDownCommandInput( 
        'external_treatments', 'External', adsk.core.DropDownStyles.TextListDropDownStyle
    )
    items = extTreatments.listItems
    items.add('None', True )
    items.add('E-clip', False)
    items.add('Snap Ring', False)

    offset = adsk.core.ValueInput.createByString('0')
    clipOffset = inputs.addDistanceValueCommandInput('clip_offset', 'End Offset', offset)
    clipOffset.isVisible = False
    clipOffset.minimumValue = 0.0

    intTreatments = inputs.addDropDownCommandInput( 
        'internal_treatments', 'Internal', adsk.core.DropDownStyles.TextListDropDownStyle
    )
    items = intTreatments.listItems
    for hole_name in hole_diameters:
        items.add(hole_name, False )
    
    items.item(0).isSelected = True

    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    diaVal = adsk.core.ValueInput.createByString('0.25in')
    diameter = inputs.addValueInput('diameter', 'Diameter', defaultLengthUnits, diaVal)
    diameter.isVisible = False
    diameter.minimumValue = 0.0

    depthVal = adsk.core.ValueInput.createByString('0.5in')
    depth = inputs.addDistanceValueCommandInput('depth', 'Depth', depthVal)
    depth.isVisible = False
    depth.minimumValue = 0.0

    # TODO Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')

    inputs = args.command.commandInputs

    select: adsk.core.SelectionCommandInput = inputs.itemById('shaft_selection')
    extTreatments: adsk.core.DropDownCommandInput = inputs.itemById('external_treatments')
    clipOffset: adsk.core.DistanceValueCommandInput = inputs.itemById('clip_offset')
    intTreatments: adsk.core.DropDownCommandInput = inputs.itemById('internal_treatments')
    diameterInp: adsk.core.ValueCommandInput = inputs.itemById('diameter')
    depthInp: adsk.core.DistanceValueCommandInput = inputs.itemById('depth')

    shaft_face: adsk.fusion.BRepFace = select.selection(0).entity
    paramBody = shaft_face.body

    shaft_diameter = get_shaft_diameter(shaft_face)
    treat = EndTreatment()
    treat.groove = None

    if extTreatments.selectedItem.index == 1:
        # E-clip
        treat.groove = EClipCollection.get(shaft_diameter)
        treat.groove.offset = clipOffset.value
    elif extTreatments.selectedItem.index == 2:
        # Snap Ring
        treat.groove = SnapRingCollection.get(shaft_diameter)
        treat.groove.offset = clipOffset.value

    outerbody = None
    if treat.groove:
        outerbody = create_groove_body( shaft_face, treat.groove )

    hole_dia = hole_diameters[intTreatments.selectedItem.name]
    if hole_dia < 0:
        hole_dia = diameterInp.value / 2.54
    
    hole_body = None
    if hole_dia > 0:
        hole_body = create_hole_body(shaft_face, hole_dia * 2.54, depthInp.value)

        # Get the temporary Brep manager
    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()
    cut_body = None
    if outerbody:
        cut_body = outerbody
        if hole_body:
            tempBrepMgr.booleanOperation(cut_body, hole_body, adsk.fusion.BooleanTypes.UnionBooleanType)
    else:
        if hole_body:
            cut_body = hole_body

    if not cut_body:
        return

    comp = paramBody.parentComponent
    baseFeat = comp.features.baseFeatures.add()
    baseFeat.startEdit()
    comp.bRepBodies.add(cut_body, baseFeat)
    baseFeat.finishEdit()

    # Create a combine feature to subtract the pocket body from the part.
    combineFeature = None
    toolBodies = adsk.core.ObjectCollection.create()
    toolBodies.add(baseFeat.bodies.item(0))
    combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineFeature = comp.features.combineFeatures.add(combineInput)

    args.isValidResult = True

    app.activeViewport.refresh()


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    select: adsk.core.SelectionCommandInput = inputs.itemById('shaft_selection')
    extTreatments: adsk.core.DropDownCommandInput = inputs.itemById('external_treatments')
    clipOffset: adsk.core.DistanceValueCommandInput = inputs.itemById('clip_offset')
    intTreatments: adsk.core.DropDownCommandInput = inputs.itemById('internal_treatments')
    diameter: adsk.core.ValueCommandInput = inputs.itemById('diameter')
    depth: adsk.core.DistanceValueCommandInput = inputs.itemById('depth')

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    if changed_input.id == 'external_treatments':
        shaft_dia = 0
        if select.selectionCount > 0:
            shaft_dia = get_shaft_diameter(select.selection(0).entity)

        idx = extTreatments.selectedItem.index
        if idx == 0:
            clipOffset.isVisible = False
            clipOffset.value = 0
            clipOffset.minimumValue = 0
        elif idx == 1:  # E-clip
            e_clip: EClipGroove = EClipCollection.get(shaft_dia)
            clipOffset.isVisible = True
            clipOffset.value = e_clip.end_margin * 2.54
            clipOffset.minimumValue = e_clip.end_margin * 2.54
        else:  # Snap Ring
            snap_ring: SnapRingGroove = SnapRingCollection.get(shaft_dia)
            clipOffset.isVisible = True
            clipOffset.value = snap_ring.end_margin * 2.54
            clipOffset.minimumValue = snap_ring.end_margin * 2.54

    elif changed_input.id == 'internal_treatments':
        idx = intTreatments.selectedItem.index
        if idx == 0:
            diameter.isVisible = False
            depth.isVisible = False
        elif idx == intTreatments.listItems.count-1 :
            diameter.isVisible = True
            depth.isVisible = True
        else:
            diameter.isVisible = False
            depth.isVisible = True


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    futil.log(f'{CMD_NAME} Command Validate Event')

    inputs = args.inputs
    extTreatments: adsk.core.DropDownCommandInput = inputs.itemById('external_treatments')
    intTreatments: adsk.core.DropDownCommandInput = inputs.itemById('internal_treatments')

    if extTreatments.selectedItem.index == 0 and intTreatments.selectedItem.index == 0:
        args.areInputsValid = False

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []

def get_shaft_diameter(shaft_face: adsk.fusion.BRepFace) -> float:
    eval = shaft_face.evaluator

    bbox = shaft_face.boundingBox
    diagonal = bbox.minPoint.distanceTo(bbox.maxPoint)

    diameterIn = diagonal * 0.70710678 / 2.54

    # Round the diameter to the nearist 1/8"
    diameterIn = math.floor(diameterIn*8.0 + 0.5) / 8.0

    return diameterIn

def create_groove_body(face: adsk.fusion.BRepFace, groove: SnapRingGroove) -> adsk.fusion.BRepBody:
    
        # Get the temporary Brep manager
    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    groove_width = groove.width * 2.54
    groove_radius = groove.diameter * 2.54 / 2.0
    shaft_radius = groove.shaft_dia * 2.54 / 2.0
    outer_radius = groove.shaft_dia * 1.155 * 2.54 / 2.0
    offset = groove.offset

    origin = adsk.core.Point3D.create(0,0,0)
    grooveEndPt = adsk.core.Point3D.create(0,0,-offset-groove_width)
    grooveStartPt = adsk.core.Point3D.create(0, 0, -offset)

    # Create a disk from the groove inside point to the shaft end, full radius
    end_disk = tempBrepMgr.createCylinderOrCone(origin, outer_radius, grooveEndPt, outer_radius)

    # Create the inside disk to keep with the groove radius
    inner_disk = tempBrepMgr.createCylinderOrCone(origin, groove_radius, grooveEndPt, groove_radius)

    # Subtract the inner_disk from the end_disk
    tempBrepMgr.booleanOperation(end_disk, inner_disk, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    cut_body = end_disk

    # Create the outer remaining disk (whole shaft for e-clip, shaft_dia for snapring)
    if isinstance(groove, EClipGroove):
        shaft_disk = tempBrepMgr.createCylinderOrCone(origin, outer_radius, grooveStartPt, outer_radius)
    else:
        shaft_disk = tempBrepMgr.createCylinderOrCone(origin, shaft_radius, grooveStartPt, shaft_radius)

    # Subtract the shaft_disk from the cut body
    tempBrepMgr.booleanOperation(cut_body, shaft_disk, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    # occTrans = adsk.core.Matrix3D.create()
    # paramBody = face.body
    # occ = paramBody.assemblyContext
    # if occ:
    #     occTrans = occ.transform2
    #     occTrans.invert()

    # centroid = face.centroid
    # eval = face.evaluator
    # (_, param) = eval.getParameterAtPoint(centroid)
    # (_, normal) = eval.getNormalAtPoint(centroid)
    # (_, lengthDir, _) = eval.getFirstDerivative(param)
    # lengthDir.normalize()
    # widthDir = normal.crossProduct(lengthDir)

    # # Define a transform to position the temp body onto the part.
    # trans = adsk.core.Matrix3D.create()
    # trans.setWithCoordinateSystem(centroid, lengthDir, widthDir, normal)
    # tempBrepMgr.transform(cut_body, trans)
    # tempBrepMgr.transform(cut_body, occTrans)
    cut_body = transform_cut_body(face, cut_body)
    return cut_body

def create_hole_body(face: adsk.fusion.BRepFace, dia, depth) -> adsk.fusion.BRepBody:
        # Get the temporary Brep manager
    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    origin = adsk.core.Point3D.create(0,0,0)
    depthPt = adsk.core.Point3D.create(0,0,-depth)

    hole_cylinder = tempBrepMgr.createCylinderOrCone(origin, dia/2, depthPt, dia/2)

    cut_body = transform_cut_body(face, hole_cylinder)
    return cut_body

def transform_cut_body(face: adsk.fusion.BRepFace, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
        # Get the temporary Brep manager
    tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()

    occTrans = adsk.core.Matrix3D.create()
    paramBody = face.body
    occ = paramBody.assemblyContext
    if occ:
        occTrans = occ.transform2
        occTrans.invert()

    centroid = face.centroid
    eval = face.evaluator
    (_, param) = eval.getParameterAtPoint(centroid)
    (_, normal) = eval.getNormalAtPoint(centroid)
    (_, lengthDir, _) = eval.getFirstDerivative(param)
    lengthDir.normalize()
    widthDir = normal.crossProduct(lengthDir)

    # Define a transform to position the temp body onto the part.
    trans = adsk.core.Matrix3D.create()
    trans.setWithCoordinateSystem(centroid, lengthDir, widthDir, normal)
    tempBrepMgr.transform(body, trans)
    tempBrepMgr.transform(body, occTrans)

    return body
