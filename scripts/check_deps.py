#!/usr/bin/env python3
"""Check this interpreter without requiring third-party packages."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


def check():
    items = {"python": {"version": ".".join(map(str, sys.version_info[:3])),
                        "ok": sys.version_info >= (3, 10)}}
    for module, distribution, minimum, ceiling in [
        ("PIL", "Pillow", (9, 5), 13), ("numpy", "numpy", (1, 24), 3)
    ]:
        try:
            importlib.import_module(module)
            version = importlib.metadata.version(distribution)
            parts = tuple(int(x) for x in version.split(".")[:2])
            items[distribution] = {"version": version,
                                   "ok": parts >= minimum and parts[0] < ceiling}
        except Exception as exc:
            items[distribution] = {"ok": False, "error": str(exc)}
    return items


def main():
    result = check()
    result["executable"] = sys.executable
    result["ready"] = all(item["ok"] for item in result.values() if isinstance(item, dict))
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    result["install_command"] = subprocess.list2cmdline(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["ready"] else 3


if __name__ == "__main__":
    sys.exit(main())
