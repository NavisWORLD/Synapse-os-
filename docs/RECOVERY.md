# Recovery Guide

If Synapse OS does not boot after an experiment:

1. Boot the Synapse live USB or another Linux recovery image.
2. Mount the installed root filesystem read/write only when you know which device it is.
3. Inspect `journalctl` from the installed system and recent package/kernel changes.
4. Disable experimental Synapse services from the chroot if necessary.
5. Restore from backup rather than improvising destructive partition commands.

The tracked Synapse defaults intentionally avoid direct disk formatting scripts. Disk layout is delegated to the graphical installer where the user can review the target explicitly.
