"""
common.py - reusable geometry helpers for building spur-gear reducers with
FreeCAD's Part API.

Everything here is pure ``Part`` / ``PartDesign.fcgear`` and works both inside a
running FreeCAD GUI and headless under ``freecadcmd``.  View-dependent things
(view providers, colours, screenshots) deliberately live in ``render.py`` so
that the model builders stay GUI-free.

Design conventions used throughout
----------------------------------
* A gear is built in its own local frame with the **axis along +Z** and the
  centre of a tooth on the local **+X** axis (see ``tooth_spin`` for how that
  was established empirically).
* Shafts are built in world coordinates with the **axis along +X**, centred on
  ``y = y_axis``, ``z = 0``.  All reducers in this repo keep every shaft axis
  in the plane ``z = 0`` so that the housing can be split along that plane.
* Reducer housing halves are ``Housing_Base`` (z < 0) and ``Housing_Cover``
  (z > 0).

Units are millimetres and degrees throughout.
"""

import math
import os

import FreeCAD as App
import Part
from PartDesign.fcgear import fcgear, involute

# --------------------------------------------------------------------------
# Flat keys, GB/T 1096 (b = width, h = height, t1 = depth in shaft,
# t2 = depth in hub).  Ranges are "shaft diameter greater than .. up to ..".
# --------------------------------------------------------------------------
KEY_TABLE = [
    # d_from, d_to, b,   h,   t1,  t2
    (10.0, 12.0, 4.0, 4.0, 2.5, 1.8),
    (12.0, 17.0, 5.0, 5.0, 3.0, 2.3),
    (17.0, 22.0, 6.0, 6.0, 3.5, 2.8),
    (22.0, 30.0, 8.0, 7.0, 4.0, 3.3),
    (30.0, 38.0, 10.0, 8.0, 5.0, 3.3),
    (38.0, 44.0, 12.0, 8.0, 5.0, 3.3),
    (44.0, 50.0, 14.0, 9.0, 5.5, 3.8),
    (50.0, 58.0, 16.0, 10.0, 6.0, 4.3),
    (58.0, 65.0, 18.0, 11.0, 7.0, 4.4),
    (65.0, 75.0, 20.0, 12.0, 7.5, 4.9),
    (75.0, 85.0, 22.0, 14.0, 9.0, 5.4),
    (85.0, 95.0, 25.0, 14.0, 9.0, 5.4),
    (95.0, 110.0, 28.0, 16.0, 10.0, 6.4),
]


def key_for(shaft_diameter):
    """Return the GB/T 1096 flat key ``(b, h, t1, t2)`` for a shaft diameter."""
    for d_from, d_to, b, h, t1, t2 in KEY_TABLE:
        if d_from < shaft_diameter <= d_to:
            return dict(b=b, h=h, t1=t1, t2=t2)
    raise ValueError("no key tabulated for shaft diameter %.1f" % shaft_diameter)


# --------------------------------------------------------------------------
# plain primitives
# --------------------------------------------------------------------------
def cyl(r, x0, x1, y_axis, z_axis=0.0):
    """Cylinder along +X from ``x0`` to ``x1`` (order does not matter)."""
    if x1 < x0:
        x0, x1 = x1, x0
    return Part.makeCylinder(r, x1 - x0,
                             App.Vector(x0, y_axis, z_axis),
                             App.Vector(1, 0, 0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0,
                        App.Vector(x0, y0, z0))


def union(shapes):
    """Fuse an iterable of shapes, returning ``None`` for an empty input."""
    out = None
    for s in shapes:
        out = s if out is None else out.fuse(s)
    return out


# --------------------------------------------------------------------------
# involute gear geometry
# --------------------------------------------------------------------------
def gear_profile_wire(m, z, alpha, add_coeff=1.0, ded_coeff=1.25,
                      fillet_coeff=0.38, shift_coeff=0.0):
    """Involute gear profile as a closed wire (local frame, axis = +Z).

    Uses the involute generator shipped inside FreeCAD's PartDesign workbench
    (``PartDesign.fcgear``), which is the same code behind the GUI command
    ``PartDesign_InvoluteGear``.  ``fillet_coeff`` defaults to 0.38 (the ISO
    rack value used by FreeCAD >= 1.0).  Returns ``(wire, n_edges)``.
    """
    w = fcgear.FCWireBuilder()
    involute.CreateExternalGear(w, m, z, alpha, split=True,
                               addCoeff=add_coeff, dedCoeff=ded_coeff,
                               filletCoeff=fillet_coeff, shiftCoeff=shift_coeff)
    wire = Part.Wire([o.toShape() for o in w.wire])
    return wire


def make_gear_solid(m, z, alpha, width, bore_r=0.0, lightening=None, key=None,
                    add_coeff=1.0, ded_coeff=1.25, fillet_coeff=0.38,
                    shift_coeff=0.0):
    """Extruded spur gear in its local frame: axis along +Z, a tooth centred on
    +X, extruded symmetrically about z = 0.

    ``bore_r``  - hub bore radius (0 for a solid blank / integral gear shaft).
    ``lightening`` - optional ``(n_holes, hole_centre_radius, hole_radius)``
        for the web lightening holes of a large wheel.
    ``key``     - optional ``(b, t2)``: cut the hub keyway here, in the local
        frame, *before* the solid is handed to a document object.

    Do **not** cut the hub keyway afterwards through ``obj.Shape``.  Reading
    ``Part::Feature.Shape`` returns the shape with the object's Placement
    already applied, so a local-frame cutter would land in the wrong place -
    and because FreeCAD also bakes the rotation into the shape and resets the
    Placement to identity, nothing about the object reveals the mistake.
    Passing ``key`` here makes that class of error impossible.
    """
    wire = gear_profile_wire(m, z, alpha, add_coeff, ded_coeff,
                             fillet_coeff, shift_coeff)
    solid = Part.Face(wire).extrude(App.Vector(0, 0, width))
    solid.translate(App.Vector(0, 0, -width / 2.0))
    if bore_r > 0.0:
        solid = solid.cut(Part.makeCylinder(bore_r, width * 3.0,
                                            App.Vector(0, 0, -width * 1.5),
                                            App.Vector(0, 0, 1)))
    if key:
        solid = cut_hub_keyway(solid, bore_r, key[0], key[1], width)
    if lightening:
        n_holes, hole_r_centre, hole_r = lightening
        for k in range(n_holes):
            a = math.radians(360.0 * k / n_holes + 90.0)
            c = App.Vector(hole_r_centre * math.cos(a),
                           hole_r_centre * math.sin(a), -width * 0.6)
            solid = solid.cut(Part.makeCylinder(hole_r, width * 1.2, c,
                                                App.Vector(0, 0, 1)))
    return solid


def tooth_spin(z, target_alpha_deg, tooth=True):
    """Spin phase (deg) that puts a tooth centre (``tooth=True``) or a tooth
    *space* centre (``tooth=False``) of a ``z``-tooth gear at world angle
    ``target_alpha``.

    Angle convention: the gear axis is first laid along +X by rotating +90 deg
    about Y; a spin of ``psi`` is then applied about X.  A feature sitting at
    local angle ``theta`` inside the gear ends up pointing at world direction
    ``(0, sin(theta + psi), -cos(theta + psi))``, so ``alpha == theta + psi``.

    ``PartDesign.fcgear`` centres a **tooth on the local +X axis**, i.e.
    ``theta = 0`` for a tooth and ``theta = 180/z`` for a space.  That was
    measured, not assumed - see docs/06-lessons-learned.md.
    """
    theta = 0.0 if tooth else 180.0 / z
    return (target_alpha_deg - theta) % 360.0


def gear_placement(psi, pos):
    """Placement for a gear: axis along +X, spin ``psi`` about that axis."""
    return App.Placement(
        App.Vector(*pos),
        App.Rotation(App.Vector(1, 0, 0), psi).multiply(
            App.Rotation(App.Vector(0, 1, 0), 90.0)))


def mesh_phases(z_pinion, z_wheel):
    """Spin phases for a standard (zero-backlash) external mesh whose line of
    centres runs along +Y, pinion at the lower Y.

    The pinion's tooth points at +Y (towards the wheel) and the wheel's tooth
    space points at -Y (towards the pinion), which is the nominal
    tooth-in-space condition for equal pressure angles and no profile shift.
    """
    return (tooth_spin(z_pinion, 90.0, tooth=True),
            tooth_spin(z_wheel, 270.0, tooth=False))


# --------------------------------------------------------------------------
# keyways
# --------------------------------------------------------------------------
def cut_hub_keyway(shape, bore_r, b, t2, width):
    """Keyway in a gear hub bore, on local +X.

    ``shape`` must be a gear solid in its **local** frame (axis +Z) - normally
    this is called from :func:`make_gear_solid` via its ``key`` argument.  Never
    pass ``part_feature.Shape``: that value already has the placement applied.
    """
    cutter = box(bore_r - 1.0, bore_r + t2, -b / 2.0, b / 2.0,
                 -width * 1.1, width * 1.1)
    return shape.cut(cutter)


def cut_shaft_keyway(shape, x0, x1, shaft_r, b, t1, direction, y_axis):
    """Keyway in a shaft whose axis is along +X at ``(y_axis, 0)``.

    ``direction`` is the unit vector (in the YZ plane) the keyway faces;
    ``b``/``t1`` come from :func:`key_for`.

    The cutter is modelled with the groove facing +Y and then rotated about X
    onto ``direction``.  Note the translation: ``App.Placement`` applies its
    translation *after* the rotation and the rotation is about the **origin**,
    so rotating about an axis through ``(0, y_axis, 0)`` requires
    ``t = axis - R * axis``.  Passing ``axis`` directly (the intuitive guess)
    silently throws the cutter to the far side of the shaft - the cut then
    removes nothing and no error is raised.
    """
    cutter = box(x0, x1, y_axis + shaft_r - t1, y_axis + shaft_r + 30.0,
                 -b / 2.0, b / 2.0)
    rot = App.Rotation(App.Vector(1, 0, 0),
                       math.degrees(math.atan2(direction.z, direction.y)))
    axis = App.Vector(0, y_axis, 0)
    return shape.cut(cutter.transformGeometry(
        App.Placement(axis - rot.multVec(axis), rot).toMatrix()))


def keyway_section_area(shaft_r, b, t1):
    """Exact cross-section area of a rectangular keyway slot cut to depth
    ``t1`` (measured from the cylinder surface) and width ``b`` into a shaft of
    radius ``shaft_r``.

    ``A = integral(-b/2..b/2) (sqrt(R^2 - y^2) - (R - t1)) dy``
    ``  = 2*(y/2*sqrt(R^2-y^2) + R^2/2*asin(y/R))|_0^(b/2)  -  b*(R - t1)``

    Handy for verifying a boolean cut: multiply by the *effective* length, i.e.
    the part of the cutter that actually lies inside the shaft.
    """
    def anti(y):
        return (y / 2.0) * math.sqrt(shaft_r ** 2 - y ** 2) \
            + (shaft_r ** 2 / 2.0) * math.asin(y / shaft_r)
    return 2.0 * anti(b / 2.0) - b * (shaft_r - t1)


def keyway_volume_analytic(shaft_r, b, t1, length):
    return keyway_section_area(shaft_r, b, t1) * length


# --------------------------------------------------------------------------
# shafts
# --------------------------------------------------------------------------
def make_shaft(segments, y_axis):
    """Stepped shaft along +X.

    ``segments`` is a list of ``(x_start, x_end, diameter)``.  Adjacent
    segments of different diameter create the shoulders that locate gears and
    bearings axially.

    Keep diameter steps **outside** the axial span occupied by an end cap, or a
    through cap's central hole (sized on the smaller diameter) will collide
    with the larger section - see docs/06-lessons-learned.md.
    """
    return union(cyl(d / 2.0, x0, x1, y_axis) for x0, x1, d in segments)\
        .removeSplitter()


# --------------------------------------------------------------------------
# rolling bearings
# --------------------------------------------------------------------------
def make_bearing(d, D, B, n_balls, x_outer_face, y_axis, side,
                 ring_ratio=0.14, ball_ratio=0.95):
    """Simplified deep-groove ball bearing: inner ring, outer ring and a ring
    of balls, fused into one solid.

    ``d``/``D``/``B``  - bore, outside diameter, width.
    ``x_outer_face``   - axial position of the face pointing away from the
                         reducer centre.
    ``side``           - -1 for the left wall, +1 for the right wall.

    The ring wall is ``ring_ratio*(D-d)`` and the balls have radius
    ``ball_ratio * ring_wall`` on the pitch radius ``(d+D)/4``, so they overlap
    both rings and the fuse yields a single connected solid.

    Beware: some (n_balls, ball_ratio) combinations produce a *self-
    intersecting* result that ``Shape.isValid()`` reports as False even though
    the boolean "succeeds".  ``check_bearing()`` guards against that.
    """
    t = ring_ratio * (D - d)
    rb = ball_ratio * t
    rp = (d + D) / 4.0
    x0, x1 = sorted((x_outer_face, x_outer_face - side * B))
    inner = cyl(d / 2.0 + t, x0, x1, y_axis).cut(
        cyl(d / 2.0, x0 - 1.0, x1 + 1.0, y_axis))
    outer = cyl(D / 2.0, x0, x1, y_axis).cut(
        cyl(D / 2.0 - t, x0 - 1.0, x1 + 1.0, y_axis))
    solid = inner.fuse(outer)
    for k in range(n_balls):
        a = 2.0 * math.pi * k / n_balls + math.pi / n_balls
        solid = solid.fuse(Part.makeSphere(
            rb, App.Vector((x0 + x1) / 2.0,
                           y_axis + rp * math.cos(a),
                           rp * math.sin(a))))
    return solid.removeSplitter()


def check_bearing(shape):
    """Return ``(ok, message)`` for a bearing solid produced above.

    ``Shape.isValid()`` is the cheap guard; a bearing that comes back invalid is
    almost always a ball-count / ball-size coincidence, so try 9 or 11 balls.
    """
    if not shape.isValid():
        return False, "shape is not valid - retry with n_balls in (9, 11)"
    if shape.Volume <= 0.0:
        return False, "non-positive volume"
    return True, "ok"


# --------------------------------------------------------------------------
# flanged bearing end caps
# --------------------------------------------------------------------------
def cap_dimensions(D, d3=8.0):
    """Standard flanged end cap sizes for a bearing of outside diameter ``D``
    and cap screw diameter ``d3`` (M8 by default):

    ``D0 = D + 2.5*d3``  bolt circle
    ``D2 = D0 + 2.5*d3`` flange outside diameter
    ``e  = 1.2*d3``      flange thickness
    ``e1 = 0.8*e``       spigot length (the locating lip that enters the bore)
    """
    D0 = D + 2.5 * d3
    D2 = D0 + 2.5 * d3
    e = 1.2 * d3
    e1 = 0.8 * e
    return dict(D0=D0, D2=D2, e=e, e1=e1, d3=d3, screw_hole=1.125 * d3)


def make_end_cap(D, side, shaft_d, y_axis, boss_face, through,
                 d3=8.0, spigot_clearance=0.2):
    """Flanged bearing end cap.

    ``D``         - bearing outside diameter; the spigot is a clearance fit in
                    the housing bore of the same nominal size.
    ``through``   - True for an opening cap (shaft passes through, central bore
                    sized ``shaft_d + 4``); False for a blind cap.
    ``boss_face`` - |x| of the housing boss face the flange is bolted to.

    The flange sits outboard of ``boss_face`` and the spigot reaches inboard by
    ``e1``, ending exactly on the bearing's outer face so it clamps the outer
    ring.

    Two details that are easy to get wrong:

    * The central bore must clear the *largest* diameter the shaft reaches
      anywhere inside the cap's axial span, not just at the flange.
    * The bore's axial extent has to be the min/max over **all four** flange and
      spigot end points.  Using only the two inboard points leaves part of the
      flange undrilled and produces a large, non-obvious collision with the
      shaft.
    """
    dim = cap_dimensions(D, d3)
    e, e1, D0, D2 = dim["e"], dim["e1"], dim["D0"], dim["D2"]

    xf_out = side * (boss_face + e)   # flange face away from the housing
    xf_in = side * boss_face          # flange face against the boss
    xs_out = side * boss_face         # spigot end against the boss
    xs_in = side * (boss_face - e1)   # spigot end clamping the bearing

    flange = cyl(D2 / 2.0, *sorted((xf_out, xf_in)), y_axis)
    spigot = cyl((D - spigot_clearance) / 2.0, *sorted((xs_out, xs_in)), y_axis)
    solid = flange.fuse(spigot)

    lo = min(xf_out, xf_in, xs_out, xs_in)
    hi = max(xf_out, xf_in, xs_out, xs_in)
    if through:
        solid = solid.cut(cyl((shaft_d + 4.0) / 2.0, lo - 3.0, hi + 3.0, y_axis))
    # cap screws: 4 holes at 45 deg offsets, which keeps them clear of the
    # housing split plane at z = 0
    for k in range(4):
        a = math.radians(45.0 + 90.0 * k)
        hole_y = y_axis + D0 / 2.0 * math.cos(a)
        hole_z = D0 / 2.0 * math.sin(a)
        solid = solid.cut(cyl(dim["screw_hole"] / 2.0,
                              lo - 3.0, lo - 3.0 + e + 6.0, hole_y, hole_z))
    return solid.removeSplitter()


# --------------------------------------------------------------------------
# measurement / verification helpers
# --------------------------------------------------------------------------
def common_volume(a, b):
    """Volume of the intersection of two shapes.

    This is the only trustworthy interference test.  ``Shape.distToShape``
    returns 0 both when two solids merely touch and when they overlap, so a
    minimum distance of 0 proves *contact* but never proves *no overlap*.
    """
    return a.common(b).Volume


def cylindrical_axis(shape, radius, tol=1e-6, near=None):
    """``(point, direction)`` of a cylindrical face of the given radius.

    Use this instead of bounding boxes when an axis position or a centre
    distance has to be checked: bounding boxes of boolean results are computed
    from discretised geometry and can be off by ~0.1 mm (0.3 % here), which is
    enough to make a correct design look wrong.

    A radius alone is often ambiguous - in this housing, 62.5 mm is both the
    6214 bearing bore radius and the 6209 boss outside radius.  Pass ``near``
    (an ``App.Vector``, normally the expected axis position) to pick the face
    whose axis passes closest to it.
    """
    hits = []
    for f in shape.Faces:
        s = f.Surface
        if s.TypeId == "Part::GeomCylinder" and abs(s.Radius - radius) < tol:
            hits.append((s.Center, s.Axis))
    if not hits:
        raise ValueError("no cylindrical face of radius %.3f" % radius)
    if near is None:
        return hits[0]
    return min(hits, key=lambda h: (h[0] - near).Length)


def report(title, rows, width=68):
    """Tiny aligned table printer used by the build/verify scripts."""
    print("\n" + "=" * width)
    print(title)
    print("=" * width)
    for row in rows:
        print(row)


# --------------------------------------------------------------------------
# document helpers
# --------------------------------------------------------------------------
def fresh_document(name):
    """Create a new document, closing any existing document of the same name.

    ``App.getDocument`` **raises** ``NameError`` for an unknown name rather than
    returning ``None``, so existence has to be tested against
    ``App.listDocuments()``.  The same trap exists in freecad-mcp itself, where
    it caused document-query handlers to leak a raw XML-RPC fault.
    """
    if name in App.listDocuments():
        App.closeDocument(name)
    return App.newDocument(name)


def save_document(doc, path):
    """Save ``doc`` to ``path``, creating parent directories as needed."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    doc.saveAs(path)
    return path
