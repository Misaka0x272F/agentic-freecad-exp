# Design 2 — expanded two-stage cylindrical gear reducer

`src/build_two_stage.py`

## Specification

| | stage 1 (high speed) | stage 2 (low speed) |
|---|---|---|
| module | m₁ = 3 mm | m₂ = 4 mm |
| teeth | z₁ = 20 / z₂ = 80 | z₃ = 20 / z₄ = 60 |
| ratio | i₁ = 4.000 | i₂ = 3.000 |
| pitch diameters | 60 / 240 mm | 80 / 240 mm |
| tip diameters | 66 / 246 mm | 88 / 248 mm |
| centre distance | a₁ = 150 mm | a₂ = 160 mm |
| face widths | 55 / 50 mm | 65 / 60 mm |

**Total ratio i = i₁ · i₂ = 12.000.**

| shaft | y | role | extension |
|---|---|---|---|
| I | 0 | high speed | extends left |
| II | 150 | intermediate | fully enclosed |
| III | 310 | low speed | extends right |

| | shaft I | shaft II | shaft III |
|---|---|---|---|
| gear carried | stage-1 pinion | stage-1 wheel **and** stage-2 pinion | stage-2 wheel |
| gear bore | Ø36 | Ø50 / Ø50 | Ø80 |
| bearing | 6206 (30×62×16) | 6209 (45×85×19) | 6214 (70×125×24) |
| housing bore | Ø62 | Ø85 | Ø125 |
| cap bolt circle / flange | 82 / 102 | 105 / 125 | 145 / 165 |

## Why the two meshes sit at different axial stations

This is the defining feature of the **expanded (展开式)** layout: the intermediate
shaft carries the stage-1 wheel *and* the stage-2 pinion. Both gears are on the
same axis, so the two meshes cannot share an axial band.

```
                    stage 2 mesh (x = +45)          stage 1 mesh (x = -45)
                                                       
  y=310  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  G4 wheel z=60 (green)
                                        ╲
                                         ╲  a2 = 160
                                        ╱
  y=150  ●━━━━● G3 pinion z=20 (red)   ●━━━━● G2 wheel z=80 (yellow)
                ╲                     ╱
                 ╲  a1 = 150         ╱
                ╱                   
  y=0    ●━━━━● G1 pinion z=20 (orange)
         └──────────────────────────────▶ x
        x = -45                x = +45
```

Consequences that shaped the geometry:

* the gear bands must not overlap axially — stage-1 gears occupy
  `x ∈ [-72.5, -17.5]`, stage-2 gears `x ∈ [12.5, 77.5]`;
* the housing cavity is correspondingly long: `x ∈ [−82, +82]`;
* the intermediate shaft carries two gears with **different** mesh phases, so its
  two keyways point in different directions.

Gear 2 (z₂ = 80) and gear 3 (z₃ = 20) are radially nested — the big wheel and the
small pinion are concentric on shaft II — which is only possible because they are
axially separated.

## Axial layout

| | value |
|---|---|
| cavity half-length | 82 mm |
| end wall / boss face | ±92 / ±114 mm |
| bearing outer face | ±106 mm (boss face − 8 mm spigot) |
| cap flange | ±[114, 124] mm |

Shaft diameter steps are placed **outside** the cap spans `|x| ∈ [106, 124]`, so
that a through cap's central bore — sized on the smaller diameter — cannot
collide with a larger section. This is a direct consequence of a bug found and
fixed during the build; see
[design notes §4](05-design-notes.md#4-clearances).

## Shafts

| shaft | segments (Ø × x-range) | length |
|---|---|---|
| I | Ø25 `[-165,-126]`, Ø30 `[-126,-85]`, Ø36 `[-85,-5]`, Ø30 `[-5,105]` | 270 |
| II | Ø45 `[-105,-72]`, Ø50 `[-72,-18]`, Ø45 `[-18,10.5]`, Ø50 `[10.5,79.5]`, Ø45 `[79.5,105]` | 210 |
| III | Ø70 `[-105,9]`, Ø80 `[9,81]`, Ø70 `[81,126]`, Ø65 `[126,165]` | 270 |

The intermediate shaft has **no** extension: both of its ends are enclosed, so it
gets two blind caps. The Ø45 spacer between its two Ø50 gear seats provides the
shoulders that locate the wheel and the pinion.

## Keyways

Six keyways — two per shaft (gear seat + coupling where the shaft extends).

| location | shaft Ø | key b×h | t₁ | length | cut / analytic |
|---|---|---|---|---|---|
| I gear seat | Ø36 | 10×8 | 5.0 | 55 mm | 2621.2 / 2621.2 mm³ |
| I coupling | Ø25 | 8×7 | 4.0 | 36 mm | 1059.3 / 1059.3 mm³ |
| II wheel seat | Ø50 | 14×9 | 5.5 | 50 mm | 3618.6 / 3618.6 mm³ |
| II pinion seat | Ø50 | 14×9 | 5.5 | 65 mm | 4704.1 / 4704.1 mm³ |
| III wheel seat | Ø80 | 22×14 | 9.0 | 60 mm | 11206.7 / 11206.7 mm³ |
| III coupling | Ø65 | 18×11 | 7.0 | 37 mm | 4263.6 / 4263.6 mm³ |

Note that shafts I and III each extend from one end, so the coupling keyway is
open at the free end while the gear-seat keyway is closed — the analytic volume
is computed on the *effective* length, i.e. the part of the cutter that is
actually inside the material.

## Housing

| dimension | value |
|---|---|
| cavity lobes | (y=0, r=45), (y=150, r=135), (y=310, r=136) |
| wall thickness | 8 mm |
| cavity half-length | 82 mm |
| oil-sump floor | z = −130 mm (6.0 mm below the stage-2 wheel's lowest tooth) |
| casting bottom | z = −140 mm |
| split flange | 12 mm per half, 24 mm overhang |
| base plate | 200 × 531 × 19 mm, 4 × M18 foundation bolts |

Bolting: 4 × M8 per end cap (6 caps), split-flange bolts at both Y extremes and
in pairs beside each bearing boss, 4 foundation bolts.

## Result

21 parts, 16336.3 cm³ (≈ 118 kg as cast iron), all solids valid, all 210 pairwise
intersection volumes zero, both centre distances exact to 10⁻⁶ mm, both meshes
touching without overlap.

See [verification](04-verification.md) for the full audit output.
