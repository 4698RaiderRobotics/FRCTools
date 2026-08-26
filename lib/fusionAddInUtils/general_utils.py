#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.

import os
import traceback
import adsk.core
import adsk.fusion
import random
import colorsys

app = adsk.core.Application.get()
ui = app.userInterface

# Attempt to read DEBUG flag from parent config.
try:
    from ... import config
    DEBUG = config.DEBUG
except:
    DEBUG = False


pZero = adsk.core.Point3D.create(0,0,0)

def get_basis_matrix_from_plane(plane: adsk.core.Plane):
    """Returns (world_to_local, local_to_world) Matrix3D pair."""
    origin = plane.origin
    normal = plane.normal
    normal.normalize()

    arbitrary = adsk.core.Vector3D.create(1, 0, 0)
    if abs(normal.dotProduct(arbitrary)) > 0.9:
        arbitrary = adsk.core.Vector3D.create(0, 1, 0)

    xAxis = normal.crossProduct(arbitrary)
    xAxis.normalize()
    yAxis = normal.crossProduct(xAxis)
    yAxis.normalize()

    local_to_world = adsk.core.Matrix3D.create()
    local_to_world.setWithCoordinateSystem(origin, xAxis, yAxis, normal)

    world_to_local = local_to_world.copy()
    world_to_local.invert()

    return world_to_local, local_to_world


# ---------- 2. Flatten 3D points to 2D tuples ----------

def flatten_points(points_3d : list[adsk.core.Point3D], world_to_local : adsk.core.Matrix3D):
    """points_3d: list of adsk.core.Point3D. Returns list of (x, y) tuples."""
    
    try:
        result = []
        for p in points_3d:
            local : adsk.core.Point3D = p.copy()
            local.transformBy(world_to_local)
            assert local.z == 0
            result.append((local.x, local.y))
         # local.z should be ~0
        return result
    except Exception as ex:
        ui.messageBox(f'{ex}')


# ---------- 3. Un-flatten 2D tuples back to 3D points ----------

def unflatten_points(points_2d, local_to_world):
    """points_2d: list of (x, y) tuples. Returns list of adsk.core.Point3D."""
    result = []
    for (x, y) in points_2d:
        pt = adsk.core.Point3D.create(x, y, 0)
        pt.transformBy(local_to_world)
        result.append(pt)
    return result


# ---------- 4. Convex hull on plain (x, y) tuples ----------

def convex_hull(points):
    """points: list of (x, y) tuples. Returns hull points in CCW order."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]
def convex_hull_3d(points):
    """
    points: list of (x, y, z) tuples
    returns: list of triangular faces, each a tuple of 3 point indices into `points`
    """
   
    def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
    def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

    def face_normal(pts, face):
        a, b, c = [pts[i] for i in face]
        return cross(sub(b, a), sub(c, a))

    def signed_dist(pts, face, p):
        a = pts[face[0]]
        n = face_normal(pts, face)
        return dot(n, sub(p, a))
    ui.messageBox(str(points))
    n = len(points)
    if n < 4:
        raise ValueError("Need at least 4 non-coplanar points for a 3D hull")

    # --- find 4 non-coplanar points to seed a tetrahedron ---
    p0, p1 = 0, 1
  
    # find a point not collinear with p0,p1
    p2 = next((i for i in range(n) if i not in (p0, p1) and
               any(c != 0 for c in cross(sub(points[p1], points[p0]), sub(points[i], points[p0])))), None)
    if p2 is None:
        ui.messageBox("all points are collinear")
        raise ValueError("All points are collinear")
    # find a point not coplanar with p0,p1,p2
    p3 = next((i for i in range(n) if i not in (p0, p1, p2) and
               signed_dist(points, (p0, p1, p2), points[i]) != 0), None)
    if p3 is None:
        ui.messageBox("all points are coplanar")
        raise ValueError("All points are coplanar")

    faces = [(p0, p1, p2), (p0, p2, p3), (p0, p3, p1), (p1, p3, p2)]

    # orient faces outward relative to the tetrahedron's centroid
    centroid = tuple(sum(points[i][k] for i in (p0,p1,p2,p3)) / 4 for k in range(3))
    oriented = []
    for f in faces:
        if signed_dist(points, f, centroid) > 0:
            f = (f[0], f[2], f[1])  # flip winding
        oriented.append(f)
    faces = oriented

    remaining = [i for i in range(n) if i not in (p0, p1, p2, p3)]

    for pt_idx in remaining:
        p = points[pt_idx]

        # faces visible from p (point is on the positive/outward side)
        visible = [f for f in faces if signed_dist(points, f, p) > 1e-9]
        if not visible:
            continue  # point is inside the current hull, skip

        # find horizon edges: edges shared by exactly one visible face
        edge_count = {}
        for f in visible:
            for e in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])]:
                edge_count[e] = edge_count.get(e, 0) + 1

        horizon_edges = []
        for (a, b), _ in edge_count.items():
            if (b, a) not in edge_count:
                horizon_edges.append((a, b))

        # remove visible faces, add new faces connecting horizon edges to p
        faces = [f for f in faces if f not in visible]
        for (a, b) in horizon_edges:
            faces.append((a, b, pt_idx))

    return faces
def random_saturated_color() -> adsk.core.Color:
    hue = random.random()
    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.9)  # full saturation, full value
    return adsk.core.Color.create(int(r * 255), int(g * 255), int(b * 255), 255)


def get_random_flat_color(occ : adsk.fusion.Occurrence, design: adsk.fusion.Design, app: adsk.core.Application):
    # Grab a base appearance to copy from Fusion's built-in library.
    # "Paint - Matte" is a good starting point since it's already low-reflectance.
    try:
        appearches = '' 
        for library in app.materialLibraries:
            appearches += f'{library.name} \n'
     
        fusion_lib = app.materialLibraries.itemByName('Fusion Appearance Library')
        name = ""
        for appearacne in fusion_lib.appearances:
            if appearacne.name.startswith('Paint'):
                name = appearacne.name
                break
     
        base_appearance = fusion_lib.appearances.itemByName(name)

        # Copy it into the design's local appearances so it's independent/editable
        new_appearance = design.appearances.addByCopy(
            base_appearance, f"RandomColor_{random.randint(0, 999999)}"
        )

        

        # Set the color
        color_prop = adsk.core.ColorProperty.cast(
            new_appearance.appearanceProperties.itemByName('Color')
        )
        color_prop.value = random_saturated_color()

        # Zero out reflectance — property name depends on the template.
        # Common names: 'Shine', 'Reflectivity', 'Specular Level', 'Roughness'
        reflect_prop = adsk.core.FloatProperty.cast(
            new_appearance.appearanceProperties.itemByName('Reflectivity')  # adjust after checking the printout above
        )
        if reflect_prop:
            reflect_prop.value = 0.0

        # Assign to the component
        occ.appearance = new_appearance
        
        return new_appearance
    except Exception as ex:
        ui.messageBox(f"{ex} {ex.__traceback__.tb_lineno}")
def apply_appearance_recursive(comp: adsk.fusion.Component, appearance: adsk.fusion.Appearance):
    # 1. Bodies directly in this component
    for body in comp.bRepBodies:
        body.appearance = appearance

    # 2. Component-level (covers anything that doesn't have its own override)
    comp.appearance = appearance

    # 3. Child occurrences — each occurrence needs its OWN appearance set;
    #    setting the underlying component's appearance does not propagate
    #    to every occurrence of it, since occurrence-level overrides sit
    #    above component-level in the hierarchy.
    for occ in comp.occurrences:
        occ.appearance = appearance
        # Recurse into the child component's own bodies/sub-occurrences
        apply_appearance_recursive(occ.component, appearance)
def bbox_area(profile: adsk.fusion.Profile) -> float:
    bbox = profile.boundingBox
    width = bbox.maxPoint.x - bbox.minPoint.x
    height = bbox.maxPoint.y - bbox.minPoint.y
    return width * height
def are_faces_coplanar(face1: adsk.fusion.BRepFace, face2: adsk.fusion.BRepFace) -> bool:
    
    geom1 = face1.geometry
    geom2 = face2.geometry
    
    if not isinstance(geom1, adsk.core.Plane) or not isinstance(geom2, adsk.core.Plane):
        return False  # one or both faces aren't planar
    
    return geom1.isCoPlanarTo(geom2)
def create_tube(width : float, length : float, height : float, startPlane : adsk.core.Base, occurence : adsk.fusion.Occurrence, cylindrical : bool = False, extensionDir : adsk.fusion.ExtentDirections = adsk.fusion.ExtentDirections.PositiveExtentDirection, startPoint : adsk.core.Point3D = pZero, extrudeOperation = adsk.fusion.FeatureOperations.NewComponentFeatureOperation):
    try:
        comp = occurence.component
        occurence.activate()
        sketch = comp.sketches.add(startPlane, occurence)
        if cylindrical:
            sketch.sketchCurves.sketchEllipses.add(startPoint, pointFromOffset(startPoint, width/2.54, 0), pointFromOffset(startPoint, 0, height/2.54))
        else:
            sketch.sketchCurves.sketchLines.addCenterPointRectangle(startPoint, pointFromOffset(startPoint, width*0.5/2.54, height * 0.5/2.54))
        input = comp.features.extrudeFeatures.createInput(sketch.profiles.item(0), extrudeOperation)
        if extensionDir == adsk.fusion.ExtentDirections.SymmetricExtentDirection:
            input.setSymmetricExtent(adsk.core.ValueInput.createByReal(length), False)

        else:
            input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(length)), extensionDir)
        comp.features.extrudeFeatures.add(input)
    except Exception as ex:
        ui.messageBox(f"error {ex} {ex.__traceback__.tb_lineno} {ex.__doc__}")
    
    
def createBelt(rollerDiameter:float, thickness:float, c2c:float, startPlane: adsk.core.Base, occurrence : adsk.fusion.Occurrence):
    """
    Creates a belt

    All parameters need to be in centimeters

    Returns the belt's component
    """
    comp = occurrence.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    sketch = comp.component.sketches.add(startPlane, occurrence)
    rollerDiameter /= 2 
    leftCoords = [
    adsk.core.Point3D.create(0,rollerDiameter,0),
    adsk.core.Point3D.create(0,rollerDiameter - 0.125*2.54 ,0),
    adsk.core.Point3D.create(0,-rollerDiameter,0),
    adsk.core.Point3D.create(0,-rollerDiameter + 0.125*2.54 ,0)]

    sketch.sketchCurves.sketchArcs.addByCenterStartEnd(pZero, leftCoords[0], leftCoords[3])
    sketch.sketchCurves.sketchArcs.addByCenterStartEnd(pZero,leftCoords[1], leftCoords[2])

    rightCoords = []
    for coord in leftCoords:
        rightCoords.append(pointFromOffset(coord, c2c/2.54 , 0))

    sketch.sketchCurves.sketchArcs.addByCenterStartEnd(pointFromOffset(pZero,  c2c/2.54, 0), rightCoords[3], rightCoords[0])
    sketch.sketchCurves.sketchArcs.addByCenterStartEnd(pointFromOffset(pZero, c2c/2.54, 0),rightCoords[2], rightCoords[1])

    sketch.sketchCurves.sketchLines.addTwoPointRectangle(leftCoords[0], rightCoords[1])
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(leftCoords[2], rightCoords[3])

    profileCollection = adsk.core.ObjectCollection.create()
    maxArea = 0
    for profile in sketch.profiles:
        if profile.face.area > maxArea:
            maxArea = profile.face.area
    for profile in sketch.profiles:
        if not profile.face.area == maxArea: profileCollection.add(profile)
    
    input = comp.component.features.extrudeFeatures.createInput(profileCollection, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(thickness)), adsk.fusion.ExtentDirections.PositiveExtentDirection)
    comp.component.features.extrudeFeatures.add(input)

    return comp.component


def collectionFromProfiles(list):
    coll = adsk.core.ObjectCollection.create()
    for element in list:
        coll.add(element)
    return coll

def pointFromOffset(reference:adsk.core.Point3D, offsetXInches, offsetYInches):

    copy = reference.copy()
    copy.translateBy(adsk.core.Vector3D.create(offsetXInches*2.54, offsetYInches*2.54, 0))
    return copy

def log(message: str, level: adsk.core.LogLevels = adsk.core.LogLevels.InfoLogLevel, force_console: bool = False):
    """Utility function to easily handle logging in your app.

    Arguments:
    message -- The message to log.
    level -- The logging severity level.
    force_console -- Forces the message to be written to the Text Command window. 
    """    
    # Always print to console, only seen through IDE.
    print(message)  

    # Log all errors to Fusion log file.
    if level == adsk.core.LogLevels.ErrorLogLevel:
        log_type = adsk.core.LogTypes.FileLogType
        app.log(message, level, log_type)

    # If config.DEBUG is True write all log messages to the console.
    if DEBUG or force_console:
        log_type = adsk.core.LogTypes.ConsoleLogType
        app.log(message, level, log_type)


def handle_error(name: str, show_message_box: bool = False):
    """Utility function to simplify error handling.

    Arguments:
    name -- A name used to label the error.
    show_message_box -- Indicates if the error should be shown in the message box.
                        If False, it will only be shown in the Text Command window
                        and logged to the log file.                        
    """    

    log('===== Error =====', adsk.core.LogLevels.ErrorLogLevel)
    log(f'{name}\n{traceback.format_exc()}', adsk.core.LogLevels.ErrorLogLevel)

    # If desired you could show an error as a message box.
    if show_message_box:
        ui.messageBox(f'{name}\n{traceback.format_exc()}')

def popup_error( message: str ):
    log(message)
    ui.messageBox( message )

def ok_cancel_message( message: str, title: str ='' ):
    result = ui.messageBox( message, title, adsk.core.MessageBoxButtonTypes.OKCancelButtonType  )
    if result == adsk.core.DialogResults.DialogOK:
        return True
    return False

def yes_no_message( message: str, title: str ='' ):
    result = ui.messageBox( message, title, adsk.core.MessageBoxButtonTypes.YesNoButtonType  )
    if result == adsk.core.DialogResults.DialogYes:
        return True
    return False

def print_SketchObjectCollection( col: adsk.core.ObjectCollection ) :
    log(f'print_SketchObjectCollection() -- Collection has {col.count} items...')
    for item in col.asArray():
        item: adsk.fusion.SketchEntity = item
        log(f'item type = {item.objectType}:')
        log(f'   isFixed({item.isFixed}), is2D({item.is2D}), isFullyConstr({item.isFullyConstrained}), isRef({item.isReference})')
        print_SketchCurve( item )

def print_Selection( selections: adsk.core.SelectionCommandInput ) :
    i = 0
    log(f'Selection has {selections.selectionCount} items.')
    while i < selections.selectionCount:
        print_BaseObject( selections.selection(i).entity )
        i += 1

def print_BaseObject( object: adsk.core.Base ) :
    log(f'item type = {object.objectType}, isValid={object.isValid}')

def print_OrientedBB( orientedBB: adsk.core.OrientedBoundingBox3D ) :
    log(f'item type = {orientedBB.objectType}, isValid={orientedBB.isValid}')
    log(f'   height = {orientedBB.height}, length={orientedBB.length}, width={orientedBB.width}')
    print_Point3D( orientedBB.centerPoint, "   centerPt: ")

def print_BBox( bbox: adsk.core.BoundingBox3D ) :
    log(f'item type = {bbox.objectType}, isValid={bbox.isValid}')
    log(f'   minPt = {format_Point3D(bbox.minPoint)}, maxPt={format_Point3D(bbox.maxPoint)}')

def print_Point2D( pt: adsk.core.Point2D, prefix: str = "" ) :
    log( f'{prefix} {format_Point2D( pt )}' )

def format_Point2D( pt: adsk.core.Point2D ) :
    return f'({pt.x:.4},{pt.y:.4})'

def format_Vector2D( v: adsk.core.Vector2D ) :
    return f'({v.x:.4},{v.y:.4})'

def print_Point3D( pt: adsk.core.Point3D, prefix: str = "" ) :
    log( f'{prefix} {format_Point3D( pt )}' )

def format_Point3D( pt: adsk.core.Point3D ) :
    return f'({pt.x:.4},{pt.y:.4},{pt.z:.4})'

def format_Vector3D( v: adsk.core.Vector3D ) :
    return f'({v.x:.4},{v.y:.4},{v.z:.4})'

def print_SketchCurve( curve: adsk.fusion.SketchCurve ) :
    if curve.objectType == adsk.fusion.SketchLine.classType() :
        line: adsk.fusion.SketchLine = curve
        log(f'SketchLine: {format_Point3D(line.startSketchPoint.geometry)} -- {format_Point3D(line.endSketchPoint.geometry)}')
    elif curve.objectType == adsk.fusion.SketchArc.classType() :
        arc: adsk.fusion.SketchArc = curve
        str = f'SketchArc: C{format_Point3D(arc.centerSketchPoint.geometry)}, '
        str += f'{format_Point3D(arc.startSketchPoint.geometry)} -- {format_Point3D(arc.endSketchPoint.geometry)}'
        log(str)
    elif curve.objectType == adsk.fusion.SketchCircle.classType() :
        circle: adsk.fusion.SketchCircle = curve
        str = f'SketchCircle: C{format_Point3D(circle.centerSketchPoint.geometry)}, '
        str += f'radius = {circle.radius}'
        log(str)
    elif curve.objectType == adsk.fusion.SketchPoint.classType() :
        pt: adsk.fusion.SketchPoint = curve
        log(f'SketchPoint: {format_Point3D(pt.geometry)}')
    else :
        log(f'print_SketchCurve() --> {curve.objectType} Not handled.')
    log(f'    is2D({curve.is2D}), isDeletable({curve.isDeletable}), isFixed({curve.isFixed}), isFullyConstrained({curve.isFullyConstrained})')
    log(f'    isLinked({curve.isLinked}), isReference({curve.isReference}), isValid({curve.isValid}), isVisible({curve.isVisible})')

def print_Curve2D( curve: adsk.core.Curve2D ) :
    if curve.objectType == adsk.core.Line2D.classType() :
        line: adsk.core.Line2D = curve
        log(f'Line2D: {format_Point2D(line.startPoint)} -- {format_Point2D(line.endPoint)}')
    elif curve.objectType == adsk.core.Arc2D.classType() :
        arc: adsk.core.Arc2D = curve
        str = f'Arc2D: C{format_Point2D(arc.center)}, {format_Point2D(arc.startPoint)} -- {format_Point2D(arc.endPoint)}'
        str += f', R={arc.radius:.4}'
        log(str)
    elif curve.objectType == adsk.core.Circle2D.classType() :
        circle: adsk.core.Circle2D = curve
        str = f'Circle2D: C{format_Point2D(circle.center)}, '
        str += f'radius = {circle.radius:.4}'
        log(str)
    elif curve.objectType == adsk.core.Point2D.classType() :
        pt: adsk.core.Point2D = curve
        log(f'Point2D: {format_Point2D(pt)}')
    else :
        log(f'print_Curve2D() --> {curve.objectType} Not handled.')

def print_Curve3D( curve: adsk.core.Curve3D ) :
    if curve.objectType == adsk.core.Line3D.classType() :
        line: adsk.core.Line3D = curve
        log(f'Line3D: {format_Point3D(line.startPoint)} -- {format_Point3D(line.endPoint)}')
    elif curve.objectType == adsk.core.Arc3D.classType() :
        arc: adsk.core.Arc3D = curve
        str = f'Arc3D: C{format_Point3D(arc.center)}, {format_Point3D(arc.startPoint)} -- {format_Point3D(arc.endPoint)}'
        str += f', R={arc.radius:.4}'
        log(str)
    elif curve.objectType == adsk.core.Circle3D.classType() :
        circle: adsk.core.Circle3D = curve
        str = f'Circle3D: C{format_Point3D(circle.center)}, '
        str += f'radius = {circle.radius}, normal={format_Vector3D(circle.normal)}'
        log(str)
    else :
        log(f'print_Curve3D() --> {curve.objectType} Not handled.')
    # log(f'    is2D({curve.is2D}), isDeletable({curve.isDeletable}), isFixed({curve.isFixed}), isFullyConstrained({curve.isFullyConstrained})')
    # log(f'    isLinked({curve.isLinked}), isReference({curve.isReference}), isValid({curve.isValid}), isVisible({curve.isVisible})')

def print_Profiles( profiles: adsk.fusion.Profiles ) :
    log(f'========= Listing for {profiles.count} Profiles =========')
    pidx = 0
    while pidx < profiles.count:
        p = profiles.item( pidx )
        log(f'    Profile #{pidx+1}, number of loops={p.profileLoops.count}:')
        lidx = 0
        while lidx < p.profileLoops.count:
            l = p.profileLoops.item(lidx)
            log(f'        Loop #{lidx+1}, number of curves = {l.profileCurves.count}')
            cidx = 0
            while cidx < l.profileCurves.count:
                c = l.profileCurves.item(cidx)
                log(f'            Sketch Entity for Curve #{cidx+1}:')
                print_SketchCurve( c.sketchEntity )
                log(f'            geometry for Curve #{cidx+1}:')
                print_Curve3D( c.geometry )
                cidx += 1
            lidx += 1
        pidx += 1


def print_Attributes( entity: adsk.fusion.SketchEntity ) :
    log(f'Entity {entity.objectType} has {len(entity.attributes)} attributes')
    for attr in entity.attributes:
        log(f'   {attr.name} ==> {attr.value}')

def inchValue( inches: float ) -> adsk.core.ValueInput :
    return adsk.core.ValueInput.createByReal( inches * 2.54 )

def Value( number: float ) -> adsk.core.ValueInput :
    return adsk.core.ValueInput.createByReal( number )