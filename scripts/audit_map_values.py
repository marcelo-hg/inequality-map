"""Reconcile saved map inputs with database percentile bins; never edit results."""
from __future__ import annotations

import json
import math
from pathlib import Path

import duckdb

from inequality_map.common import digest_file, write_json
from inequality_map.experiments import _validated_distributions
from inequality_map.maps import _global_summary

ROOT = Path(__file__).resolve().parents[1]


def audit():
    cache, hashes, reports = {}, {}, []
    for path in sorted((ROOT / "outputs/experiments").glob("*/metadata.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        rows = json.loads((path.parent / "country_results.json").read_text(encoding="utf-8"))
        errors = []

        def check(label, actual, expected, *, absolute=1e-5):
            if not math.isclose(actual, expected, rel_tol=1e-8, abs_tol=absolute):
                errors.append({"field": label, "stored": actual, "recomputed": expected})

        database = meta["database"]
        if database not in hashes:
            hashes[database] = digest_file(database)
        if hashes[database] != meta["database_sha256"]:
            raise ValueError(f"Source database checksum changed: {database}")
        key = (database, meta["year"], meta["population_basis"])
        if key not in cache:
            with duckdb.connect(database, read_only=True) as db:
                cache[key] = _validated_distributions(db, meta["year"], meta["population_basis"])
        available, _, ppp = cache[key]
        distributions = {row["iso3"]: available[row["iso3"]] for row in rows}
        flat = [item for bins in distributions.values() for item in bins]
        population = math.fsum(item["population"] for item in flat)
        mean = math.fsum(item["income_before_ppp"] * item["population"] for item in flat) / population
        rule = meta["scenario"].get("reference", {"scope": "global", "statistic": "mean"})
        reference = mean
        if rule["statistic"] == "median":
            cumulative = 0
            for item in sorted(flat, key=lambda item: item["income_before_ppp"]):
                cumulative += item["population"]
                if cumulative >= population / 2:
                    reference = item["income_before_ppp"]
                    break
        if rule["scope"] == "global":
            check("reference_income", meta["reference"]["value_ppp"], reference)
        for field in ("ppp_currency", "price_year"):
            recorded = meta.get("ppp", {}).get(field, meta["reference"].get(field))
            if recorded is not None and recorded != ppp[field]:
                errors.append({"field": field, "stored": recorded, "recomputed": ppp[field]})
        transform = meta["scenario"]["redistribution"]
        tolerance = meta["scenario"].get("classification", {}).get("unchanged_tolerance", 0)
        for row in rows:
            iso = row["iso3"]
            bins = distributions[iso]
            pop = math.fsum(item["population"] for item in bins)
            country_mean = math.fsum(item["population"] * item["income_before_ppp"] for item in bins) / pop
            local_ref = country_mean if rule["scope"] == "national" else reference
            target = local_ref * transform.get("target_multiplier", 1)
            low = target if transform["type"] == "equal" else local_ref * transform["floor_multiplier"]
            high = target if transform["type"] == "equal" else local_ref * transform["ceiling_multiplier"]
            counts = {kind: 0 for kind in ("winner", "unchanged", "loser")}
            new_income = 0
            for item in bins:
                old = item["income_before_ppp"]
                category = "winner" if old < low * (1-tolerance) else "loser" if old > high * (1+tolerance) else "unchanged"
                counts[category] += item["population"]
                new_income += min(max(old, low), high) * item["population"]
            check(f"{iso}.population", row.get("population", row["adult_population"]), pop)
            check(f"{iso}.original_mean", row["original_mean"], country_mean)
            check(f"{iso}.new_mean", row["new_mean"], new_income / pop)
            check(f"{iso}.income_before", row["income_before"], country_mean * pop)
            check(f"{iso}.income_after", row["income_after"], new_income)
            if row.get("target_income_ppp") is not None:
                check(f"{iso}.target_income", row["target_income_ppp"], target)
            for kind, count in counts.items():
                check(f"{iso}.{kind}_share", row[f"{kind}_share"], count / pop, absolute=1e-9)
                check(f"{iso}.{kind}_population", row[f"{kind}_population"], count)
        try:
            summary = _global_summary(path.parent, rows)
        except ValueError as exc:
            errors.append({"field": "global_summary", "error": str(exc)})
            summary = {}
        reports.append({"experiment": path.parent.name, "countries": len(rows), "status": "passed" if not errors else "failed",
                        "source_ppp": ppp, "global_summary": summary, "errors": errors})
    comparisons = json.loads((ROOT / "outputs/reference_tables/experiment_comparison.json").read_text(encoding="utf-8"))
    comparison_errors = []
    for entry in comparisons:
        data = json.loads((Path(entry["experiment_directory"]) / "country_results.json").read_text(encoding="utf-8"))
        row = next(row for row in data if row["iso3"] == entry["iso3"])
        meta = json.loads((Path(entry["experiment_directory"]) / "metadata.json").read_text(encoding="utf-8"))
        for field in ("winner_share", "loser_share", "unchanged_share", "target_income_ppp"):
            value = row.get(field, meta["reference"].get("value_ppp"))
            if not math.isclose(value, entry[field], rel_tol=1e-9, abs_tol=1e-9):
                comparison_errors.append({"scenario": entry["scenario"], "iso3": entry["iso3"], "field": field})
    report = {"experiments": reports, "comparison_rows_checked": len(comparisons), "comparison_errors": comparison_errors,
              "status": "passed" if all(r["status"] == "passed" for r in reports) and not comparison_errors else "failed"}
    write_json(ROOT / "outputs/reports/map_value_audit.json", report)
    print(json.dumps({"status": report["status"], "experiments": len(reports), "country_results": sum(r["countries"] for r in reports),
                      "comparison_rows": len(comparisons), "failures": [r for r in reports if r["errors"]]}, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if audit()["status"] == "passed" else 1)
