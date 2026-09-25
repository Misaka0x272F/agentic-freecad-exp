# FreeCAD API traps

Behaviour of FreeCAD's Python API that bites silently. Every entry was hit for
real; each is written *symptom → cause → fix → takeaway*.

These are properties of FreeCAD, not of any particular model, so they apply to
anything built with the `Part` API.

---

## 1. `Part::Feature.Shape` already has the Placement applied

**Symptom.** A feature cut in the object's local frame is simply not there. No
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

So `gear.Shape = cut_local_feature(gear.Shape, ...)` cuts a local-frame tool into
an already-rotated shape. In the reducers here it cut two spurious slots into the
rim near `x ∈ [17.2, 21.3]` and produced **no hub keyway at all** — while the part
still passed `isValid()` and its volume changed only ≈0.1 %.

**Fix.** Do every local-frame feature operation on the solid **before** it is
assigned to a document object:

```python
solid = make_gear_solid(...)                 # local frame
solid = cut_hub_keyway(solid, ...)           # still local frame
obj.Shape = solid                            # assign once
obj.Placement = place
```

**Takeaway.** Never treat `obj.Shape` as "the thing I assigned". Either operate
on the intermediate solid, or accept that you are working in world coordinates.
And add a *positive* check that the feature exists where you expect it — a volume
delta and `isValid()` are not enough.

---

## 2. `App.Placement` translates **after** rotating, about the origin

**Symptom.** A cutter rotated onto a shaft's cross-section direction cuts
**0 mm³**. No error.

**Cause.** `p_world = R · p_local + t`, and `R` rotates about the **origin**, not
about the point you had in mind. Passing `t = axis` rotates the cutter all the
way around the world origin and lands it ~2·|axis| away.

**Fix.** To rotate about an axis through `axis`:

```python
t = axis - rot.multVec(axis)
tool.transformGeometry(App.Placement(t, rot).toMatrix())
```

**Takeaway.** Whenever a rotated cutter "does nothing", check the removal volume
against an analytic value — it is the fastest way to see that the boolean ran in
the wrong place.

---

## 3. Selecting a face by radius alone is ambiguous

**Symptom.** A coaxiality check reported a phantom 160 mm misalignment on a
design that is exact.

**Cause.** In that housing, `r = 62.5 mm` is *both* the 6214 bearing bore radius
*and* the 6209 boss outside radius. "The" cylindrical face of that radius was a
different shaft's.

**Fix.** Pass a positional hint and pick the nearest candidate:

```python
cylindrical_axis(shape, radius, near=expected_point)
```

---

## 4. `Shape.distToShape` returns 0 for touching *and* for overlapping

Two solids that merely touch have minimum distance 0 — and so do two solids that
overlap by a millimetre. A distance of 0 proves *contact*; it never proves
*absence of penetration*.

**Use intersection volume** (`a.common(b).Volume`) for interference, and keep
`distToShape` only for the separate claim "the surfaces actually meet".

---

## 5. Bounding boxes of boolean results are approximate

Measuring a centre distance from bound-box centres gave **159.888 mm** for a
design that is exactly 160.000 mm — a 0.11 mm error caused by discretised
geometry after fuse/cut.

Bounding boxes remain fine for *excluding* candidate pairs cheaply (see
[verification methodology](03-verification-methodology.md)). They are not good
enough to measure with. Read the true axis from a cylindrical face:

```python
for f in shape.Faces:
    s = f.Surface
    if s.TypeId == "Part::GeomCylinder" and abs(s.Radius - r) < 1e-6:
        return s.Center, s.Axis
```

---

## 6. `App.getDocument(name)` raises for an unknown name

```python
if App.getDocument("X"):        # NameError: Unknown document 'X'
```

It does **not** return `None`. Test membership instead:
`if "X" in App.listDocuments():`.

(The upstream freecad-mcp project hit the same trap and leaked raw XML-RPC faults
from it.)

---

## 7. A bearing can silently fuse into an invalid solid

**Symptom.** `shape.isValid()` returns `False` for an otherwise plausible
bearing, while the boolean reported success.

**Cause.** For a 6214 (70×125×24) with rings sized as 14 % of `(D − d)` and balls
at `0.95 ×` ring thickness, **`n_balls = 10` is invalid** while 9 and 11 are fine,
and 10 balls at `0.90` or `0.85` are also fine. The balls overlap both rings, and
with that particular spacing the fused intersection curves go bad.

**Fix.** Use 9 balls (which also matches the real 6214 ball diameter of ≈15 mm),
and assert validity. Alternatively skip the boolean entirely:
`Part.makeCompound([inner, outer, *balls])` is valid by construction and avoids
the failure mode — worth preferring when you do not need a single connected
solid.

**Takeaway.** After any fuse of tangent or overlapping solids, assert
`isValid()`. A boolean that returns a shape has not necessarily produced a good
one.

---

## 8. `ViewObject` is `None` under `freecadcmd`

Any line such as `obj.ViewObject.ShapeColor = ...` raises

```
AttributeError: 'NoneType' object has no attribute 'ShapeColor'
```

Keep colours, transparency and screenshots out of model builders; put them in a
separate GUI-only script. (`getattr(o, "ViewObject", None) is not None` is the
guard.)

---

## 9. A headless-saved document renders blank

**Symptom.** `saveImage()` succeeds and writes a PNG of exactly the requested
size — and the file is a uniform white rectangle.

**Cause.** `freecadcmd` has no view providers. A `.FCStd` written by a headless
build contains no `ViewObject` data, so when the GUI later opens it the objects
can come up with `Visibility` false.

**Fix.** Force visibility before rendering:

```python
for o in doc.Objects:
    vp = getattr(o, "ViewObject", None)
    if vp is not None:
        vp.Visibility = True
```

**Takeaway.** Sanity-check rendered output programmatically — a plausible file
size is not evidence of content. A blank 1600×1000 PNG compresses to about
7.7 kB; a real one is several times that.

---

## 10. `Part.Shape` has no `CenterOfMass`

```python
AttributeError: 'Part.Shape' object has no attribute 'CenterOfMass'
```

Use `shape.BoundBox.Center`, or `shape.Solids[0].CenterOfMass`.

---

## 11. `Shape.clean()` does not exist on a `Compound`

Boolean results are often `Part.Compound`, which has no `.clean()`. Use
`.removeSplitter()`.

---

## 12. Helper functions must encode the axis

A helper that builds along +Z — `cyl(r, z0, z1)` — called with `.translated()`
will not complain; it just silently produces a part pointing the wrong way. One
session's breather body ended up 50 mm clear of the housing this way, and a
`hex_prism(..., axis="Y")` fell through to the default branch because only `"X"`
was implemented, turning an oil-drain plug hex the wrong way.

**Fix.** Make the axis a required argument that raises on an unknown value, or
split the helpers by axis (`cyl_x` / `cyl_z`). Never let a silent default stand
in for a required decision.

---

## 13. `freecadcmd script.py` does not run the script

A positional argument to `freecad`/`freecadcmd` is a **document to open**, not a
script. Running `freecadcmd src/build_single_stage.py` prints the banner and
exits. Use:

```bash
freecadcmd -P src -c "import build_single_stage as m; m.main()"
```

`-P` puts `src/` on the Python path, so `__file__` is defined and the modules can
import each other.

For scripts that need a GUI, FreeCAD *does* execute a `.FCMacro` argument — which
is what the `render.sh` wrapper relies on.

---

## 14. Output redirected to a file is lost when a script raises

**Symptom.** `freecadcmd ... > log 2>&1` exits non-zero with a log containing
only FreeCAD's own banner — all `print()` output vanished, yet the same run looks
fine on a terminal.

**Cause.** FreeCAD's embedded interpreter exits through its C++ path, which does
not flush Python's `stdout` buffer. On a TTY, `print` is line-buffered and you
never notice.

**Fix.** `sys.stdout.reconfigure(line_buffering=True)` at the top of the script.
