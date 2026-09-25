# Design notes

Notes specific to cylindrical gear reducers, as opposed to the general FreeCAD
practice collected under [`docs/practices/`](../../../docs/practices/).

---

## 1. Integral gear shaft (齿轮轴) criterion

A pinion is made integral with its shaft when its root circle is close to the
shaft diameter; the usual rule of thumb is `d_f / d_shaft < 1.5`.

| gear | d_f | shaft | ratio | verdict |
|---|---|---|---|---|
| stage-1 pinion (m=3, z=20) | 52.5 | Ø36 | 1.46 | marginal — integral is reasonable |
| stage-2 pinion (m=4, z=20) | 70 | Ø50 | 1.40 | marginal — integral is reasonable |
| stage-1 wheel (z=80) | 232.5 | Ø50 | 4.65 | separate gear |
| stage-2 wheel (z=60) | 230 | Ø80 | 2.88 | separate gear |

A 240 mm wheel on an output shaft is emphatically **not** a gear-shaft candidate:
an integral Ø230 blank on a Ø80 shaft wastes material, cannot be replaced when
worn, and gains nothing.

## 2. Expanded (展开式) layout

The intermediate shaft carries both the wheel of one stage and the pinion of the
next, so the two meshes must sit at **different axial stations**. Both gears of a
mesh share an axial band; the bands are offset. The shaft axes are collinear in
plan view.

Consequences that shape the whole design:

* gear bands must not overlap axially;
* the housing cavity becomes correspondingly long;
* an intermediate shaft carrying two gears has **two keyways pointing in
  different directions**, since each follows its own gear's mesh phase.

## 3. Meshing phase for a pair whose line of centres is along +Y

With the gear axis laid along +X and the gear spun by `ψ` about that axis, a
feature at local angle `θ` points at world direction `(0, sin(θ+ψ), −cos(θ+ψ))`.
For a standard (zero-backlash) mesh:

* pinion: tooth towards the wheel → `ψ_p = 90° − 0°`
* wheel: space towards the pinion → `ψ_w = 270° − 180°/z_w`

The wheel's `180°/z_w` term is the half-tooth-pitch offset between a tooth centre
and a space centre in the generator's convention. Measured result: the pair then
touches at exactly one point (`distToShape == 0.0000 mm`) with **zero**
intersection volume.

### Establishing the generator's convention

`PartDesign.fcgear` centres a **tooth on the local +X axis**, with a space at half
pitch. That was measured, not assumed, and the first measurement was wrong:

the tip of an involute tooth as generated here is effectively a **point** — the
plateau where `r == r_tip` is 0.048° wide, while the root plateau is 2.57° wide.
Scanning for "the angle that maximises the radius" therefore returns whichever
edge of the plateau the scan reaches first, and the phase came out ~1.8° off.

Two reliable methods:

* evaluate the radius at candidate angles directly
  (`r(0°) = 44.002`, `r(9°) = 35.000`, …);
* find the flank crossings of the pitch circle, where `r == m·z/2`.

Both gave the same answer.

## 4. Clearances

* cavity wall radius = gear tip radius + 10…15 mm (12 used here);
* the **oil-sump floor must clear the lowest tooth of the whole train** — see
  [assembly practice §8](../../../docs/practices/04-cad-assembly-practice.md);
* a bottom wall of ≥ 8–10 mm below the sump floor;
* the expanded layout's axial length is driven by the sum of the two gear bands
  plus the gap between them.

## 5. Layout choices made in these designs

* shafts axes all in the plane `z = 0`, so the housing splits along that plane;
* each shaft extends from **one** end only, which is what makes the through/blind
  cap split meaningful (an enclosed intermediate shaft gets two blind caps);
* gear hubs are keyed, not shrunk or splined, so every gear seat has a keyway and
  every hub has a matching groove at the same angular position.
