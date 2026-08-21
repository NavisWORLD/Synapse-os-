from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZerefImageContractTests(unittest.TestCase):
    def test_build_stages_pinned_beastbox_and_verified_qc67_assets(self):
        build = (ROOT / "build/build.sh").read_text(encoding="utf-8")
        self.assertIn("ZEREF_BEASTBOX_COMMIT", build)
        self.assertIn("NavisWORLD/The-beast-box-", build)
        self.assertIn("phera-ra/QC67_cosmo", build)
        self.assertIn("955805d45f7b407ef5cc9b6efe178d9a5f63df5b32eaf539d9aedcbb2967f1dc", build)
        self.assertIn("02a509f9c2a20f63c38dca186c082bfdc2603aa8b6f1f903ec19a0e709218d87", build)
        self.assertIn("aa0cb13c1e67d459db280a53b6407dfc2b5b5f3fd6f640bc43686b70d799acd1", build)

    def test_chroot_hook_installs_full_zeref_without_embedding_a_credential(self):
        hook = (ROOT / "build/hooks/040-zeref.hook.chroot").read_text(encoding="utf-8")
        self.assertIn("/usr/src/cosmos-beast-box", hook)
        self.assertIn("full-zeref --help", hook)
        self.assertNotIn("IBM_QUANTUM_TOKEN=", hook)
        self.assertNotIn("ibm-quantum-token", hook)

    def test_vm_smoke_certifies_resident_integration_payload(self):
        smoke = (ROOT / "rootfs/usr/local/lib/synapse/vm-smoke").read_text(encoding="utf-8")
        self.assertIn("zeref-python-package", smoke)
        self.assertIn("full-zeref-command", smoke)
        self.assertIn("zeref-runtime-unit", smoke)
        self.assertIn("zeref-ibm-broker-unit", smoke)
        self.assertIn("SYNAPSE_ZEREF_READY", smoke)

    def test_package_list_contains_native_model_runtime_dependency(self):
        packages = (ROOT / "build/config/package-lists/synapse.list.chroot").read_text(encoding="utf-8").splitlines()
        self.assertIn("python3-torch", packages)


if __name__ == "__main__":
    unittest.main()
