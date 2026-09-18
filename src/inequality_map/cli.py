from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from .build import build, current_database
from .download import download
from .experiments import run_experiment
from .maps import generate_maps
from .validate import validate_database


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproducible inequality source database")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("download", "build"):
        p = sub.add_parser(command)
        p.add_argument("--sources", nargs="+", choices=["wid", "world_bank"])
        p.add_argument("--countries", nargs="+", help="ISO-3 codes; omit for all")
        p.add_argument("--start-year", type=int)
        p.add_argument("--end-year", type=int)
        p.add_argument("--snapshot", type=Path, required=command == "build", help="Raw snapshot path; for download, resumes it")
        if command == "download":
            p.add_argument("--workers", type=int)
        else:
            p.add_argument("--allow-incomplete", action="store_true")
    p = sub.add_parser("validate")
    p.add_argument("--database", type=Path)
    sub.add_parser("current")
    p = sub.add_parser("experiment")
    p.add_argument("scenario", help="Scenario ID from config/scenarios.yml")
    p.add_argument("--year", type=int, help="Source year; defaults to the latest validated year")
    p.add_argument("--database", type=Path)
    p.add_argument("--output", type=Path)
    p = sub.add_parser("maps")
    p.add_argument("--experiment", type=Path, required=True, help="Experiment output directory")
    p.add_argument("--boundaries", type=Path, help="Natural Earth GeoJSON; downloads it when omitted")
    args = parser.parse_args(argv)
    try:
        if args.command in ("download", "build"):
            params = {"sources": args.sources, "countries": args.countries, "start": args.start_year,
                      "end": args.end_year, "snapshot": args.snapshot}
            if args.command == "download":
                if args.workers is not None and not 1 <= args.workers <= 8:
                    parser.error("workers must be between 1 and 8")
                path = download(args.root, workers=args.workers, **params)
                state = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
                return 0 if state["status"] == "complete" else 2
            build(args.root, allow_incomplete=args.allow_incomplete, **params)
        elif args.command == "validate":
            print(json.dumps(validate_database(args.database or current_database(args.root)), indent=2))
        elif args.command == "experiment":
            output, _, _, global_summary = run_experiment(args.root, args.scenario, args.year, args.database, args.output)
            print(f"Published experiment: {output}")
            print(json.dumps(global_summary, indent=2))
        elif args.command == "maps":
            for path in generate_maps(args.root, args.experiment, args.boundaries):
                print(path)
        else:
            print(current_database(args.root))
    except (ValueError, RuntimeError, OSError, duckdb.Error) as exc:
        parser.exit(1, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
