"""Compatibility entry point for deterministic experiment choropleths."""
from inequality_map.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["maps", *__import__("sys").argv[1:]]))
