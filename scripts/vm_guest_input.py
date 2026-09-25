#!/usr/bin/env python3
"""Send physical keyboard events directly to the disposable QEMU guest.

The prior host-level xdotool test could hover the GTK window but did not
deliver usable key/click events to the guest. HMP 'sendkey' is a QEMU-defined
guest input path. Only test-controlled key sequences are accepted.
"""
from __future__ import annotations

import argparse
import socket
import sys
import time


def monitor(path: str, commands: list[str]) -> str:
    transcript = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(6)
        sock.connect(path)
        try:
            transcript.append(sock.recv(8192).decode(errors="replace"))
        except TimeoutError:
            pass
        for command in commands:
            sock.sendall(("sendkey " + command + "\n").encode("ascii"))
            time.sleep(0.13)
            sock.settimeout(0.25)
            try:
                transcript.append(sock.recv(8192).decode(errors="replace"))
            except TimeoutError:
                pass
    output = "".join(transcript)
    if any(word in output.lower() for word in ("unknown key", "invalid key", "invalid parameter")):
        raise RuntimeError(output)
    return output


def encode_text(value: str) -> list[str]:
    codes = {" ": "spc", "-": "minus", ".": "dot", "/": "slash"}
    commands = []
    for char in value:
        if "a" <= char <= "z" or "0" <= char <= "9":
            commands.append(char)
        elif char in codes:
            commands.append(codes[char])
        else:
            raise ValueError(f"unsupported guest test character: {char!r}")
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket_path")
    parser.add_argument("mode", choices=("key", "type"))
    parser.add_argument("value")
    args = parser.parse_args()
    commands = [args.value] if args.mode == "key" else encode_text(args.value)
    response = monitor(args.socket_path, commands)
    print(f"sent {len(commands)} real guest key event(s) via QEMU HMP: {args.mode} {args.value}")
    print(response[-3500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
