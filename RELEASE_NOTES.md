# PredSenseLinux 1.1.0

## Highlights

- **Module via DKMS** — the Linuwu-Sense kernel module is now registered with
  DKMS (`linuwu-sense/1.0`) and is rebuilt automatically on every kernel upgrade.
  The installer pins driver commit `4483b6c`, which has `strscpy()` for Linux 7.2+
  (where `strncpy()` was removed) and `platform_profile_ops` for 6.17+.
- **Secure Boot works** — the installer generates a local MOK, signs the module and
  queues enrolment with `mokutil`. First boot with Secure Boot still enabled
  requires one reboot to complete the blue MOK manager screen; the module loads
  automatically afterwards.
- **Fresh installs have a working GUI.** The profile helper is now enabled
  unconditionally (it used to be skipped when the module was not installed yet),
  the launcher no longer dies silently if `sg` is missing or the
  `linuwu_sense` group is not there yet, and hidden controls are reported.

## Install (recommended)

```bash
chmod +x PredSenseLinux-Installer.run
./PredSenseLinux-Installer.run   # as your normal desktop user, not sudo
```

## Installer assets in this release

- `predsenselinux_1.1.0_all.deb` — package with the GUI, helper and installer
  scripts (install with `sudo apt install`).
- `PredSenseLinux-Installer.run` — the single-file installer (verified payload
  checksum).
- `README.md` — install, verify, troubleshooting and uninstall notes.

## Notes

- The module is third-party; review the upstream [Linuwu-Sense project](https://github.com/0x7375646F/Linuwu-Sense).
- Helpers live in `/usr/lib/linuwu-profile-helper`, units in `/usr/lib/systemd/system`.
