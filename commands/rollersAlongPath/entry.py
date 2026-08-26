import adsk.core
import adsk.fusion
from adsk.core import Vector3D as v3
import math
import os
from ...lib import fusionAddInUtils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_RollersOnPath'
CMD_NAME = 'Rollers Along Path'
CMD_Description = 'A Fusion Add-in Command with a dialog'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []




# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = config.get_marker_submenu()

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = config.get_marker_submenu()
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):

    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.


    # Create a value input field and set the default using 1 unit of the default length unit.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    try: 
        pathInput = inputs.addSelectionInput('path', "Path", 'Path to make rollers along')
        pathInput.addSelectionFilter("SketchCurves")
        #pathInput.addSelectionFilter(adsk.core.SelectionCommandInput.Edges)
        inputs.addValueInput('roller_length', 'Length of Rollers', defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 * 6))
        inputs.addValueInput('roller_diameter', 'Roller Diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(2.54 * 1))
        inputs.addIntegerSliderListCommandInput('roller_count', "Roller Count", [3, 4, 5, 6, 7, 8, 9, 10])


        
    except Exception as ex:
        ui.messageBox(f'{ex}')



    

    

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

    # TODO ******************************** Your code here ********************************

    design = adsk.fusion.Design.cast(app.activeProduct)
    startIndex = design.timeline.count
    root = design.rootComponent

    inputs = args.command.commandInputs

    # Get a reference to your command's inputs.
    try:
        path : adsk.core.SelectionCommandInput = inputs.itemById('path')
        curve : adsk.fusion.SketchCurve = path.selection(0).entity
    
      
        
        pathEval : adsk.core.CurveEvaluator3D = curve.worldGeometry.evaluator
        pathStart = pathEval.getParameterExtents()[1]
        pathLength = curve.length
        rollerLength = inputs.itemById('roller_length').value
        rollerDiameter = inputs.itemById('roller_diameter').value
        rollerCount = inputs.itemById('roller_count').valueOne

        workingOcc = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        workingOcc.activate()
        plane = workingOcc.component.constructionPlanes.createInput()
    
        sketch = workingOcc.component.sketches.add(curve.parentSketch.referencePlane)
        for curve in sketch.sketchCurves:
            curve.isConstruction = True


        circles : list[adsk.fusion.SketchCircle] = []
        points : list[adsk.core.Point3D] = []
        for i in range(rollerCount-1):
            centerPoint = pathEval.getPointAtParameter(pathEval.getParameterAtLength(pathStart, i * pathLength/(rollerCount - 1))[1])[1]
            points.append(centerPoint)
            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(centerPoint, rollerDiameter/2)
            circle.isFixed = True
            circles.append(circle)

        plane = sketch.referencePlane
        normal = None
        if isinstance(plane, adsk.fusion.BRepFace):
            normal = plane.evaluator.getNormalAtPoint(plane.pointOnFace)[1]
        if isinstance(plane, adsk.fusion.ConstructionPlane):
            normal = plane.geometry.normal
        else:
            ui.messageBox(f"commands/rollersAlongPath/entry.py has error on line 167, face {type(plane)} is not accounted for, please contact developer to fix")
            return
        endCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius(pathEval.getEndPoints()[2], rollerDiameter/2)
        endCircle.isFixed = True
        circles.append(endCircle)
        points.append(pathEval.getEndPoints()[2])
        rollerCollection = adsk.core.ObjectCollection.create()
        for profile in sketch.profiles:
            rollerCollection.add(profile)

        input2 = workingOcc.component.features.extrudeFeatures.createInput(rollerCollection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        input2.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(rollerLength)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        workingOcc.component.features.extrudeFeatures.add(input2)




        for i in range(len(circles) - 1):
            v1, v2 = getVectors(points[i], points[i+1], normal)
            v1.normalize()
            v2.normalize()
            line1 = sketch.sketchCurves.sketchLines.addByTwoPoints(futil.pointFromOffset(points[i], v1.x*rollerDiameter/2/2.54, v1.y*rollerDiameter/2/2.54), futil.pointFromOffset(points[i+1], v1.x*rollerDiameter/2/2.54, v1.y*rollerDiameter/2/2.54))
            line2 = sketch.sketchCurves.sketchLines.addByTwoPoints(futil.pointFromOffset(points[i], v2.x*rollerDiameter/2/2.54, v2.y*rollerDiameter/2/2.54), futil.pointFromOffset(points[i+1], v2.x*rollerDiameter/2/2.54, v2.y*rollerDiameter/2/2.54))
           # sketch.geometricConstraints.addCoincident(line1.startSketchPoint, circles[i])
            #sketch.geometricConstraints.addCoincident(line2.endSketchPoint, circles[i])
            #sketch.geometricConstraints.addCoincident(line1.endSketchPoint, circles[i+1])
       #     sketch.geometricConstraints.addCoincident(line2.startSketchPoint, circles[i+1])
            

        
        normalCollection = adsk.core.ObjectCollection.create()
        
        for profile in sketch.profiles:
            
        
            normalCollection.add(profile)

        input = workingOcc.component.features.extrudeFeatures.createInput(normalCollection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(0.125*2.54)), adsk.fusion.ExtentDirections.NegativeExtentDirection)
       
        feature = workingOcc.component.features.extrudeFeatures.add(input)
        
        annoyingCollection = adsk.core.ObjectCollection.create()
        annoyingCollection.add(feature)
        planeInput = workingOcc.component.constructionPlanes.createInput()
        planeInput.setByOffset(plane,adsk.core.ValueInput.createByReal( rollerLength/2))
        
        inp = workingOcc.component.features.mirrorFeatures.createInput(annoyingCollection, workingOcc.component.constructionPlanes.add(planeInput))
        workingOcc.component.features.mirrorFeatures.add(inp)
        futil.get_random_flat_color(workingOcc, design, app)
        workingOcc.component.name = f"Rollers Along Path"
        endIndex = design.timeline.count - 1
        design.timeline.timelineGroups.add(startIndex, endIndex)
    except Exception as ex:
        ui.messageBox(f'{ex}')



def translateBy(self : adsk.core.Point3D, vector: adsk.core.Vector3D):
    fuck = self.copy()
    fuck.translateBy(vector)
    return fuck
        
def getVectors(point1 : adsk.core.Point3D, point2 : adsk.core.Point3D, normal : adsk.core.Vector3D):
    positiveRotationMatrix = adsk.core.Matrix3D.create()
    positiveRotationMatrix.setToRotation(math.radians(90), normal, point1)
    negativeRotationMatrix = adsk.core.Matrix3D.create()
    negativeRotationMatrix.setToRotation(math.radians(-90), normal, point1)
    positiveVector = point1.vectorTo(point2)
    negativeVector = point1.vectorTo(point2)
    positiveVector.transformBy(positiveRotationMatrix)
    negativeVector.transformBy(negativeRotationMatrix)
    return positiveVector, negativeVector
        

def pointFromOffset(reference:adsk.core.Point3D, offsetXInches, offsetYInches):
    copy = reference.copy()
    copy.translateBy(v3.create(offsetXInches*2.54, offsetYInches*2.54, 0))
    return copy



# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    valueInput = inputs.itemById('value_input')
    if valueInput.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
