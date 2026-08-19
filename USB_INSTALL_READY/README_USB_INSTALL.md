# Synapse OS — ready-to-flash computer kit

The payload is distributed through GitHub Releases as ordered parts because the completed ISO may exceed GitHub's per-asset size limit. This folder contains the downloader, reassembly helpers, checksum tools, and a Synapse-specific removable-USB raw writer.

The expected flow is:

```text
GitHub Release
   ↓ download verified parts
SynapseOS-Nebula-amd64.iso.part-000 ...
   ↓ reassemble + SHA-256
SynapseOS-Nebula-amd64.iso
   ↓ raw write + full read-back verification
BOOTABLE USB VERIFIED
   ↓ UEFI Boot Menu
Synapse live environment / GENESIS installer
   ↓
Synapse OS internal installation
```

For a third-party writer, Rufus and balenaEtcher are valid alternatives after the ISO has been reconstructed and verified.
