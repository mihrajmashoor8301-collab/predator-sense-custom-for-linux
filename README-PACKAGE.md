# PredSenseLinux Debian package

PredSenseLinux is a desktop control center for supported Acer Predator and Nitro laptops. It uses the Linuwu-Sense kernel module for hardware access. The Debian package installs the GUI, restricted profile helper service, desktop launcher, and the module installation script.

The kernel module is third-party reverse-engineered software. It is not bundled in either the `.deb` or the self-extracting `.run` installer. The `.run` includes the PredSenseLinux package and setup script; during installation, that script downloads the module source and builds it for the target laptop's running kernel. Confirm that your exact laptop model is supported before installing the module.

## Requirements

- Kali, Debian, Ubuntu, or another Debian-based Linux distribution using systemd and `apt`/`dpkg`.
- A supported Acer Predator or Nitro laptop.
- A working graphical desktop session.
- Internet access, matching headers for the running kernel, and `sudo` access. The installer attempts to get system packages and kernel headers through APT and gets the module source from GitHub.
- Secure Boot disabled for automatic module installation, unless you build, sign, and enroll the module yourself.

## Install

On a fresh laptop, **`PredSenseLinux-Installer.run` is the only project file you need to copy**. Download it from the [GitHub Releases page](https://github.com/mihrajmashoor8301-collab/predator-sense-custom-for-linux/releases) or build the distribution bundle from this repository, then run it as your normal desktop user, without `sudo`:

```bash
chmod +x PredSenseLinux-Installer.run
./PredSenseLinux-Installer.run
```

The `.run` file embeds the PredSenseLinux `.deb` and setup script, but **does not contain the OS dependencies or Linuwu-Sense kernel module source**. It needs internet access to install dependencies and headers through APT and clone the module source from GitHub. It builds the module for the running kernel, unless the expected module controls are already present. Automatic module installation stops if Secure Boot is enabled. Installing the module replaces the built-in `acer_wmi` driver. For a manual GUI-only install, use the `.deb` below and run the packaged module helper separately when ready.

From a terminal in the extracted package directory, install the `.deb` with `apt` so dependencies are resolved:

```bash
sudo apt install ./predsenselinux_0.1.12_all.deb
```

If you used `dpkg -i` and it reported missing dependencies, run:

```bash
sudo apt --fix-broken install
```

The package creates the `linuwu_sense` system group. When installation is run through `sudo`, it attempts to add the invoking user to that group. If it could not identify your desktop user, add yourself manually:

```bash
sudo adduser "$USER" linuwu_sense
```

Log out and back in after changing group membership. Do not run PredSenseLinux with `sudo`.

## Install or check the kernel module

The single-file installer runs this step automatically. If installing the `.deb` manually, run the module helper as your normal user:

```bash
/usr/share/predsenselinux/install-kernel-module.sh
```

It skips installation if the expected Predator/Nitro controls are already present. Otherwise it installs build tools and matching headers, checks Secure Boot, clones the upstream source, then runs its `make install`. That process replaces/blacklists `acer_wmi` as described by the upstream project. It requires an internet connection and `sudo` access.

After the module is loaded, enable the profile helper:

```bash
sudo systemctl enable --now linuwu-profile-helper.service
```

Open **PredSenseLinux** from your desktop application menu. The Cooling page offers Auto, Max, and Custom fan modes with animated fan indicators. The Profiles page stores separate AC and battery choices and switches profiles when power changes while the GUI is running. Static lighting offers separate four-zone colors or one shared color across all four zones; dynamic effects are also available. Available controls depend on your firmware and laptop model. Per-key keyboard RGB is not supported by the module.

## Remove

Remove the GUI and helper service with:

```bash
sudo apt remove predsenselinux
```

To also remove the package's generated helper configuration:

```bash
sudo apt purge predsenselinux
```

Removing this package does not uninstall the Linuwu-Sense kernel module and does not delete the `linuwu_sense` group. Follow the upstream module's uninstall instructions separately if you want to remove the driver. Remove your user from the group only if no other installed tool needs it.

## Troubleshooting

- **Profile helper unavailable:** check `systemctl status linuwu-profile-helper.service` and `journalctl -u linuwu-profile-helper.service -b`.
- **Permission denied for hardware controls:** confirm your account is in `linuwu_sense`, then log out and back in.
- **Controls missing:** confirm the driver is loaded and check the available sysfs nodes under `/sys/devices/platform/acer-wmi/`.
- **Module build fails:** install headers matching `uname -r`, reboot into the matching kernel, and rerun `/usr/share/predsenselinux/install-kernel-module.sh`. Secure Boot may require disabling it or manually signing/enrolling the module.
