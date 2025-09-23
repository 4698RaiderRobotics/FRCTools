import adsk.core
import adsk.fusion
import os
import math
import typing
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_TubifyDialog'
CMD_NAME = 'Tubify Solid'
CMD_Description = 'Shell and create holes in a rectangular solid'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Bolt Pattern struct
class HoleConfig(typing.NamedTuple) :
    number_sides_with_holes: int = 0
    hole_spacing: float = 0.5
    hole_diameter: float = 0.196
    description: str = "unset"

holeConfigs: list[HoleConfig] = [
    HoleConfig(0, 0, 0.196, 'No Holes'),
    HoleConfig(4, 0.5, 0.196, 'All 4 Sides 1/2" Spacing (WCP)'),
    HoleConfig(4, 1, 0.196, 'All 4 Sides 1" Spacing (VEX)'),     # Only for 1x1 tubing...
    HoleConfig(2, 0.5, 0.196, '2 Sides 1/2" Spacing (WCP)'),
    HoleConfig(2, 1, 0.196, '2 Sides 1" Spacing (VEX)'),
]

holeCfgDefault = 0      #   No Holes

wallThicknesses = ( 
    (0.050, '0.050"'),
    (0.0625, '1/16"'),
    (0.09375, '3/32"'),
    (0.1, '0.100"'),
    (0.125, '1/8"'),
)
wallThicknessesDefault = wallThicknesses.index( (0.125, '1/8"') )

class TubifyParams :
    solid: adsk.fusion.BRepBody = None
    wall_thickness: float = 0.125
    config: HoleConfig = None
    end_offset: float = 0.0
    showPartialHoles: bool = True

    def __init__( self, solid: adsk.fusion.BRepBody, wThickIdx: int, holeConfigIdx, endOffsetIn, showPartialHoles ) :
        self.solid = solid
        thicknessCfg = wallThicknesses[ wThickIdx ]
        self.wall_thickness = thicknessCfg[0]
        self.config = holeConfigs[ holeConfigIdx ]
        self.end_offset = endOffsetIn
        self.showPartialHoles = showPartialHoles

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
    # futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.

    # Create a Solid Body selection input.
    solidSelection = inputs.addSelectionInput('tube_solid', 'Tubes', 'Select the solid to Tubify')
    solidSelection.addSelectionFilter( "SolidBodies" )
    solidSelection.setSelectionLimits( 1, 0 )

    # Create a simple text box input.
    holeSidesInp = inputs.addDropDownCommandInput('hole_sides', 'Hole Sides', adsk.core.DropDownStyles.TextListDropDownStyle)
    for holeCfg in holeConfigs:
        holeSidesInp.listItems.add( holeCfg.description, False, '')
    holeSidesInp.listItems.item( holeCfgDefault ).isSelected = True

    # Create a simple text box input.
    wallThickInput = inputs.addDropDownCommandInput('wall_thickness', 'Wall Thickness', adsk.core.DropDownStyles.TextListDropDownStyle)
    for wallthick in wallThicknesses:
        wallThickInput.listItems.add( wallthick[1], False, '')
    wallThickInput.listItems.item( wallThicknessesDefault ).isSelected = True

    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = "in"
    default_value = adsk.core.ValueInput.createByString('0.0')
    endOffset = inputs.addValueInput('end_offset', 'End Offset', defaultLengthUnits, default_value)
    endOffset.isVisible = False

    # Create a checkbox for partial holes.
    showPartialHoles = inputs.addBoolValueInput( "create_partial_holes", "Show Partial Holes", True, "", True )
    showPartialHoles.isVisible = False

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
    # futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    solidSelection: adsk.core.SelectionCommandInput = inputs.itemById('tube_solid')
    endOffset: adsk.core.ValueCommandInput = inputs.itemById('end_offset')
    holeSides: adsk.core.DropDownCommandInput = inputs.itemById('hole_sides')
    wallThickness: adsk.core.DropDownCommandInput = inputs.itemById('wall_thickness')
    showPartialHoles = inputs.itemById('create_partial_holes').value

    wThickIdx = wallThickness.selectedItem.index
    holeSidesIdx = holeSides.selectedItem.index
    endOffsetIn = endOffset.value / 2.54

    ui.progressBar.show( 'Tubifying ... %v of %m', 0, solidSelection.selectionCount - 1 )
    try :
        i = 0
        while i < solidSelection.selectionCount :
            ui.progressBar.progressValue = i
            adsk.doEvents()
            solid: adsk.fusion.BRepBody = solidSelection.selection(i).entity
            if solid.vertices.count != 8 :
                futil.popup_error(f'Invalid number of vertices in body!  Should be 8 got {solid.vertices.count}')
            else :
                tubifyInfo = TubifyParams( solid, wThickIdx, holeSidesIdx, endOffsetIn, showPartialHoles )
                tubifySolid( tubifyInfo )
            i += 1
    except:
        futil.handle_error( '        ============  Tubify Failed  ============\n\n', True )

    ui.progressBar.hide()

# Tubify and single BRep solid
def tubifySolid( tubifyInfo: TubifyParams ) :

    orientedBB = tubifyInfo.solid.orientedMinimumBoundingBox
    # futil.print_OrientedBB( orientedBB )
    longLength = orientedBB.height
    if orientedBB.width > longLength:
        longLength = orientedBB.width
    if orientedBB.length > longLength:
        longLength = orientedBB.length
    longLength /= 2.54 # convert to inches

    # Find end faces with the smallest area
    endArea = 999999
    sideMaxArea = 0
    i = 0
    while i < tubifyInfo.solid.faces.count :
        face = tubifyInfo.solid.faces.item(i)
        if face.area < endArea :
            endArea = face.area
        if face.area > sideMaxArea :
            sideMaxArea = face.area
        i += 1

    endFaces = adsk.core.ObjectCollection.create()
    i = 0
    while i < tubifyInfo.solid.faces.count :
        face = tubifyInfo.solid.faces.item(i)
        if abs(face.area - endArea) < 0.001:
            endFaces.add( face )
        i += 1

    isRectangle = False
    if abs(endArea - 12.9032) < 0.001 :
        futil.log( f'Found {len(endFaces)} end Faces of the Solid 2 x 1 Body.')
        isRectangle = True
    elif abs(endArea - 6.4516) < 0.001 :
        futil.log( f'Found {len(endFaces)} end Faces of the Solid 1 x 1 Body.')
    else :
        futil.log( f'Found {len(endFaces)} end Faces of the Solid ? x ? Body with area = {endArea}.')
        futil.popup_error(f'Body does not appear to be either 1x1 or 1x2')
        return

    # Determine the side faces and wide side faces if 2 x 1 body
    narrowSideFaces = adsk.core.ObjectCollection.create()
    wideSideFaces = adsk.core.ObjectCollection.create()
    otherWideSideFaces = adsk.core.ObjectCollection.create()
    i = 0
    while i < tubifyInfo.solid.faces.count :
        face = tubifyInfo.solid.faces.item(i)
        if abs(face.area - sideMaxArea) < 0.001:
            wideSideFaces.add( face )
        elif isRectangle and face.area - endArea > 0.001 :
            narrowSideFaces.add( face )
        i += 1

    if not isRectangle:
        otherWideSideFaces.add( wideSideFaces.item(1) )
        otherWideSideFaces.add( wideSideFaces.item(3) )
        wideSideFaces.removeByIndex( 1 )
        wideSideFaces.removeByIndex( 2 ) # 3 becomes 2

    # futil.log( f'Found {len(wideSideFaces)} wide side Faces, {len(otherWideSideFaces)} other wide faces, and {len(narrowSideFaces)} narrow side Faces.')


    # Obtain the component of the solid body
    workingComp = tubifyInfo.solid.parentComponent

    # Shell out the tube 
    shells = workingComp.features.shellFeatures
    shellThickness = adsk.core.ValueInput.createByReal( tubifyInfo.wall_thickness * 2.54 )
    shellSolidInput = shells.createInput( endFaces )
    shellSolidInput.insideThickness = shellThickness
    shells.add( shellSolidInput )

    # If no holes just return
    if tubifyInfo.config.number_sides_with_holes == 0 :
        return

    # 2 Side Holes
    if isRectangle :
        createHoleProfiles( workingComp, tubifyInfo, narrowSideFaces, longLength )
    else:
        createHoleProfiles( workingComp, tubifyInfo, wideSideFaces, longLength )

    # 4 Side Holes
    if tubifyInfo.config.number_sides_with_holes == 4 : 
        if isRectangle :
            createHoleProfiles( workingComp, tubifyInfo, wideSideFaces, longLength )
        else :
            createHoleProfiles( workingComp, tubifyInfo, otherWideSideFaces, longLength )


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs

    command_execute( args )
    args.isValidResult = True

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # # General logging for debug.
    # futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

    endOffset: adsk.core.ValueCommandInput = inputs.itemById('end_offset')
    holeSides: adsk.core.DropDownCommandInput = inputs.itemById('hole_sides')
    showPartialHoles = inputs.itemById('create_partial_holes')

    if changed_input.id == 'hole_sides' :
        holeCfg = holeConfigs[ holeSides.selectedItem.index ]
        if holeCfg.number_sides_with_holes == 0 :
            # No holes
            endOffset.isVisible = False
            showPartialHoles.isVisible = False
        else :
            endOffset.isVisible = True
            showPartialHoles.isVisible = True
                

# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):

    inputs = args.inputs

    endOffset: adsk.core.ValueCommandInput = inputs.itemById('end_offset')
    holeSides: adsk.core.DropDownCommandInput = inputs.itemById('hole_sides')

    # Verify the validity of the input values. This controls if the OK button is enabled or not.

    holeCfg = holeConfigs[ holeSides.selectedItem.index ]

    if holeCfg[0] == 0 :
        args.areInputsValid = True
    elif endOffset.value >= 0 and endOffset.value <= holeCfg[1] * 2.54 :  # in centimeters?
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    # futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def createHoleProfiles( 
        workingComp: adsk.fusion.Component, tubifyInfo: TubifyParams,
        sideFaces: adsk.core.ObjectCollection, cutDepth: float ) :

    # Create a new sketch for the wide side holes
    sketch = workingComp.sketches.add( sideFaces.item(0) )
    sketch.name = 'Tubify'
    sketchEdges = adsk.core.ObjectCollection.create()
    for edge in sideFaces.item(0).edges :
        sketchEdges.add( sketch.project( edge ).item(0) )
    
    # futil.print_SketchObjectCollection( sketchEdges )

    longEdge: adsk.fusion.SketchLine = sketchEdges.item(0)
    shortEdge: adsk.fusion.SketchLine = sketchEdges.item(1)
    if shortEdge.length > longEdge.length :
        longEdge = sketchEdges.item(1)
        shortEdge = sketchEdges.item(0)

    lengthIn = longEdge.length / 2.54
    widthIn = shortEdge.length / 2.54
        
    leUnitVec = futil.sketchLineUnitVec( longEdge )
    seUnitVec = futil.sketchLineUnitVec( shortEdge )
    if longEdge.startSketchPoint.geometry.isEqualTo( shortEdge.startSketchPoint.geometry ) :
        # Set the corner point, unit vectors are correct.
        cornerPoint = longEdge.startSketchPoint
        # futil.log( f'longEdge Start is shortEdge Start.')
    elif longEdge.startSketchPoint.geometry.isEqualTo( shortEdge.endSketchPoint.geometry ) :
        # Set the corner point, se unit vector is flipped.
        cornerPoint = longEdge.startSketchPoint
        seUnitVec = futil.multVector2D( seUnitVec, -1.0 )
        # futil.log( f'longEdge Start is shortEdge End.')
    elif longEdge.endSketchPoint.geometry.isEqualTo( shortEdge.startSketchPoint.geometry ) :
        # Set the corner point, le unit vector is flipped.
        cornerPoint = longEdge.endSketchPoint
        leUnitVec = futil.multVector2D( leUnitVec, -1.0 )
        # futil.log( f'longEdge End is shortEdge Start.')
    elif longEdge.endSketchPoint.geometry.isEqualTo( shortEdge.endSketchPoint.geometry ) :
        # Set the corner point, both unit vectors are flipped.
        cornerPoint = longEdge.endSketchPoint
        leUnitVec = futil.multVector2D( leUnitVec, -1.0 )
        seUnitVec = futil.multVector2D( seUnitVec, -1.0 )
        # futil.log( f'longEdge End is shortEdge End.')
        # futil.print_SketchCurve( longEdge )
        # futil.print_SketchCurve( shortEdge )
        # futil.log( f'leUnitVec= {futil.format_Vector2D(leUnitVec)}, seUnitVec= {futil.format_Vector2D(seUnitVec)}')
    else:
        # We should never get here!!!
        futil.print_Point3D( longEdge.startSketchPoint.geometry, "longEdge start: ")
        futil.print_Point3D( longEdge.endSketchPoint.geometry, "longEdge end: ")
        futil.print_Point3D( shortEdge.startSketchPoint.geometry, "shortEdge start: ")
        futil.print_Point3D( shortEdge.endSketchPoint.geometry, "shortEdge end: ")
        futil.popup_error(f'Unhandled shortEdge/longEdge point case.')
        return

    # Determine what the length dimension should be for the first hole
    if tubifyInfo.config.hole_spacing - tubifyInfo.end_offset < tubifyInfo.config.hole_diameter/2.0 :
        # Negative means the hole center should be off the solid initially
        LengthOffsetIn = -1.0 * (tubifyInfo.config.hole_spacing - tubifyInfo.end_offset)
    else :
        LengthOffsetIn = tubifyInfo.end_offset

    # futil.log( f'hs={tubifyInfo.config.hole_spacing} off={tubifyInfo.end_offset}, dia={tubifyInfo.config.hole_diameter}')
    # futil.log( f'LengthOffset={LengthOffsetIn}')
    # Create the corner hole to use as the rectangular pattern
    holeDiameter = tubifyInfo.config.hole_diameter * 2.54
    if LengthOffsetIn > 0 :
        diag = leUnitVec.copy()
        diag.add( seUnitVec )
        holeCenterPt = adsk.core.Point3D.create( diag.x, diag.y, 0 )
    else :
        diag = futil.multVector2D( leUnitVec, -1.0 )
        diag.add( seUnitVec )
        holeCenterPt = adsk.core.Point3D.create( diag.x, diag.y, 0 )
    holeCenterPt = futil.addPoint3D( holeCenterPt, cornerPoint.geometry )
    # futil.log( f' -------- Corner Hole center point:::')
    # futil.print_Point3D( holeCenterPt )
    cornerHole = sketch.sketchCurves.sketchCircles.addByCenterRadius( holeCenterPt, holeDiameter / 2 )
    textPoint = futil.offsetPoint3D( cornerHole.centerSketchPoint.geometry, 0.1, 0.1, 0 )
    diamDim = sketch.sketchDimensions.addDiameterDimension( cornerHole, textPoint )
    diamDim.value = holeDiameter

    # Create the width direction dimension
    textPoint = cornerPoint.geometry
    widthDim = sketch.sketchDimensions.addOffsetDimension( 
        longEdge, cornerHole.centerSketchPoint, textPoint )
    widthDim.value = 0.5 * 2.54

    # horizDim = sketch.sketchDimensions.addDistanceDimension( 
    #     cornerHole.centerSketchPoint, cornerPoint, 
    #     adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation, textPoint )
    # horizDim.value = 0.5 * 2.54


    # Either create the length direction dimension of make the center
    # coincident with the end line if the offset is zero.
    if abs( LengthOffsetIn ) < 0.001 :
        sketch.geometricConstraints.addCoincident( cornerHole.centerSketchPoint, shortEdge )
    else :
        textPoint = cornerPoint.geometry
        lengthDim = sketch.sketchDimensions.addOffsetDimension( 
            shortEdge, cornerHole.centerSketchPoint, textPoint )
        lengthDim.value = abs(LengthOffsetIn * 2.54)
        # vertDim = sketch.sketchDimensions.addDistanceDimension( 
        #     cornerHole.centerSketchPoint, cornerPoint, 
        #     adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, textPoint )
        # vertDim.value = dimValue

    # Create the rectangular pattern
    rectPattern = sketch.geometricConstraints.createRectangularPatternInput( 
        [cornerHole], adsk.fusion.PatternDistanceType.SpacingPatternDistanceType )
    rectPattern.directionOneEntity = shortEdge
    rectPattern.directionTwoEntity = longEdge

    # Determine the number repeats in the rectangular pattern
    widthRepeats = int( (widthIn / 0.5) - 0.5 )
        
    lengthRepeats = int( (lengthIn / tubifyInfo.config.hole_spacing) + 0.5 )
    if tubifyInfo.showPartialHoles :
        lengthRepeats += 1

    if widthRepeats == 0 :
        futil.log(f'    Problem computing width repeats GOT ZERO !!!!')
        widthRepeats = 1
    if lengthRepeats == 0 :
        futil.log(f'    Problem computing length repeats GOT ZERO !!!!')
        lengthRepeats = 1
    futil.log( f' Using a {widthRepeats} x {lengthRepeats} rectangular pattern on {widthIn}" x {lengthIn}" tube.')

    # Setup the width hole spacing and number of holes...
    rectPattern.distanceOne = futil.Value( 0.5 )
    rectPattern.quantityOne = futil.Value( widthRepeats )

    # Setup the length hole spacing and number of holes
    rectPattern.distanceTwo = futil.Value( tubifyInfo.config.hole_spacing )
    rectPattern.quantityTwo = futil.Value( lengthRepeats )
    sketch.geometricConstraints.addRectangularPattern( rectPattern )

    holeArea = holeDiameter * holeDiameter * math.pi / 4.0

    # for p in sketch.profiles:
    #     futil.log(f'   Profile area = {p.areaProperties().area}, hole area = {holeArea}')

    # Find the holes profiles
    holeProfiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        if tubifyInfo.showPartialHoles:
            if holeArea - profile.areaProperties().area > -0.001 : 
                holeProfiles.add( profile )
        elif abs( holeArea - profile.areaProperties().area ) < 0.001 :
            holeProfiles.add( profile )
    
    # Extrude the holes through the tube
    extrudes = workingComp.features.extrudeFeatures
    cutDistance = adsk.core.ValueInput.createByReal( cutDepth * 2.54 )
    extrudeCut = extrudes.createInput(holeProfiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    distance = adsk.fusion.DistanceExtentDefinition.create( cutDistance )
    extrudeCut.setOneSideExtent( distance, adsk.fusion.ExtentDirections.NegativeExtentDirection )
    extrudeCut.participantBodies = [ sideFaces.item(0).body ]
    extrudes.add( extrudeCut )
