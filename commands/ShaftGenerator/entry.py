import adsk.core
from adsk.core import Point3D as p3d
from adsk.core import Vector3D as v3d
import adsk.fusion
import os
import math
from ...lib import fusionAddInUtils as futil
from ... import config
from enum import Enum


app = adsk.core.Application.get()
ui = app.userInterface

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ShaftGenDialog'
CMD_NAME = 'Generate Shaft'
CMD_Description = 'Create a shaft of arbitrary length'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = False

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

class ShaftType:
    MAXSPLINE = "MAXSpline"
    HALF_HEX = '1/2" Hex'
    THREE_EIGHTS_HEX = '3/8" Hex'
    THREE_QUARTERS_TUBE = '3/4" OD Tube'

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

def command_created(args: adsk.core.CommandCreatedEventArgs):

  

    # General logging for debug.
    futil.log(f'{CMD_NAME} command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs
    shaftType = inputs.addDropDownCommandInput('shaft_type', 'Shaft Type', adsk.core.DropDownStyles.TextListDropDownStyle)
    items = shaftType.listItems
  
    items.add(ShaftType.MAXSPLINE, False )
    items.add(ShaftType.HALF_HEX, True)
    items.add(ShaftType.THREE_EIGHTS_HEX,  False)
    items.add(ShaftType.THREE_QUARTERS_TUBE, False)

    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    offset = adsk.core.ValueInput.createByString('0')
    lengthOfShaft = inputs.addValueInput('shaft_length', 'Shaft Length', defaultLengthUnits, offset)
    lengthOfShaft.minimumValue = 0.0

    futil.add_handler(args.command.execute, command_execute, local_handlers= local_handlers)

   

   
kZero = adsk.core.Point3D.create(0,0,0)



# # This event handler is called when the user clicks the OK button in the command dialog or 
# # is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):

#     # General logging for debug.
     futil.log(f'{CMD_NAME} Command Execute Event')

     inputs = args.command.commandInputs
     shaft_length: adsk.core.ValueCommandInput = inputs.itemById("shaft_length")
     shaft_type: adsk.core.DropDownCommandInput = inputs.itemById("shaft_type")

     

     design = adsk.fusion.Design.cast(app.activeProduct)
     root = design.rootComponent
     transform = adsk.core.Matrix3D.create()
     workingOccurance = root.occurrences.addNewComponent(transform)
     workingComp = workingOccurance.component
     workingComp.name = f'Shaft {shaft_type.selectedItem.name} {shaft_length.value} cm'

     sketch = workingComp.sketches.add(root.xYConstructionPlane)
     sketch.name = "Shaft Base"

     match (shaft_type.selectedItem.name):
         case ShaftType.MAXSPLINE:
            try: 
                
                p1 = p3d.create(0.347*2.54, -0.442*2.54)
               
                p2 = rotatePointByAngle(p1, kZero, -16.366)

                leftleftarccenter = p3d.create(0.239*2.54, -0.597*2.54)

                p3 = rotatePointByAngle(p2, leftleftarccenter, 69.836)

                

                leftmiddlearccenter = p3d.create(0.078*2.54, -0.602*2.54)

                p4 = rotatePointByAngle(p3, leftmiddlearccenter, -84.297 )

                rightmiddlecenter = p3d.create(-leftmiddlearccenter.x, leftmiddlearccenter.y)
                rightrightcenter = p3d.create(-leftleftarccenter.x, leftleftarccenter.y)
                p5 = p3d.create(-p4.x, p4.y)
                p6 = p3d.create(-p3.x, p3.y)
                p7 = p3d.create(-p2.x, p2.y)
                p8=p3d.create(-p1.x, p1.y)


            

                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(kZero, p2, p1)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(leftleftarccenter, p2, p3)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(leftmiddlearccenter, p4, p3)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(rightmiddlecenter, p6, p5)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(rightrightcenter, p6, p7)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(kZero, p8, p7)
                sketch.sketchCurves.sketchArcs.addByCenterStartEnd(kZero, p5, p4)


                sketch.sketchCurves.sketchLines.addByTwoPoints(kZero, p1)
                sketch.sketchCurves.sketchLines.addByTwoPoints(kZero, p8)


                
                




                    
                
            except Exception as ex:
                ui.messageBox(ex)
         case ShaftType.HALF_HEX:
            sketch.sketchCurves.sketchLines.addScribedPolygon(adsk.core.Point3D.create(0,0,0), 6 , 0, 0.635, False)
         case ShaftType.THREE_EIGHTS_HEX:
            sketch.sketchCurves.sketchLines.addScribedPolygon(adsk.core.Point3D.create(0,0,0), 6 , 0, 0.47625, False)
         case ShaftType.THREE_QUARTERS_TUBE:
            sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0,0,0), 1.905/2)
           
                 
         
   

     extrudeInput = workingComp.features.extrudeFeatures.createInput(sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
     valueInput = adsk.core.ValueInput.createByReal(shaft_length.value)
     distanceDef = adsk.fusion.DistanceExtentDefinition.create(valueInput)
     extrudeInput.setOneSideExtent(distanceDef, adsk.fusion.ExtentDirections.PositiveExtentDirection)
     
     workingComp.features.extrudeFeatures.add(extrudeInput)
     shellDistance = 0.125*2.54*0.5
     if (shaft_type.selectedItem.name == ShaftType.MAXSPLINE):
         shellDistance = 2.54 * 1/16
         try:
            circularPatternObjectCollection = adsk.core.ObjectCollection.create()
            circularPatternObjectCollection.add(workingComp.bRepBodies.item(0))
            circularPatterInput = workingComp.features.circularPatternFeatures.createInput(circularPatternObjectCollection, workingComp.zConstructionAxis)
            circularPatterInput.quantity = adsk.core.ValueInput.createByReal(6)
            workingComp.features.circularPatternFeatures.add(circularPatterInput)
            bodies = adsk.core.ObjectCollection.create()
            i = 0
            for body in workingComp.bRepBodies:
                if i != 0:
                    bodies.add(body)
                i += 1
            combineInput = workingComp.features.combineFeatures.createInput(workingComp.bRepBodies.item(0), bodies)
            workingComp.features.combineFeatures.add(combineInput)
         except Exception as ex:
             ui.messageBox(str(ex))

     if (shaft_type.selectedItem.name == ShaftType.THREE_QUARTERS_TUBE or shaft_type.selectedItem.name == ShaftType.MAXSPLINE):
         faces = []
         try:
            for face in workingComp.bRepBodies.item(0).faces:
                toAppend = True
                if not face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
                    toAppend = False
                else:
                    for edge in face.edges:
                        if (math.isclose(edge.length, shaft_length.value)):
                            toAppend = False
                            break
                if (toAppend):
                    faces.append(face)
            
         except Exception as e:
             ui.messageBox(str(e))
         try:
            shellObjectCollection = adsk.core.ObjectCollection.create()
            for face in faces:
                shellObjectCollection.add(face)
            shellFeatureInput = workingComp.features.shellFeatures.createInput(shellObjectCollection)
            shellFeatureInput.insideThickness = adsk.core.ValueInput.createByReal(shellDistance)
            workingComp.features.shellFeatures.add(shellFeatureInput)
         except Exception as ex:
            ui.messageBox(str(ex))

    
def rotatePointByAngle(point: p3d, center: p3d, angle: float) -> p3d:
    transformationMatrix = adsk.core.Matrix3D.create()
    transformationMatrix.setToRotation(math.radians(angle), v3d.create(0,0,1), center)
    copy = point.copy()
    copy.transformBy(transformationMatrix)
    return copy
