from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UsbFlashHtmlTests(unittest.TestCase):
    def test_flash_usb_html_has_explicit_state_machine_and_hold_gate(self) -> None:
        html = (ROOT / "phone-bootstrap" / "FLASH_USB.html").read_text(encoding="utf-8")
        for state in (
            "CAPABILITY CHECK",
            "DEVICE SELECTION",
            "IMAGE READY",
            "PREFLIGHT",
            "ARMED",
            "FLASHING",
            "VERIFYING",
            "BOOTABLE USB VERIFIED",
            "FAILED",
        ):
            self.assertIn(state, html)
        self.assertIn("const HOLD_MS = 2500", html)
        self.assertIn("HOLD TO FLASH USB", html)

    def test_html_probes_webusb_and_secure_context(self) -> None:
        html = (ROOT / "phone-bootstrap" / "FLASH_USB.html").read_text(encoding="utf-8")
        self.assertIn("navigator.usb", html)
        self.assertIn("isSecureContext", html)
        self.assertIn("requestDevice", html)
        self.assertIn("claimInterface", html)
        self.assertIn("SecurityError", html)

    def test_direct_mode_is_restricted_to_usb_mass_storage_bot_scsi(self) -> None:
        html = (ROOT / "phone-bootstrap" / "FLASH_USB.html").read_text(encoding="utf-8")
        self.assertIn("MSC_CLASS = 0x08", html)
        self.assertIn("SCSI_SUBCLASS = 0x06", html)
        self.assertIn("BOT_PROTOCOL = 0x50", html)
        self.assertIn("0x43425355", html)  # CBW signature
        self.assertIn("0x53425355", html)  # CSW signature
        self.assertIn("0x25", html)  # READ CAPACITY(10)
        self.assertIn("0x2a", html.lower())  # WRITE(10)
        self.assertIn("0x28", html)  # READ(10)
        self.assertIn("0x35", html)  # SYNCHRONIZE CACHE(10)

    def test_html_hashes_before_write_and_readback_before_success(self) -> None:
        html = (ROOT / "phone-bootstrap" / "FLASH_USB.html").read_text(encoding="utf-8")
        self.assertIn("IncrementalSHA256", html)
        self.assertIn("verifyImageBeforeFlash", html)
        self.assertIn("verifyDirectReadback", html)
        self.assertIn("setState('BOOTABLE USB VERIFIED')", html)
        success_index = html.index("setState('BOOTABLE USB VERIFIED')")
        verify_index = html.index("await verifyDirectReadback")
        self.assertLess(verify_index, success_index)
        self.assertNotIn("simulateSuccess", html)
        self.assertNotIn("fakeSuccess", html)

    def test_helper_adapter_uses_fixed_purpose_routes(self) -> None:
        html = (ROOT / "phone-bootstrap" / "FLASH_USB.html").read_text(encoding="utf-8")
        for route in (
            "/v1/health",
            "/v1/capabilities",
            "/v1/devices",
            "/v1/image",
            "/v1/preflight",
            "/v1/image/prepare",
            "/v1/flash/arm",
            "/v1/flash/start",
            "/v1/flash/status",
            "/v1/flash/receipt",
        ):
            self.assertIn(route, html)
        self.assertNotIn("/shell", html)
        self.assertNotIn("/exec", html)

    def test_packaging_contract(self) -> None:
        launcher = ROOT / "rootfs" / "usr" / "local" / "bin" / "synapse-usb-flash-server"
        self.assertTrue(launcher.exists())
        build = (ROOT / "build" / "build.sh").read_text(encoding="utf-8")
        self.assertIn("FLASH_USB.html", build)
        self.assertIn("usr/share/synapse/FLASH_USB.html", build)
        # The privileged raw writer must remain owner-started rather than enabled on every Synapse boot.
        self.assertFalse((ROOT / "rootfs" / "etc" / "systemd" / "system" / "multi-user.target.wants" / "synapse-usb-flash.service").exists())

    def test_documentation_links_phone_flasher(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        usb = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("FLASH_USB.md", readme)
        self.assertIn("FLASH_USB.md", usb)
        self.assertTrue((ROOT / "FLASH_USB.md").exists())


if __name__ == "__main__":
    unittest.main()
