from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

LC_DYLIB_COMMANDS = {0x0C, 0x0D, 0x18 | 0x80000000, 0x1F | 0x80000000, 0x20, 0x23 | 0x80000000}
CPU_TYPES = {0x01000007: "x86_64", 0x0100000C: "arm64", 7: "x86", 12: "arm"}
FILE_TYPES = {1: "object", 2: "executable", 6: "dylib", 8: "bundle", 10: "dsym", 11: "kext"}


def _invalid(reason: str) -> dict[str, Any]:
    return {"valid": False, "reason": reason, "bits": None, "endian": None, "architecture": "unknown", "file_type": "unknown", "dependencies": []}


def inspect_macho(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError as exc:
        return _invalid(f"unreadable: {exc}")
    if len(data) < 4:
        return _invalid("file too small")
    magic = data[:4]
    if magic == b"\xcf\xfa\xed\xfe":
        endian, bits = "little", 64
        fmt = "<IiiIIIII"
        header_size = 32
    elif magic == b"\xfe\xed\xfa\xcf":
        endian, bits = "big", 64
        fmt = ">IiiIIIII"
        header_size = 32
    elif magic in {b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"}:
        return _invalid("32-bit Mach-O is outside Apple Intel bridge v1")
    elif magic in {b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}:
        return _invalid("FAT/universal Mach-O is not parsed by bridge v1")
    else:
        return _invalid("not a Mach-O file")
    if len(data) < header_size:
        return _invalid("truncated Mach-O header")
    try:
        _magic, cputype, _cpusubtype, filetype, ncmds, sizeofcmds, _flags, _reserved = struct.unpack_from(fmt, data, 0)
    except struct.error:
        return _invalid("truncated Mach-O header")
    if header_size + sizeofcmds > len(data):
        return _invalid("load-command region exceeds file size")
    dependencies: list[str] = []
    offset = header_size
    prefix = "<" if endian == "little" else ">"
    for _ in range(ncmds):
        if offset + 8 > len(data):
            return _invalid("truncated load command")
        cmd, cmdsize = struct.unpack_from(prefix + "II", data, offset)
        if cmdsize < 8 or offset + cmdsize > len(data):
            return _invalid("invalid load-command size")
        if cmd in LC_DYLIB_COMMANDS:
            if cmdsize < 24:
                return _invalid("truncated dylib command")
            name_offset = struct.unpack_from(prefix + "I", data, offset + 8)[0]
            if name_offset < 24 or name_offset >= cmdsize:
                return _invalid("invalid dylib name offset")
            start = offset + name_offset
            end = data.find(b"\0", start, offset + cmdsize)
            if end < 0:
                end = offset + cmdsize
            dependencies.append(data[start:end].decode("utf-8", errors="replace"))
        offset += cmdsize
    return {
        "valid": True,
        "reason": None,
        "bits": bits,
        "endian": endian,
        "architecture": CPU_TYPES.get(cputype & 0xFFFFFFFF, f"cpu:0x{cputype & 0xFFFFFFFF:08x}"),
        "file_type": FILE_TYPES.get(filetype, f"type:{filetype}"),
        "dependencies": dependencies,
    }


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Inspect one thin Mach-O file without executing it")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    result = inspect_macho(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
