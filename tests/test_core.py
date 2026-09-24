import unittest
from unittest import mock

from synapse import core


class CoreTests(unittest.TestCase):
    def test_profile_map(self):
        self.assertEqual(core.PROFILE_MAP["pulse"], "performance")
        self.assertEqual(core.PROFILE_MAP["quiet"], "power-saver")

    def test_cosmos_ports_are_unique(self):
        ports = list(core.COSMOS_PORTS.values())
        self.assertEqual(len(ports), len(set(ports)))
        self.assertIn(11434, ports)
        self.assertIn(8081, ports)

    @mock.patch("synapse.core.shutil.which", return_value=None)
    def test_profile_gracefully_handles_missing_powerprofilesctl(self, _):
        result = core.set_profile("balanced")
        self.assertFalse(result["ok"])
        self.assertEqual(result["target"], "balanced")

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            core.set_profile("warp-11")

    def test_benchmark_returns_positive_rates(self):
        result = core.benchmark(size_mb=1)
        self.assertGreater(result["sha256_mib_s"], 0)
        self.assertGreater(result["temp_write_mib_s"], 0)

    @mock.patch("synapse.core.Path.is_socket", return_value=False)
    def test_doctor_includes_fail_soft_resident_zeref_section(self, _):
        result = core.doctor()
        self.assertIn("zeref", result)
        self.assertIn(result["zeref"]["state"], {"OFFLINE", "DEGRADED", "READY", "READY_NO_IBM", "READY_STALE_IBM"})
        self.assertFalse(result["zeref"]["socket_reachable"])
        self.assertIn("credential_exposed_to_subject", result["zeref"])
        self.assertFalse(result["zeref"]["credential_exposed_to_subject"])
