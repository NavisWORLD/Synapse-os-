# Synapse OS Architecture Matrix

Synapse OS uses `build/architectures.json` as the machine-readable source of truth for build and VM parameters.

| Architecture | Debian 13 | Synapse state | Kernel package | VM gate |
|---|---|---|---|---|
| `amd64` | supported | `vm-certified` | `linux-image-amd64` | required on PR/main |
| `arm64` | supported | `experimental` | `linux-image-arm64` | manual promotion workflow |
| `riscv64` | supported | `experimental` | `linux-image-riscv64` | manual promotion workflow |

`experimental` means the repository contains build and QEMU boot machinery but Synapse does not claim that architecture passed its full boot gate yet.

## Architecture-neutral checks

```bash
make check
python3 scripts/arch_matrix.py validate
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=amd64 ./build/build.sh
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=arm64 ./build/build.sh
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=riscv64 ./build/build.sh
```

## amd64 required image gate

```bash
sudo env SYNAPSE_ARCH=amd64 ./build/build.sh
sha256sum -c out/*-amd64.iso.sha256
bash scripts/qemu-smoke.sh amd64 out/*-amd64.iso
```

This gate is required by `.github/workflows/build-vm-smoke.yml`.

## ARM64 and RISC-V promotion

Run the GitHub Actions workflow **Experimental architecture VM gate** and select `arm64` or `riscv64`. It performs foreign bootstrap, produces the architecture image, verifies its checksum, then runs the same in-guest `SYNAPSE_VM_READY` contract through architecture-specific QEMU.

Only change an architecture from `experimental` to `vm-certified` after that workflow completes successfully and its evidence artifact is retained.

## Native SDK portability

The C ABI is compiled inside each target image. C++, Rust, and Python adapters consume that ABI rather than embedding amd64 binaries. The repository therefore stores portable source, not architecture-specific compiled libraries.
