#!/bin/sh
# Launches PredSenseLinux. `sg` applies the linuwu_sense group to a session that
# predates the install (no logout needed) and is skipped when unavailable.
GUI=/opt/linuwu-gui/linuwu_gui.py

if command -v sg >/dev/null 2>&1 && getent group linuwu_sense >/dev/null 2>&1; then
    exec sg linuwu_sense -c "exec python3 $GUI"
fi

exec python3 "$GUI"
