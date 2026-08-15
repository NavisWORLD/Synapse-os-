# Synapse OS Hardware Certification

Hardware certification is evidence-based. A machine may be a known target before it is certified, but `physical-certified` is reserved for a real-device acceptance run.

## Reference Hardware #1

- Profile: `asus-cx1700cka-gallop`
- Retail family: ASUS Chromebook CX1700CKA
- ChromeOS board/HWID token: `GALLOP`
- Architecture: `amd64`
- Current state: `physical-target`

The machine-readable profile lives in `hardware/profiles.json`. Synapse runtime detection lives in `src/synapse/hardware.py` and prefers the ChromeOS HWID when available.

## Physical acceptance checklist

Record evidence for every item before promoting the profile to `physical-certified`:

- [ ] HWID contains `GALLOP` and runtime architecture normalizes to `amd64`
- [ ] Synapse OS live image reaches the desktop
- [ ] Internal storage is visible without I/O errors
- [ ] Keyboard and touchpad work
- [ ] Internal display reaches native usable resolution
- [ ] Wi-Fi associates and transfers data
- [ ] Audio output works
- [ ] Battery percentage is reported
- [ ] Suspend and resume complete without a forced reboot
- [ ] Calamares installer launches
- [ ] Installed system reboots into Synapse OS
- [ ] `synapse status` and `synapse doctor` pass
- [ ] `libsynapse_abi` reports ABI version 1
- [ ] Phone Bootstrap connects and reads the laptop
- [ ] COSMOS install/activation flow completes or reports a specific unsupported dependency

## Promotion rule

After the checklist passes, attach logs/screenshots/checksums to the project evidence and change only the corresponding profile's `certification_state` from `physical-target` to `physical-certified`.

Firmware modification and write-protection changes are separate preparation procedures and are not automated by the certification API or Phone Bootstrap.
