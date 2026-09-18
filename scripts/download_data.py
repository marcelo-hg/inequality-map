"""Compatibility entry point from PLAN.md."""
import sys
from pathlib import Path

from inequality_map.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--root", str(Path(__file__).resolve().parents[1]), "download", *sys.argv[1:]]))
