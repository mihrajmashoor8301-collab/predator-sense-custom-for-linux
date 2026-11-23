# PredSenseLinux 1.0.0

A Tkinter desktop control center for supported Acer Predator and Nitro laptops using the
Linuwu-Sense kernel module. The gaming-inspired interface groups live telemetry, cooling,
four-zone keyboard lighting, and battery/firmware options into separate pages. Its geometric PS
system-core mark is original PredSenseLinux branding.

Available controls depend on the laptop firmware and the loaded module. The GUI detects the
Predator or Nitro sysfs directory and hides controls the firmware does not expose. It includes
CPU/GPU temperature, usage and fan RPM telemetry, AC and battery thermal profiles, animated
CPU/GPU fan controls with Auto, Max, and Custom modes, four-zone effects, static four-zone or
shared single-zone colors, a circular hue selector with 0–255 RGB sliders and numeric inputs,
keyboard idle timeout, battery limiter and calibration, USB charging thresholds, boot
animation/sound, and LCD override. The AC and battery profile choices are saved separately and
switched automatically while the GUI is running. Per-key RGB is not supported by the module.

## What changed in 1.0.0

- **The kernel module is installed through DKMS.** It is rebuilt automatically after every
  `apt upgrade` that pulls a new kernel, instead of disappearing until you reinstall it by hand.
- **Pinned, current driver source.** The installer fetches Linuwu-Sense commit `4483b6c`, which
  has `platform_profile_ops` for kernel 6.17+, `strscpy()` for Linux 7.2+ (where `strncpy()` was
  removed), and support for PTX17-71, AN16-42 and ANV15-52.
- **Secure Boot works.** The installer generates a local MOK, signs the module, and queues
  enrolment with `mokutil`. No more "disable Secure Boot in firmware".
- **Fresh installs have a working GUI.** The profile helper is now enabled unconditionally (it
  used to be skipped unless the module was already loaded, which left every profile button
  broken on a new machine).
- **The launcher no longer dies silently.** It falls back to plain `python3` when `sg` is
  missing or the `linuwu_sense` group does not exist yet.
- **One helper path.** GUI and package both use `/usr/lib/linuwu-profile-helper` and
  `/usr/lib/systemd/system`, so installing from source and then from the `.deb` no longer leaves
  two competing units. (`util-linux-extra` is recommended because it provides `sg`.)
- **The self-extracting installer verifies its own payload** against an embedded SHA-256.

## Requirements

- A supported Acer Predator or Nitro laptop. Available controls vary by model and firmware.
- Kali, Debian, Ubuntu, or another `apt`-based distribution with systemd and a graphical desktop.
- Internet access and `sudo` for dependencies, kernel headers, and the driver source.
- Headers matching the running kernel (the installer installs them through `apt`).
- Secure Boot may stay enabled: the first install needs one reboot to enrol the signing key.

The kernel module is third-party software from the
[Linuwu-Sense project](https://github.com/0x7375646F/Linuwu-Sense). It is not embedded in the
installer; the installer downloads a pinned commit and builds it for your kernel. Installing it
replaces the built-in `acer_wmi` driver.

GPU temperature is read using `nvidia-smi` when it is installed and the NVIDIA driver is
working. Without it, the GPU temperature is shown as `N/A`; fan RPM and CPU temperature
discovery do not depend on NVIDIA.

## Install

### The single-file installer (recommended)

Download `PredSenseLinux-Installer.run` from the
[releases page](https://github.com/mihrajmashoor8301-collab/predator-sense-custom-for-linux/releases),
then run it as your normal desktop user — not with `sudo`:

```bash
chmod +x PredSenseLinux-Installer.run
./PredSenseLinux-Installer.run
```

It installs the `.deb`, then installs the kernel module through DKMS and configures the system:
`acer_wmi` blacklist, `modules-load.d`, the shutdown unit, the `linuwu_sense` group, sysfs
permissions, and the profile helper.

If Secure Boot is on, the installer ends with a **reboot required** message. On the next boot,
complete the blue MOK manager screen: `Enroll MOK -> Continue -> Reboot`. The module loads
automatically afterwards.

### Debian package

```bash
sudo apt install ./predsenselinux_1.0.0_all.deb
/usr/share/predsenselinux/install-kernel-module.sh
```

The `.deb` alone installs the GUI and helper only. The second command adds the driver. Run it as
your normal user; it escalates by itself.

### From a source checkout

```bash
git clone https://github.com/mihrajmashoor8301-collab/predator-sense-custom-for-linux.git
cd predator-sense-custom-for-linux
./install.sh --with-kernel-module
```

`./install.sh` installs only the GUI and helper (for a machine that already has the module).
Build the release artefacts with:

```bash
./build-package.sh
```

That writes `dist/PredSenseLinux/` and `dist/Completed Projects/PredSenseLinux-Installer.run`.

## The kernel module

`install-kernel-module.sh` is the only supported module path and does the following:

1. `apt install` build tools, `dkms`, `mokutil` and headers for the running kernel.
2. Fetch the pinned Linuwu-Sense commit and stage it in `/usr/src/linuwu-sense-1.0`.
3. Generate a MOK in `~/module-signing/` and queue it with `mokutil` when Secure Boot is on.
4. `dkms add / build / install`, so the module is signed and rebuilt on kernel upgrades.
5. Blacklist `acer_wmi` and load `linuwu_sense` through `modules-load.d`.
6. Create the `linuwu_sense` group, add your user, and set `0660 root:linuwu_sense` on the fan,
   battery, keyboard and firmware attributes through `systemd-tmpfiles`.
7. Enable the profile helper.

Exit code `3` means "installed, reboot to finish Secure Boot enrolment"; the installer wrapper
treats that as success and prints the reboot instructions.

### Kernel compatibility

| kernel | note |
|---|---|
| 7.2+ | `strncpy()` was removed; the pinned driver uses `strscpy()` at all sysfs write handlers |
| 6.17+ | `platform_profile` moved to the `platform_profile_ops` API; covered by the pinned commit |
| any upgrade | DKMS rebuilds the module automatically; `dkms status` shows the installed version |

You can override the driver revision with `LINUWU_SENSE_REF=<tag-or-sha>` when running
`install-kernel-module.sh`.

## Launch

Open **PredSenseLinux** from the application menu. The launcher re-executes the GUI inside the
`linuwu_sense` group with `sg`, so profile changes work even in a session that started before
the install. If `sg` is unavailable, it starts the GUI directly. Never launch it with `sudo`.

## Verify the installation

```bash
dkms status | grep linuwu
lsmod | grep linuwu_sense
systemctl is-enabled linuwu-profile-helper.service
systemctl is-active linuwu-profile-helper.service
stat -c '%A %U:%G %n' /run/linuwu-profile-helper/profile.sock
```

Expected: a DKMS entry named `linuwu-sense/1.0`, the module loaded, `enabled` and `active`, and
`srw-rw---- root:linuwu_sense` on the socket.

## Troubleshooting

| symptom | cause and fix |
|---|---|
| Installer ends with "reboot required" | Secure Boot key queued: reboot, then `Enroll MOK -> Continue` |
| `Key was rejected by service` | MOK not enrolled: `sudo mokutil --import ~/module-signing/MOK.der`, reboot |
| `modprobe: FATAL: Module linuwu_sense not found` | DKMS build failed: `sudo dkms autoinstall`, then `dkms status` |
| Profile buttons say the helper is not running | `sudo systemctl enable --now linuwu-profile-helper.service` |
| `Permission denied` writing fan/battery values | group not active in this session: log out and back in, or use the desktop launcher |
| Fan RPM or temperature shows `N/A` | no `acer` hwmon device, or NVIDIA driver/`nvidia-smi` missing |
| Module gone after a kernel upgrade | check `dkms status`; if the new kernel has no headers, `sudo apt install linux-headers-$(uname -r)` |

## Uninstall

Module (restores `acer_wmi`):

```bash
sudo /usr/share/predsenselinux/uninstall-kernel-module.sh
sudo reboot
```

GUI and helper:

```bash
sudo apt remove --purge predsenselinux
```

From a source install instead:

```bash
sudo systemctl disable --now linuwu-profile-helper.service
sudo rm -f /usr/lib/systemd/system/linuwu-profile-helper.service /etc/default/linuwu-profile-helper
sudo rm -f /usr/share/applications/linuwu-sense.desktop
sudo rm -rf /opt/linuwu-gui /usr/lib/linuwu-profile-helper /usr/share/predsenselinux
sudo systemctl daemon-reload
```

The module uninstaller removes the group membership. Uninstall the GUI first if you want the
module's group cleanup to run last.

## Files installed

| path | owner | purpose |
|---|---|---|
| `/opt/linuwu-gui/linuwu_gui.py`, `launch.sh` | package | GUI and launcher |
| `/usr/lib/linuwu-profile-helper/linuwu_profile_helper.py` | package | root helper for profile writes |
| `/usr/lib/systemd/system/linuwu-profile-helper.service` | package | helper unit |
| `/usr/share/applications/linuwu-sense.desktop` | package | menu entry |
| `/usr/share/predsenselinux/install-kernel-module.sh` | package | module installer (DKMS) |
| `/usr/share/predsenselinux/uninstall-kernel-module.sh` | package | module uninstaller |
| `/etc/tmpfiles.d/linuwu_sense.conf` | module installer | sysfs permissions |
| `/etc/modprobe.d/blacklist-acer_wmi.conf` | module installer | replaces the stock driver |
| `/etc/modules-load.d/linuwu_sense.conf` | module installer | load at boot |
| `/usr/src/linuwu-sense-1.0`, `/var/lib/dkms/linuwu-sense` | DKMS | source and build trees |
