#!/usr/bin/env bash
# Removes the Linuwu-Sense DKMS module installed by install-kernel-module.sh
# and restores the stock acer_wmi driver. Run as your normal user, no sudo.
set -euo pipefail

MODULE="linuwu_sense"
GROUP="linuwu_sense"
DKMS_NAME="linuwu-sense"
REAL_USER="${SUDO_USER:-$(id -un)}"

say() { printf '==> %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] && { echo "error: run this as your normal user, without sudo" >&2; exit 2; }

say "Removing DKMS registrations"
for version in $(sudo dkms status 2>/dev/null | awk -F'[,/ ]+' -v n="$DKMS_NAME" '$1 == n { print $2 }'); do
    sudo dkms remove "$DKMS_NAME/$version" --all >/dev/null 2>&1 || true
    sudo rm -rf "/usr/src/$DKMS_NAME-$version"
done

say "Removing the module and its configuration"
sudo modprobe -r "$MODULE" 2>/dev/null || true
sudo rm -f /etc/modules-load.d/$MODULE.conf
sudo rm -f /etc/modprobe.d/blacklist-acer_wmi.conf
sudo rm -f /etc/tmpfiles.d/$MODULE.conf
sudo rm -f "/lib/modules/$(uname -r)/kernel/drivers/platform/x86/$MODULE.ko"
sudo rm -f /etc/systemd/system/linuwu_sense.service
sudo systemctl daemon-reload || true
sudo depmod -a

say "Restoring acer_wmi"
sudo modprobe acer_wmi 2>/dev/null || true

say "Removing the group membership"
if getent group "$GROUP" >/dev/null; then
    sudo gpasswd -d "$REAL_USER" "$GROUP" >/dev/null 2>&1 || true
    sudo groupdel "$GROUP" 2>/dev/null || true
fi

say "Done. Reboot to fully restore the stock driver."
