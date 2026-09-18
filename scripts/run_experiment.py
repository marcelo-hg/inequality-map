"""Compatibility entry point for `python scripts/run_experiment.py hard_equality`."""
from inequality_map.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["experiment", *__import__("sys").argv[1:]]))
