# Verification

`src/verify.py` re-opens a saved `.FCStd` and re-derives what it can from the
geometry itself, so the audit does not simply repeat the builder's assumptions.
Run it with:

```bash
freecadcmd -P src -c "import verify; verify.main('single')"   # single-stage
freecadcmd -P src -c "import verify; verify.main('two')"      # two-stage
```

It exits non-zero if any check fails. Both models pass with **zero failures**.

## What is checked, and why each check earns its place

| # | check | why it is not redundant |
|---|---|---|
| 1 | every solid is a valid BRep; every bearing passes `check_bearing` | a boolean can return a shape that `isValid()` rejects, and ball-count coincidences make this real (see [API traps §7](../../../docs/practices/02-freecad-api-traps.md#7-a-bearing-can-silently-fuse-into-an-invalid-solid)) |
| 2 | gear tip radius, tooth count and face width match module and z | measuring the tip radius about the gear's **own axis** cross-checks `m·z` without counting teeth by eye; the tooth count is then counted independently by clustering the tip-circle vertices |
| 3 | each gear hub keyway is an actual void at the angle the mating shaft keyway uses | this is the check that catches the silent local-frame/world-frame mistake described in [API traps §1](../../../docs/practices/02-freecad-api-traps.md#1-partfeatureshape-already-has-the-placement-applied) |
| 4 | shaft, bearing-bore and housing-bore axes are coaxial; centre distances exact | measured from cylindrical faces, not bounding boxes (bounding boxes are ~0.1 mm off after booleans) |
| 5 | no two parts share volume | the decisive test: `distToShape == 0` cannot distinguish "touching" from "overlapping" |
| 6 | each meshing pair touches **and** does not overlap | proves the phase alignment is right, not merely close |

## Design values asserted

| | single-stage | two-stage |
|---|---|---|
| centre distance | 160.000000 mm | 150.000000 / 160.000000 mm |
| gear tip radii | 44.004 / 124.001 mm | 33.003 / 123.000 / 44.004 / 124.001 mm |
| tooth counts | 20 / 60 | 20 / 80 / 20 / 60 |
| interference pairs | 91, all zero | 210, all zero |

Tolerance on every position check is 10⁻⁴ mm. Booleans are exact well below
that; the slack exists only so that a future kernel change does not produce
spurious failures.

## Output — single-stage

```
VERIFY models/reducer_single_stage.FCStd
objects: 14
-- 1. solid validity --          all PASS (bearings also pass integrity)
-- 2. gear geometry --
  [PASS] Gear_Pinion tip radius 44.004 (expect 44.000)   m=4.0
  [PASS] Gear_Pinion tooth count 20 (expect 20)
  [PASS] Gear_Pinion face width 50.00 (expect 50.0)
  [PASS] Gear_Wheel  tip radius 124.001 (expect 124.000) m=4.0
  [PASS] Gear_Wheel  tooth count 60 (expect 60)
  [PASS] Gear_Wheel  face width 45.00 (expect 45.0)
-- 3. gear hub keyways --
  [PASS] Gear_Pinion hub keyway present at (19.650, -0.000)
  [PASS] Gear_Wheel  hub keyway present at (-29.609, 1.552)
-- 4. axis alignment and centre distances --
  [PASS] Shaft_Input / Shaft_Output axes along X
  [PASS] centre distance Shaft_Input-Shaft_Output = 160.000000 (design 160.000)
  [PASS] 4 bearings coaxial with their shafts (offset 0.000000 mm)
  [PASS] housing bores coaxial with Shaft_Input / Shaft_Output
-- 5. pairwise interference --
  [PASS] no part pair intersects (91 pairs)
  [PASS] mesh Gear_Pinion-Gear_Wheel touches without overlap
ALL CHECKS PASSED
```

## Output — two-stage

```
VERIFY models/reducer_two_stage.FCStd
objects: 21
-- 1. solid validity --          all PASS (6 bearings also pass integrity)
-- 2. gear geometry --
  G1_Pinion_HS  r_tip  33.003 (33.000)  teeth 20 (20)  width 55.00
  G2_Wheel_HS   r_tip 123.000 (123.000) teeth 80 (80)  width 50.00
  G3_Pinion_LS  r_tip  44.004 (44.000)  teeth 20 (20)  width 65.00
  G4_Wheel_LS   r_tip 124.001 (124.000) teeth 60 (60)  width 60.00
-- 3. gear hub keyways --
  all four PASS at the direction their mating shaft keyway uses
-- 4. axis alignment and centre distances --
  [PASS] centre distance Shaft_HS-Shaft_MID  = 150.000000 (design 150.000)
  [PASS] centre distance Shaft_MID-Shaft_LS  = 160.000000 (design 160.000)
  [PASS] 6 bearings coaxial with their shafts (offset 0.000000 mm)
  [PASS] housing bores coaxial with Shaft_HS / Shaft_MID / Shaft_LS
-- 5. pairwise interference --
  [PASS] no part pair intersects (210 pairs)
  [PASS] mesh G1_Pinion_HS-G2_Wheel_HS touches without overlap
  [PASS] mesh G3_Pinion_LS-G4_Wheel_LS touches without overlap
ALL CHECKS PASSED
```

## Independent cross-checks

Two of the numbers are also verified by a completely different route, so a
systematic error in the builder would have to fool both:

* **Cut volumes.** Every keyway's boolean result is compared against the closed
  form for a rectangular slot in a cylinder
  ([verification §3](../../../docs/practices/03-verification-methodology.md#3-cross-check-every-cut-against-a-closed-form-volume)).
  All twelve keyways across the two models agree to better than 0.1 %.
* **Housing clearances.** Oil-sump floor to lowest tooth = 6.0 mm,
  gear tip to cavity wall = 12.0 mm, both stated and re-measured.

## A note on the earlier builds

The first generation of these models — built on the CAD machine over MCP — had
**defective gear hub keyways**: cut in the local frame against an already-placed
shape, they removed no material from the bore and instead cut two spurious slots
into the rim near one face ([API traps §1](../../../docs/practices/02-freecad-api-traps.md#1-partfeatureshape-already-has-the-placement-applied)).
The models committed here are rebuilt with the fix and fully audited; the
`Reducer.FCStd` / `Reducer_2stage.FCStd` files in `models/` are the originals for
comparison.

This is exactly why the build script and the audit script are separate programs.
The builder's own report said the keyways were fine.
