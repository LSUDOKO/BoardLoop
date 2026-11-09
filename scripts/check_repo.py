#!/usr/bin/env python3
"""Pre-release repo check (catalog rule 17 + secrets): no binaries, bytecode, build outputs or
Wokwi tokens in tracked files. Exit 1 on any finding."""
import re
import subprocess
import sys

BAD_EXT = (".bin", ".elf", ".hex", ".pyc", ".pyo", ".so", ".dll", ".exe", ".dylib", ".wasm", ".zip", ".a")
MAGIC = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\x00asm")
TOKEN = re.compile(rb"wok_[A-Za-z0-9]{30,}")


def main() -> int:
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    problems = []
    for f in files:
        if f.endswith(BAD_EXT) or "/build/" in f or f.startswith("build/"):
            problems.append(f"{f}: build output or binary file type")
            continue
        try:
            data = open(f, "rb").read()
        except OSError:
            continue
        if data.startswith(MAGIC):
            problems.append(f"{f}: executable header")
        if TOKEN.search(data):
            problems.append(f"{f}: looks like a Wokwi token")
    for p in problems:
        print("✗", p)
    print(f"checked {len(files)} tracked files: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
