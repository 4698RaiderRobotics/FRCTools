#  

import math
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface

def toPoint2D( pt: adsk.core.Point3D ) -> adsk.core.Point2D :
    return adsk.core.Point2D.create( pt.x, pt.y )

def toPoint3D( pt: adsk.core.Point2D ) -> adsk.core.Point3D :
    return adsk.core.Point3D.create( pt.x, pt.y, 0 )

def addPoint3D( pt1: adsk.core.Point3D, pt2: adsk.core.Point3D ) -> adsk.core.Point3D :
    return adsk.core.Point3D.create( pt1.x + pt2.x, pt1.y + pt2.y, pt1.z + pt2.z )

def midPoint3D( pt1: adsk.core.Point3D, pt2: adsk.core.Point3D ) -> adsk.core.Point3D :
    return adsk.core.Point3D.create( (pt1.x + pt2.x)/2, (pt1.y + pt2.y)/2, (pt1.z + pt2.z)/2 )

def offsetPoint3D( pt1: adsk.core.Point3D, x: float, y: float, z: float ) -> adsk.core.Point3D :
    return adsk.core.Point3D.create( pt1.x + x, pt1.y + y, pt1.z + z )

def addPoint2D( pt1: adsk.core.Point2D, pt2: adsk.core.Point2D ) -> adsk.core.Point2D :
    return adsk.core.Point2D.create( pt1.x + pt2.x, pt1.y + pt2.y )

def addPoint2D( pt1: adsk.core.Point2D, v2: adsk.core.Vector2D ) -> adsk.core.Point2D :
    return adsk.core.Point2D.create( pt1.x + v2.x, pt1.y + v2.y )

def offsetPoint2D( pt1: adsk.core.Point2D, x: float, y: float ) -> adsk.core.Point2D :
    return adsk.core.Point2D.create( pt1.x + x, pt1.y + y )

def toLine2D( l3d: adsk.core.Line3D ) -> adsk.core.Line2D :
    return adsk.core.Line2D.create( toPoint2D(l3d.startPoint), toPoint2D(l3d.endPoint) )

def toVector2D( v: adsk.core.Vector3D ) -> adsk.core.Vector2D :
    return adsk.core.Vector2D.create( v.x, v.y )

def multVector2D( v: adsk.core.Vector2D, val: float ) -> adsk.core.Vector2D :
    return adsk.core.Vector2D.create( v.x * val, v.y * val )

def twoPointUnitVector( startPt: adsk.core.Point2D, endPt: adsk.core.Point2D  ) -> adsk.core.Vector2D :
    vec_x = endPt.x - startPt.x
    vec_y = endPt.y - startPt.y
    mag = math.hypot( vec_x, vec_y )
    return adsk.core.Vector2D.create( vec_x / mag, vec_y / mag )

def sketchLineUnitVec( line: adsk.fusion.SketchLine ) -> adsk.core.Vector2D :
    return twoPointUnitVector( 
        toPoint2D(line.startSketchPoint.geometry),
        toPoint2D(line.endSketchPoint.geometry) )

def make_Midpt( line: adsk.fusion.SketchLine ) -> adsk.core.Point3D :
    startpt = line.startSketchPoint.geometry
    endpt = line.endSketchPoint.geometry

    return midPoint3D( startpt, endpt )

# Determines if a point in the plane is to the right of a line.
# Determined as though sitting on the start point looking at the end point
def toTheRightOf( line: adsk.core.Line2D, pt: adsk.core.Point2D  ) -> bool :
    lineUnitVec = twoPointUnitVector( line.startPoint, line.endPoint )
    startToPtVec = twoPointUnitVector( line.startPoint, pt )

    # Find the z-component of the cross product
    z_comp = lineUnitVec.x*startToPtVec.y - lineUnitVec.y*startToPtVec.x

    return z_comp < 0

def lineNormal( line: adsk.core.Line2D ) -> adsk.core.Vector2D :
    return lineNormal( line.startPoint, line.endPoint )

def lineNormal( startPt: adsk.core.Point2D, endPt: adsk.core.Point2D ) -> adsk.core.Vector2D :
    norm_x = -(endPt.y - startPt.y)
    norm_y = endPt.x - startPt.x
    mag = math.hypot( norm_x, norm_y )

    return adsk.core.Vector2D.create( norm_x / mag, norm_y / mag )

def sketchLineNormal( line: adsk.fusion.SketchLine, towardPt: adsk.core.Point3D = None ) -> adsk.core.Vector2D :
    normal = lineNormal( toPoint2D(line.startSketchPoint.geometry), toPoint2D(line.endSketchPoint.geometry) )
    if towardPt == None:
        return normal
    
    towardUnitVec = twoPointUnitVector( toPoint2D(line.startSketchPoint.geometry), toPoint2D(towardPt) )
    angle = towardUnitVec.angleTo( normal )
    if abs(angle) > math.pi:
        normal = multVector2D( normal, -1.0 )
    return normal

def BBCentroid( bb: adsk.core.BoundingBox3D ) :
    sum = addPoint3D( bb.maxPoint, bb.minPoint )
    return adsk.core.Point3D.create( sum.x / 2, sum.y / 2, sum.z / 2 )

def Arc3DTextPoint( arc: adsk.fusion.SketchArc ) -> adsk.core.Point3D:
    eval = arc.geometry.evaluator
    status, param0, param1 = eval.getParameterExtents()
    status, arcMidPt = eval.getPointAtParameter( (param0 + param1) / 2 )
    return midPoint3D( arcMidPt, arc.centerSketchPoint.geometry )