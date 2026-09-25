# Verification methodology

How to convince yourself that generated CAD geometry is actually correct, rather
than merely plausible. Written from the mistakes that got through.

The governing rule: **the builder's report is not evidence.** A separate program
should re-open the saved file and re-derive what it can from the geometry itself.
That separation is what caught the defect described in
[API traps §1](02-freecad-api-traps.md#1-partfeatureshape-already-has-the-placement-applied)
— the builder had reported the keyways as fine.

---

## 1. Interference: intersection volume, nothing else

`Shape.distToShape` returns 0 both for touching and for overlapping solids. The
only sound test is the volume of the intersection:

```python
a.common(b).Volume        # > 0 means real interference
```

Keep `distToShape` for the *separate* claim "the surfaces actually meet", and use
them together to assert a correct mesh: distance ≈ 0 **and** volume == 0.

## 2. Pre-filter large pairwise sweeps with bounding boxes

41 parts is 820 pairs. A full sweep took **more than two minutes** and was
indistinguishable from a hang; the user thought FreeCAD had died. A bounding-box
overlap pre-filter cut it to 201 candidate pairs and finished in seconds with
identical conclusions.

```python
def overlap(a, b):                      # a, b: Shape.BoundBox
    return (a.XMin <= b.XMax and b.XMin <= a.XMax and
            a.YMin <= b.YMax and b.YMin <= a.YMax and
            a.ZMin <= b.ZMax and b.ZMin <= a.ZMax)

candidates = [(x, y) for x, y in itertools.combinations(objs, 2)
              if overlap(bb[x.Name], bb[y.Name])]
```

Bounding boxes are too crude to *measure* with, but entirely adequate to
*exclude* with.

## 3. Cross-check every cut against a closed-form volume

A rectangular slot of width `b` cut to depth `t1` into a cylinder of radius `R`
has cross-section

```
A = ∫(-b/2 .. b/2) ( sqrt(R² − y²) − (R − t1) ) dy
  = 2·( y/2·sqrt(R²−y²) + R²/2·asin(y/R) ) |₀^(b/2)  −  b·(R − t1)
```

Multiply by the length and the boolean must reproduce it to well under 0.1 %.
Every mismatch found this way had a real cause, and every cause was an *effective
length* subtlety rather than a formula error:

* a cutter deliberately overshooting the end of a shaft is clipped by the
  material, so the effective length is
  `min(x1, part_max) − max(x0, part_min)`;
* because the slot's corners are limited by the cylinder, the removed volume is
  slightly *less* than the naive `b · t1 · L` (2382.9 vs 2500 mm³ in one case) —
  which is correct, not a bug.

This one habit caught a misplaced coupling keyway (0 mm³ removed) and the missing
hub keyways, and confirmed every successful cut.

## 4. Measure axes from cylindrical faces, not bounding boxes

See [API traps §5](02-freecad-api-traps.md#5-bounding-boxes-of-boolean-results-are-approximate).
A correct 160.000 mm centre distance measured as 159.888 mm from bound-box
centres. Assert to 1e-6 mm from the underlying cylindrical surfaces.

## 5. Prove the check has discriminating power

Confirming "correct phase → 0 interference" is not enough. Rotate the driven gear
by half a tooth pitch and confirm you get ≈1900 mm³. Without that negative
control you cannot rule out a check that returns 0 for *any* input.

**A verification step that has never failed is an untested verification step.**
Seed each new check with a known-bad case at least once.

## 6. Assert that features exist, and let code produce the verdict

A hub-keyway check printed

```
empty inside hub keyway     ? True  (expect False)
```

which is a **failure** — `isInside` returning `True` means material is present,
i.e. no keyway. It was read as a pass because the line contained "True" and the
surrounding lines contained "PASS". The bug then survived a whole design cycle.

**Fix.** Make checks binary and machine-judged:

```python
def check(label, ok, detail=""):
    if not ok:
        FAILURES.append(label)
    print("  [%s] %-56s %s" % ("PASS" if ok else "FAIL", label, detail))
```

and exit non-zero. Never leave a raw value next to a hand-written expectation for
a human to interpret.

## 7. Measure gear tooth count independently

Clustering the vertices that lie on the tip circle recovers the tooth count
without counting teeth by eye, and cross-checks both the module and the phase.
Use half the expected pitch as the clustering threshold (the two vertices
bounding one tip arc are far closer together than adjacent teeth).

Watch the wrap-around: a cluster straddling the 0°/360° boundary counts as two,
which produced a phantom 21st tooth on a 20-tooth gear. Merge the wrap gap
explicitly:

```python
if (band[0] + 2 * math.pi) - band[-1] <= threshold:
    n -= 1
```

## 8. Find orphan parts with connectivity analysis

Build a graph of parts whose bounding boxes overlap, union-find the components,
and anything in a small component is floating. This caught a breather body
sitting **50.3 mm from the nearest part** — an error that reads as "a normal
boss" in a thumbnail.

## 9. Distinguish "still running" from "hung"

When a call appears stuck, check the RPC status — it is answered off the GUI
thread, so it works while a GUI operation is in flight:

* `state: busy` with `running_for_seconds` climbing → **it is running**; wait.
  `timeout_seconds = 0` means it will not time out on its own;
* `state: healthy` yet the call cannot get onto the GUI thread for 90 s →
  something else owns the GUI thread, and the usual culprit is a **modal dialog
  open on the remote FreeCAD**.

## 10. Check the assembly sequence, not just the final picture

Geometry that is correct in the assembled state can still be unbuildable. A
bearing slides on from a shaft end and is located by a shoulder, so going inwards
the diameter must be monotonically non-increasing until that shoulder. The same
logic decides which end a gear must be fitted from: one z = 60 wheel with a Ø60
bore could only go on from one end, because the other end had a Ø68 shoulder in
the way.
