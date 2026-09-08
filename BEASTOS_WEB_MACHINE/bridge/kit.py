from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import urllib.parse
import urllib.request
import zipfile

MANIFEST_SCHEMA = "synapse-beast-kit-v1"
MAX_KIT_BYTES = 64 * 1024 * 1024


def load_manifest(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unsupported Beast kit manifest")
    required = {"tag", "commit", "asset", "download_url", "size", "sha256", "prerelease", "integration_api"}
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"Beast kit manifest missing fields: {missing}")
    if not isinstance(data["size"], int) or not (0 < data["size"] <= MAX_KIT_BYTES):
        raise ValueError("invalid Beast kit size")
    digest = str(data["sha256"]).lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("invalid Beast kit SHA-256")
    parsed = urllib.parse.urlparse(str(data["download_url"]))
    expected_path = f"/NavisWORLD/The-beast-box-/releases/download/{data['tag']}/{data['asset']}"
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.path != expected_path:
        raise ValueError("Beast kit download URL is not the pinned GitHub release asset")
    return data


def _digest(path: Path) -> str:
    h = sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_file(path: Path, manifest: dict) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Beast kit is missing or is a symlink")
    actual_size = path.stat().st_size
    expected_size = int(manifest["size"])
    if actual_size != expected_size:
        raise ValueError(f"Beast kit size mismatch: expected {expected_size}, got {actual_size}")
    actual_sha = _digest(path)
    expected_sha = str(manifest["sha256"]).lower()
    if actual_sha != expected_sha:
        raise ValueError("Beast kit SHA-256 mismatch")
    return {"path": str(path), "size": actual_size, "sha256": actual_sha}


def _safe_member(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise ValueError("unsafe Beast kit member name")
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts or any(":" in part for part in member.parts):
        raise ValueError(f"unsafe Beast kit member: {name}")
    return member


def safe_extract(archive: Path, destination: Path) -> list[str]:
    archive = Path(archive)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            member = _safe_member(info.filename)
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise ValueError(f"symlink not allowed in Beast kit: {info.filename}")
            target = (destination / Path(*member.parts)).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError(f"Beast kit member escapes destination: {info.filename}") from exc
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info, "r") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
            extracted.append(member.as_posix())
    return extracted


def _download(url: str, destination: Path, expected_size: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "SynapseOS-BeastKit/1"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("xb") as target:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > expected_size or total > MAX_KIT_BYTES:
                    raise ValueError("Beast kit download exceeded pinned size")
                target.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def materialize_kit(
    manifest_path: Path,
    destination: Path,
    *,
    source_file: Path | None = None,
    extract_to: Path | None = None,
) -> dict:
    manifest = load_manifest(manifest_path)
    destination = Path(destination)
    if source_file is not None:
        source_file = Path(source_file)
        verify_file(source_file, manifest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_file.resolve() != destination.resolve():
            shutil.copyfile(source_file, destination)
    elif not destination.is_file():
        _download(str(manifest["download_url"]), destination, int(manifest["size"]))
    receipt = verify_file(destination, manifest)
    receipt.update({
        "tag": manifest["tag"],
        "commit": manifest["commit"],
        "asset": manifest["asset"],
        "prerelease": bool(manifest["prerelease"]),
    })
    if extract_to is not None:
        members = safe_extract(destination, extract_to)
        expected_wheel = manifest.get("expected_wheel")
        if expected_wheel and expected_wheel not in members:
            raise ValueError(f"verified Beast kit does not contain expected wheel: {expected_wheel}")
        receipt["extract_to"] = str(Path(extract_to))
        receipt["members"] = members
    return receipt
