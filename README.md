# PredSenseLinux

A Tkinter desktop control center for supported Acer Predator and Nitro laptops using the Linuwu-Sense kernel module. The gaming-inspired interface groups live telemetry, cooling, four-zone keyboard lighting, and battery/firmware options into separate pages. Its geometric PS system-core mark is original PredSenseLinux branding.

Available controls depend on the laptop firmware and the loaded module. The GUI detects the Predator or Nitro sysfs directory and reports missing core interfaces. It includes CPU/GPU temperature, usage and fan RPM telemetry, AC and battery thermal profiles, animated CPU/GPU fan controls with Auto, Max, and Custom modes, four-zone effects, static four-zone or shared single-zone colors, a circular hue selector with 0–255 RGB sliders and numeric inputs, keyboard idle timeout, battery limiter and calibration, USB charging thresholds, boot animation/sound, and LCD override. The AC and battery profile choices are saved separately and switched automatically while the GUI is running. Per-key RGB is not supported by the module.

## Requirements

- A supported Acer Predator laptop. You can install the Linuwu-Sense kernel module yourself first, or use the package's opt-in module installer described below.
- A Linux desktop session with systemd.
- Python 3, Tkinter, Git, and `sg` (provided by `util-linux`). On Kali, Debian, and Ubuntu, install them with:

  ```bash
  sudo apt update
  sudo apt install git python3 python3-tk util-linux
  ```
- `sudo` access for installing the system service and desktop launcher.
- The module's expected sysfs paths, including `/sys/devices/platform/acer-wmi/predator_sense` and `/sys/devices/platform/acer-wmi/platform-profile/platform-profile-0/profile`.

The kernel-module installer additionally needs `build-essential`, Git, `mokutil`, and headers for the currently running kernel. It installs these through `apt` when requested.

GPU temperature is read using `nvidia-smi` when it is installed and the NVIDIA driver is working. Without it, the GPU temperature is shown as `N/A`; fan RPM and CPU temperature discovery do not depend on NVIDIA.

## Clone the repository

Replace the URL below with the GitHub or GitLab URL where this project is hosted:

```bash
git clone <REPOSITORY_URL> linuwu-sense-gui
cd linuwu-sense-gui
```

If you downloaded a source archive instead, extract it and `cd` into the extracted project directory.

## Install

### Build the Debian package

On this project checkout, run:

```bash
./build-package.sh
```

This creates the Debian package and checksums in `dist/PredSenseLinux/`, plus a downloadable self-extracting installer and complete distribution archive under `dist/Completed Projects/` and `dist/PredSenseLinux-Complete.zip`. The single-file installer uses APT to install the GUI and its dependencies, then installs Linuwu-Sense if its controls are not already present. It checks matching kernel headers and Secure Boot before building the module. The upstream module installer replaces the built-in `acer_wmi` driver.

Make the installer executable and run it as your regular desktop user. If Linuwu-Sense is already installed, use:

```bash
chmod +x install.sh
./install.sh
```

If the kernel module is not installed, use the opt-in all-in-one command:

```bash
./install.sh --with-kernel-module
```

This first runs `install-kernel-module.sh`, which clones the [upstream Linuwu-Sense module](https://github.com/0x7375646F/Linuwu-Sense), builds it for the currently running kernel, and invokes its upstream `make install`. That upstream installer unloads and blacklists the built-in `acer_wmi` driver before installing/loading `linuwu_sense`; the script explains this and asks before proceeding. The module is third-party, reverse-engineered software with model-dependent support, so check the upstream compatibility information for your exact laptop before choosing this option.

The module build needs matching headers for `uname -r`. On Kali, install or update the running kernel's matching headers if the script reports they are missing, reboot into that kernel, and rerun the command. The module is installed for the current kernel; after a kernel update, rebuild/reinstall it for the new running kernel.

The automated module script stops if it detects Secure Boot enabled. Disable Secure Boot in firmware to use this option, or manually build, sign, and enroll the module by following the upstream `module_signing_readme`. The GUI and helper are not installed until the module step succeeds.

The script asks `sudo` to install the GUI under `/opt/linuwu-gui`, install the root-owned profile helper under `/usr/local/lib/linuwu-profile-helper`, add your account to the `linuwu_sense` group, install the systemd unit and desktop entry, then enable and start the helper service. Enter your own password at the sudo prompt. **Do not launch the GUI with `sudo`.**

The helper is restricted to changing the profile sysfs attribute. The GUI sends it requests over a local Unix socket. It accepts only these profile values:

```text
low-power
quiet
balanced
balanced-performance
performance
```

It does not accept shell commands, arbitrary paths, or other actions. The socket is owned by `root:linuwu_sense` with mode `0660`; no TCP listener is used.

## Launch

Open **PredSenseLinux** from the desktop application menu. The installed launcher starts the GUI as your normal user and applies the `linuwu_sense` group for access to the profile socket.

## Verify the installation

Check that the privileged helper is enabled and running:

```bash
systemctl is-enabled linuwu-profile-helper.service
systemctl is-active linuwu-profile-helper.service
systemctl status linuwu-profile-helper.service --no-pager
```

Expected results are `enabled` and `active`. Check the socket owner and permissions:

```bash
stat -c '%A %U:%G %n' /run/linuwu-profile-helper/profile.sock
```

Expected output includes `srw-rw---- root:linuwu_sense`.

The GUI refreshes telemetry once per second. Fan nodes are located by the hwmon device name (`acer`), so changing hwmon numbers do not break RPM display. CPU temperature uses the `coretemp` package sensor. NVIDIA GPU temperature needs a working `nvidia-smi` command:

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

To check the underlying fan nodes if RPM shows `N/A`:

```bash
for hw in /sys/class/hwmon/hwmon*; do
    [ -r "$hw/name" ] || continue
    [ "$(cat "$hw/name")" = acer ] || continue
    cat "$hw/fan1_input" "$hw/fan2_input"
done
```

## Troubleshooting

### Profile buttons show “Profile helper unavailable”

Check the service and its recent log messages:

```bash
systemctl status linuwu-profile-helper.service --no-pager
journalctl -u linuwu-profile-helper.service -b --no-pager
```

Confirm your account is in the helper group:

```bash
getent group linuwu_sense
```

The desktop launcher uses `sg` so a previously open login session can use the group without running the GUI as root. Restart the GUI after installing or updating.

### Profile service fails to start

Confirm the profile attribute exists and the kernel module is loaded:

```bash
test -r /sys/devices/platform/acer-wmi/platform-profile/platform-profile-0/profile && echo "profile interface found"
cat /sys/devices/platform/acer-wmi/platform-profile/platform-profile-0/profile
```

The helper is specific to the sysfs path above. It will not work on a machine where the module exposes the controls at a different path.

### CPU or GPU temperature shows `N/A`

CPU temperature requires the `coretemp` hwmon device and its `Package id 0` input. GPU temperature requires `nvidia-smi` to be installed and able to query the NVIDIA driver. Check the NVIDIA command above. Temperature is read-only; this GUI does not set thermal limits or create fan curves.

### Fan RPM shows `N/A`

Check that `/sys/class/hwmon` contains a device whose `name` is `acer`, with `fan1_input` and `fan2_input` files. The GUI resolves this device dynamically; no specific `hwmonN` number is required.

## Uninstall

Run these commands to stop and remove the GUI and profile helper:

```bash
sudo systemctl disable --now linuwu-profile-helper.service
sudo rm -f /etc/systemd/system/linuwu-profile-helper.service
sudo rm -f /etc/default/linuwu-profile-helper
sudo rm -f /usr/share/applications/linuwu-sense.desktop
sudo rm -rf /opt/linuwu-gui /usr/local/lib/linuwu-profile-helper
sudo systemctl daemon-reload
```

The installer adds your account to `linuwu_sense`. Remove that group membership separately if you no longer use it; do not delete the group if another installed tool depends on it. Uninstalling this GUI does not remove the Linuwu-Sense kernel module. The module's upstream `make uninstall` also removes the `linuwu_sense` group; uninstall the GUI/helper first if you want to remove both, then follow the upstream uninstall instructions.
