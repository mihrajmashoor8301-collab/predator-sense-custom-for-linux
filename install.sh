#!/bin/bash
set -e
D="$(cd "$(dirname "$0")" && pwd)"
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
sudo mkdir -p /opt/linuwu-gui
sudo cp "$D/linuwu_gui.py" "$D/launch.sh" /opt/linuwu-gui/
sudo chmod +x /opt/linuwu-gui/linuwu_gui.py /opt/linuwu-gui/launch.sh
sudo cp "$D/linuwu-sense.desktop" /usr/share/applications/
sudo install -d -o root -g root -m 0755 /usr/local/lib/linuwu-profile-helper
sudo install -o root -g root -m 0755 "$D/linuwu_profile_helper.py" /usr/local/lib/linuwu-profile-helper/linuwu_profile_helper.py
GROUP_GID="$(getent group linuwu_sense | cut -d: -f3)"
if [ -z "$GROUP_GID" ]; then
    sudo groupadd --system linuwu_sense
    GROUP_GID="$(getent group linuwu_sense | cut -d: -f3)"
fi
TARGET_USER="${SUDO_USER:-$(id -un)}"
sudo usermod -aG linuwu_sense "$TARGET_USER"
printf 'LINUWU_GROUP_GID=%s\n' "$GROUP_GID" | sudo tee /etc/default/linuwu-profile-helper >/dev/null
sudo chown root:root /etc/default/linuwu-profile-helper
sudo chmod 0644 /etc/default/linuwu-profile-helper
sudo install -o root -g root -m 0644 "$D/linuwu-profile-helper.service" /etc/systemd/system/linuwu-profile-helper.service
sudo systemctl daemon-reload
sudo systemctl enable --now linuwu-profile-helper.service
echo "Installed. Open 'PredSenseLinux' from the application menu."
