#!/usr/bin/env bash
# Linuwu-Sense kernel module installer for PredSenseLinux.
#
# Builds and installs the module through DKMS, so it is rebuilt automatically
# whenever the kernel is upgraded, and handles Secure Boot with a local MOK.
#
# Run as your normal desktop user, without sudo: this script escalates only for
# the privileged steps.
#
# Exit codes: 0 = installed, 3 = installed but a reboot is required to enrol the
# Secure Boot key, anything else = failure.
set -euo pipefail

MODULE="linuwu_sense"
GROUP="linuwu_sense"
PROFILE_HELPER="linuwu-profile-helper.service"

# Pinned upstream commit (2026-11): platform_profile_ops for kernel 6.17+,
# PTX17-71 / AN16-42 / ANV15-52 support, and strscpy() for Linux 7.2+, where
# strncpy() was removed. Override with LINUWU_SENSE_REF=<ref> to test another.
REPOSITORY="https://github.com/0x7375646F/Linuwu-Sense.git"
REF="${LINUWU_SENSE_REF:-4483b6c38b9bb963ac9ada9ca476578e0c63cc08}"

KERNEL_RELEASE="$(uname -r)"
ACER_BASE="/sys/devices/platform/acer-wmi"
FAN_ATTRIBUTE="$ACER_BASE/predator_sense/fan_speed"
NITRO_FAN_ATTRIBUTE="$ACER_BASE/nitro_sense/fan_speed"
PROFILE_ATTRIBUTE="$ACER_BASE/platform-profile/platform-profile-0/profile"

say()  { printf '==> %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "run this script as your normal user, without sudo"

command -v apt-get >/dev/null 2>&1 \
    || die "this installer supports Kali, Debian and Ubuntu (apt-based systems)"

if { [ -e "$FAN_ATTRIBUTE" ] || [ -e "$NITRO_FAN_ATTRIBUTE" ]; } && [ -e "$PROFILE_ATTRIBUTE" ]; then
    say "Linuwu-Sense is already active; refreshing DKMS and configuration only."
fi

# --- dependencies -----------------------------------------------------------
say "Installing build dependencies"
sudo apt-get update -qq
sudo apt-get install -y git build-essential dkms mokutil

if [ ! -f "/lib/modules/$KERNEL_RELEASE/build/Makefile" ]; then
    say "Installing kernel headers for $KERNEL_RELEASE"
    sudo apt-get install -y "linux-headers-$KERNEL_RELEASE" || true
fi
[ -f "/lib/modules/$KERNEL_RELEASE/build/Makefile" ] || die \
"kernel headers for $KERNEL_RELEASE are missing; install them, reboot into that kernel, then retry"

REAL_USER="${SUDO_USER:-$(id -un)}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
[ -n "$REAL_HOME" ] || die "cannot resolve the home directory of $REAL_USER"

SECURE_BOOT=0
if command -v mokutil >/dev/null 2>&1 && mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
    SECURE_BOOT=1
    say "Secure Boot detected"
else
    say "Secure Boot not enabled; the module will be unsigned"
fi

# --- fetch the driver -------------------------------------------------------
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/linuwu-sense.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

say "Fetching Linuwu-Sense $REF"
git init -q "$WORKDIR/src"
git -C "$WORKDIR/src" remote add origin "$REPOSITORY"
git -C "$WORKDIR/src" fetch -q --depth 1 origin "$REF"
git -C "$WORKDIR/src" checkout -q FETCH_HEAD

DKMS_NAME="$(sed -n 's/^PACKAGE_NAME="\(.*\)"/\1/p' "$WORKDIR/src/dkms.conf")"
DKMS_VERSION="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"/\1/p' "$WORKDIR/src/dkms.conf")"
[ -n "$DKMS_NAME" ] && [ -n "$DKMS_VERSION" ] || die "upstream dkms.conf is missing PACKAGE_NAME/PACKAGE_VERSION"

STAGE="/usr/src/$DKMS_NAME-$DKMS_VERSION"

# --- Secure Boot: create and enrol a MOK ------------------------------------
REBOOT_REQUIRED=0
if [ "$SECURE_BOOT" -eq 1 ]; then
    KEYDIR="$REAL_HOME/module-signing"
    say "Preparing the module signing key in $KEYDIR"
    sudo install -d -o "$REAL_USER" -g "$(id -gn "$REAL_USER")" -m 0700 "$KEYDIR"
    if [ ! -f "$KEYDIR/MOK.priv" ] || [ ! -f "$KEYDIR/MOK.der" ]; then
        sudo openssl req -new -x509 -newkey rsa:2048 -nodes -days 36500 \
            -keyout "$KEYDIR/MOK.priv" -outform DER -out "$KEYDIR/MOK.der" \
            -subj "/CN=Linuwu-Sense Module Signing/" >/dev/null 2>&1
    fi
    sudo chmod 600 "$KEYDIR/MOK.priv"
    sudo chmod 644 "$KEYDIR/MOK.der"
    if mokutil --test-key "$KEYDIR/MOK.der" 2>/dev/null | grep -q "already enrolled"; then
        say "Signing key is already enrolled"
    else
        echo
        echo "  Secure Boot needs this key enrolled once. mokutil asks for a"
        echo "  one-time password (at least 8 characters); you will re-enter it"
        echo "  on the blue MOK screen after the reboot."
        echo
        if sudo mokutil --import "$KEYDIR/MOK.der"; then
            REBOOT_REQUIRED=1
        else
            die "the Secure Boot key was not queued; run 'sudo mokutil --import $KEYDIR/MOK.der' in a terminal, reboot, then rerun this script"
        fi
    fi
fi

# --- DKMS -------------------------------------------------------------------
say "Staging sources in $STAGE"
sudo rm -rf "$STAGE"
sudo install -d "$STAGE"
sudo cp -a "$WORKDIR/src/." "$STAGE/"
sudo rm -rf "$STAGE/.git"
sudo make -C "$STAGE" clean >/dev/null 2>&1 || true

say "Registering with DKMS"
dp_versions_file=$(mktemp)
sudo dkms status 2>/dev/null | awk -F'[,/ ]+' -v n="$DKMS_NAME" '$1 == n { print $2 }' > "$dp_versions_file"
while read -r version; do
    [ -n "$version" ] || continue
    if [ "$version" != "$DKMS_VERSION" ]; then
        sudo dkms remove "$DKMS_NAME/$version" --all >/dev/null 2>&1 || true
    fi
done < "$dp_versions_file"
rm -f "$dp_versions_file"

sudo dkms remove "$DKMS_NAME/$DKMS_VERSION" --all >/dev/null 2>&1 || true
sudo dkms add "$DKMS_NAME/$DKMS_VERSION"
sudo dkms build "$DKMS_NAME/$DKMS_VERSION"
sudo dkms install "$DKMS_NAME/$DKMS_VERSION" --force

# Drop any copy left behind by an older, non-DKMS `make install`.
if [ -f "/lib/modules/$KERNEL_RELEASE/kernel/drivers/platform/x86/$MODULE.ko" ]; then
    say "Removing the previous non-DKMS module copy"
    sudo rm -f "/lib/modules/$KERNEL_RELEASE/kernel/drivers/platform/x86/$MODULE.ko"
    sudo depmod -a
fi

# --- acer_wmi replacement ---------------------------------------------------
say "Blacklisting the stock acer_wmi driver"
echo "blacklist acer_wmi" | sudo tee /etc/modprobe.d/blacklist-acer_wmi.conf >/dev/null
echo "$MODULE" | sudo tee /etc/modules-load.d/$MODULE.conf >/dev/null
sudo modprobe -r "$MODULE" 2>/dev/null || true
sudo modprobe -r acer_wmi 2>/dev/null || true

if [ "$REBOOT_REQUIRED" -eq 0 ]; then
    say "Loading $MODULE"
    if ! sudo modprobe "$MODULE"; then
        warn "the module did not load; inspect 'dmesg | grep -i linuwu'"
    fi
fi

# --- service, group and sysfs permissions -----------------------------------
say "Installing the shutdown unit"
sudo install -m 0644 "$(dirname "$0")/linuwu_sense.service" /etc/systemd/system/ 2>/dev/null || \
    sudo install -m 0644 /usr/share/predsenselinux/linuwu_sense.service /etc/systemd/system/ 2>/dev/null || \
    warn "linuwu_sense.service not found; skipping"
sudo systemctl daemon-reload || true
sudo systemctl enable linuwu_sense.service >/dev/null 2>&1 || true

say "Configuring the $GROUP group"
getent group "$GROUP" >/dev/null || sudo groupadd --system "$GROUP"
sudo usermod -aG "$GROUP" "$REAL_USER"

if [ -d "$ACER_BASE/predator_sense" ]; then
    MODEL_PATH="predator_sense"
    FIELDS="backlight_timeout battery_calibration battery_limiter boot_animation_sound fan_speed lcd_override usb_charging"
elif [ -d "$ACER_BASE/nitro_sense" ]; then
    MODEL_PATH="nitro_sense"
    FIELDS="fan_speed battery_limiter battery_calibration usb_charging"
else
    MODEL_PATH=""
    warn "no predator_sense/nitro_sense node found; sysfs permissions not set"
fi

if [ -n "$MODEL_PATH" ]; then
    say "Setting sysfs permissions"
    CONF="/etc/tmpfiles.d/$MODULE.conf"
    : | sudo tee "$CONF" >/dev/null
    for field in $FIELDS; do
        echo "f $ACER_BASE/$MODEL_PATH/$field 0660 root $GROUP" | sudo tee -a "$CONF" >/dev/null
    done
    if [ -d "$ACER_BASE/four_zoned_kb" ]; then
        for entry in four_zone_mode per_zone_mode; do
            echo "f $ACER_BASE/four_zoned_kb/$entry 0660 root $GROUP" | sudo tee -a "$CONF" >/dev/null
        done
    fi
    sudo systemd-tmpfiles --create "$CONF"
fi

if systemctl list-unit-files "$PROFILE_HELPER" >/dev/null 2>&1 && \
   systemctl list-unit-files "$PROFILE_HELPER" 2>/dev/null | grep -q "$PROFILE_HELPER"; then
    say "Enabling the profile helper"
    sudo systemctl enable --now "$PROFILE_HELPER" || true
fi

# --- verify -----------------------------------------------------------------
if [ "$REBOOT_REQUIRED" -eq 1 ]; then
    cat <<EOF

Secure Boot key queued. Reboot now and complete the blue MOK manager screen
(Enroll MOK -> Continue -> Reboot); $MODULE loads automatically afterwards.

EOF
    exit 3
fi

if [ ! -e "$FAN_ATTRIBUTE" ] && [ ! -e "$NITRO_FAN_ATTRIBUTE" ]; then
    die "the module installed but no fan interface appeared; check 'dmesg | grep -i linuwu'"
fi

say "Linuwu-Sense is installed through DKMS and will rebuild on kernel upgrades"
echo "    Log out and back in once so your user picks up the $GROUP group."
