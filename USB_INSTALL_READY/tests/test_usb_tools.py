import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools' / 'synapse_usb_flasher.py'
spec = importlib.util.spec_from_file_location('synapse_usb_flasher', MODULE)
flasher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flasher)


class SafetyTests(unittest.TestCase):
    def base_candidate(self):
        return {
            'id': 'disk2',
            'path': '/dev/fake2',
            'name': 'Test USB',
            'size': 16 * 1024 * 1024,
            'bus': 'usb',
            'removable': True,
            'system': False,
            'boot': False,
            'type': 'disk',
        }

    def test_safe_candidate_accepts_only_external_usb_disk(self):
        c = self.base_candidate()
        ok, reason = flasher.safe_candidate(c, 8 * 1024 * 1024)
        self.assertTrue(ok, reason)

    def test_safe_candidate_rejects_non_usb_system_boot_small_and_non_disk(self):
        mutations = [
            ('bus', 'nvme'),
            ('removable', False),
            ('system', True),
            ('boot', True),
            ('type', 'part'),
            ('size', 1024),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                c = self.base_candidate()
                c[key] = value
                ok, _ = flasher.safe_candidate(c, 8 * 1024 * 1024)
                self.assertFalse(ok)

    def test_confirmation_phrase_binds_to_device_identity(self):
        c = self.base_candidate()
        self.assertEqual(flasher.confirmation_phrase(c), 'ERASE USB disk2')


class HashAndWriteTests(unittest.TestCase):
    def test_parse_sha256_sidecar(self):
        digest = 'a' * 64
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'image.iso.sha256'
            p.write_text(f'{digest}  image.iso\n', encoding='utf-8')
            self.assertEqual(flasher.parse_sha256_sidecar(p, 'image.iso'), digest)

    def test_write_and_readback_hash_file_backed_target(self):
        payload = (b'SYNAPSE' * 131071) + b'END'
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'image.iso'
            dst = Path(td) / 'fake-device.bin'
            src.write_bytes(payload)
            dst.write_bytes(b'X' * (len(payload) + 4096))
            flasher.write_image(src, dst, len(payload), progress=None)
            actual = flasher.sha256_prefix(dst, len(payload))
            self.assertEqual(actual, expected)
            self.assertEqual(dst.read_bytes()[:len(payload)], payload)


if __name__ == '__main__':
    unittest.main()

# Downloader selection tests live here so the USB kit can be validated with one command.
DOWNLOADER = ROOT / 'tools' / 'download_release.py'
dspec = importlib.util.spec_from_file_location('download_release', DOWNLOADER)
downloader = importlib.util.module_from_spec(dspec)
dspec.loader.exec_module(downloader)

class ReleaseDownloadTests(unittest.TestCase):
    def test_select_release_assets_requires_parts_and_checksums(self):
        assets = [
            {'name': 'SynapseOS-Nebula-amd64.iso.part-000', 'browser_download_url': 'https://example/0'},
            {'name': 'SynapseOS-Nebula-amd64.iso.part-001', 'browser_download_url': 'https://example/1'},
            {'name': 'SynapseOS-Nebula-amd64.iso.sha256', 'browser_download_url': 'https://example/iso'},
            {'name': 'SynapseOS-Nebula-amd64.iso.parts.sha256', 'browser_download_url': 'https://example/parts'},
            {'name': 'reassemble-usb-installer.ps1', 'browser_download_url': 'https://example/ps1'},
            {'name': 'reassemble-usb-installer.sh', 'browser_download_url': 'https://example/sh'},
            {'name': 'unrelated.txt', 'browser_download_url': 'https://example/no'},
        ]
        selected = downloader.select_installer_assets(assets)
        self.assertEqual([a['name'] for a in selected], [
            'SynapseOS-Nebula-amd64.iso.part-000',
            'SynapseOS-Nebula-amd64.iso.part-001',
            'SynapseOS-Nebula-amd64.iso.parts.sha256',
            'SynapseOS-Nebula-amd64.iso.sha256',
            'reassemble-usb-installer.ps1',
            'reassemble-usb-installer.sh',
        ])

    def test_select_release_assets_rejects_incomplete_release(self):
        with self.assertRaises(ValueError):
            downloader.select_installer_assets([
                {'name': 'SynapseOS-Nebula-amd64.iso.sha256', 'browser_download_url': 'https://example/iso'}
            ])
