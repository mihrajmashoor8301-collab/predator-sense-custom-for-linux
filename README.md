# PredSenseLinux

A Tkinter desktop control center for supported Acer Predator and Nitro laptops using the Linuwu-Sense kernel module. The gaming-inspired interface groups live telemetry, cooling, four-zone keyboard lighting, and battery/firmware options into separate pages. Its geometric PS system-core mark is original PredSenseLinux branding.

Available controls depend on the laptop firmware and the loaded module. The GUI detects the Predator or Nitro sysfs directory and reports missing core interfaces. It includes CPU/GPU temperature, usage and fan RPM telemetry, AC and battery thermal profiles, animated CPU/GPU fan controls with Auto, Max, and Custom modes, four-zone effects, static four-zone or shared single-zone colors, a circular hue selector with 0–255 RGB sliders and numeric inputs, keyboard idle timeout, battery limiter and calibration, USB charging thresholds, boot animation/sound, and LCD override. The AC and battery profile choices are saved separately and switched automatically while the GUI is running. Per-key RGB is not supported by the module.

## Requirements

- A supported Acer Predator or Nitro laptop. Available controls vary by model and firmware.
- A Debian-based Linux distribution with `apt`/`apt-get`, a graphical desktop, and systemd for the packaged install.
- Internet access and `sudo` access for the installer to install system dependencies and fetch the Linuwu-Sense kernel module source.
- Headers matching the currently running kernel. The installer attempts to install them through `apt`.
- Secure Boot disabled for the automatic module installation, or manual module signing and enrollment.

The kernel module is third-party software from the [Linuwu-Sense project](https://github.com/0x7375646F/Linuwu-Sense). It is not embedded in the PredSenseLinux installer: the installer downloads the module source and builds it for the target laptop's running kernel. Installing it replaces the built-in `acer_wmi` driver. Review the upstream model compatibility information before installing it.

GPU temperature is read using `nvidia-smi` when it is installed and the NVIDIA driver is working. Without it, the GPU temperature is shown as `N/A`; fan RPM and CPU temperature discovery do not depend on NVIDIA.

## Clone the repository

```bash
git clone https://github.com/mihrajmashoor8301-collab/predator-sense-custom-for-linux.git
cd predator-sense-custom-for-linux
```

If you downloaded a source archive instead, extract it and `cd` into the extracted project directory.

## Install

### Build the Debian package

On this project checkout, run:

```bash
./build-package.sh
```

This creates the Debian package in `dist/PredSenseLinux/` and a self-extracting installer in `dist/Completed Projects/PredSenseLinux-Installer.run`. On a fresh target laptop, **that `.run` file is the only project file you need to copy**. Run it as your normal desktop user:

The prebuilt installer is available on the [GitHub Releases page](https://github.com/mihrajmashoor8301-collab/predator-sense-custom-for-linux/releases).

```bash
chmod +x PredSenseLinux-Installer.run
./PredSenseLinux-Installer.run
```

The installer embeds the PredSenseLinux Debian package and setup script. It downloads required OS packages through APT and, unless the expected Linuwu-Sense controls are already available, clones the module source from GitHub and builds it for the target laptop. **Internet access is required; the kernel module itself and OS dependencies are not bundled in the `.run` file.** The target needs matching kernel headers. Automatic module installation stops when Secure Boot is enabled. The module install replaces the built-in `acer_wmi` driver.

To install from a source checkout instead, run one of these as your normal user. The first installs only the GUI and helper when the module is already installed; the second also downloads and installs the module:

```bash
./install.sh
./install.sh --with-kernel-module
```

`install.sh --with-kernel-module` fetches and builds the upstream module before installing the GUI. If matching headers are unavailable, install headers for `uname -r`, reboot into that kernel, and retry. After a kernel update, rebuild/reinstall the module. With Secure Boot enabled, manually build, sign, and enroll the module by following the upstream signing instructions.

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
