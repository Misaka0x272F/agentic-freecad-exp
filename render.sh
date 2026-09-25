#!/usr/bin/env bash
# render.sh - regenerate the PNGs in images/ from the models in models/.
#
# FreeCAD will not execute a script passed as a positional argument (it treats
# the argument as a document to open), but it *will* execute a .FCMacro.  This
# wrapper therefore drops a tiny macro that imports src/render.py and runs it,
# under Xvfb because rendering needs a GUI (and therefore a display).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FREECAD="${FREECAD:-freecad}"

if ! command -v "$FREECAD" >/dev/null 2>&1; then
    echo "error: '$FREECAD' not found; set FREECAD=/path/to/freecad" >&2
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/run_render.FCMacro" <<EOF
import sys
sys.path.insert(0, r"$ROOT/src")
import render
render.main()
EOF

if command -v xvfb-run >/dev/null 2>&1; then
    xvfb-run -a "$FREECAD" "$WORK/run_render.FCMacro"
else
    echo "note: xvfb-run not found, trying with the current DISPLAY" >&2
    "$FREECAD" "$WORK/run_render.FCMacro"
fi
