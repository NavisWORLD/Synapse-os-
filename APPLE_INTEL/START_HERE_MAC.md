# Start Here // Intel MacBook Pro

1. Flash the verified Synapse OS amd64 ISO to USB.
2. Power the Mac off.
3. Insert USB, power on, and hold **Option (⌥)**.
4. Choose **EFI Boot**.
5. Prefer the GENESIS/failsafe entry so the kernel includes `synapse.genesis=1`.
6. Run `synapse-apple-diagnostics` first.
7. Run `synapse-apple-preflight`. Do not install unless it reports PASS.
8. Run `synapse-apple-install` to start the existing guarded GENESIS installer API and follow its verified target/image authorization flow.

First-boot acceptance: display/GPU, keyboard, trackpad or external pointer, internal SSD, Wi-Fi/network, audio, battery/AC, Apple SMC telemetry where available, brightness, and suspend behavior.

Broadcom Wi-Fi is a known variable on this Mac generation. A missing Wi-Fi driver is reported as a warning, not hidden. Use Ethernet/USB networking for installation if needed.

EFI recovery uses `RECOVER_SYNAPSE_MAC.sh --esp /dev/<esp> --root /dev/<root>` and writes the fallback x86_64 EFI path without creating Apple NVRAM entries.
