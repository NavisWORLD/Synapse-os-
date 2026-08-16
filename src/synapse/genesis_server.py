from __future__ import annotations

from . import phone_bootstrap
from .genesis_runtime import InstallerGenesisManager


def main(argv: list[str] | None = None) -> int:
    # Only this dedicated entrypoint swaps in the privileged installer runtime.
    # Normal `synapse.phone_bootstrap` continues using the non-destructive base manager.
    phone_bootstrap.GenesisManager = InstallerGenesisManager
    return phone_bootstrap.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
