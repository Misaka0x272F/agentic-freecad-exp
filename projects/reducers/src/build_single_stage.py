#!/usr/bin/env python3
"""
build_single_stage.py - single-stage cylindrical gear reducer.

    shaft I  (high speed, extends to the left)  : pinion z=20, m=4
    shaft II (low speed,  extends to the right) : wheel  z=60, m=4
    i = 3.000,  a = 160 mm

Run headless (``freecadcmd`` treats a positional filename as a *document* to
open, so the module has to be imported explicitly)::

    freecadcmd -P src -c "import build_single_stage as m; m.main()"

Inside FreeCAD's Python console::

    import sys; sys.path.insert(0, 'src')
    import build_single_stage as m; m.main()

Writes ``models/reducer_single_stage.FCStd``.
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
from housing import build_housing, single_stage_spec  # noqa: E402

DOC_NAME = "Reducer_SingleStage"
MODEL_PATH = os.path.join(os.path.dirname(_HERE),
                         "models", "reducer_single_stage.FCStd")

# --------------------------------------------------------------------------
# design parameters
# --------------------------------------------------------------------------
M = 4.0                  # module
ALPHA = 20.0             # pressure angle
Z_P, Z_W = 20, 60        # teeth
B_P, B_W = 50.0, 45.0    # face widths
BORE_P, BORE_W = 18.0, 27.5      # hub bore radii (D36 / D55)
A_CENTRES = M * (Z_P + Z_W) / 2.0

Y_HS, Y_LS = 0.0, A_CENTRES      # shaft axes, both in the z = 0 plane

BOSS_X = 64.0                    # housing bearing boss face (|x|)
CAP_E1 = 0.8 * 1.2 * 8.0         # end cap spigot length = 8
BRG_FACE = BOSS_X - CAP_E1       # bearing outer face = 56

HS_SEGS = [(-120.0, -78.0, 25.0), (-78.0, -40.0, 30.0),
           (-40.0, 40.0, 36.0), (40.0, 55.0, 30.0)]
LS_SEGS = [(-55.0, -37.0, 45.0), (-37.0, 37.0, 55.0),
           (37.0, 56.0, 45.0), (56.0, 115.0, 40.0)]
SEGS = {"Shaft_Input": HS_SEGS, "Shaft_Output": LS_SEGS}

BRG_HS = dict(name="6206", d=30, D=62, B=16, n=9)
BRG_LS = dict(name="6209", d=45, D=85, B=19, n=9)
BEARINGS = [("Bearing_HS_L", BRG_HS, Y_HS, -1, "6206 (input, left)"),
            ("Bearing_HS_R", BRG_HS, Y_HS, 1, "6206 (input, right)"),
            ("Bearing_LS_L", BRG_LS, Y_LS, -1, "6209 (output, left)"),
            ("Bearing_LS_R", BRG_LS, Y_LS, 1, "6209 (output, right)")]

# through caps need the diameter of the shaft that passes through them
CAPS = [("Cap_HS_L", BRG_HS, Y_HS, -1, True, 30.0, "6206 through (input)"),
        ("Cap_HS_R", BRG_HS, Y_HS, 1, False, 30.0, "6206 blind (input)"),
        ("Cap_LS_L", BRG_LS, Y_LS, -1, False, 45.0, "6209 blind (output)"),
        ("Cap_LS_R", BRG_LS, Y_LS, 1, True, 45.0, "6209 through (output)")]

# (shaft key, x0, x1, shaft radius); x spans overshoot the open end by 1 mm
SHAFT_KEYWAYS = [
    ("Shaft_Input", -25.0, 25.0, BORE_P, key_for(2 * BORE_P)),
    ("Shaft_Input", -121.0, -84.0, 12.5, key_for(25.0)),
    ("Shaft_Output", -22.5, 22.5, BORE_W, key_for(2 * BORE_W)),
    ("Shaft_Output", 78.0, 116.0, 20.0, key_for(40.0)),
]


def main(save=True):
    doc = fresh_document(DOC_NAME)

    psi_p, psi_w = mesh_phases(Z_P, Z_W)
    pl_p = gear_placement(psi_p, (0.0, Y_HS, 0.0))
    pl_w = gear_placement(psi_w, (0.0, Y_LS, 0.0))

    # ---- gears ----
    kp, kw = key_for(2 * BORE_P), key_for(2 * BORE_W)

    def gear(name, label, z, width, bore_r, key, place):
        o = doc.addObject("Part::Feature", name)
        # the hub keyway is cut inside make_gear_solid, in the local frame,
        # before the placement exists - see the docstring for why
        o.Shape = make_gear_solid(M, z, ALPHA, width, bore_r,
                                  key=(key["b"], key["t2"]))
        o.Label = label
        o.Placement = place
        return o

    pinion = gear("Gear_Pinion", "Pinion z=%d" % Z_P, Z_P, B_P, BORE_P, kp, pl_p)
    wheel = gear("Gear_Wheel", "Gear z=%d" % Z_W, Z_W, B_W, BORE_W, kw, pl_w)

    # ---- shafts ----
    for name, label, segs in (("Shaft_Input", "Input shaft (HS)", HS_SEGS),
                              ("Shaft_Output", "Output shaft (LS)", LS_SEGS)):
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_shaft(segs, Y_HS if name == "Shaft_Input" else Y_LS)
        o.Label = label

    # ---- shaft keyways, groove direction follows the mating gear ----
    dir_for = {"Shaft_Input": pl_p.Rotation.multVec(App.Vector(1, 0, 0)),
               "Shaft_Output": pl_w.Rotation.multVec(App.Vector(1, 0, 0))}
    keyway_rows = []
    for name, x0, x1, r, k in SHAFT_KEYWAYS:
        obj = doc.getObject(name)
        y = Y_HS if name == "Shaft_Input" else Y_LS
        before = obj.Shape.Volume
        obj.Shape = cut_shaft_keyway(obj.Shape, x0, x1, r, k["b"], k["t1"],
                                     dir_for[name], y)
        # analytic check on the part of the cutter that is really inside the shaft
        s_lo = min(seg[0] for seg in SEGS[name])
        s_hi = max(seg[1] for seg in SEGS[name])
        eff = min(x1, s_hi) - max(x0, s_lo)
        keyway_rows.append((name, x0, x1, 2 * r, k["b"], k["h"], k["t1"],
                            before - obj.Shape.Volume,
                            keyway_volume_analytic(r, k["b"], k["t1"], eff)))

    # ---- bearings ----
    for name, spec, y, s, label in BEARINGS:
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_bearing(spec["d"], spec["D"], spec["B"], spec["n"],
                               s * BRG_FACE, y, s)
        o.Label = "Bearing " + label

    # ---- end caps ----
    for name, spec, y, s, through, shaft_d, label in CAPS:
        o = doc.addObject("Part::Feature", name)
        o.Shape = make_end_cap(spec["D"], s, shaft_d, y, BOSS_X, through)
        o.Label = "End cap " + label

    # ---- housing ----
    build_housing(doc, single_stage_spec())

    doc.recompute()
    _audit(doc, pinion, wheel, keyway_rows)
    if save:
        save_document(doc, MODEL_PATH)
        print("\nsaved: %s" % MODEL_PATH)
    return doc


def _audit(doc, pinion, wheel, keyway_rows):
    hs, ls = doc.getObject("Shaft_Input"), doc.getObject("Shaft_Output")
    ax_hs = cylindrical_axis(hs.Shape, BORE_P)[0].y
    ax_ls = cylindrical_axis(ls.Shape, BORE_W)[0].y

    report("SINGLE-STAGE REDUCER", [
        "gear ratio       i = z2/z1 = %d/%d = %.3f" % (Z_W, Z_P, Z_W / Z_P),
        "module           m = %.1f mm,  pressure angle %.0f deg" % (M, ALPHA),
        "pitch diameters  d1 = %.1f,  d2 = %.1f mm" % (M * Z_P, M * Z_W),
        "centre distance  a = %.3f mm (design %.3f, measured %.6f)"
        % (M * (Z_P + Z_W) / 2.0, A_CENTRES, abs(ax_ls - ax_hs)),
        "mesh             clearance %.4f mm, interference %.6f mm3"
        % (pinion.Shape.distToShape(wheel.Shape)[0],
           common_volume(pinion.Shape, wheel.Shape)),
    ])

    print("\n-- shaft keyways: boolean cut vs exact analytic volume --")
    for name, x0, x1, d, b, h, t1, got, exp in keyway_rows:
        flag = "OK" if abs(got - exp) < 1.0 else "MISMATCH"
        print("  %-13s D%-3.0f x[%7.1f,%7.1f]  %2.0fx%-2.0f  t1=%.1f  "
              "%9.1f / %9.1f mm3  %s" % (name, d, x0, x1, b, h, t1, got, exp, flag))

    print("\n-- parts --")
    total = 0.0
    for o in sorted(doc.Objects, key=lambda x: x.Name):
        total += o.Shape.Volume
        print("  %-14s %-34s %9.1f cm3  valid=%s"
              % (o.Name, o.Label, o.Shape.Volume / 1000.0, o.Shape.isValid()))
    print("  %-14s %-34s %9.1f cm3  (~%.1f kg as cast iron)"
          % ("", "TOTAL", total / 1000.0, total / 1000.0 * 7.2 / 1000.0))


if __name__ == "__main__":
    main()
