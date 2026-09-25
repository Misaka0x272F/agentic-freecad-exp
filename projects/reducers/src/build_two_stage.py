#!/usr/bin/env python3
"""
build_two_stage.py - expanded two-stage cylindrical gear reducer.

    shaft I   (high speed, extends left)     : stage-1 pinion  z=20, m=3
    shaft II  (intermediate, fully enclosed) : stage-1 wheel   z=80, m=3
                                               stage-2 pinion  z=20, m=4
    shaft III (low speed, extends right)     : stage-2 wheel   z=60, m=4

    i1 = 4.000,  i2 = 3.000,  i = 12.000,  a1 = 150 mm,  a2 = 160 mm

The three shaft axes are collinear (y = 0 / 150 / 310) and the two meshes sit at
different axial stations (x = -45 / +45).  That is the classic "expanded"
(layout): the intermediate shaft carries the wheel of stage 1 *and* the pinion
of stage 2, so the two gear pairs must occupy different axial bands.

Run headless::

    freecadcmd -P src -c "import build_two_stage as m; m.main()"

Writes ``models/reducer_two_stage.FCStd``.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) \
    if "__file__" in globals() else os.path.join(os.getcwd(), "src")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import FreeCAD as App  # noqa: E402

from common import (  # noqa: E402
    common_volume, cylindrical_axis, cut_shaft_keyway, fresh_document,
    gear_placement, key_for, keyway_volume_analytic, make_bearing,
    make_end_cap, make_gear_solid, make_shaft, mesh_phases, report,
    save_document,
)
from housing import build_housing, two_stage_spec  # noqa: E402

DOC_NAME = "Reducer_TwoStage"
MODEL_PATH = os.path.join(os.path.dirname(_HERE),
                         "models", "reducer_two_stage.FCStd")

# --------------------------------------------------------------------------
# design parameters
# --------------------------------------------------------------------------
ALPHA = 20.0
# stage 1: shaft I -> shaft II
M1, Z1, Z2 = 3.0, 20, 80
B1, B2 = 55.0, 50.0            # pinion1 / wheel1 face width
BORE1, BORE2 = 18.0, 25.0      # D36 / D50
A1 = M1 * (Z1 + Z2) / 2.0
# stage 2: shaft II -> shaft III
M2, Z3, Z4 = 4.0, 20, 60
B3, B4 = 65.0, 60.0            # pinion2 / wheel2 face width
BORE3, BORE4 = 25.0, 40.0      # D50 / D80
A2 = M2 * (Z3 + Z4) / 2.0

Y_I, Y_II, Y_III = 0.0, A1, A1 + A2
X_ST1, X_ST2 = -45.0, 45.0     # axial stations of the two meshes

BOSS_X = 114.0                 # housing bearing boss face (|x|)
CAP_E1 = 0.8 * 1.2 * 8.0       # end cap spigot length = 8
BRG_FACE = BOSS_X - CAP_E1     # bearing outer face = 106

# Diameter steps are kept OUTSIDE the cap spans (|x| 106 .. 124) so that a
# through cap's central bore, sized on the smaller diameter, clears the shaft.
HS_SEGS = [(-165.0, -126.0, 25.0), (-126.0, -85.0, 30.0),
           (-85.0, -5.0, 36.0), (-5.0, 105.0, 30.0)]
MID_SEGS = [(-105.0, -72.0, 45.0), (-72.0, -18.0, 50.0), (-18.0, 10.5, 45.0),
            (10.5, 79.5, 50.0), (79.5, 105.0, 45.0)]
LS_SEGS = [(-105.0, 9.0, 70.0), (9.0, 81.0, 80.0),
           (81.0, 126.0, 70.0), (126.0, 165.0, 65.0)]
SEGS = {"Shaft_HS": (HS_SEGS, Y_I),
        "Shaft_MID": (MID_SEGS, Y_II),
        "Shaft_LS": (LS_SEGS, Y_III)}
SHAFT_LABEL = {"Shaft_HS": "Shaft I  (high speed, extends left)",
               "Shaft_MID": "Shaft II (intermediate, fully enclosed)",
               "Shaft_LS": "Shaft III (low speed, extends right)"}

# (object name, label, m, z, width, bore r, lightening holes, (x, y), spin phase)
GEAR_DEFS = [
    ("G1_Pinion_HS", "Stage-1 pinion z=%d (shaft I)" % Z1,
     M1, Z1, B1, BORE1, None, (X_ST1, Y_I)),
    ("G2_Wheel_HS", "Stage-1 wheel z=%d (shaft II)" % Z2,
     M1, Z2, B2, BORE2, (6, 72.0, 15.0), (X_ST1, Y_II)),
    ("G3_Pinion_LS", "Stage-2 pinion z=%d (shaft II)" % Z3,
     M2, Z3, B3, BORE3, None, (X_ST2, Y_II)),
    ("G4_Wheel_LS", "Stage-2 wheel z=%d (shaft III)" % Z4,
     M2, Z4, B4, BORE4, (6, 82.0, 17.0), (X_ST2, Y_III)),
]

BRG_I = dict(d=30, D=62, B=16, n=9)
BRG_II = dict(d=45, D=85, B=19, n=9)
BRG_III = dict(d=70, D=125, B=24, n=9)   # 9 balls: n=10 with ball_ratio 0.95
                                         # fuses into an invalid solid
BEARINGS = [("Bearing_HS_L", BRG_I, Y_I, -1, "6206 (shaft I, left)"),
            ("Bearing_HS_R", BRG_I, Y_I, 1, "6206 (shaft I, right)"),
            ("Bearing_MID_L", BRG_II, Y_II, -1, "6209 (shaft II, left)"),
            ("Bearing_MID_R", BRG_II, Y_II, 1, "6209 (shaft II, right)"),
            ("Bearing_LS_L", BRG_III, Y_III, -1, "6214 (shaft III, left)"),
            ("Bearing_LS_R", BRG_III, Y_III, 1, "6214 (shaft III, right)")]

CAPS = [("Cap_HS_L", BRG_I, Y_I, -1, True, 30.0, "6206 through (I left)"),
        ("Cap_HS_R", BRG_I, Y_I, 1, False, 30.0, "6206 blind (I right)"),
        ("Cap_MID_L", BRG_II, Y_II, -1, False, 45.0, "6209 blind (II left)"),
        ("Cap_MID_R", BRG_II, Y_II, 1, False, 45.0, "6209 blind (II right)"),
        ("Cap_LS_L", BRG_III, Y_III, -1, False, 70.0, "6214 blind (III left)"),
        ("Cap_LS_R", BRG_III, Y_III, 1, True, 70.0, "6214 through (III right)")]

# (shaft, x0, x1, shaft radius, key, gear whose keyway direction to follow)
SHAFT_KEYWAYS = [
    ("Shaft_HS", -72.5, -17.5, BORE1, key_for(2 * BORE1), "G1_Pinion_HS"),
    ("Shaft_HS", -166.0, -130.0, 12.5, key_for(25.0), "G1_Pinion_HS"),
    ("Shaft_MID", -70.0, -20.0, BORE2, key_for(2 * BORE2), "G2_Wheel_HS"),
    ("Shaft_MID", 12.5, 77.5, BORE3, key_for(2 * BORE3), "G3_Pinion_LS"),
    ("Shaft_LS", 15.0, 75.0, BORE4, key_for(2 * BORE4), "G4_Wheel_LS"),
    ("Shaft_LS", 129.0, 166.0, 32.5, key_for(65.0), "G4_Wheel_LS"),
]


def _phases():
    """Spin phase per gear: pinion tooth at +Y, wheel tooth space at -Y."""
    p1, w1 = mesh_phases(Z1, Z2)
    p2, w2 = mesh_phases(Z3, Z4)
    return {"G1_Pinion_HS": p1, "G2_Wheel_HS": w1,
            "G3_Pinion_LS": p2, "G4_Wheel_LS": w2}


def main(save=True):
    doc = fresh_document(DOC_NAME)
    phase = _phases()

    # ---- gears (hub keyway cut inside make_gear_solid, in the local frame) ----
    for name, label, m, z, width, bore_r, holes, (gx, gy) in GEAR_DEFS:
        k = key_for(2 * bore_r)
        o = doc.addObject("Part::Feature", name)
        o.Label = label
        o.Shape = make_gear_solid(m, z, ALPHA, width, bore_r, holes,
                                  key=(k["b"], k["t2"]))
        o.Placement = gear_placement(phase[name], (gx, gy, 0.0))

    # ---- shafts ----
    for name, (segs, y) in SEGS.items():
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_shaft(segs, y)
        o.Label = SHAFT_LABEL[name]

    # ---- shaft keyways; groove direction follows the mating gear so that both
    #      keyways of one shaft could be milled in a single setup ----
    keyway_rows = []
    for name, x0, x1, r, k, gear_name in SHAFT_KEYWAYS:
        obj = doc.getObject(name)
        d = doc.getObject(gear_name).Placement.Rotation.multVec(
            App.Vector(1, 0, 0))
        before = obj.Shape.Volume
        obj.Shape = cut_shaft_keyway(obj.Shape, x0, x1, r, k["b"], k["t1"],
                                     d, SEGS[name][1])
        lo = min(s[0] for s in SEGS[name][0])
        hi = max(s[1] for s in SEGS[name][0])
        eff = min(x1, hi) - max(x0, lo)
        keyway_rows.append((name, x0, x1, 2 * r, k["b"], k["h"], k["t1"],
                            before - obj.Shape.Volume,
                            keyway_volume_analytic(r, k["b"], k["t1"], eff)))

    # ---- bearings and end caps ----
    for name, spec, y, s, label in BEARINGS:
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_bearing(spec["d"], spec["D"], spec["B"], spec["n"],
                               s * BRG_FACE, y, s)
        o.Label = "Bearing " + label
    for name, spec, y, s, through, shaft_d, label in CAPS:
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_end_cap(spec["D"], s, shaft_d, y, BOSS_X, through)
        o.Label = "End cap " + label

    # ---- housing ----
    build_housing(doc, two_stage_spec())

    doc.recompute()
    _audit(doc, keyway_rows)
    if save:
        save_document(doc, MODEL_PATH)
        print("\nsaved: %s" % MODEL_PATH)
    return doc


def _audit(doc, keyway_rows):
    g1, g2 = doc.getObject("G1_Pinion_HS"), doc.getObject("G2_Wheel_HS")
    g3, g4 = doc.getObject("G3_Pinion_LS"), doc.getObject("G4_Wheel_LS")
    ax = {name: cylindrical_axis(doc.getObject(name).Shape, r)[0].y
          for name, r in (("Shaft_HS", BORE1), ("Shaft_MID", BORE2),
                          ("Shaft_LS", BORE4))}

    report("TWO-STAGE (EXPANDED) REDUCER", [
        "stage 1           m=%.1f  z=%d/%d  i1=%.3f  a1=%.1f mm"
        % (M1, Z1, Z2, Z2 / Z1, A1),
        "stage 2           m=%.1f  z=%d/%d  i2=%.3f  a2=%.1f mm"
        % (M2, Z3, Z4, Z4 / Z3, A2),
        "total ratio       i = i1*i2 = %.3f" % (Z2 / Z1 * Z4 / Z3),
        "shaft axes        y = %.0f / %.0f / %.0f mm" % (Y_I, Y_II, Y_III),
        "centre distance   a1 = %.6f mm  (design %.3f)"
        % (ax["Shaft_MID"] - ax["Shaft_HS"], A1),
        "                  a2 = %.6f mm  (design %.3f)"
        % (ax["Shaft_LS"] - ax["Shaft_MID"], A2),
        "mesh stage 1      clearance %.4f mm,  interference %.6f mm3"
        % (g1.Shape.distToShape(g2.Shape)[0], common_volume(g1.Shape, g2.Shape)),
        "mesh stage 2      clearance %.4f mm,  interference %.6f mm3"
        % (g3.Shape.distToShape(g4.Shape)[0], common_volume(g3.Shape, g4.Shape)),
    ])

    print("\n-- shaft keyways: boolean cut vs exact analytic volume --")
    for name, x0, x1, d, b, h, t1, got, exp in keyway_rows:
        flag = "OK" if abs(got - exp) < 1.0 else "MISMATCH"
        print("  %-13s D%-3.0f x[%7.1f,%7.1f]  %2.0fx%-2.0f  t1=%.1f  "
              "%9.1f / %9.1f mm3  %s"
              % (name, d, x0, x1, b, h, t1, got, exp, flag))

    print("\n-- parts --")
    total = 0.0
    for o in sorted(doc.Objects, key=lambda x: x.Name):
        total += o.Shape.Volume
        print("  %-14s %-38s %9.1f cm3  valid=%s"
              % (o.Name, o.Label, o.Shape.Volume / 1000.0, o.Shape.isValid()))
    print("  %-14s %-38s %9.1f cm3  (~%.1f kg as cast iron)"
          % ("", "TOTAL", total / 1000.0, total / 1000.0 * 7.2 / 1000.0))


if __name__ == "__main__":
    main()
