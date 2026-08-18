from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_usb_release_workflow_and_guide_exist():
    workflow = ROOT / ".github" / "workflows" / "release-usb-installer.yml"
    guide = ROOT / "USB_INSTALL.md"

    assert workflow.exists(), "USB installer release workflow is missing"
    assert guide.exists(), "USB installation guide is missing"


def test_usb_release_workflow_publishes_iso_and_checksum():
    workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in workflow
    assert "SynapseOS-*-amd64.iso" in workflow
    assert "*.iso.sha256" in workflow
    assert "gh release" in workflow
    assert "build/build.sh" in workflow
    assert "genesis-installed-vm-smoke.sh" in workflow


def test_usb_guide_documents_genesis_and_safe_flashing():
    guide = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")

    assert "GENESIS" in guide
    assert "GALLOP" in guide
    assert "SHA-256" in guide
    assert "Rufus" in guide
    assert "balenaEtcher" in guide
    assert "dd" in guide
    assert "all data on the USB" in guide
