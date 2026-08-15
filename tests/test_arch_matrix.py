import unittest
from pathlib import Path

from scripts import arch_matrix


class ArchMatrixTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(arch_matrix.normalize_arch("x86_64"), "amd64")
        self.assertEqual(arch_matrix.normalize_arch("aarch64"), "arm64")
        self.assertEqual(arch_matrix.normalize_arch("riscv64"), "riscv64")

    def test_kernel_packages(self):
        reg = arch_matrix.load_registry(Path("build/architectures.json"))
        self.assertEqual(reg["architectures"]["amd64"]["kernel_package"], "linux-image-amd64")
        self.assertEqual(reg["architectures"]["arm64"]["kernel_package"], "linux-image-arm64")
        self.assertEqual(reg["architectures"]["riscv64"]["kernel_package"], "linux-image-riscv64")

    def test_unknown_rejected(self):
        with self.assertRaises(ValueError):
            arch_matrix.profile_for_arch("sparc64", {"schema_version": 1, "architectures": {}})


if __name__ == "__main__":
    unittest.main()
