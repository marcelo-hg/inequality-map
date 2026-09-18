"""Compare new equality scenarios with matching global-mean baseline experiments."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "outputs/experiments"
REFERENCE_COUNTRIES = ("BRA", "USA", "FRA", "CHN", "NOR", "IND", "NGA")
NEW_SCENARIOS = (
    "global_median_target", "national_mean_equalization",
    "global_median_target_full_population", "national_mean_equalization_full_population",
)


def records():
    found = []
    for path in EXPERIMENTS.glob("*/metadata.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata["scenario_id"] not in NEW_SCENARIOS + ("hard_equality", "hard_equality_full_population"):
            continue
        found.append((path.parent, metadata))
    return found


def matching(candidates, scenario_id, selected):
    matches = [(path, metadata) for path, metadata in candidates
               if metadata["scenario_id"] == scenario_id
               and metadata["year"] == selected["year"]
               and metadata["population_basis"] == selected["population_basis"]
               and metadata["database_sha256"] == selected["database_sha256"]
               and metadata.get("coverage", {}).get("included_countries") == selected["coverage"]["included_countries"]]
    if not matches:
        raise ValueError(f"No comparable {scenario_id} run on the same data and coverage")
    return max(matches, key=lambda item: item[1]["calculation_date"])


def main():
    candidates = records()
    selected = {scenario: max(((p, m) for p, m in candidates if m["scenario_id"] == scenario),
                              key=lambda item: item[1]["calculation_date"])
                for scenario in NEW_SCENARIOS}
    runs = {}
    for basis, suffix in (("adult_20_plus", ""), ("full_population", "_full_population")):
        anchor = selected["global_median_target" + suffix][1]
        for scenario in ("hard_equality" + suffix, "global_median_target" + suffix,
                         "national_mean_equalization" + suffix):
            path, metadata = matching(candidates, scenario, anchor)
            rows = {row["iso3"]: row for row in json.loads((path / "country_results.json").read_text(encoding="utf-8"))}
            global_result = json.loads((path / "global_results.json").read_text(encoding="utf-8"))
            runs[scenario] = {"directory": str(path), "metadata": metadata, "results": rows, "global": global_result}
    data = []
    lines = ["# Equality scenario comparison", "",
             "2024 WID data in 2025 PPP USD. Targets and average gains/losses are per adult or person per year according to the population basis.",
             "All rows within a population basis use the same database hash, year, and included-country set.", ""]
    for basis, suffix in (("adult_20_plus", ""), ("full_population", "_full_population")):
        lines += [f"## {basis}", "",
                  "| Country | Scenario | Year | Population basis | Target PPP USD | Winners | Unchanged | Losers | Avg. gain | Avg. loss | Country net change | Global budget gap |",
                  "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for iso3 in REFERENCE_COUNTRIES:
            for scenario in ("hard_equality" + suffix, "global_median_target" + suffix,
                             "national_mean_equalization" + suffix):
                run = runs[scenario]
                if iso3 not in run["results"]:
                    raise ValueError(f"Reference country {iso3} missing from {scenario}")
                row, global_result = run["results"][iso3], run["global"]
                target = row.get("target_income_ppp", run["metadata"]["reference"].get("value_ppp"))
                data.append({"iso3": iso3, "scenario": scenario, "population_basis": basis,
                             "year": run["metadata"]["year"],
                             "target_income_ppp": target, "winner_share": row["winner_share"],
                             "unchanged_share": row["unchanged_share"], "loser_share": row["loser_share"],
                             "average_gain": row["average_gain"], "average_loss": row["average_loss"],
                             "country_net_change": row["net_transfer"], "global_budget_gap": global_result["budget_gap"],
                             "experiment_directory": run["directory"]})
                country_gap = 0.0 if row.get("budget_balanced") else row["net_transfer"]
                world_gap = 0.0 if global_result.get("budget_balanced") else global_result["budget_gap"]
                lines.append(f"| {iso3} | {scenario.removesuffix(suffix)} | {run['metadata']['year']} | {basis} | {target:,.0f} | "
                             f"{row['winner_share']:.1%} | {row['unchanged_share']:.1%} | {row['loser_share']:.1%} | "
                             f"{row['average_gain']:,.0f} | {row['average_loss']:,.0f} | "
                             f"{country_gap:,.0f} | {world_gap:,.0f} |")
        lines.append("")
    output = ROOT / "outputs/reference_tables"
    output.mkdir(parents=True, exist_ok=True)
    (output / "experiment_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "experiment_comparison.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(output / "experiment_comparison.md")


if __name__ == "__main__":
    main()
