# PredSenseLinux 1.1.0 Debian package

PredSenseLinux is a desktop control center for supported Acer Predator and Nitro laptops. It uses
the Linuwu-Sense kernel module for hardware access. This package installs the GUI, the restricted
profile helper service, the desktop launcher, and the module installer/uninstaller scripts.

The kernel module is third-party reverse-engineered software and is not bundled in the `.deb` or
the `.run`. During installation the module script downloads a pinned Linuwu-Sense commit, builds
it with DKMS for the running kernel, signs it when Secure Boot is on, and configures the system.

## Requirements

- Kali, Debian, Ubuntu, or another `apt`-based distribution using systemd and a graphical desktop.
- A supported Acer Predator or Nitro laptop.
- Internet access, headers for the running kernel, and `sudo`.
- Secure Boot may stay enabled; the first install needs one reboot to enrol a local MOK.

## Install

The single-file installer embeds this package and the setup script:

```bash
chmod +x PredSenseLinux-Installer.run
./PredSenseLinux-Installer.run
```

Run it as your normal desktop user, without `sudo`. It verifies its payload checksum, installs the
package, then installs the kernel module. If it ends with "reboot required", reboot and complete
the blue MOK manager screen (`Enroll MOK -> Continue -> Reboot`).

To install the package on its own:

```bash
sudo apt install ./predsenselinux_1.1.0_all.deb
/usr/share/predsenselinux/install-kernel-module.sh
```

The package creates the `linuwu_sense` group, adds the invoking `sudo` user, and enables the
profile helper immediately — the helper is designed to run before the module exists.

Log out and back in after installation so the session picks up the group. Do not run
PredSenseLinux with `sudo`.

## Kernel module

`/usr/share/predsenselinux/install-kernel-module.sh`:

1. Installs `git`, `build-essential`, `dkms`, `mokutil` and matching kernel headers.
2. Fetches the pinned Linuwu-Sense commit into `/usr/src/linuwu-sense-1.0`.
3. Creates `~/module-signing/MOK.{priv,der}` and queues enrolment when Secure Boot is enabled.
4. Runs `dkms add/build/install`, so kernel upgrades rebuild the module automatically.
5. Blacklists `acer_wmi`, loads `linuwu_sense` at boot, creates the group and `systemd-tmpfiles`
   permissions, and enables the profile helper.

It exits `0` when the module is loaded, `3` when a reboot is required to finish Secure Boot
enrolment, and non-zero on failure. Rerun it any time; it is idempotent.

`/usr/share/predsenselinux/uninstall-kernel-module.sh` removes the DKMS registration and
configuration, then restores `acer_wmi`.

## Verify

```bash
dkms status | grep linuwu
systemctl is-enabled linuwu-profile-helper.service
systemctl is-active linuwu-profile-helper.service
stat -c '%A %U:%G %n' /run/linuwu-profile-helper/profile.sock
```

## Remove the package

```bash
sudo apt remove --purge predsenselinux
```

Removing the package leaves the kernel module in place. Remove it first with
`/usr/share/predsenselinux/uninstall-kernel-module.sh` if you want both gone.
