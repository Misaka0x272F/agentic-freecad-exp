# Design 1 — single-stage cylindrical gear reducer

`src/build_single_stage.py`

## Specification

| | |
|---|---|
| module | m = 4 mm |
| pressure angle | α = 20° |
| teeth | z₁ = 20 (pinion) / z₂ = 60 (wheel) |
| ratio | i = 3.000 |
| pitch diameters | d₁ = 80 mm, d₂ = 240 mm |
| tip / root diameters | 88 / 70 mm and 248 / 230 mm |
| centre distance | a = 160 mm |
| face widths | 50 mm (pinion), 45 mm (wheel) |
| bearings | 6206 (30×62×16) ×2, 6209 (45×85×19) ×2 |

Shaft axes lie in the plane `z = 0`, 160 mm apart along Y. Stage layout is
deliberately the simplest possible: one gear pair, no axial offset.

```
        y
        ▲
  160 ──┼──────────────●  shaft II (output, extends right)
        │             ╱ ╲
        │            │   │  wheel z=60
        │             ╲ ╱
        │              │
        │              ●   mesh, a = 160
        │             ╱ ╲
    0 ──┼────────────●   │  pinion z=20
        │             ╲ ╱
        └──────────────▶ x
                        shaft I (input, extends left)
```

## Shafts

Both shafts are stepped, with the shoulder between the gear seat and the bearing
seat acting as the axial locating feature for both the gear hub and the bearing
inner ring.

| shaft | segments (Ø × x-range) | length | extension |
|---|---|---|---|
| I (input) | Ø25 `[-120,-78]`, Ø30 `[-78,-40]`, Ø36 `[-40,40]`, Ø30 `[40,55]` | 175 | left |
| II (output) | Ø45 `[-55,-37]`, Ø55 `[-37,37]`, Ø45 `[37,56]`, Ø40 `[56,115]` | 170 | right |

The input shaft carries the pinion on its Ø36 seat; the output shaft carries the
wheel on its Ø55 seat. The extension ends are Ø25 and Ø40, ready for a coupling.

## Keyways

Four keyways, GB/T 1096 flat keys, chosen from the shaft diameter by
`key_for()`:

| location | shaft Ø | key b×h | groove t₁ | length | cut volume vs analytic |
|---|---|---|---|---|---|
| input, gear seat | Ø36 | 10×8 | 5.0 | 50 mm | 2382.9 / 2382.9 mm³ |
| input, coupling | Ø25 | 8×7 | 4.0 | 36 mm | 1089.6 / 1089.6 mm³ |
| output, gear seat | Ø55 | 16×10 | 6.0 | 45 mm | 4037.1 / 4037.1 mm³ |
| output, coupling | Ø40 | 12×8 | 5.0 | 37 mm | 2084.9 / 2084.9 mm³ |

Both coupling keyways are **open at the shaft end** so a coupling hub can slide
on. All keyways on one shaft share an angular direction, as they would if milled
in a single setup; that direction is inherited from the gear's mesh phase.

Matching hub grooves (`t₂`) are cut into the gear bores in the gears' own local
frames — see `make_gear_solid(..., key=...)`.

## Bearings and end caps

Bearings sit flush with the inner end of the housing bore, so the outer face of
each bearing lands exactly on the plane the cap spigot reaches. That is what
makes the cap clamp the bearing outer ring.

| | input | output |
|---|---|---|
| bearing | 6206, 30×62×16 | 6209, 45×85×19 |
| bore in housing | Ø62 | Ø85 |
| cap bolt circle D₀ | 82 | 105 |
| cap flange D₂ | 102 | 125 |

Cap sizes follow the standard flanged pattern with M8 screws:

```
D0 = D + 2.5·d3 = D + 20      bolt circle
D2 = D0 + 2.5·d3 = D + 40     flange outside diameter
e  = 1.2·d3 = 9.6 → 10 mm     flange thickness
e1 = 0.8·e = 8 mm             spigot length
```

Two through caps (input-left, output-right — where the shafts leave the housing),
two blind caps.

## Housing

Split along the plane through both shaft axes (`z = 0`) into `Housing_Base`
(z < 0) and `Housing_Cover` (z > 0).

| dimension | value |
|---|---|
| cavity lobes | (y=0, r=56), (y=160, r=136) — gear tip radius + 12 mm |
| wall thickness | 8 mm |
| cavity axial half-length | 37 mm |
| end wall / boss face | ±47 / ±64 mm |
| oil-sump floor | z = −130 mm (6.1 mm below the wheel's lowest tooth) |
| casting bottom | z = −140 mm |
| split flange | 12 mm per half, 24 mm radial overhang |
| bore length | 27 mm (bearing + 8 mm spigot) |

The lower half is a rectangular box rather than a continuing circle: real bases
are boxy, and it gives a genuinely flat bottom. The cover is the two-lobe dome.
The split flange is a rim around the outline plus an "ear" around each bearing
boss, so the bearing-adjacent bolts have material to sit in.

Bolting: 4 × M8 per end cap, 12 split-flange bolts, 4 foundation bolts.

## Result

14 parts, 7744.2 cm³ of material (≈ 56 kg as cast iron), all solids valid, every
pairwise intersection volume zero, centre distance exactly 160.000000 mm, and
both meshes touching without overlap.

See [verification](05-verification.md) for the full audit output.
