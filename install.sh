#!/bin/bash
# Source installer for PredSenseLinux (GUI + profile helper).
# For the module install without a DKMS package, run ./install-kernel-module.sh.
set -euo pipefail

D="$(cd "$(dirname "$0")" && pwd)"
GUI_DIR=/opt/linuwu-gui
HELPER_DIR=/usr/lib/linuwu-profile-helper
UNIT_DIR=/usr/lib/systemd/system
DOC_DIR=/usr/share/predsenselinux
GROUP=linuwu_sense
UNIT=linuwu-profile-helper.service

if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [--with-kernel-module]" >&2
    exit 2
fi
case "${1:-}" in
    "") ;;
    --with-kernel-module) "$D/install-kernel-module.sh" ;;
    *)
        echo "Usage: $0 [--with-kernel-module]" >&2
        exit 2
        ;;
esac

if ! python3 -c 'import tkinter' 2>/dev/null; then
    echo "Python tkinter is missing. Install it with:  sudo apt install python3-tk" >&2
    exit 1
fi

sudo install -d -o root -g root -m 0755 "$GUI_DIR" "$HELPER_DIR" "$UNIT_DIR" "$DOC_DIR"
sudo install -o root -g root -m 0755 "$D/linuwu_gui.py" "$D/launch.sh" "$GUI_DIR/"
sudo install -o root -g root -m 0644 "$D/linuwu-sense.desktop" /usr/share/applications/
sudo install -o root -g root -m 0644 "$D/predsenselinux.svg" /usr/share/icons/hicolor/scalable/apps/
sudo install -o root -g root -m 0644 "$D/linuwu_profile_helper.py" "$HELPER_DIR/linuwu_profile_helper.py"
sudo install -o root -g root -m 0644 "$D/$UNIT" "$UNIT_DIR/$UNIT"
sudo install -o root -g root -m 0755 "$D/install-kernel-module.sh" "$D/uninstall-kernel-module.sh" "$DOC_DIR/"
sudo install -o root -g root -m 0644 "$D/linuwu_sense.service" "$DOC_DIR/"

GROUP_GID="$(getent group "$GROUP" | cut -d: -f3 || true)"
if [ -z "$GROUP_GID" ]; then
    sudo groupadd --system "$GROUP"
    GROUP_GID="$(getent group "$GROUP" | cut -d: -f3)"
fi
TARGET_USER="${SUDO_USER:-$(id -un)}"
sudo usermod -aG "$GROUP" "$TARGET_USER"

printf 'LINUWU_GROUP_GID=%s\n' "$GROUP_GID" | sudo tee /etc/default/linuwu-profile-helper >/dev/null
sudo chown root:root /etc/default/linuwu-profile-helper
sudo chmod 0644 /etc/default/linuwu-profile-helper

sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT"

echo "Installed. Open 'PredSenseLinux' from the application menu."
echo "If the profile controls stay unavailable, run ./install-kernel-module.sh, then log out and back in."
