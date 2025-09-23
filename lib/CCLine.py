import adsk.core
import adsk.fusion
from . import fusionAddInUtils as futil



# Attribute constants
CC_ATTRIBUTE_GROUP = "CCDistance_Group"
CC_LINE_TEETH = "Teeth"
CC_LINE_N1 = "N1"
CC_LINE_N2 = "N2"
CC_LINE_PIN1 = "PIN1"
CC_LINE_PIN2 = "PIN2"
CC_LINE_EC = "EC"
CC_LINE_MOTION_TYPE = "MOTION"
CC_LINE_PITCH_CIRCLE1 = "PC1"
CC_LINE_PITCH_CIRCLE2 = "PC2"
CC_LINE_OD_CIRCLE1 = "OD1"
CC_LINE_OD_CIRCLE2 = "OD2"
CC_LINE_TEXT = "TEXT"
# Dimensions
CC_LINE_LENGTH_DIM = "LENGTH_DIM"
CC_LINE_PITCH_CIRCLE1_DIM = "PC1_DIM"
CC_LINE_PITCH_CIRCLE2_DIM = "PC2_DIM"
CC_LINE_OD_CIRCLE1_DIM = "OD1_DIM"
CC_LINE_OD_CIRCLE2_DIM = "OD2_DIM"
CC_LINE_TEXT_HEIGHT_DIM = "TEXT_HEIGHT"

CC_LINE_PARENT_LINE = "CCLine"

class CCLineData :
    N1 = 0
    N2 = 0
    PIN1 = 0    # For addendum gears (pinions) this is the number of teeth and N1 will be the CD
    PIN2 = 0    # For addendum gears (pinions) this is the number of teeth and N2 will be the CD
    Teeth = 0
    ExtraCenterIN = 0.00
    motion = 0
    ccDistIN = 0.0    # Calculated before EC is added
    PD1 = 0.0
    PD2 = 0.0
    OD1 = 0.0
    OD2 = 0.0

class CCLine :
    data = CCLineData()
    line: adsk.fusion.SketchLine = None
    pitchCircle1: adsk.fusion.SketchCircle = None
    pitchCircle2: adsk.fusion.SketchCircle = None
    ODCircle1: adsk.fusion.SketchCircle = None
    ODCircle2: adsk.fusion.SketchCircle = None
    # Dimensions
    lengthDim: adsk.fusion.SketchLinearDimension = None
    PD1Dim: adsk.fusion.SketchDiameterDimension = None
    PD2Dim: adsk.fusion.SketchDiameterDimension = None
    OD1Dim: adsk.fusion.SketchDiameterDimension = None
    OD2Dim: adsk.fusion.SketchDiameterDimension = None
    textHeight: adsk.fusion.SketchLinearDimension = None
    # Line Label
    textBox: adsk.fusion.SketchText = None


def isCCLine( line: adsk.fusion.SketchLine ) -> bool :
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_N1 )
    if not attr:
        return False
    
    return True

def setAttribute( ent: adsk.fusion.SketchEntity, name: str, value: str ) :
    newattr = ent.attributes.add( CC_ATTRIBUTE_GROUP, name, value )
    if not newattr:
        futil.log(f'  ======== Adding attribute {name} = {value} FAILED!!')

def setAttributeList( ents: list[adsk.fusion.SketchEntity], name: str, value: str ) :
    for ent in ents:
        # futil.log(f'Setting attribute {name} on {ent.entityToken}')
        newattr = ent.attributes.add( CC_ATTRIBUTE_GROUP, name, value )
        if not newattr:
            futil.log(f'  ======== Adding attribute {name} = {value} FAILED!!')

def setCCLineAttributes( ccLine: CCLine ) :
    line = ccLine.line
    ld = ccLine.data

    # Set the data attributes
    setAttribute( line, CC_LINE_N1, str(ld.N1) )
    setAttribute( line, CC_LINE_N2, str(ld.N2) )
    setAttribute( line, CC_LINE_PIN1, str(ld.PIN1) )
    setAttribute( line, CC_LINE_PIN2, str(ld.PIN2) )
    setAttribute( line, CC_LINE_TEETH, str(ld.Teeth) )
    setAttribute( line, CC_LINE_EC, str(ld.ExtraCenterIN) )
    setAttribute( line, CC_LINE_MOTION_TYPE, str(ld.motion) )

    # Set the end circle tokens
    setAttribute( line, CC_LINE_PITCH_CIRCLE1, ccLine.pitchCircle1.entityToken )
    setAttribute( line, CC_LINE_PITCH_CIRCLE2, ccLine.pitchCircle2.entityToken )
    setAttribute( line, CC_LINE_OD_CIRCLE1, ccLine.ODCircle1.entityToken )
    setAttribute( line, CC_LINE_OD_CIRCLE2, ccLine.ODCircle2.entityToken )

    # Set the TextBox token
    setAttribute( line, CC_LINE_TEXT, ccLine.textBox.entityToken )

    # Set the dimension tokens
    setAttribute( line, CC_LINE_LENGTH_DIM, ccLine.lengthDim.entityToken )
    setAttribute( line, CC_LINE_PITCH_CIRCLE1_DIM, ccLine.PD1Dim.entityToken )
    setAttribute( line, CC_LINE_PITCH_CIRCLE2_DIM, ccLine.PD2Dim.entityToken )
    setAttribute( line, CC_LINE_OD_CIRCLE1_DIM, ccLine.OD1Dim.entityToken )
    setAttribute( line, CC_LINE_OD_CIRCLE2_DIM, ccLine.OD2Dim.entityToken )
    setAttribute( line, CC_LINE_TEXT_HEIGHT_DIM, ccLine.textHeight.entityToken )

    # futil.print_Attributes( line )

    # Set the line as the parent to all the child entities
    setAttributeList( [ccLine.pitchCircle1, ccLine.pitchCircle2, ccLine.ODCircle1, ccLine.ODCircle2,
                       ccLine.PD1Dim, ccLine.PD2Dim, ccLine.OD1Dim, ccLine.OD2Dim, ccLine.lengthDim,
                       ccLine.textBox, ccLine.textHeight],
                       CC_LINE_PARENT_LINE, line.entityToken )
    textDef: adsk.fusion.MultiLineTextDefinition = ccLine.textBox.definition
    for tbline in textDef.rectangleLines:
        setAttribute( tbline, CC_LINE_PARENT_LINE, line.entityToken )

    # futil.print_Attributes( ccLine.pitchCircle1 )

def getLineData( line: adsk.fusion.SketchLine ) -> CCLineData :

    cclineData = CCLineData()
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_N1 )
    if not attr:
        return None
    
    cclineData.N1 = int(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_N2 )
    cclineData.N2 = int(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_PIN1 )
    cclineData.PIN1 = int(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_PIN2 )
    cclineData.PIN2 = int(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_TEETH )
    cclineData.Teeth = int(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_EC )
    cclineData.ExtraCenterIN = float(attr.value)
    attr = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_MOTION_TYPE )
    cclineData.motion = int(attr.value)

    return cclineData

# Returns the parent line of the CCLine or None if not a member of a CCLine
def getParentLine( curve: adsk.fusion.SketchCurve ) -> adsk.fusion.SketchLine :
    if not curve:
        return None
    
    # Check to see if the curve has the CC_LINE_PARENT_LINE attribute set
    try:
        token = curve.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_PARENT_LINE )
    except:
        return None
    
    if not token:
        # No parent line set.  Check if this is the actual CCLine by looking for N1
        token = curve.attributes.itemByName( CC_ATTRIBUTE_GROUP, CC_LINE_N1 )
        if not token:
            return None
        else:
            return curve
    
    # Get the Parent Line and return it if it exists
    line = curve.parentSketch.parentComponent.parentDesign.findEntityByToken( token.value )
    if len(line) == 0:
        return None
    
    return line[0]
    
def getChildCircles( line: adsk.fusion.SketchLine ) -> list[adsk.fusion.SketchCircle] :

    design = line.parentSketch.parentComponent.parentDesign

    attrNames = [ CC_LINE_PITCH_CIRCLE1, CC_LINE_PITCH_CIRCLE2, CC_LINE_OD_CIRCLE1, CC_LINE_OD_CIRCLE2 ]

    circles = []
    i = 0
    while i < len(attrNames):
        token = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, attrNames[i] )
        circle = design.findEntityByToken( token.value )
        if len( circle ) == 0:
            futil.log(f'Error getting child circles of line...')
            return None
        circles.append( circle[0] )
        i += 1

    return circles

def getChildEntity( line: adsk.fusion.SketchLine, attribute: str ) :

    design = line.parentSketch.parentComponent.parentDesign

    token = line.attributes.itemByName( CC_ATTRIBUTE_GROUP, attribute )
    if not token:
        futil.log(f'Error getting attribute "{attribute}" from line')

    ents = design.findEntityByToken( token.value )
    if len( ents ) == 0:
        futil.log(f'Error getting child entity "{attribute}"')
        return None
    
    return ents[0]

def getCCLineFromEntity( curve: adsk.fusion.SketchCurve ) -> CCLine :
    ccLine = CCLine()

    # futil.log(f'getCCLineFromEntity --- ')
    # futil.print_Attributes( curve )

    ccLine.line = getParentLine( curve )
    if not ccLine.line:
        return None

    # Get the associated data from the line attributes
    ccLine.data = getLineData( ccLine.line )

    circles = getChildCircles( ccLine.line )
    if len(circles) != 4:
        futil.log( f'Error getting child circle data.')
        return ccLine
    
    ccLine.pitchCircle1 = circles[0]
    ccLine.pitchCircle2 = circles[1]
    ccLine.ODCircle1 = circles[2]
    ccLine.ODCircle2 = circles[3]

    ccLine.lengthDim = getChildEntity( ccLine.line, CC_LINE_LENGTH_DIM )
    ccLine.PD1Dim = getChildEntity( ccLine.line, CC_LINE_PITCH_CIRCLE1_DIM )
    ccLine.PD2Dim = getChildEntity( ccLine.line, CC_LINE_PITCH_CIRCLE2_DIM )
    ccLine.OD1Dim = getChildEntity( ccLine.line, CC_LINE_OD_CIRCLE1_DIM )
    ccLine.OD2Dim = getChildEntity( ccLine.line, CC_LINE_OD_CIRCLE2_DIM )
    ccLine.textBox = getChildEntity( ccLine.line, CC_LINE_TEXT )
    ccLine.textHeight = getChildEntity( ccLine.line, CC_LINE_TEXT_HEIGHT_DIM )

    return ccLine
    
def deleteCCLine( ccLine: CCLine ):
    try:
        ccLine.pitchCircle1.deleteMe()
    except:
        None
    try:
        ccLine.pitchCircle2.deleteMe()
    except:
        None
    try:
        ccLine.ODCircle1.deleteMe()
    except:
        None
    try:
        ccLine.ODCircle2.deleteMe()
    except:
        None
    try:
        ccLine.textBox.deleteMe()
    except:
        None
    try:
        ccLine.line.deleteMe()
    except:
        None
