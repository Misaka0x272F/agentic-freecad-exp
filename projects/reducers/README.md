# Reducers

Three cylindrical gear reducers, built entirely by script and audited
part-by-part. This is the first project in the repository and the source of most
of the lessons now collected under [`docs/practices/`](../../docs/practices/).

| design | ratio | shafts | parts | material | model |
|---|---|---|---|---|---|
| [single-stage](docs/01-single-stage.md) | 3.000 | 2 | 14 | 7.74 L | `models/reducer_single_stage.FCStd` |
| [two-stage, expanded](docs/02-two-stage.md) | 12.000 | 3 | 21 | 16.34 L | `models/reducer_two_stage.FCStd` |
| [three-stage, expanded](docs/03-three-stage.md) | 8.000 | 4 | 41 | ≈ 22.6 L | *(not committed — see below)* |

Each design is a complete transmission plus its enclosure: involute gears with
genuine tooth profiles and root fillets, stepped shafts with GB/T 1096 keyways,
deep-groove ball bearings with balls, flanged end caps (through and blind), and a
split cast housing with bearing bosses, flanges, ribs and bolt holes.

| | single-stage | two-stage | three-stage |
|---|---|---|---|
| module | m = 4 | m₁ = 3, m₂ = 4 | m = 3 |
| teeth | 20 / 60 | 20 / 80 and 20 / 60 | 20 / 80, 38 / 76, 56 / 56 |
| centre distances | 160 | 150 and 160 | 150, 171, 168 |
| bearings | 6206 ×2, 6209 ×2 | 6206 ×2, 6209 ×2, 6214 ×2 | 6207 / 6208 / 6209 / 6211 |
| end caps | 2 through + 2 blind | 2 through + 4 blind | 2 through + 6 blind |

The two-stage and three-stage designs are **expanded** (展开式) layouts: the
intermediate shafts carry the wheel of one stage and the pinion of the next, so
the meshes sit at different axial stations. See
[docs/02](docs/02-two-stage.md) for why that shapes everything.

## Layout

```
src/
  common.py              reusable geometry + this project's design conventions
                         (read the docstring at the top first)
  housing.py             parameterised split-cast housing builder
  build_single_stage.py  design 1
  build_two_stage.py     design 2
  verify.py              independent audit; exits non-zero on failure
  render.py              offscreen PNG rendering (GUI-only; slow under Xvfb)
render.sh                wrapper that runs render.py
models/                  the two verified models, plus original-build/ holding the
                         first generation, whose hub keyways are defective
images/                  process renders: gear train, housing iterations,
                         bearings and end caps, assembly
docs/                    per-design records, the audit write-up, design notes
```

## Running it

```bash
cd projects/reducers

freecadcmd -P src -c "import build_single_stage as m; m.main()"
freecadcmd -P src -c "import build_two_stage as m; m.main()"

freecadcmd -P src -c "import verify; verify.main('single')"   # exits non-zero on failure
freecadcmd -P src -c "import verify; verify.main('two')"
```

`freecadcmd` treats a positional filename as a document to open, so the modules
have to be imported — see
[API traps §13](../../docs/practices/02-freecad-api-traps.md#13-freecadcmd-scriptpy-does-not-run-the-script).

## Verification results

Every committed model is audited by a **separate** program that re-opens the saved
file and re-derives geometry from scratch — it does not trust the builder.

| check | single-stage | two-stage |
|---|---|---|
| solids valid | 14 / 14 | 21 / 21 |
| centre distance, measured from cylindrical faces | 160.000000 mm | 150.000000 / 160.000000 mm |
| pairs with non-zero intersection volume | **0** of 91 | **0** of 210 |
| gear meshes touching without overlap | ✓ | ✓ both stages |
| keyway cut volume vs closed-form solution | 4 / 4 exact | 6 / 6 exact |
| tooth counts recovered by clustering tip vertices | 20 / 60 ✓ | 20 / 80 / 20 / 60 ✓ |

Three-stage build, as recorded by its session: 41 parts all valid, 820 pairs
pre-filtered to 201 candidates, **all zero**; connectivity analysis returns a
single component (no orphan parts); ratio 4.000 × 2.000 × 1.000 = 8.000.

Full output: [docs/04-verification.md](docs/04-verification.md).

## Design conventions

Full text at the top of `src/common.py`:

* millimetres and degrees;
* **shaft axes along +X, all axes in the plane z = 0** — the housing is split
  along that plane into `Housing_Base` (z < 0) and `Housing_Cover` (z > 0);
* gears are built in a local frame (**axis +Z, tooth centre on local +X**) and
  placed by `gear_placement()`;
* flat keys per GB/T 1096, selected by `key_for(shaft_diameter)`.

Anything built for this project must follow them. In particular, a model built
with a different convention cannot simply be dropped in — see
[assembly practice §9](../../docs/practices/04-cad-assembly-practice.md#9-coordinate-system-drift-between-sessions-is-a-real-risk).

## Why the three-stage model is not committed

Its 41 parts live only on the CAD host, and committing the binary would
contradict the point of the repository, which is that **models are produced by
scripts**. [docs/03-three-stage.md](docs/03-three-stage.md) records the design,
the process, the verification, and the fact that it was built in a *different*
coordinate convention (shafts along +Z, split at X = 0) — so it needs rotating
into this project's frame before it can be merged, not copying. That document is
in Chinese; the rest of this project's docs are in English.

## Honesty notes

* This is a **geometry** exercise. Nothing is stress-analysed: modules, tooth
  counts and widths were chosen for sensible proportions, not from a strength
  calculation. Load capacity is not asserted.
* Fasteners are modelled as **holes** in designs 1 and 2; the three-stage build
  modelled them as solids and hit the interference problems recorded in
  [assembly practice](../../docs/practices/04-cad-assembly-practice.md) as a
  result.
* Bearings are simplified: rings and balls, no cage, no fillets, catalogue sizes.
* `models/original-build/` holds the first-generation files, which have defective
  hub keyways and spurious rim slots — they are kept as evidence, not as
  reference geometry. The committed models are rebuilt with the fix and fully
  audited.
