#!/usr/bin/env python3
"""
render.py - colour and render the built reducers to PNG.

This is the only script here that needs a GUI (view providers, colours and
``saveImage`` do not exist under ``freecadcmd``).  Run it through Xvfb via the
``render.sh`` wrapper at the repository root::

    ./render.sh

It forces ``ViewObject.Visibility`` on every part first: the models are written
by ``freecadcmd``, which has no view providers, so a freshly opened ``.FCStd``
can come up with everything hidden and produce a blank - but correctly sized -
PNG.

**Expect this to be slow.** Offscreen software rendering of these models (a 21
part assembly whose gears are thousands of Bezier faces) took more than ten
minutes per frame here, which is why the images committed under ``images/`` were
captured from a native GUI over MCP instead.  The script is kept because it is
correct and useful on a machine with real graphics hardware.

Note also that plain ``freecad``/``freecadcmd`` will not execute a script passed
as a positional argument - it treats it as a document to open.  The wrapper
therefore writes a temporary ``.FCMacro``, which FreeCAD does execute.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) \
    if "__file__" in globals() else os.path.join(os.getcwd(), "src")
ROOT = os.path.dirname(_HERE)

import FreeCAD as App          # noqa: E402
import FreeCADGui as Gui       # noqa: E402

IMAGES = os.path.join(ROOT, "images")

# part name prefix / name -> (r, g, b, transparency)
COLORS = {
    "Housing_Cover": ((0.76, 0.78, 0.80, 1.0), 60),
    "Housing_Base": ((0.60, 0.63, 0.67, 1.0), 60),
    "Gear_Pinion": ((0.92, 0.58, 0.18, 1.0), 0),
    "Gear_Wheel": ((0.88, 0.82, 0.28, 1.0), 0),
    "G1_Pinion_HS": ((0.92, 0.58, 0.18, 1.0), 0),
    "G2_Wheel_HS": ((0.88, 0.82, 0.28, 1.0), 0),
    "G3_Pinion_LS": ((0.86, 0.40, 0.28, 1.0), 0),
    "G4_Wheel_LS": ((0.48, 0.72, 0.42, 1.0), 0),
    "Shaft_Input": ((0.62, 0.68, 0.76, 1.0), 0),
    "Shaft_Output": ((0.40, 0.48, 0.60, 1.0), 0),
    "Shaft_HS": ((0.62, 0.68, 0.76, 1.0), 0),
    "Shaft_MID": ((0.50, 0.58, 0.68, 1.0), 0),
    "Shaft_LS": ((0.40, 0.48, 0.60, 1.0), 0),
}
DEFAULT = ((0.53, 0.56, 0.61, 1.0), 0)          # caps
BEARING = ((0.28, 0.30, 0.34, 1.0), 0)

MODELS = {
    "single_stage": dict(
        path=os.path.join(ROOT, "models", "reducer_single_stage.FCStd"),
        views=[("iso", "viewIsometric"), ("axial", "viewRight"),
               ("front", "viewFront")]),
    "two_stage": dict(
        path=os.path.join(ROOT, "models", "reducer_two_stage.FCStd"),
        views=[("iso", "viewIsometric"), ("axial", "viewRight"),
               ("front", "viewFront")]),
}
W, H = 1600, 1000


def colorize(doc):
    """Colour every part and make sure it is visible.

    Visibility has to be forced: the models are produced by ``freecadcmd``,
    which has no view providers, so the ``.FCStd`` files carry no ViewObject
    data.  Loaded into the GUI the objects can therefore come up hidden and the
    render is a blank white image of the expected size - easy to miss, because
    ``saveImage`` still succeeds.
    """
    for o in doc.Objects:
        vp = getattr(o, "ViewObject", None)
        if vp is None:
            continue
        if o.Name.startswith("Bearing_"):
            col, tr = BEARING
        else:
            col, tr = COLORS.get(o.Name, DEFAULT)
        vp.Visibility = True
        vp.ShapeColor = col
        vp.Transparency = tr
        vp.DisplayMode = "Flat Lines"


def shoot(path, view_method, width=W, height=H):
    view = Gui.ActiveDocument.ActiveView
    getattr(view, view_method)()
    view.fitAll()
    view.saveImage(path, width, height, "White")
    print("  wrote %s" % os.path.relpath(path, ROOT))


def render_model(key, spec):
    print("%s" % key)
    doc = App.openDocument(spec["path"])
    colorize(doc)
    doc.recompute()

    for suffix, method in spec["views"]:
        shoot(os.path.join(IMAGES, "%s_%s.png" % (key, suffix)), method)

    # cover off: the gear train inside
    cover = doc.getObject("Housing_Cover")
    if cover is not None:
        cover.ViewObject.Visibility = False
        base = doc.getObject("Housing_Base")
        if base is not None:
            base.ViewObject.Transparency = 25
        doc.recompute()
        shoot(os.path.join(IMAGES, "%s_internals.png" % key), "viewIsometric")
        shoot(os.path.join(IMAGES, "%s_internals_axial.png" % key), "viewRight")

    App.closeDocument(doc.Name)


def main():
    if not os.path.isdir(IMAGES):
        os.makedirs(IMAGES)
    for key, spec in MODELS.items():
        if not os.path.isfile(spec["path"]):
            print("skip %s: %s not found (build it first)" % (key, spec["path"]))
            continue
        render_model(key, spec)
    print("\nimages written to %s" % IMAGES)


if __name__ == "__main__":
    main()
