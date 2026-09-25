# CAD assembly practice

Lessons about *building assemblies* — mostly about split cast housings, where
almost every problem in this repository appeared. Written from the three-stage
build, which is where an assembly stops being a gear train and starts being a
machine.

---

## 1. Fuse every boss and flange **before** cutting the cavity

**Symptom.** The housing is solid and *every* transmission part reports
interference — ten parts at once.

**Cause.** A split-plane flange is a **solid plate**, not a ring. Cutting the
cavity first and fusing the flanges afterwards refills the cavity.

**Fix.** Fuse flanges, bearing bosses and ribs first; cut the cavity last.

**Takeaway.** When a boolean-fresh part suddenly collides with everything, check
the *order* of the boolean operations before suspecting a dimension.

---

## 2. Flanges must overhang, and the overhang must be relieved

Two coupled constraints on a split-plane flange:

* overhang only in ±Y and the flange bolts on the ±Z sides end up with their
  **nuts buried in the base casting** — 26905 mm³ of interference, at both ends;
* overhang in ±Z and the flange **blocks the shaft extensions**.

Resolution: overhang in every direction, then cut a relief at each bearing seat —
radius = boss radius + 8 mm, axial extent stopping **exactly** at the boss face
(going deeper starts removing the boss itself).

---

## 3. Ribs must clear the bolt-head circumscribed circle

A hex head's circumscribed radius is `across-flats / √3 ≈ 0.577·af`. Ribs that
look clear on centre lines will still clip a bolt head by tens to hundreds of
mm³.

These are the most expensive collisions to find, because the bounding boxes
overlap and the volume is tiny — no threshold on the volume will flag them, and
they do not show in a render. Check them deliberately.

---

## 4. Exactly coplanar contact faces produce numerical slivers

**Symptom.** A bolt head or nut face sitting *exactly* on the flange face reports
111 mm³ of interference. Nothing is actually wrong.

**Fix.** Inset the end face by 0.2 mm — invisible, and the sliver disappears.

**Takeaway.** Residual sub-mm³ "interference" between faces you deliberately
placed in contact is a numerics artefact, not a design error. Distinguish the two
by asking whether the parts are *meant* to touch.

---

## 5. Keep diameter steps out of the axial span of a through cap

A through end cap's central bore is sized on the diameter of the shaft that
passes through it. If the shaft steps up to a bigger diameter *inside* the cap's
axial span, the bore no longer clears the shaft.

Measured instance: the shaft went Ø45 → Ø40 at exactly the spigot face, and the
cap's Ø49 bore overlapped the Ø45 section by 26939 mm³. Fix: move the step outside
the cap span and extend the shaft.

---

## 6. A through cap's bore needs the min/max over all four end points

A flanged cap's geometry spans two features: the flange and the spigot. They have
four axial end points between them. Taking the min/max over only the two *inboard*
points leaves part of the flange undrilled, producing a large and otherwise
non-obvious shaft–cap collision.

---

## 7. Blind caps: the shaft end stops at the bearing outer face

Otherwise the shaft runs into the blind cap's spigot. Place every shaft end from
the bearing span: `x_end = wall inner face ± bearing width`.

---

## 8. The cavity floor must clear the lowest tooth of the whole train

This is the easiest way to quietly cut a wheel. A first attempt put the oil-sump
floor at `z = −120` while the largest wheel's teeth reached `z = −123.9`, removing
2578 mm³ from the gear.

Decide the floor from the largest tip radius in the train, plus the required
clearance, and leave ≥ 8–10 mm of casting below it.

---

## 9. Coordinate-system drift between sessions is a real risk

**Symptom.** Nothing *errors*, but every placement, phase formula, view direction
and cap/bearing axial definition is subtly wrong.

**Cause.** One session used **shafts along +Z with the housing split at X = 0**;
the repository's convention is **shafts along +X split at z = 0**. The gear-local
convention happened to match, which makes the divergence harder to spot.

**Fix / takeaway.** Write the conventions down at the top of the shared library
and read them before building, rather than working from memory of a previous
round. If a model from another session is to be merged, rotate it into the shared
frame — do not mix the two.

---

## 10. A threaded shank must be smaller than the tap drill

An M8 bolt modelled at its nominal Ø8 will not enter a Ø6.8 tap drill. Model
fasteners as two diameters: the shank that passes through the cap (Ø8) and the
threaded section that enters the housing (Ø6.6).
