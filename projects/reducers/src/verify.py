#!/usr/bin/env python3
"""
verify.py - independent geometry audit of a built reducer.

The point of this script is to *not* trust the builder.  It re-opens the saved
``.FCStd`` and re-derives everything it can from the geometry itself.

Two habits matter more than the individual checks:

1.  **Measure in the frame the data is actually in.**  ``Part::Feature.Shape``
    returns the shape with the object's Placement already applied, so a gear
    that was modelled in its own local frame reads back rotated into world
    coordinates.  This module therefore measures every gear about its own axis
    (along +X through ``y_axis``) instead of assuming a local frame.

2.  **Never use ``Shape.distToShape`` to prove non-overlap.**  It returns 0 both
    for touching and for overlapping solids.  Intersection *volume* is the only
    sound interference test.

Each gear is checked for tip radius, tooth count, face width, and for the
presence of its hub keyway at the angular position the mating shaft keyway
uses.  That last check is the one that catches the classic mistake of cutting a
local-frame feature into an already-placed shape.

Usage::

    freecadcmd -P src -c "import verify; verify.main('two')"

Exits non-zero when a check fails.
"""

import math
import os
import sys

try:
    # FreeCAD's embedded interpreter exits through its own C++ path, which does
    # not flush Python's stdout buffer - without this, output redirected to a
    # file is silently lost when a check fails and raises SystemExit.
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__)) \
    if "__file__" in globals() else os.path.join(os.getcwd(), "src")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import FreeCAD as App  # noqa: E402

from common import (  # noqa: E402
    check_bearing, common_volume, cylindrical_axis, gear_placement, report,
)

TOL = 1e-4      # position tolerance (mm)

MODELS = {
    "single": dict(
        path="models/reducer_single_stage.FCStd",
        gears={
            "Gear_Pinion": dict(m=4.0, z=20, width=50.0, y=0.0, psi=90.0,
                                bore_r=18.0, t2=3.3),
            "Gear_Wheel": dict(m=4.0, z=60, width=45.0, y=160.0, psi=267.0,
                               bore_r=27.5, t2=4.3),
        },
        meshes=[("Gear_Pinion", "Gear_Wheel")],
        shafts={"Shaft_Input": 18.0, "Shaft_Output": 27.5},
        bores={"Shaft_Input": 31.0, "Shaft_Output": 42.5},
        bearing_shaft={"Bearing_HS_L": "Shaft_Input",
                       "Bearing_HS_R": "Shaft_Input",
                       "Bearing_LS_L": "Shaft_Output",
                       "Bearing_LS_R": "Shaft_Output"},
        centres=[("Shaft_Input", "Shaft_Output", 160.0)],
        housing="Housing_Cover",
    ),
    "two": dict(
        path="models/reducer_two_stage.FCStd",
        gears={
            "G1_Pinion_HS": dict(m=3.0, z=20, width=55.0, y=0.0, psi=90.0,
                                 bore_r=18.0, t2=3.3),
            "G2_Wheel_HS": dict(m=3.0, z=80, width=50.0, y=150.0, psi=267.75,
                                bore_r=25.0, t2=3.8),
            "G3_Pinion_LS": dict(m=4.0, z=20, width=65.0, y=150.0, psi=90.0,
                                 bore_r=25.0, t2=3.8),
            "G4_Wheel_LS": dict(m=4.0, z=60, width=60.0, y=310.0, psi=267.0,
                                bore_r=40.0, t2=5.4),
        },
        meshes=[("G1_Pinion_HS", "G2_Wheel_HS"),
                ("G3_Pinion_LS", "G4_Wheel_LS")],
        shafts={"Shaft_HS": 18.0, "Shaft_MID": 25.0, "Shaft_LS": 40.0},
        bores={"Shaft_HS": 31.0, "Shaft_MID": 42.5, "Shaft_LS": 62.5},
        bearing_shaft={"Bearing_HS_L": "Shaft_HS", "Bearing_HS_R": "Shaft_HS",
                       "Bearing_MID_L": "Shaft_MID",
                       "Bearing_MID_R": "Shaft_MID",
                       "Bearing_LS_L": "Shaft_LS", "Bearing_LS_R": "Shaft_LS"},
        centres=[("Shaft_HS", "Shaft_MID", 150.0),
                 ("Shaft_MID", "Shaft_LS", 160.0)],
        housing="Housing_Cover",
    ),
}

FAILURES = []


def check(label, ok, detail=""):
    if not ok:
        FAILURES.append(label)
    print("  [%s] %-56s %s" % ("PASS" if ok else "FAIL", label, detail))
    return ok


def polar_vertices(shape, y_axis):
    """``(angle, radius)`` of every vertex about the axis X through ``y_axis``."""
    out = []
    for v in shape.Vertexes:
        dy = v.Point.y - y_axis
        out.append((math.atan2(v.Point.z, dy) % (2 * math.pi),
                    math.hypot(dy, v.Point.z)))
    return out


def count_teeth(shape, y_axis, expected_z):
    """Count teeth by clustering the vertices that sit on the tip circle.

    Uses half the *expected* tooth pitch as the clustering threshold: the two
    vertices bounding one tip arc are far closer together than adjacent teeth.

    The wrap-around gap is handled explicitly - a tip arc straddling the 0/360
    boundary otherwise counts as two clusters and inflates the tooth count by
    one.  (The same trap caused a mis-measured tooth phase earlier in this
    project, which is why the check is written this way.)
    """
    pts = polar_vertices(shape, y_axis)
    r_tip = max(r for _, r in pts)
    band = sorted(a for a, r in pts if r > r_tip - 0.25)
    if len(band) < 2:
        return r_tip, len(band)
    thr = 0.5 * 2 * math.pi / expected_z
    n = 1
    for prev, cur in zip(band, band[1:]):
        if cur - prev > thr:
            n += 1
    if (band[0] + 2 * math.pi) - band[-1] <= thr:
        n -= 1          # first and last cluster are the same tooth
    return r_tip, n


def main(variant_or_path):
    spec = MODELS.get(variant_or_path)
    if spec is None:
        spec = next((v for v in MODELS.values()
                     if v["path"] == variant_or_path), None)
    if spec is None:
        raise SystemExit("unknown variant/path: %s" % variant_or_path)

    path = spec["path"]
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(_HERE), path)
    if not os.path.isfile(path):
        raise SystemExit("model not found: %s (run the builder first)" % path)

    doc = App.openDocument(path)
    name = doc.Name
    report("VERIFY %s" % os.path.relpath(path, os.path.dirname(_HERE)),
           ["objects: %d" % len(doc.Objects)])

    # ------------------------------------------------------------- 1. solids
    print("\n-- 1. solid validity --")
    for o in sorted(doc.Objects, key=lambda x: x.Name):
        check("%s valid" % o.Name, o.Shape.isValid(),
              "%.1f cm3" % (o.Shape.Volume / 1000.0))
        if o.Name.startswith("Bearing_"):
            ok, msg = check_bearing(o.Shape)
            check("%s bearing integrity" % o.Name, ok, msg)

    # ---------------------------------------------------------- 2. gears
    print("\n-- 2. gear geometry (tip radius, tooth count, face width) --")
    for gname, g in spec["gears"].items():
        o = doc.getObject(gname)
        r_tip, n_teeth = count_teeth(o.Shape, g["y"], g["z"])
        want_tip = g["m"] * (g["z"] / 2.0 + 1.0)
        bb = o.Shape.BoundBox
        check("%s tip radius %.3f (expect %.3f)" % (gname, r_tip, want_tip),
              abs(r_tip - want_tip) < 0.05 * g["m"], "m=%.1f" % g["m"])
        check("%s tooth count %d (expect %d)" % (gname, n_teeth, g["z"]),
              n_teeth == g["z"])
        check("%s face width %.2f (expect %.1f)"
              % (gname, bb.XMax - bb.XMin, g["width"]),
              abs((bb.XMax - bb.XMin) - g["width"]) < 1e-3)

    # ------------------------------------------------- 3. hub keyways
    print("\n-- 3. gear hub keyways at the mating shaft keyway angle --")
    for gname, g in spec["gears"].items():
        o = doc.getObject(gname)
        d = gear_placement(g["psi"], (0.0, g["y"], 0.0)).Rotation.multVec(
            App.Vector(1, 0, 0))
        r = g["bore_r"] + g["t2"] / 2.0
        p = App.Vector(0.0, g["y"] + d.y * r, d.z * r)
        empty = not o.Shape.isInside(p, 1e-6, True)
        check("%s hub keyway present at (%.3f, %.3f)"
              % (gname, d.y * r, d.z * r), empty,
              "expected void, got %s" % ("void" if empty else "material"))

    # --------------------------------------------- 4. axes / centre distances
    print("\n-- 4. axis alignment and centre distances --")
    axis = {}
    for sname, r in spec["shafts"].items():
        pt, direction = cylindrical_axis(doc.getObject(sname).Shape, r)
        axis[sname] = pt
        check("%s axis along X" % sname,
              abs(direction.y) < 1e-9 and abs(direction.z) < 1e-9,
              "dir=(%.6f, %.6f, %.6f)" % (direction.x, direction.y, direction.z))
    for a, b, design in spec["centres"]:
        got = math.hypot(axis[b].y - axis[a].y, axis[b].z - axis[a].z)
        check("centre distance %s-%s = %.6f (design %.3f)" % (a, b, got, design),
              abs(got - design) < TOL)

    for bname, sname in sorted(spec["bearing_shaft"].items()):
        b = doc.getObject(bname)
        r_bore = min(f.Surface.Radius for f in b.Shape.Faces
                     if f.Surface.TypeId == "Part::GeomCylinder")
        pt, _ = cylindrical_axis(b.Shape, r_bore)
        off = math.hypot(pt.y - axis[sname].y, pt.z - axis[sname].z)
        check("%s coaxial with %s" % (bname, sname), off < 1e-6,
              "offset %.6f mm" % off)

    cover = doc.getObject(spec["housing"])
    for sname, r_bore in spec["bores"].items():
        # the expected axis is passed as a *selector* only, to disambiguate
        # between faces that share a radius; the position itself is then
        # asserted against the design value
        pt, _ = cylindrical_axis(cover.Shape, r_bore, near=axis[sname])
        off = math.hypot(pt.y - axis[sname].y, pt.z - axis[sname].z)
        check("housing bore coaxial with %s" % sname, off < 1e-6,
              "offset %.6f mm" % off)

    # --------------------------------------------------- 5. interference
    print("\n-- 5. pairwise interference (intersection volume) --")
    objs = sorted(doc.Objects, key=lambda x: x.Name)
    worst = []
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            v = common_volume(objs[i].Shape, objs[j].Shape)
            if v > 1e-3:
                worst.append((v, objs[i].Name, objs[j].Name))
    for v, a, b in sorted(worst, reverse=True)[:10]:
        print("      %-14s / %-14s %12.4f mm3" % (a, b, v))
    check("no part pair intersects (%d pairs)"
          % (len(objs) * (len(objs) - 1) // 2), not worst)

    for a, b in spec["meshes"]:
        va, vb = doc.getObject(a).Shape, doc.getObject(b).Shape
        check("mesh %s-%s touches without overlap" % (a, b),
              va.distToShape(vb)[0] < 1e-3 and common_volume(va, vb) < 1e-3)

    App.closeDocument(name)

    print("\n" + "=" * 72)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("   - %s" % f)
        raise SystemExit(1)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "two")
