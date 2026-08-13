from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tomllib
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile


class PackageError(RuntimeError):
    pass


@dataclass(frozen=True)
class PackageSpec:
    name: str
    version: str
    source: str
    sha256: str


@dataclass
class Manifest:
    name: str
    version: str
    entry: str
    dependencies: dict[str, str]

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        p = Path(path)
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        pkg = data.get("package", {})
        name = str(pkg.get("name", "")).strip()
        version = str(pkg.get("version", "")).strip()
        entry = str(pkg.get("entry", "main.syn")).strip()
        if not name or not version or not entry.endswith(".syn"):
            raise PackageError("manifest requires package.name, package.version and .syn entry")
        deps = {str(k): str(v) for k, v in dict(data.get("dependencies", {})).items()}
        return cls(name, version, entry, deps)


class RegistryClient:
    """Integrity-checked package client for a simple HTTPS JSON registry."""

    def __init__(self, index_url: str, cache_dir: str | Path | None = None):
        parsed = urlparse(index_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise PackageError("registry index must use https")
        self.index_url = index_url
        self.cache_dir = Path(cache_dir or Path.home() / ".cache" / "synapse" / "packages")

    def fetch_index(self) -> dict[str, Any]:
        req = Request(self.index_url, headers={"User-Agent": "SynapsePkg/2"})
        try:
            with urlopen(req, timeout=10) as response:
                raw = response.read(2_000_001)
        except OSError as exc:
            raise PackageError(f"registry request failed: {exc}") from exc
        if len(raw) > 2_000_000:
            raise PackageError("registry index too large")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackageError("registry index is not valid JSON") from exc
        if not isinstance(data, dict):
            raise PackageError("registry index must be an object")
        return data

    def resolve(self, name: str, version: str | None = None) -> PackageSpec:
        data = self.fetch_index()
        package = data.get("packages", {}).get(name)
        if not isinstance(package, dict):
            raise PackageError(f"package not found: {name}")
        versions = package.get("versions", {})
        if not isinstance(versions, dict) or not versions:
            raise PackageError(f"package has no versions: {name}")
        chosen = version or package.get("latest")
        if not chosen or chosen not in versions:
            raise PackageError(f"version not found: {name}@{chosen}")
        item = versions[chosen]
        url = str(item.get("url", "")); digest = str(item.get("sha256", "")).lower()
        if urlparse(url).scheme != "https" or len(digest) != 64:
            raise PackageError("registry entry must provide HTTPS url and SHA-256")
        return PackageSpec(name, str(chosen), url, digest)

    def install(self, spec: PackageSpec) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_dir / f"{spec.name}-{spec.version}"
        if target.exists():
            return target
        req = Request(spec.source, headers={"User-Agent": "SynapsePkg/2"})
        try:
            with urlopen(req, timeout=20) as response:
                raw = response.read(25_000_001)
        except OSError as exc:
            raise PackageError(f"package download failed: {exc}") from exc
        if len(raw) > 25_000_000:
            raise PackageError("package archive too large")
        actual = hashlib.sha256(raw).hexdigest()
        if actual != spec.sha256:
            raise PackageError("package SHA-256 mismatch")
        with tempfile.TemporaryDirectory(prefix="synpkg-") as td:
            archive = Path(td) / "package.zip"
            archive.write_bytes(raw)
            unpack = Path(td) / "unpack"; unpack.mkdir()
            with zipfile.ZipFile(archive) as zf:
                for member in zf.infolist():
                    rel = Path(member.filename)
                    if rel.is_absolute() or ".." in rel.parts:
                        raise PackageError("unsafe path in package archive")
                zf.extractall(unpack)
            Manifest.load(unpack / "synapse.toml")
            shutil.copytree(unpack, target)
        return target


def write_lock(path: str | Path, specs: list[PackageSpec]) -> None:
    payload = {"lock_version": 1, "packages": [spec.__dict__ for spec in sorted(specs, key=lambda x: x.name)]}
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
