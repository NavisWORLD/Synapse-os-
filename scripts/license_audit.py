#!/usr/bin/env python3
"""Fail closed when Synapse OS first-party licensing or provenance drifts from policy."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ZENODO_DOI = "10.5281/zenodo.17574447"
ZENODO_TITLE_MARKER = "The 12-Dimensional Cosmic Synapse Theory"

REQUIRED_FILES = (
    "LICENSE",
    "LICENSE-HISTORY.md",
    "COMMERCIAL-LICENSING.md",
    "NOTICE",
    "PROVENANCE.md",
    "CITATION.cff",
    "TRADEMARKS.md",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTOR_LICENSE_AGREEMENT.md",
    "CONTRIBUTING.md",
    ".github/pull_request_template.md",
    "docs/LICENSING.md",
)

ROOT_LICENSE_MARKERS = (
    "Cory Davis / NavisWORLD Synapse Source License 1.0",
    "SOURCE-AVAILABLE LICENSE, NOT AN OPEN-SOURCE LICENSE",
    "AI/ML Use",
    "NO PATENT LICENSE",
    "THIRD-PARTY MATERIAL",
    "HISTORICAL VERSIONS",
)

README_MARKERS = (
    "source-available, not open source",
    "COMMERCIAL-LICENSING.md",
    "LICENSE-HISTORY.md",
    "THIRD_PARTY_NOTICES.md",
    "PROVENANCE.md",
    ZENODO_DOI,
)

LICENSING_GUIDE_MARKERS = (
    "Synapse Source License 1.0",
    "source-available license, not an open-source license",
    "Historical MIT versions",
    "Third-party components",
    "PROVENANCE.md",
    ZENODO_DOI,
)

NOTICE_MARKERS = (
    "PROVENANCE.md",
    "CITATION.cff",
    ZENODO_DOI,
)

PROVENANCE_MARKERS = (
    ZENODO_DOI,
    ZENODO_TITLE_MARKER,
    "not represented as the software DOI for Synapse OS",
    "not, by itself",
    "COMMERCIAL-LICENSING.md",
)

CITATION_MARKERS = (
    "cff-version: 1.2.0",
    "title: Synapse OS",
    "references:",
    ZENODO_TITLE_MARKER,
    ZENODO_DOI,
)

# These patterns indicate a current permissive-license declaration, not a
# historical reference. Historical/legal-design files are explicitly excluded.
FORBIDDEN_DECLARATIONS = (
    re.compile(r"(?im)^\s*MIT License\s*$"),
    re.compile(r"(?i)\b(?:is|are)\s+MIT\s+licensed\b"),
    re.compile(r'(?im)^\s*license\s*=\s*"MIT"\s*$'),
    re.compile(r'(?im)^\s*license\s*=\s*\{\s*text\s*=\s*"MIT"\s*\}\s*$'),
)

HISTORICAL_ALLOWLIST = {
    Path("LICENSE"),
    Path("LICENSE-HISTORY.md"),
}

SKIP_PREFIXES = (
    Path(".git"),
    Path("docs/superpowers"),
)

TEXT_SUFFIXES = {
    "",
    ".cff",
    ".md",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".py",
    ".sh",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".rs",
    ".json",
}


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _is_skipped(relative: Path) -> bool:
    if relative in HISTORICAL_ALLOWLIST:
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in SKIP_PREFIXES)


def _iter_first_party_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if _is_skipped(relative):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(relative)
    return files


def _require_markers(errors: list[str], relative: str, markers: tuple[str, ...]) -> None:
    path = ROOT / relative
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{relative} missing marker: {marker}")


def audit() -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required legal file: {relative}")

    _require_markers(errors, "LICENSE", ROOT_LICENSE_MARKERS)
    _require_markers(errors, "README.md", README_MARKERS)
    _require_markers(errors, "docs/LICENSING.md", LICENSING_GUIDE_MARKERS)
    _require_markers(errors, "NOTICE", NOTICE_MARKERS)
    _require_markers(errors, "PROVENANCE.md", PROVENANCE_MARKERS)
    _require_markers(errors, "CITATION.cff", CITATION_MARKERS)

    pyproject = ROOT / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        if "Cory Davis / NavisWORLD Synapse Source License 1.0" not in text:
            errors.append("pyproject.toml does not declare the Synapse Source License")

    cargo = ROOT / "sdk/rust/Cargo.toml"
    if cargo.is_file():
        text = cargo.read_text(encoding="utf-8")
        if 'license-file = "../../LICENSE"' not in text:
            errors.append("sdk/rust/Cargo.toml must reference ../../LICENSE")

    for relative in _iter_first_party_text_files():
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in FORBIDDEN_DECLARATIONS:
            if pattern.search(text):
                errors.append(
                    f"current permissive-license declaration found in {relative}: {pattern.pattern}"
                )
                break

    return sorted(set(errors))


def main() -> int:
    errors = audit()
    if errors:
        print("Synapse license/provenance audit: FAILED", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    print("Synapse license/provenance audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
