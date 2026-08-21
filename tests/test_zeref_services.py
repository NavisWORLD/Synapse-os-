from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZerefServiceContractTests(unittest.TestCase):
    def test_runtime_is_user_service_without_ibm_credential_authority(self):
        unit = (ROOT / "rootfs/usr/lib/systemd/user/zeref-runtime.service").read_text(encoding="utf-8")
        launcher = (ROOT / "rootfs/usr/local/lib/synapse/zeref-runtime").read_text(encoding="utf-8")
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ExecStart=/usr/local/lib/synapse/zeref-runtime", unit)
        self.assertNotIn("LoadCredential", unit)
        self.assertNotIn("IBM_QUANTUM_TOKEN", unit)
        self.assertNotIn("IBM_QUANTUM_TOKEN", launcher)
        self.assertNotIn("sudo", launcher)
        self.assertNotIn("--allow-run", launcher)

    def test_broker_is_separate_fixed_purpose_credential_consumer(self):
        unit = (ROOT / "rootfs/etc/systemd/system/zeref-ibm-broker.service").read_text(encoding="utf-8")
        launcher = (ROOT / "rootfs/usr/local/lib/synapse/zeref-ibm-broker").read_text(encoding="utf-8")
        self.assertIn("Type=oneshot", unit)
        self.assertIn("LoadCredential=IBM_QUANTUM_TOKEN:/etc/synapse/secrets/ibm-quantum-token", unit)
        self.assertIn("ConditionPathExists=/etc/synapse/secrets/ibm-quantum-token", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ReadWritePaths=/var/lib/synapse/zeref/ibm", unit)
        self.assertIn("CREDENTIALS_DIRECTORY", launcher)
        self.assertIn("IBM_QUANTUM_TOKEN", launcher)
        self.assertNotIn("full-zeref", launcher)
        self.assertNotIn("submit", launcher.lower())

    def test_pinned_broker_configuration_has_no_secret(self):
        config = (ROOT / "rootfs/etc/synapse/zeref-ibm.json").read_text(encoding="utf-8")
        self.assertIn("da1l0maein7c73bdi2d0", config)
        self.assertIn("ibm_marrakesh", config)
        self.assertIn("8ccea7c430e7e42a664d92ce99f8b8107b1983f2e5710e2763aef9c3458c4c85", config)
        self.assertNotIn("IBM_QUANTUM_TOKEN", config)
        self.assertNotIn("token", config.lower())

    def test_runtime_configuration_selects_qc67_native_trinity(self):
        config = (ROOT / "rootfs/etc/synapse/zeref.json").read_text(encoding="utf-8")
        self.assertIn("cosmos_serve.py", config)
        self.assertIn("spark_cst.pt", config)
        self.assertIn('"native_enabled": true', config)
        self.assertIn("/var/lib/synapse/zeref/ibm/latest.json", config)


if __name__ == "__main__":
    unittest.main()
