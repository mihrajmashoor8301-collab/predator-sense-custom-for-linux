#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION=$(cat "$PROJECT_DIR/packaging/VERSION")
OUTPUT_DIR="$PROJECT_DIR/dist/PredSenseLinux"
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/predsenselinux-package.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT HUP INT TERM

install -d "$OUTPUT_DIR"
install -d "$STAGE/DEBIAN"
install -d "$STAGE/opt/linuwu-gui"
install -d "$STAGE/usr/lib/linuwu-profile-helper"
install -d "$STAGE/usr/lib/systemd/system"
install -d "$STAGE/usr/share/applications"
install -d "$STAGE/usr/share/icons/hicolor/scalable/apps"
install -d "$STAGE/usr/share/doc/predsenselinux"
install -d "$STAGE/usr/share/predsenselinux"

install -m 0644 "$PROJECT_DIR/packaging/debian/control" "$STAGE/DEBIAN/control"
install -m 0755 "$PROJECT_DIR/packaging/debian/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$PROJECT_DIR/packaging/debian/prerm" "$STAGE/DEBIAN/prerm"
install -m 0755 "$PROJECT_DIR/packaging/debian/postrm" "$STAGE/DEBIAN/postrm"
install -m 0755 "$PROJECT_DIR/linuwu_gui.py" "$STAGE/opt/linuwu-gui/linuwu_gui.py"
install -m 0755 "$PROJECT_DIR/launch.sh" "$STAGE/opt/linuwu-gui/launch.sh"
install -m 0644 "$PROJECT_DIR/linuwu_profile_helper.py" "$STAGE/usr/lib/linuwu-profile-helper/linuwu_profile_helper.py"
install -m 0644 "$PROJECT_DIR/packaging/debian/linuwu-profile-helper.service" "$STAGE/usr/lib/systemd/system/linuwu-profile-helper.service"
install -m 0644 "$PROJECT_DIR/linuwu-sense.desktop" "$STAGE/usr/share/applications/linuwu-sense.desktop"
install -m 0644 "$PROJECT_DIR/predsenselinux.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/predsenselinux.svg"
install -m 0755 "$PROJECT_DIR/install-kernel-module.sh" "$STAGE/usr/share/predsenselinux/install-kernel-module.sh"
install -m 0644 "$PROJECT_DIR/README-PACKAGE.md" "$STAGE/usr/share/doc/predsenselinux/README.md"

chmod 0755 "$STAGE"
PACKAGE_NAME="predsenselinux_${VERSION}_all.deb"
PACKAGE="$OUTPUT_DIR/$PACKAGE_NAME"
dpkg-deb --build --root-owner-group "$STAGE" "$PACKAGE"
install -m 0644 "$PROJECT_DIR/README-PACKAGE.md" "$OUTPUT_DIR/README.md"
(cd "$OUTPUT_DIR" && sha256sum "$PACKAGE_NAME" > "$PACKAGE_NAME.sha256")

BUNDLE_DIR="$PROJECT_DIR/dist/Completed Projects"
install -d "$BUNDLE_DIR"
cat > "$BUNDLE_DIR/PredSenseLinux-Installer.run" <<'RUN_HEADER'
#!/bin/sh
set -eu
TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/predsenselinux-installer.XXXXXX")
trap 'rm -rf "$TEMP_DIR"' EXIT HUP INT TERM
MARKER_LINE=$(awk '/^__PREDSENSE_DEB_BELOW__$/ { print NR + 1; exit }' "$0")
if [ -z "$MARKER_LINE" ]; then
    echo "Installer payload marker is missing." >&2
    exit 1
fi
tail -n +"$MARKER_LINE" "$0" | base64 -d > "$TEMP_DIR/predsenselinux.deb"
if [ "$(id -u)" -eq 0 ]; then
    echo "Run this installer as your regular desktop user, without sudo." >&2
    exit 1
fi
if ! command -v sudo >/dev/null 2>&1; then
    echo "Install sudo, then run this installer again." >&2
    exit 1
fi
sudo apt install "$TEMP_DIR/predsenselinux.deb"
if ! /usr/share/predsenselinux/install-kernel-module.sh; then
    cat <<'FAILED'

The desktop application is installed, but the kernel module step did not finish.
Fix the reported kernel header/Secure Boot issue and rerun:
  /usr/share/predsenselinux/install-kernel-module.sh
FAILED
    exit 1
fi
cat <<'DONE'

PredSenseLinux and the Linuwu-Sense kernel module are installed. Log out and
back in if this installer added your account to the linuwu_sense group, then
launch PredSenseLinux from the desktop menu.
DONE
exit 0
__PREDSENSE_DEB_BELOW__
RUN_HEADER
base64 "$PACKAGE" >> "$BUNDLE_DIR/PredSenseLinux-Installer.run"
chmod 0755 "$BUNDLE_DIR/PredSenseLinux-Installer.run"
install -m 0644 "$OUTPUT_DIR/README.md" "$BUNDLE_DIR/README.md"
install -m 0644 "$PROJECT_DIR/predsenselinux.svg" "$BUNDLE_DIR/predsenselinux.svg"
install -m 0644 "$PACKAGE" "$BUNDLE_DIR/$PACKAGE_NAME"
(cd "$BUNDLE_DIR" && sha256sum PredSenseLinux-Installer.run "$PACKAGE_NAME" > SHA256SUMS)
if command -v zip >/dev/null 2>&1; then
    (cd "$PROJECT_DIR/dist" && zip -q -r -FS PredSenseLinux-Complete.zip "Completed Projects")
else
    python3 - "$BUNDLE_DIR" "$PROJECT_DIR/dist/PredSenseLinux-Complete.zip" <<'PY'
import pathlib
import sys
import zipfile

folder = pathlib.Path(sys.argv[1])
archive = pathlib.Path(sys.argv[2])
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for item in sorted(folder.rglob("*")):
        if item.is_file():
            bundle.write(item, item.relative_to(folder.parent))
PY
fi

printf 'Package created: %s\n' "$PACKAGE"
printf 'Instructions:    %s/README.md\n' "$OUTPUT_DIR"
printf 'Single installer: %s/PredSenseLinux-Installer.run\n' "$BUNDLE_DIR"
