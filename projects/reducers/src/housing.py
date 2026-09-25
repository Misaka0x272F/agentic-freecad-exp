"""
housing.py - split-cast housing builder for the reducers in this repo.

The housing outline is the union of one circle per shaft axis ("lobes"), which
is how real cast reducers look: a dome that wraps each gear pair.  Both
variants here are split horizontally through the plane that contains every
shaft axis (``z = 0``), giving ``Housing_Base`` (z < 0) and ``Housing_Cover``
(z > 0).

Geometry conventions
--------------------
* ``cavity_r`` per lobe is the *inner* wall radius = gear tip radius + oil
  clearance.  The body outline is ``cavity_r + wall`` and the split flange rim
  is ``cavity_r + wall + 2*f`` so that the flange overhangs the wall.
* The lower half is a rectangular box rather than a continuing circle.  Real
  bases are boxy and this also gives a genuinely flat bottom to sit on.
* The cavity floor is a flat oil sump, and it must clear the lowest gear tooth
  of the whole train - the single most common way to accidentally cut a wheel.
"""

import math

import Part

from common import box, cyl, union


def build_housing(doc, spec, name_cover="Housing_Cover",
                  name_base="Housing_Base", label_cover="Housing cover",
                  label_base="Housing base"):
    """Build and return ``(cover, base)`` objects.

    ``spec`` keys
    -------------
    lobes            : [(y_axis, cavity_radius), ...]
    cavity_x         : half length of the inner cavity
    wall_x           : |x| of the end wall's outer face
    boss_x           : |x| of the bearing boss face
    boss_radius      : {y_axis: boss outer radius}
    bore_radius      : {y_axis: bearing bore radius}
    bolt_circle      : {y_axis: end-cap screw circle diameter D0}
    z_body_bottom    : flat bottom of the casting
    z_cavity_bottom  : flat floor of the oil sump
    flange_t         : half thickness of the split flange (total = 2*flange_t)
    lower_box_y      : (y_min, y_max) of the rectangular lower housing
    base_plate       : (x_half, y_min, y_max, z_min, z_max)
    foundation_bolts : [(x, y), ...] tapped through the base plate
    split_bolts      : [(x, y), ...] through the split flange
    wall             : casting wall thickness (default 8)
    flange_overhang  : radial overhang of the split flange (default 24)
    """
    lobes = spec["lobes"]
    cx = spec["cavity_x"]
    wx = spec["wall_x"]
    bx = spec["boss_x"]
    wall = spec.get("wall", 8.0)
    over = spec.get("flange_overhang", 24.0)
    ft = spec["flange_t"]
    zb = spec["z_body_bottom"]
    zc = spec["z_cavity_bottom"]

    def lobe(radii, x0, x1):
        return union(cyl(r, x0, x1, y) for y, r in radii)

    body_radii = [(y, r + wall) for y, r in lobes]
    rim_radii = [(y, r + wall + over) for y, r in lobes]

    # ---- body ----
    upper = lobe(body_radii, -wx, wx).common(
        box(-1e4, 1e4, -1e4, 1e4, 0, 1e4))
    ly0, ly1 = spec["lower_box_y"]
    lower = box(-wx, wx, ly0, ly1, zb, 0)
    body = upper.fuse(lower)

    # ---- bearing bosses ----
    boss = union(cyl(spec["boss_radius"][y], s * wx, s * bx, y)
                 for y in spec["boss_radius"] for s in (-1, 1))

    # ---- split flange: rim around the outline + an ear around each boss ----
    slab = box(-1e4, 1e4, -1e4, 1e4, -ft, ft)
    rim = lobe(rim_radii, -wx, wx).cut(lobe(body_radii, -wx, wx)).common(slab)
    ears = None
    for y, rb in spec["boss_radius"].items():
        for s in (-1, 1):
            e = cyl(rb + over, s * wx, s * bx, y).cut(
                cyl(rb, s * wx, s * bx, y)).common(slab)
            ears = e if ears is None else ears.fuse(e)

    # ---- base plate ----
    bpx, bpy0, bpy1, bpz0, bpz1 = spec["base_plate"]
    base = box(-bpx, bpx, bpy0, bpy1, bpz0, bpz1)

    full = body.fuse(boss).fuse(rim).fuse(ears).fuse(base).removeSplitter()

    # ---- cavity (flat oil-sump floor) ----
    cav = lobe(lobes, -cx, cx).common(box(-1e4, 1e4, -1e4, 1e4, zc, 1e4))
    full = full.cut(cav)

    # ---- bearing bores ----
    for y, r in spec["bore_radius"].items():
        full = full.cut(cyl(r, -bx - 5.0, bx + 5.0, y))

    # ---- end-cap screw holes in the boss faces ----
    for y, D0 in spec["bolt_circle"].items():
        for s in (-1, 1):
            for k in range(4):
                a = math.radians(45.0 + 90.0 * k)
                full = full.cut(cyl(4.5, s * bx, s * (bx - 16.0),
                                    y + D0 / 2.0 * math.cos(a),
                                    D0 / 2.0 * math.sin(a)))

    # ---- split-flange bolts ----
    for x, y in spec["split_bolts"]:
        full = full.cut(box(x - 5.5, x + 5.5, y - 5.5, y + 5.5,
                            -ft - 4.0, ft + 4.0))

    # ---- foundation bolts ----
    for x, y in spec["foundation_bolts"]:
        full = full.cut(box(x - 10.0, x + 10.0, y - 10.0, y + 10.0,
                            bpz0 - 12.0, zb + 6.0))

    full = full.removeSplitter()
    cover = full.common(box(-1e4, 1e4, -1e4, 1e4, 0, 1e4)).removeSplitter()
    base_s = full.common(box(-1e4, 1e4, -1e4, 1e4, -1e4, 0)).removeSplitter()

    o1 = doc.addObject("Part::Feature", name_cover)
    o1.Shape = cover
    o1.Label = label_cover
    o2 = doc.addObject("Part::Feature", name_base)
    o2.Shape = base_s
    o2.Label = label_base
    return o1, o2


# --------------------------------------------------------------------------
# concrete housing specs
# --------------------------------------------------------------------------
def single_stage_spec(gear_tip_r=(44.0, 124.0), clearance=12.0,
                      ax=(37.0, 47.0, 64.0), bearings=None,
                      sump_clearance=6.0, **kw):
    """Housing for the single-stage reducer (shaft axes at y = 0 and 160)."""
    y0, y1 = 0.0, 160.0
    lobes = [(y0, gear_tip_r[0] + clearance), (y1, gear_tip_r[1] + clearance)]
    _, _, boss_x = ax
    spec = dict(
        lobes=lobes,
        cavity_x=ax[0], wall_x=ax[1], boss_x=boss_x,
        boss_radius={y0: 51.0, y1: 62.5},        # 6206 / 6209 cap flange radii
        bore_radius={y0: 31.0, y1: 42.5},
        bolt_circle={y0: 82.0, y1: 105.0},
        z_body_bottom=-140.0,
        z_cavity_bottom=-140.0 + 10.0,
        flange_t=12.0,
        lower_box_y=(-64.0, 304.0),
        base_plate=(55.0, -76.0, 316.0, -158.0, -139.0),
        foundation_bolts=[(-36.0, -58.0), (36.0, -58.0),
                          (-36.0, 298.0), (36.0, 298.0)],
        split_bolts=[(-30.0, -76.0), (30.0, -76.0), (-30.0, 316.0), (30.0, 316.0),
                     (55.0, 70.0), (-55.0, 70.0), (55.0, -70.0), (-55.0, -70.0),
                     (55.0, 234.5), (-55.0, 234.5), (55.0, 85.5), (-55.0, 85.5)],
    )
    del sump_clearance, bearings, kw
    return spec


def two_stage_spec(ax=(82.0, 92.0, 114.0), bearings=None, **kw):
    """Housing for the expanded two-stage reducer (axes at y = 0/150/310)."""
    yI, yII, yIII = 0.0, 150.0, 310.0
    lobes = [(yI, 45.0), (yII, 135.0), (yIII, 136.0)]
    boss_r = {yI: 51.0, yII: 62.5, yIII: 62.5}    # 6206 / 6209 / 6214 caps
    spec = dict(
        lobes=lobes,
        cavity_x=ax[0], wall_x=ax[1], boss_x=ax[2],
        boss_radius=boss_r,
        bore_radius={yI: 31.0, yII: 42.5, yIII: 62.5},
        bolt_circle={yI: 82.0, yII: 105.0, yIII: 145.0},
        z_body_bottom=-140.0,
        z_cavity_bottom=-130.0,
        flange_t=12.0,
        lower_box_y=(-53.0, 454.0),
        base_plate=(100.0, -65.0, 466.0, -158.0, -139.0),
        foundation_bolts=[(-75.0, -50.0), (75.0, -50.0),
                          (-75.0, 450.0), (75.0, 450.0)],
        split_bolts=[],
    )
    # flange bolts at the two Y extremes plus one pair beside every boss
    spec["split_bolts"] = [(x, -65.0) for x in (-58.0, 0.0, 58.0)]
    spec["split_bolts"] += [(x, 466.0) for x in (-58.0, 0.0, 58.0)]
    for y, rb in boss_r.items():
        rr = rb + 12.0
        for s in (-1, 1):
            spec["split_bolts"] += [(s * (ax[1] + 11.0), y - rr),
                                    (s * (ax[1] + 11.0), y + rr)]
    del bearings, kw
    return spec
