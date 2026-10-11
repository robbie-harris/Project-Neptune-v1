#!/usr/bin/env bash
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ -z "${NEPTUNE_GUI_PYTHON:-}" ]]; then
    for candidate in python3.12 python3 /opt/anaconda3/bin/python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tkinter; assert tkinter.TkVersion >= 8.6' >/dev/null 2>&1; then
            NEPTUNE_GUI_PYTHON="$candidate"; break
        fi
    done
fi
if [[ -z "${NEPTUNE_GUI_PYTHON:-}" ]]; then
    echo 'The camera preview requires Python with Tk 8.6+. Set NEPTUNE_GUI_PYTHON to a compatible interpreter.' >&2
    exit 1
fi
exec "$NEPTUNE_GUI_PYTHON" "$NEPTUNE_ROOT/src/neptune_gui/auv_gui.py" "$@"
