import adsk.core
import adsk.fusion
# import os
import math
# from ...lib import fusionAddInUtils as futil
# from ... import config
from ...lib.CCLine import *

app = adsk.core.Application.get()
# ui = app.userInterface

def calcCCLineData( ld: CCLineData ):
    if ld.motion == 0:
        # 20DP Gears
        ld.Teeth = 0
        ld.ccDistIN = GearsCCDistanceIN( ld.N1, ld.N2, 20 )
        ld.PD1 = GearsPitchDiameterIN( ld.N1, 20 )
        ld.PD2 = GearsPitchDiameterIN( ld.N2, 20 )
        ld.OD1 = GearsOuterDiameterIN( ld.N1, 20 )
        ld.OD2 = GearsOuterDiameterIN( ld.N2, 20 )
    else :
        if ld.motion == 1:
            # HTD 5mm Belt
            beltPitchMM = 5
        else :
            # HTD 3mm Belt
            beltPitchMM = 3
        ld.ccDistIN = BeltCCDistanceIN( ld.N1, ld.N2, ld.Teeth, beltPitchMM )
        ld.PD1 = BeltPitchDiameterIN( ld.N1, beltPitchMM )
        ld.PD2 = BeltPitchDiameterIN( ld.N2, beltPitchMM )
        ld.OD1 = BeltOuterDiameterIN( ld.N1, beltPitchMM )
        ld.OD2 = BeltOuterDiameterIN( ld.N2, beltPitchMM )


def GearsCCDistanceIN( N1: int, N2: int, dp: int ) -> float:
    pitch_diameter1 = N1 / (1.0 * dp)
    pitch_diameter2 = N2 / (1.0 * dp)

    return (pitch_diameter1 + pitch_diameter2) / 2

def GearsPitchDiameterIN( NT: int, dp: int ) -> float:
    return NT / (1.0 * dp)

def GearsOuterDiameterIN( NT: int, dp: int ) -> float:
    return NT / (1.0 * dp) + 0.1

def BeltCCDistanceIN( N1: int, N2: int, beltTeeth: int, pitchMM: int ) -> float:
    PL = beltTeeth * pitchMM / 25.4 # in inches
    if N1 > N2:
        PD1 = BeltPitchDiameterIN( N1, pitchMM )
        PD2 = BeltPitchDiameterIN( N2, pitchMM )
    else:
        PD1 = BeltPitchDiameterIN( N2, pitchMM )
        PD2 = BeltPitchDiameterIN( N1, pitchMM )

    b = 2 * PL - math.pi * ( PD1 + PD2 )
    fourAC = 8 * (PD1 - PD2)*(PD1 - PD2)

    if b*b - fourAC < 0 :
        return 0.0
    
    return ( b + math.sqrt( b*b - fourAC) ) / 8

def BeltPitchDiameterIN( NT: int, pitchMM: int ) -> float:
    return NT * pitchMM / ( 25.4 * math.pi )

def BeltOuterDiameterIN( NT: int, pitchMM: int ) -> float:
        # Approximation of the OD of the flanges on the pulleys
    return BeltPitchDiameterIN(NT, pitchMM) + 0.15

def createCCLine( 
    startpt: adsk.fusion.SketchPoint, 
    endpt: adsk.fusion.SketchPoint ) -> adsk.fusion.SketchLine :

    if startpt == None:
        design = adsk.fusion.Design.cast(app.activeProduct)
        sketch = design.activeEditObject
        startpt = sketch.sketchPoints.add( adsk.core.Point3D.create( 0, 0, 0 ) )
    
    sketch = startpt.parentSketch

    if endpt == None:
        endpt3D = futil.offsetPoint3D( startpt.geometry, 2 * 2.54, 0, 0 )
        endpt = sketch.sketchPoints.add( endpt3D )

    # futil.log( f' createCCLine() points = {futil.format_Point3D(startpt.geometry)} -- {futil.format_Point3D(endpt.geometry)}')

    # Create C-C line a midpoint for it and dimension it
    ccLine = sketch.sketchCurves.sketchLines.addByTwoPoints( startpt, endpt )
    ccLine.isConstruction = True

    return ccLine

def dimAndLabelCCLine( ccLine: CCLine ) :

    sketch = ccLine.line.parentSketch
    line = ccLine.line
    ld = ccLine.data

    midPt = futil.midPoint3D( line.startSketchPoint.geometry, line.endSketchPoint.geometry )
    normal = futil.sketchLineNormal( line )
    normal = futil.multVector2D( normal, ld.ccDistIN / 4 )

    # Dimension C-C line
    if abs(normal.y) < 0.001  :
        textPt = futil.offsetPoint3D( midPt, normal.x, normal.y, 0 )
    elif normal.y < 0 :
        textPt = futil.offsetPoint3D( midPt, normal.x, normal.y, 0 )
    else:
        textPt = futil.offsetPoint3D( midPt, -normal.x, -normal.y, 0 )
    
    ccLine.lengthDim = sketch.sketchDimensions.addDistanceDimension( 
        line.startSketchPoint, line.endSketchPoint, 
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPt )
    ccLine.lengthDim.value = (ld.ccDistIN + ld.ExtraCenterIN) * 2.54

    # Create SketchText and attach it to the C-C Line
    label = createLabelString( ld )
    textHeight = computeTextSizeIN( ld ) * 2.54 # in cm

    # futil.log( f'ccDist = {ld.ccDistIN}in, Text Height = {textHeight}in')
    cornerPt = line.startSketchPoint.geometry
    diagPt =  futil.addPoint3D( cornerPt, adsk.core.Point3D.create( line.length, textHeight, 0 ) )
    textInput = sketch.sketchTexts.createInput2( label, textHeight )
    textInput.setAsMultiLine( cornerPt, diagPt, 
                        adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                        adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0 )
    ccLine.textBox = sketch.sketchTexts.add( textInput )
    textDef: adsk.fusion.MultiLineTextDefinition = ccLine.textBox.definition
    textBoxLines = textDef.rectangleLines
    textBaseLine = textBoxLines[0]
    TextHeightLine = textBoxLines[1]
    # midPt3D = futil.midPoint3D(textBaseLine.startSketchPoint.geometry, textBaseLine.endSketchPoint.geometry )
    # ccLine.midPt = sketch.sketchPoints.add( midPt3D )

    textPoint = futil.offsetPoint3D( TextHeightLine.startSketchPoint.geometry, -textHeight/2, textHeight/2, 0 )
    ccLine.textHeight = sketch.sketchDimensions.addDistanceDimension( TextHeightLine.startSketchPoint, TextHeightLine.endSketchPoint,
                                                              adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                                              textPoint  )
    ccLine.textHeight.value = textHeight * 2.0

    # sketch.geometricConstraints.addMidPoint( ccLine.midPt, textBaseLine  )
    # sketch.geometricConstraints.addMidPoint( ccLine.midPt, line  )
    # sketch.geometricConstraints.addParallel( textBaseLine, line  )
    if textBaseLine.startSketchPoint.geometry.distanceTo(line.startSketchPoint.geometry) < \
        textBaseLine.startSketchPoint.geometry.distanceTo(line.endSketchPoint.geometry) :
        sketch.geometricConstraints.addCoincident( textBaseLine.startSketchPoint, line.startSketchPoint )
        sketch.geometricConstraints.addCoincident( textBaseLine.endSketchPoint, line.endSketchPoint )
    else:
        sketch.geometricConstraints.addCoincident( textBaseLine.startSketchPoint, line.endSketchPoint )
        sketch.geometricConstraints.addCoincident( textBaseLine.endSketchPoint, line.startSketchPoint )


def createLabelString( ld: CCLineData ) -> str:

    n1 = ld.N1
    n2 = ld.N2
    p1 = ld.PIN1
    p2 = ld.PIN2
    if n1 > n2 :
        n1 = ld.N2
        n2 = ld.N1
        p1 = ld.PIN2
        p2 = ld.PIN1

    if ld.motion == 0:
        if p1 > 0 and p1 != n1 :
            if p2 > 0 and p2 != n2 :
                lineLabel = f'Gear 20DP {p1}T({n1}T-CD)+{p2}T({n2}T-CD)'
            else:
                lineLabel = f'Gear 20DP {p1}T({n1}T-CD)+{n2}T'
        else:
            lineLabel = f'Gear 20DP {n1}T+{n2}T'
    else :
        if ld.motion == 1:
    #         # HTD 5mm Belt
            lineLabel = f'{ld.Teeth}T HTD 5mm ({n1}Tx{n2}T)'
        else :
    #         # HTD 3mm Belt
            lineLabel = f'{ld.Teeth}T GT2 3mm ({n1}Tx{n2}T)'
    
    if abs(ld.ExtraCenterIN) > 0.0005 :
        lineLabel += f' EC({ld.ExtraCenterIN:.3})'

    return lineLabel

def createEndCircles( ccLine: CCLine ) :
    PDcircleData = createCirclePair( ccLine.line, ccLine.data.PD1, ccLine.data.PD2, 45.0 )
    ccLine.pitchCircle1 = PDcircleData[0][0]
    ccLine.pitchCircle2 = PDcircleData[0][1]
    ccLine.PD1Dim = PDcircleData[1][0]
    ccLine.PD2Dim = PDcircleData[1][1]
    ODcircleData = createCirclePair( ccLine.line, ccLine.data.OD1, ccLine.data.OD2, 135.0 )
    ccLine.ODCircle1 = ODcircleData[0][0]
    ccLine.ODCircle2 = ODcircleData[0][1]
    ccLine.OD1Dim = ODcircleData[1][0]
    ccLine.OD2Dim = ODcircleData[1][1]

def createCirclePair( line: adsk.fusion.SketchLine, 
                      dia1IN: float, dia2IN: float, dimAngleDeg: float ) :

    sketch = line.parentSketch

    # Create Start point centered circle and dimension it
    startCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( line.startSketchPoint, dia1IN * 2.54 / 2 )
    startCircle.isConstruction = True

    dimDir = adsk.core.Vector2D.create( dia1IN * 2.54 / 5, 0 )
    rotMatrix = adsk.core.Matrix2D.create()
    rotMatrix.setToRotation( dimAngleDeg * math.pi / 180, adsk.core.Point2D.create() )
    dimDir.transformBy( rotMatrix )
    textPoint = futil.offsetPoint3D( startCircle.centerSketchPoint.geometry, dimDir.x, dimDir.y, 0 )
    diaDim1 = sketch.sketchDimensions.addDiameterDimension( startCircle, textPoint )
    diaDim1.value = dia1IN * 2.54
    # sketch.geometricConstraints.addCoincident( startCircle.centerSketchPoint, line.startSketchPoint )

    # Create End point centered circle and dimension it
    endCircle = sketch.sketchCurves.sketchCircles.addByCenterRadius( line.endSketchPoint, dia2IN * 2.54 / 2 )
    endCircle.isConstruction = True

    dimDir = adsk.core.Vector2D.create( dia2IN * 2.54 / 5, 0 )
    rotMatrix = adsk.core.Matrix2D.create()
    rotMatrix.setToRotation( dimAngleDeg * math.pi / 180, adsk.core.Point2D.create() )
    dimDir.transformBy( rotMatrix )
    textPoint = futil.offsetPoint3D( endCircle.centerSketchPoint.geometry, dimDir.x, dimDir.y, 0 )
    diaDim2 = sketch.sketchDimensions.addDiameterDimension( endCircle, textPoint )
    diaDim2.value = dia2IN * 2.54
    # sketch.geometricConstraints.addCoincident( endCircle.centerSketchPoint, line.endSketchPoint )

    return ([ startCircle, endCircle ], [diaDim1, diaDim2])

def computeTextSizeIN( ld: CCLineData ) -> float:
    textHeight = ld.ccDistIN / 28.0
    if textHeight < 0.025:
        textHeight = 0.025

    return textHeight

def modifyCCLine( ccLine: CCLine ):

    ld = ccLine.data

    try:
        ccLine.lengthDim.value = (ld.ccDistIN + ld.ExtraCenterIN) * 2.54
    except:
        futil.popup_error( 'Failed to resize centerline!  Are both ends of C-C Distance constrained?', True )
        return

    label = createLabelString( ld )
    ccLine.textBox.text = label
    ccLine.textBox.height = computeTextSizeIN( ld ) * 2.54
    ccLine.textHeight.value = ccLine.textBox.height * 2.0

    ccLine.PD1Dim.value = ld.PD1 * 2.54
    ccLine.PD2Dim.value = ld.PD2 * 2.54
    ccLine.OD1Dim.value = ld.OD1 * 2.54
    ccLine.OD2Dim.value = ld.OD2 * 2.54

