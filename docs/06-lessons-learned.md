# Lessons learned

Everything below was hit for real while building this repository. Each entry is
written as *symptom → cause → fix → takeaway*, because the symptoms are what you
will actually see.

Sections **A–E** come from the single-stage and two-stage work; section **F**
comes from the three-stage reducer (`docs/04-design-three-stage.md`), which was
built in a separate session and is where the housing-assembly problems surfaced.

Some of these entries are load-bearing for the code: `src/common.py` references
this file from several docstrings, so the facts recorded here are conventions the
builders depend on, not just notes.

Units are millimetres and degrees.

---

## A. Driving FreeCAD on another machine over MCP

### A1. Registering the MCP server

```bash
codebuddy mcp add --scope user freecad -- uvx freecad-mcp --host <freecad-host>
```

The server is a thin stdio MCP bridge; the addon inside FreeCAD exposes an
XML-RPC server on port **9875**. `--host` only selects the *GUI RPC host*.

### A2. "TCP connects, but every XML-RPC call is closed with no response"

**Symptom.** `cat < /dev/null > /dev/tcp/<freecad-host>/9875` succeeds, yet
`uvx freecad-mcp --host <freecad-host>` reports

```
Failed to get RPC status: Remote end closed connection without response
```

and a raw `xmlrpc.client.ServerProxy('http://<freecad-host>:9875')` reproduces it.

**Cause.** The addon's `FilteredXMLRPCServer` accepts the TCP connection and then
rejects the HTTP request when the client IP is not in the **Allowed IPs**
allowlist. The addon defaults that list to `127.0.0.1`, so enabling **Remote
Connections** (which binds `0.0.0.0`) is not enough on its own.

**Fix.** On the FreeCAD machine: *MCP Addon* workbench → *FreeCAD MCP* toolbar →
**Configure Allowed IPs** → add the client's address (a single IP is better than
a subnet) → restart the RPC server.

**Takeaway.** "Port open" means nothing here. If TCP connects but the request is
dropped without a response, suspect an application-level allowlist, and verify
with a plain XML-RPC client rather than the MCP layer.

### A3. `execute_code_headless` does not run on the remote host

**Symptom.** A headless script reports a missing file, or edits nothing visible.

**Cause.** `execute_code_headless` shells out to `freecadcmd` **on the machine
running the MCP server**, and opens documents from *its* filesystem. `--host`
does not redirect it.

**Takeaway.** Only `execute_code` / `execute_code_async` execute on the remote
FreeCAD. Use `reload_document` after a headless script has rewritten a `.FCStd`
that the remote GUI has open.

### A4. GUI-thread budgets

`execute_code` runs on the GUI thread with a 90 s queue and execution budget, and
GUI operations run strictly one at a time. Heavy OpenCascade work should go
through `execute_code_async` (with `commit()` for document writes) or headless.
`get_rpc_status` is answered off the GUI thread, so it still works when a GUI
operation is stuck.

---

## B. FreeCAD API traps

### B1. `Part::Feature.Shape` already has the Placement applied — and this one is silent

**Symptom.** A feature cut in the object's local frame simply is not there. No
exception, no warning; the boolean "succeeds" and removes almost nothing.

**Cause.** Two facts combine badly:

1. Reading `obj.Shape` returns the shape **with `obj.Placement` already
   applied**. Measured: a local `Part.makeBox(10, 20, 30)` with a placement
   rotating Z→X and translating +100 in Y reports
   `Shape.Vertexes[0].Point == (30, 100, 0)` and
   `Shape.BoundBox == X[0,30] Y[100,110] Z[0,20]`.
2. Assigning `.Shape` and then `.Placement` makes FreeCAD **bake the rotation
   into the stored shape and reset the Placement to identity**. After
   `obj.Shape = local; obj.Placement = R`, `obj.Placement.Rotation.Q` is
   `(0, 0, 0, 1)` and the shape reads back already rotated.

So `gear.Shape = cut_hub_keyway(gear.Shape, ...)` cuts a local-frame cutter into
an already-rotated gear. In this project it cut two spurious slots into the rim
near `x ∈ [17.2, 21.3]` and produced **no hub keyway at all** — while the part
still passed `isValid()` and its volume changed only slightly (≈0.1 %).

**Fix.** Do every local-frame feature operation on the solid **before** it is
assigned to a document object:

```python
solid = make_gear_solid(...)                 # local frame
solid = cut_hub_keyway(solid, ...)           # still local frame
obj.Shape = solid                            # assign once
obj.Placement = place
```

`make_gear_solid(..., key=(b, t2))` exists so this ordering cannot be got wrong.

**Takeaway.** Never treat `obj.Shape` as "the thing I assigned". Either operate
on the intermediate solid, or accept that you are working in world coordinates.
And add a *positive* check that the feature exists where you expect it — a
volume delta and `isValid()` are not enough.

### B2. `App.Placement` translates **after** rotating, about the origin

**Symptom.** A keyway cutter rotated onto a shaft's cross-section direction cuts
**0 mm³**. No error.

**Cause.** `p_world = R · p_local + t`, and `R` rotates about the **origin**, not
about the point you had in mind. Passing `t = axis` rotates the cutter all the
way around the world origin and lands it ~2·|axis| away.

**Fix.** To rotate about an axis through `axis`:

```python
t = axis - rot.multVec(axis)
cutter.transformGeometry(App.Placement(t, rot).toMatrix())
```

**Takeaway.** Whenever a rotated cutter "does nothing", check the removal volume
against an analytic value — it is the fastest way to see that the boolean ran in
the wrong place.

### B3. `App.getDocument(name)` raises for an unknown name

```python
if App.getDocument("X"):        # NameError: Unknown document 'X'
```

Test membership instead: `if "X" in App.listDocuments():`. (The upstream
freecad-mcp project hit the same trap and leaked raw XML-RPC faults from it.)

### B4. `Part.Shape` has no `CenterOfMass`

```python
AttributeError: 'Part.Shape' object has no attribute 'CenterOfMass'
```

Use `shape.BoundBox.Center`, or `shape.Solids[0].CenterOfMass`.

### B5. `ViewObject` is `None` under `freecadcmd`

Any line such as `obj.ViewObject.ShapeColor = ...` raises

```
AttributeError: 'NoneType' object has no attribute 'ShapeColor'
```

Keep colours, transparency and screenshots out of the model builders — that is
why `render.py` is a separate script.

### B6. A bearing can silently fuse into an invalid solid

**Symptom.** `shape.isValid()` returns `False` for an otherwise plausible
bearing, while the boolean reported success.

**Cause.** For a 6214 (70×125×24) with the rings sized as 14 % of `(D - d)` and
balls at `0.95 ×` ring thickness, **`n_balls = 10` is invalid** while 9 and 11
are fine, and 10 balls at `0.90` or `0.85` are also fine. The balls overlap both
rings, and with that particular spacing the fused intersection curves go bad.

**Fix.** Use 9 balls (which also matches the real 6214 ball diameter of ≈15 mm),
and assert validity: `check_bearing()` in `common.py`.

**Takeaway.** After any fuse of tangent/overlapping solids, assert
`isValid()`. Do not assume a boolean that returns a shape produced a good one.

### B7. `freecadcmd script.py` does not run the script

A positional argument to `freecad`/`freecadcmd` is a **document to open**, not a
script. Running `freecadcmd src/build_single_stage.py` prints the banner and
exits. Use:

```bash
freecadcmd -P src -c "import build_single_stage as m; m.main()"
```

`-P` puts `src/` on the Python path, so `__file__` is defined and the modules can
import each other.

For scripts that need a GUI, FreeCAD *does* execute a `.FCMacro` argument, which
is what `render.sh` uses.

### B8. Output redirected to a file is lost when a check fails

**Symptom.** `freecadcmd ... > log 2>&1` with an `exit=1` and a log containing
only FreeCAD's own banner — all your `print()` output vanished, yet the same run
looks fine on a terminal.

**Cause.** FreeCAD's embedded interpreter exits through its C++ path, which does
not flush Python's `stdout` buffer. On a TTY, `print` is line-buffered and you
never notice.

**Fix.** `sys.stdout.reconfigure(line_buffering=True)` at the top of the script.

---

## C. Measurement and verification methodology

### C1. `distToShape` cannot prove non-overlap

Two solids that merely touch have minimum distance 0 — and so do two solids that
overlap by a millimetre. A distance of 0 proves *contact*; it never proves
*absence of penetration*.

**Use intersection volume** (`a.common(b).Volume`) for interference, and keep
`distToShape` only for the separate claim "the teeth actually meet".

### C2. Bounding boxes of boolean results are approximate

Measuring the centre distance from bound-box centres gave **159.888 mm** for a
design that is exactly 160.000 mm — a 0.11 mm error caused by discretised
geometry after fuse/cut.

Read the true axis from a cylindrical face instead:

```python
for f in shape.Faces:
    s = f.Surface
    if s.TypeId == "Part::GeomCylinder" and abs(s.Radius - r) < 1e-6:
        return s.Center, s.Axis
```

### C3. A radius alone is often ambiguous

In the two-stage housing, `r = 62.5 mm` is *both* the 6214 bearing bore radius
*and* the 6209 boss outside radius. Selecting "the" face with that radius picked
the wrong shaft and produced a phantom 160 mm misalignment. Pass a positional
hint and pick the nearest candidate.

### C4. Measure gear phase at the pitch circle, not at the tip

The tip of an involute tooth as generated by `PartDesign.fcgear` is effectively a
**point**: the plateau where `r == r_tip` is 0.048° wide, while the root plateau
is 2.57° wide. Scanning for "the angle that maximises the radius" therefore
returns whichever edge of the plateau the scan reaches first, and the resulting
phase is off by ~1.8°.

Two reliable methods:

* evaluate the radius at candidate angles directly
  (`r(0°) = 44.002`, `r(9°) = 35.000` …) — unambiguous, 13 lines of code;
* find the flank crossings of the pitch circle, where `r == m·z/2`.

Both gave the same answer: `PartDesign.fcgear` centres **a tooth on the local +X
axis** (`θ = 0`), with a tooth *space* centred at half pitch (`180°/z`).

### C5. Wrap-around clustering, twice

A cluster that straddles the 0°/360° boundary is counted as two. This produced

* a phantom 21st tooth on a 20-tooth gear, and
* a phantom extra tooth period in the earlier phase measurement.

Merge the wrap gap explicitly:

```python
if (band[0] + 2 * math.pi) - band[-1] <= threshold:
    n -= 1
```

### C6. Cross-check every cut against an exact analytic volume

A rectangular keyway slot of width `b` cut to depth `t1` into a cylinder of
radius `R` has cross-section

```
A = ∫(-b/2 .. b/2) ( sqrt(R² - y²) - (R - t1) ) dy
  = 2·( y/2·sqrt(R²-y²) + R²/2·asin(y/R) ) |₀^(b/2)  −  b·(R − t1)
```

Multiplying by the length gives a figure the boolean must reproduce to well under
0.1 %. Every mismatch found this way had a real cause — and every cause was an
"effective length" subtlety, not a bug in the formula:

* a cutter deliberately overshooting the shaft end is clipped by the material,
  so the effective length is `min(x1, shaft_max) − max(x0, shaft_min)`;
* because the slot's corners are limited by the cylinder, the removed volume is
  slightly *less* than the naive `b · t1 · L` (2382.9 vs 2500 mm³ for one case) —
  which is correct, not an error.

This single habit caught the missing hub keyway (B1), the misplaced coupling
keyway (B2), and confirmed every successful cut.

### C7. Assert the feature exists, and read your own assertion labels

The hub-keyway check printed

```
empty inside hub keyway     ? True  (expect False)
```

which is a **failure** — `isInside` returning `True` means material is present,
i.e. no keyway. It was read as a pass because the line contained "True" and the
surrounding lines contained "PASS". The bug survived a whole design cycle
because of it.

**Takeaway.** Make checks binary and explicit (`check(label, ok)`), so the
verdict is produced by code rather than by reading a raw value next to a
hand-written expectation.

---

## D. Design-domain notes

### D1. Integral gear shaft (齿轮轴) criterion

A pinion is made integral with its shaft when the root circle is close to the
shaft diameter; the usual rule of thumb is `d_f / d_shaft < 1.5`. For the designs
here:

| gear | d_f | shaft | ratio | verdict |
|---|---|---|---|---|
| stage-1 pinion (m=3, z=20) | 52.5 | Ø36 | 1.46 | marginal — integral is reasonable |
| stage-2 pinion (m=4, z=20) | 70 | Ø50 | 1.40 | marginal — integral is reasonable |
| stage-1 wheel (z=80) | 232.5 | Ø50 | 4.65 | separate gear |
| stage-2 wheel (z=60) | 230 | Ø80 | 2.88 | separate gear |

The output shaft's 240 mm wheel is emphatically *not* a gear-shaft candidate: an
integral Ø230 blank on a Ø80 shaft wastes material, cannot be replaced when worn,
and gains nothing.

### D2. Expanded (展开式) two-stage layout

The intermediate shaft carries both the stage-1 wheel and the stage-2 pinion, so
the two meshes must sit at **different axial stations**. Both shafts of a mesh
share the same axial band; the bands are offset (here `x = -45` and `x = +45`).
The three axes are collinear in plan view.

### D3. Meshing phase for a pair whose line of centres is along +Y

With the gear axis laid along +X and the gear spun by `ψ` about that axis, a
feature at local angle `θ` points at world `(0, sin(θ+ψ), −cos(θ+ψ))`. For a
standard (zero-backlash) mesh:

* pinion: tooth towards the wheel → `ψ_p = 90° − 0°`
* wheel: space towards the pinion → `ψ_w = 270° − 180°/z_w`

Measured result: the two gears then touch at exactly one point
(`distToShape == 0.0000 mm`) with **zero** intersection volume.

### D4. Clearances the housing must respect

* cavity wall radius = gear tip radius + 10…15 mm (12 used here);
* **the oil-sump floor must clear the lowest tooth of the whole train** — first
  attempt put it at `z = −120`, which cut 2578 mm³ out of the stage-2 wheel whose
  teeth reach `z = −123.9`;
* the bottom wall below the sump floor should stay ≥ 8…10 mm;
* shaft diameter steps must lie **outside** the axial span occupied by an end
  cap, otherwise a through cap's central bore (sized on the smaller diameter)
  collides with the larger section.

---

## E. Rendering and headless operation

### E1. A headless-saved document has no view data, so it renders blank

**Symptom.** `saveImage()` succeeds and writes a PNG of exactly the requested
size — and the file is a uniform white rectangle. The frame the script believed
it had captured never contained anything.

**Cause.** `freecadcmd` has no view providers. A `.FCStd` written by a headless
build therefore contains no `ViewObject` data, and when the GUI later opens it
the objects can come up with `Visibility` false.

**Fix.** Force visibility before rendering:

```python
for o in doc.Objects:
    vp = getattr(o, "ViewObject", None)
    if vp is not None:
        vp.Visibility = True
```

**Takeaway.** Sanity-check rendered output programmatically — a plausible file
size is not evidence of content. A blank 1600×1000 PNG compresses to ~7.7 kB; a
real one is several times that.

### E2. Software rendering under Xvfb is far too slow for heavy models

With a 21-part reducer whose gears are thousands of Bezier faces, a single
1600×1000 offscreen render did not finish in **10 minutes** under Xvfb software
GL. Producing a handful of views this way is not practical.

The images in `images/` were therefore captured from the **native GUI** on the
CAD machine (via the MCP `get_view` tool, which renders on the machine that owns
the display). Keep the rendering where the hardware is; use the agent side for
geometry and verification.

**Takeaway.** Bulk geometry work belongs wherever the CPU is; bulk *pixel* work
belongs wherever the GPU is. Do not assume the two are the same machine just
because the MCP connection makes them feel like one.

---

## F. Housing assembly, big-model verification, and the remote environment

From the three-stage build (i = 4/2/1, 41 parts, four shafts). This is where a
reducer stops being a gear train and starts being an assembly.

### F1. Coordinate-system drift between sessions is a real risk

**Symptom.** Nothing *errors*, but every placement, phase formula, view
direction and cap/bearing axial definition is subtly wrong.

**Cause.** That session used **shafts along +Z with the housing split at X = 0**,
while this repository's convention (`common.py`, top of file) is **shafts along
+X split at z = 0**. Gear-local conventions happened to match, which makes the
divergence harder to spot.

**Fix / takeaway.** Read the conventions block before building, rather than
working from memory of a previous round. If a model from a different session is
to be merged, it must be rotated into the repository frame — do not mix the two.

### F2. Fuse every boss and flange *before* cutting the cavity

**Symptom.** The housing is solid and *every* transmission part reports
interference — ten parts at once.

**Cause.** The split-plane flange and the base flange are **solid plates**, not
rings. Cutting the cavity first and fusing the flanges afterwards refills the
cavity.

**Fix.** Fuse flanges, bearing bosses and ribs first; cut the cavity last.

**Takeaway.** When a boolean-fresh part suddenly collides with everything, check
the *order* of the boolean operations before suspecting a dimension.

### F3. The split flange must overhang on all four sides — and be relieved at the bearings

Two coupled constraints:

* overhang only in ±Y and the flange bolts on the ±Z sides end up with their
  **nuts buried in the base casting** (26905 mm³ of interference, at both ends);
* overhang in ±Z and the flange **blocks the shaft extensions**.

The resolution is to overhang in all directions and then cut a relief at every
bearing seat: radius = boss radius + 8 mm, axial extent stopping exactly at the
boss face (going deeper cuts into the boss itself).

### F4. Ribs must clear the bolt-head circumscribed circle

A hex head's circumscribed radius is `across-flats / √3 ≈ 0.577·af`. Ribs placed
on centre lines that look clear will still clip a bolt head by tens to hundreds
of mm³.

**Takeaway.** These are the most expensive collisions to find, because the
bounding boxes overlap and the volume is tiny. Check them deliberately.

### F5. Exactly coplanar contact faces produce numerical slivers

**Symptom.** A bolt head or nut face sitting *exactly* on the flange face reports
111 mm³ of interference. Nothing is actually wrong.

**Fix.** Inset the end face by 0.2 mm — invisible, and the sliver disappears.

**Takeaway.** Residual sub-mm³ "interference" between faces you deliberately
placed in contact is a numerics artefact, not a design error. Distinguish it by
asking whether the parts are *meant* to touch.

### F6. A bearing is cleaner as a compound than as a fused solid

Fusing tangent balls to rings can produce a self-intersecting solid that
`isValid()` rejects, with no other visible symptom (see
[B6](#b6-a-bearing-can-silently-fuse-into-an-invalid-solid)). The three-stage
build sidesteps it entirely: `Part.makeCompound([inner, outer, *balls])` needs no
boolean at all and is valid by construction. Worth preferring when you do not
need a single connected solid.

### F7. A threaded shank must be smaller than the tap drill

An M8 bolt modelled at its nominal Ø8 will not enter a Ø6.8 tap drill. Model
fasteners as two diameters: the shank that passes through the cap (Ø8) and the
threaded section that enters the housing (Ø6.6).

### F8. Blind cap: the shaft end must stop at the bearing outer face

Otherwise the shaft runs into the spigot of the blind cap. Every shaft end is
placed from the bearing span: `x_end = wall inner face ± bearing width`.

### F9. Assembly path: diameters must not grow again from the insertion end

A bearing slides on from a shaft end and is located by a shoulder, so going
inwards the diameter must be **monotonically non-increasing** until that
shoulder. The same logic decides which end a gear must be fitted from: one
z = 60 wheel with a Ø60 bore could only go on from one end, because the other end
had a Ø68 shoulder in the way.

**Takeaway.** Geometry that is correct in the assembled state can still be
unbuildable. Check the assembly sequence, not just the final picture.

### F10. Pre-filter large pairwise interference checks with bounding boxes

41 parts = 820 pairs. A full sweep took **more than two minutes** and looked
indistinguishable from a hang. A bounding-box overlap pre-filter reduced it to
201 candidate pairs and finished in seconds with identical conclusions.

```python
def overlap(a, b):                      # a, b are Shape.BoundBox
    return (a.XMin <= b.XMax and b.XMin <= a.XMax and
            a.YMin <= b.YMax and b.YMin <= a.YMax and
            a.ZMin <= b.ZMax and b.ZMin <= a.ZMax)

candidates = [(x, y) for x, y in itertools.combinations(objs, 2)
              if overlap(bbox[x.Name], bbox[y.Name])]
```

Bounding boxes are too imprecise to *measure* with (see
[C2](#c2-bounding-boxes-of-boolean-results-are-approximate)) but perfectly
adequate to *exclude* with.

### F11. Prove your check has discriminating power

Confirming "correct phase → 0 interference" is not enough. Rotate the driven gear
by half a tooth pitch and confirm you get ≈1900 mm³. Without that negative
control you cannot rule out a check that returns 0 for *any* input.

**Takeaway.** A verification step that has never failed is an untested
verification step. Seed each new check with a known-bad case at least once.

### F12. Find orphan parts with connectivity analysis

Build a graph of parts whose bounding boxes overlap, union-find the components,
and anything in a small component is floating. This caught a breather body
sitting **50.3 mm from the nearest part** — an error that reads as "a normal
boss" in a thumbnail.

### F13. `execute_code` environment: two sessions, contradictory observations

The two sessions recorded *different* environments for the same tool, and the
difference matters enough to flag rather than resolve:

| observation | three-stage session | single/two-stage session |
|---|---|---|
| `import Gui` | `ModuleNotFoundError` | not attempted |
| `App.Vector` | `AttributeError` — had to use `FreeCAD.Vector` | used `App.Vector` throughout |
| `obj.ViewObject` | accessible; colours could be set remotely | not attempted |
| namespace across calls | **not** preserved | preserved (the addon documents persistence) |

**Takeaway.** Probe the environment at the start of a session instead of trusting
either this table or the documentation; and when state must survive, do not rely
on the interpreter — write constants to a module file and import it, or attach
results to document objects. That is what the three-stage session did.

### F14. Distinguish "still running" from "hung"

`get_rpc_status` is answered off the GUI thread, so it works while a GUI
operation is in flight:

* `state: busy` with `running_for_seconds` climbing → **it is running**, wait;
  `timeout_seconds = 0` means it will not time out on its own;
* `state: healthy` yet `execute_code` cannot get onto the GUI thread for 90 s →
  something else owns the GUI thread, and the usual culprit is a **modal dialog
  open on the remote FreeCAD**.

### F15. Helper functions must encode the axis

A helper that builds along +Z — `cyl(r, z0, z1)` — called with `.translated()`
will not complain, it will just silently produce a part pointing the wrong way.
In the three-stage build this sent the breather body 50 mm clear of the housing.
The same session found `hex_prism(..., axis="Y")` silently falling through to the
default branch because only `"X"` was implemented, which turned an oil-drain plug
hex the wrong way.

**Fix.** Make the axis a required argument that raises on an unknown value, or
split the helpers by axis (`cyl_x` / `cyl_z`). Never let a silent default stand in
for a required decision.

### F16. `Shape.clean()` does not exist on a `Compound`

Boolean results are often `Part.Compound`, which has no `.clean()`. Use
`.removeSplitter()`.
