# agentic-freecad-exp

Hands-on practice at **building real CAD with an agent driving FreeCAD** — and a
place to write down what that actually takes.

Not a reducer repository. Reducers happen to be the first project in it, because
they are unforgiving: a gear reducer has lots of parts, exact geometric
relationships, and mistakes that look fine in a render. That makes them a good
proving ground for the workflow.

The repository has two layers:

```
docs/practices/     knowledge that transfers to any agentic FreeCAD work
projects/           concrete builds, each self-contained and reproducible
```

---

## Practice notes

Design-agnostic, written from mistakes that got through. Read these before
building anything with an agent and FreeCAD.

| | |
|---|---|
| [Driving FreeCAD on another machine over MCP](docs/practices/01-remote-mcp-workflow.md) | architecture, setup, the IP-allowlist trap, where headless execution really runs, and why the remote environment must be re-probed every session |
| [FreeCAD API traps](docs/practices/02-freecad-api-traps.md) | 14 behaviours that fail **silently** — `Part::Feature.Shape` already carrying its placement, `Placement` rotating about the origin, booleans that return invalid solids, `distToShape` that cannot prove non-overlap, and the rest |
| [Verification methodology](docs/practices/03-verification-methodology.md) | how to prove generated geometry is correct rather than merely plausible: intersection volume, bounding-box pre-filtering, closed-form cross-checks, negative controls, orphan detection |
| [CAD assembly practice](docs/practices/04-cad-assembly-practice.md) | boolean ordering for castings, flange overhang and relief, bolt-head clearances, coplanar-face slivers, assembly-path constraints |

The short version, if you read nothing else:

1. **`Part::Feature.Shape` already has the Placement applied**, and assigning
   `.Shape` then `.Placement` bakes the rotation in and resets the Placement to
   identity. A local-frame feature cut through `obj.Shape` lands in the wrong
   place — silently, with `isValid()` still `True`.
2. **`distToShape == 0` cannot prove non-overlap.** Use intersection volume.
3. **Bounding boxes of boolean results are ~0.1 mm off** — enough to make an exact
   160.000 mm centre distance measure as 159.888 mm.
4. **`App.Placement` translates after rotating, about the origin.** To rotate about
   an arbitrary axis, `t = axis − R·axis`.
5. **Assert that features exist, and prove your checks can fail.** A verification
   step that has never failed is an untested verification step.

## Projects

| project | what it is | status |
|---|---|---|
| [reducers](projects/reducers/) | three cylindrical gear reducers (i = 3, 12, 8), script-generated, with an independent audit | two models committed and verified; the third is documented |

Each project is self-contained: its own `src/`, `models/`, `images/` and `docs/`.
Nothing in `projects/` is needed to understand `docs/practices/`, and vice versa.

<p align="center">
  <img src="projects/reducers/images/01-gear-train-v1-iso.png" width="49%" alt="three-stage gear train">
  <img src="projects/reducers/images/14-housing-transparent.png" width="49%" alt="assembly with translucent housing">
</p>

```bash
git clone https://github.com/Misaka0x272F/agentic-freecad-exp
cd agentic-freecad-exp/projects/reducers

freecadcmd -P src -c "import build_two_stage as m; m.main()"   # build
freecadcmd -P src -c "import verify; verify.main('two')"       # audit
```

## Adding a project

`projects/reducers/` is the template. The conventions that make it work:

* **models are script-generated**, never hand-modelled — the script is the source
  of truth and the `.FCStd` is a build artifact;
* a project carries its own **design-conventions block** at the top of its shared
  library (`projects/reducers/src/common.py`); other sessions read that before
  contributing, rather than working from memory of a previous round;
* **build and verify are separate programs**, and the verifier re-opens the saved
  file rather than trusting the builder;
* anything learned that is *not* specific to the project goes into
  `docs/practices/`, not into the project's docs.

## Requirements

* FreeCAD with Python (`freecadcmd` on `PATH`) — developed against 1.0.0 and
  1.1.0
* the built-in `PartDesign.fcgear` module, shipped with FreeCAD; the FCGear addon
  is **not** needed
* `xvfb-run` only for offscreen rendering, and a lot of patience: software
  rendering of these models exceeded ten minutes per frame, which is why the
  committed images were captured from a native GUI instead

## Honesty notes

* These are **geometry** exercises. Nothing is stress-analysed; load capacity is
  not asserted anywhere.
* The practice notes describe one project's experience, not universal truths.
  Where two sessions observed *contradictory* behaviour from the same tool, the
  contradiction is recorded rather than resolved — see
  [the environment table](docs/practices/01-remote-mcp-workflow.md#probe-the-remote-environment-every-session--it-is-not-stable).
* `projects/reducers/models/original-build/` holds a first generation with
  defective hub keyways, kept as evidence rather than as reference geometry.

## License

MIT — see [LICENSE](LICENSE).
