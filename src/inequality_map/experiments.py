"""Reproducible Equal-Earth scenarios from validated WID percentile distributions."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .build import current_database
from .common import digest_file, read_yaml, write_json

VALID_BASES = {"adult_20_plus", "full_population"}
VALID_REFERENCES = {("global", "mean"), ("global", "median"), ("national", "mean")}


def reference_rule(scenario):
    rule = scenario.get("reference", {"scope": "global", "statistic": "mean"})
    if not isinstance(rule, dict) or set(rule) - {"scope", "statistic"}:
        raise ValueError("reference must contain only scope and statistic")
    scope, statistic = rule.get("scope"), rule.get("statistic")
    if (scope, statistic) not in VALID_REFERENCES:
        raise ValueError(f"Unsupported reference scope/statistic: {scope}/{statistic}")
    return scope, statistic


def load_scenario(root, scenario_id):
    scenarios = read_yaml(Path(root) / "config/scenarios.yml")
    if scenario_id not in scenarios:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    scenario = scenarios[scenario_id]
    kind = scenario.get("redistribution", {}).get("type")
    basis = scenario.get("population", {}).get("basis")
    if kind not in {"equal", "clamp"}:
        raise ValueError(f"Unsupported redistribution type: {kind}")
    scope, statistic = reference_rule(scenario)
    if (scope, statistic) != ("global", "mean") and kind != "equal":
        raise ValueError("Global median and national mean require equal redistribution")
    multiplier = scenario["redistribution"].get("target_multiplier", 1.0)
    if kind == "equal" and (not isinstance(multiplier, (int, float)) or not math.isfinite(multiplier) or multiplier <= 0):
        raise ValueError("Equal scenarios need a positive finite target_multiplier")
    if scope == "national" and multiplier != 1:
        raise ValueError("National-mean equalization requires target_multiplier=1")
    if basis not in VALID_BASES:
        raise ValueError(f"population.basis must be one of {sorted(VALID_BASES)}")
    tolerance = scenario.get("classification", {}).get("unchanged_tolerance", 0)
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise ValueError("unchanged_tolerance must be a non-negative number")
    if kind == "clamp":
        floor = scenario["redistribution"].get("floor_multiplier")
        ceiling = scenario["redistribution"].get("ceiling_multiplier")
        if not isinstance(floor, (int, float)) or not isinstance(ceiling, (int, float)) or not 0 < floor < ceiling:
            raise ValueError("Clamp scenarios need positive floor_multiplier < ceiling_multiplier")
    return scenario


def resolve_year(db, requested_year=None, configured_year=None):
    if requested_year is not None and configured_year is not None and requested_year != configured_year:
        raise ValueError("The requested year conflicts with the scenario configuration")
    year = requested_year if requested_year is not None else configured_year
    if year is not None:
        count = db.execute("SELECT count(*) FROM distribution_checks WHERE year=? AND status='passed'", [year]).fetchone()[0]
        if not count:
            raise ValueError(f"No validated percentile distributions are available for {year}")
        return year
    row = db.execute("SELECT max(year) FROM distribution_checks WHERE status='passed'").fetchone()
    if row[0] is None:
        raise ValueError("No validated percentile distributions are available")
    return row[0]


def _gini(rows, value_key):
    ordered = sorted((float(row[value_key]), float(row["population"])) for row in rows if row["population"] > 0)
    total_population = sum(weight for _, weight in ordered)
    total_income = sum(value * weight for value, weight in ordered)
    if not total_population or not total_income:
        return None
    cumulative_population = cumulative_income = area = 0.0
    for value, weight in ordered:
        old_population, old_income = cumulative_population, cumulative_income
        cumulative_population += weight / total_population
        cumulative_income += value * weight / total_income
        area += (cumulative_population - old_population) * (cumulative_income + old_income) / 2
    return max(0.0, min(1.0, 1 - 2 * area))


def _raw_distribution_rows(db, year):
    return db.execute("""
        WITH population AS (
            SELECT a.iso3, o.year, s.indicator_code, o.value
            FROM observations o JOIN series s USING(series_id) JOIN areas a USING(area_id)
            JOIN percentile_groups g USING(group_id)
            WHERE s.indicator_code IN ('npopul992i','npopul999i') AND g.original_code='p0p100' AND o.is_requested
        )
        SELECT p.observation_id, p.iso3, c.country_name, p.year, p.percentile, p.lower_bound, p.upper_bound,
               p.income_ppp, p.ppp_currency, p.price_year, p.ppp_reference, p.conversion_id,
               p.ppp_observation_id, p.price_observation_id, p.file_id, o.source_row, o.source_quality,
               adults.value AS adult_population, total.value AS total_population
        FROM income_percentiles p
        JOIN observations o USING(observation_id)
        JOIN distribution_checks d ON d.iso3=p.iso3 AND d.year=p.year AND d.status='passed'
        JOIN countries c ON c.iso3=p.iso3
        LEFT JOIN population adults ON adults.iso3=p.iso3 AND adults.year=p.year AND adults.indicator_code='npopul992i'
        LEFT JOIN population total ON total.iso3=p.iso3 AND total.year=p.year AND total.indicator_code='npopul999i'
        WHERE p.year=? ORDER BY p.iso3, p.lower_bound
    """, [year]).fetch_arrow_table().to_pylist()


def _validated_distributions(db, year, basis):
    grouped, exclusions = defaultdict(list), {}
    for row in _raw_distribution_rows(db, year):
        grouped[row["iso3"]].append(row)
    eligible = {}
    for iso3, rows in grouped.items():
        rows.sort(key=lambda row: row["lower_bound"])
        adult, total = rows[0]["adult_population"], rows[0]["total_population"]
        reason = None
        if len(rows) != 100 or [row["lower_bound"] for row in rows] != list(range(100)) or [row["upper_bound"] for row in rows] != list(range(1, 101)):
            reason = "incomplete_or_duplicate_percentile_bins"
        elif any(not math.isfinite(row["income_ppp"]) or row["income_ppp"] < 0 for row in rows):
            reason = "invalid_percentile_income"
        elif any(left["income_ppp"] > right["income_ppp"] + 1e-8 * max(1, abs(left["income_ppp"]), abs(right["income_ppp"])) for left, right in zip(rows, rows[1:])):
            reason = "nonmonotonic_percentile_income"
        elif adult is None or not math.isfinite(adult) or adult <= 0:
            reason = "invalid_adult_population"
        elif basis == "full_population" and (total is None or not math.isfinite(total) or total <= 0 or adult > total):
            reason = "invalid_total_population"
        elif any(row["adult_population"] != adult or row["total_population"] != total for row in rows):
            reason = "inconsistent_population_input"
        if reason:
            exclusions[iso3] = reason
            continue
        scale = adult / total if basis == "full_population" else 1.0
        population = total if basis == "full_population" else adult
        eligible[iso3] = [{**row, "income_before_ppp": row["income_ppp"] * scale,
                           "population": population / 100, "scaling_factor": scale,
                           "population_basis": basis} for row in rows]
    if not eligible:
        raise ValueError(f"No eligible {basis} distributions are available for {year}: {exclusions}")
    currencies = {row["ppp_currency"] for rows in eligible.values() for row in rows}
    price_years = {row["price_year"] for rows in eligible.values() for row in rows}
    if len(currencies) != 1 or len(price_years) != 1 or None in currencies or None in price_years:
        raise ValueError(f"Scenario requires one PPP currency and price year; got currencies={sorted(currencies)}, price_years={sorted(price_years)}")
    references = {row["ppp_reference"] for rows in eligible.values() for row in rows}
    return eligible, exclusions, {"ppp_currency": next(iter(currencies)), "price_year": next(iter(price_years)),
                                   "ppp_references": sorted(reference or "unspecified" for reference in references),
                                   "common_ppp_benchmark": len(references) == 1 and None not in references}


def calculate_reference(distributions, basis):
    population = sum(row["population"] for rows in distributions.values() for row in rows)
    income = sum(row["income_before_ppp"] * row["population"] for rows in distributions.values() for row in rows)
    if population <= 0 or income <= 0:
        raise ValueError("Eligible distributions do not contain a positive income total")
    return {"value_ppp": income / population, "population": population, "income_total_ppp": income,
            "country_count": len(distributions), "population_basis": basis,
            "unit": "PPP per person per year" if basis == "full_population" else "PPP per adult per year",
            "method": ("full-population-weighted mean of adult percentile incomes scaled by adult_population / total_population"
                       if basis == "full_population" else "adult-population-weighted mean of validated WID 1-percentile income rows")}


def weighted_median(distributions):
    bins = sorted((row["income_before_ppp"], row["population"])
                  for rows in distributions.values() for row in rows if row["population"] > 0)
    population = math.fsum(weight for _, weight in bins)
    if not bins or population <= 0:
        raise ValueError("Median requires positive population")
    cumulative = 0.0
    for income, weight in bins:
        cumulative += weight
        if cumulative >= population / 2:
            return income
    return bins[-1][0]


def scenario_references(distributions, basis, scenario):
    scope, statistic = reference_rule(scenario)
    summary = calculate_reference(distributions, basis)
    if scope == "global" and statistic == "mean":
        reference = {**summary, "scope": scope, "statistic": statistic}
        targets = {iso3: summary["value_ppp"] for iso3 in distributions}
    elif scope == "global":
        median = weighted_median(distributions)
        reference = {**summary, "value_ppp": median, "scope": scope, "statistic": statistic,
                     "baseline_mean_ppp": summary["value_ppp"],
                     "method": "lower population-weighted median of eligible percentile-bin means"}
        targets = {iso3: median for iso3 in distributions}
    else:
        targets = {iso3: math.fsum(row["income_before_ppp"] * row["population"] for row in rows) /
                   math.fsum(row["population"] for row in rows) for iso3, rows in distributions.items()}
        reference = {"scope": scope, "statistic": statistic, "value_ppp": None,
                     "country_targets_ppp": dict(sorted(targets.items())), "population": summary["population"],
                     "income_total_ppp": summary["income_total_ppp"], "country_count": summary["country_count"],
                     "population_basis": basis, "unit": summary["unit"],
                     "method": "within-country population-weighted mean of eligible percentile-bin incomes"}
    return reference, targets


def _classify(old, scenario, reference):
    tolerance = scenario.get("classification", {}).get("unchanged_tolerance", 0)
    if scenario["redistribution"]["type"] == "equal":
        target = reference * scenario["redistribution"].get("target_multiplier", 1.0)
        low, high, new = target * (1 - tolerance), target * (1 + tolerance), target
    else:
        floor = reference * scenario["redistribution"]["floor_multiplier"]
        ceiling = reference * scenario["redistribution"]["ceiling_multiplier"]
        low, high, new = floor * (1 - tolerance), ceiling * (1 + tolerance), min(max(old, floor), ceiling)
    return ("winner" if old < low else "loser" if old > high else "unchanged"), new


def country_result(iso3, rows, scenario, reference):
    buckets = {"winner": 0.0, "unchanged": 0.0, "loser": 0.0}
    gains, losses, before, after, transformed = [], [], 0.0, 0.0, []
    for row in rows:
        status, new = _classify(row["income_before_ppp"], scenario, reference)
        population, delta = row["population"], new - row["income_before_ppp"]
        buckets[status] += population
        before += row["income_before_ppp"] * population
        after += new * population
        transformed.append({**row, "income_after_ppp": new})
        if delta > 0:
            gains.append((delta, population))
        elif delta < 0:
            losses.append((-delta, population))
    population = sum(buckets.values())
    def weighted_mean(items):
        total_weight = sum(weight for _, weight in items)
        return sum(value * weight for value, weight in items) / total_weight if total_weight else 0.0
    basis = rows[0]["population_basis"]
    budget_gap = after - before
    balanced = math.isclose(after, before, rel_tol=0, abs_tol=max(1e-6, abs(before) * 1e-10))
    return {"iso3": iso3, "country_name": rows[0]["country_name"], "year": rows[0]["year"],
            "target_income_ppp": reference * scenario["redistribution"].get("target_multiplier", 1.0) if scenario["redistribution"]["type"] == "equal" else None,
            "population_basis": basis, "population": population, "adult_population": rows[0]["adult_population"],
            "total_population": rows[0]["total_population"], "scaling_factor": rows[0]["scaling_factor"],
            "distribution_status": "estimated" if basis == "full_population" else "source_published",
            "distribution_method": "adult_shape_scaled_to_total_population" if basis == "full_population" else "published_adult_1_percentile_bins",
            "source_distribution_validation": "passed", "source_quality_values": sorted({row["source_quality"] for row in rows if row["source_quality"] is not None}),
            "winner_share": buckets["winner"] / population, "unchanged_share": buckets["unchanged"] / population,
            "loser_share": buckets["loser"] / population, "winner_population": buckets["winner"],
            "unchanged_population": buckets["unchanged"], "loser_population": buckets["loser"],
            "original_mean": before / population, "new_mean": after / population,
            "average_gain": weighted_mean(gains), "average_loss": weighted_mean(losses),
            "total_gain": sum(value * weight for value, weight in gains), "total_loss": sum(value * weight for value, weight in losses),
            "income_before": before, "income_after": after, "net_transfer": after - before,
            "budget_gap": budget_gap, "budget_balanced": balanced,
            "undistributed_surplus": 0.0 if balanced else max(-budget_gap, 0.0),
            "funding_requirement": 0.0 if balanced else max(budget_gap, 0.0),
            "required_transfer": sum(value * weight for value, weight in gains), "surplus_transfer": sum(value * weight for value, weight in losses),
            "gini_before": _gini(rows, "income_before_ppp"), "gini_after": _gini(transformed, "income_after_ppp")}


def global_result(results):
    population = sum(result["population"] for result in results)
    before = sum(result["income_before"] for result in results)
    after = sum(result["income_after"] for result in results)
    gap = after - before
    balanced = math.isclose(after, before, rel_tol=0, abs_tol=max(1e-6, abs(before) * 1e-10))
    return {"country_count": len(results), "population": population, "income_before": before, "income_after": after,
            "winner_population": sum(result["winner_population"] for result in results),
            "unchanged_population": sum(result["unchanged_population"] for result in results),
            "loser_population": sum(result["loser_population"] for result in results),
            "winner_share": sum(result["winner_population"] for result in results) / population,
            "unchanged_share": sum(result["unchanged_population"] for result in results) / population,
            "loser_share": sum(result["loser_population"] for result in results) / population,
            "required_transfer": sum(result["required_transfer"] for result in results),
            "surplus_transfer": sum(result["surplus_transfer"] for result in results), "budget_gap": gap,
            "undistributed_surplus": 0.0 if balanced else max(-gap, 0.0),
            "funding_requirement": 0.0 if balanced else max(gap, 0.0),
            "budget_balanced": balanced}


def _fingerprint(scenario_id, scenario, year, database_hash, basis):
    payload = json.dumps({"scenario_id": scenario_id, "scenario": scenario, "year": year,
                          "database_sha256": database_hash, "population_basis": basis,
                          "engine_sha256": digest_file(Path(__file__))}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _comparison(adult_rows, full_rows, scenario):
    adult_reference, adult_targets = scenario_references(adult_rows, "adult_20_plus", scenario)
    full_reference, full_targets = scenario_references(full_rows, "full_population", scenario)
    adult = {iso3: country_result(iso3, rows, scenario, adult_targets[iso3]) for iso3, rows in adult_rows.items()}
    full = {iso3: country_result(iso3, rows, scenario, full_targets[iso3]) for iso3, rows in full_rows.items()}
    return {"adult_reference_ppp": adult_reference["value_ppp"], "full_population_reference_ppp": full_reference["value_ppp"],
            "adult_reference": adult_reference, "full_population_reference": full_reference,
            "results": [{"iso3": iso3, "adult_winner_share": adult[iso3]["winner_share"],
                         "full_population_winner_share": full[iso3]["winner_share"],
                         "adult_target_income_ppp": adult[iso3]["target_income_ppp"],
                         "full_population_target_income_ppp": full[iso3]["target_income_ppp"],
                         "adult_population": adult[iso3]["population"], "total_population": full[iso3]["population"],
                         "scaling_factor": full[iso3]["scaling_factor"], "adult_net_transfer": adult[iso3]["net_transfer"],
                         "full_population_net_transfer": full[iso3]["net_transfer"]} for iso3 in sorted(adult)]}


def _input_lineage(distributions):
    return [{"iso3": iso3, "income_observation_ids": [row["observation_id"] for row in rows],
             "source_file_ids": sorted({row["file_id"] for row in rows}),
             "source_rows": [row["source_row"] for row in rows],
             "conversion_ids": sorted({row["conversion_id"] for row in rows}),
             "ppp_observation_ids": sorted({row["ppp_observation_id"] for row in rows}),
             "price_observation_ids": sorted({row["price_observation_id"] for row in rows}),
             "ppp_currency": rows[0]["ppp_currency"], "price_year": rows[0]["price_year"],
             "ppp_reference": rows[0]["ppp_reference"]} for iso3, rows in sorted(distributions.items())]


def run_experiment(root, scenario_id, year=None, database=None, output_root=None):
    root = Path(root).resolve()
    scenario = load_scenario(root, scenario_id)
    basis = scenario["population"]["basis"]
    database = Path(database).resolve() if database else current_database(root)
    database_hash = digest_file(database)
    with duckdb.connect(str(database), read_only=True) as db:
        resolved_year = resolve_year(db, year, scenario.get("year", {}).get("target"))
        distributions, exclusions, ppp = _validated_distributions(db, resolved_year, basis)
        adult_distributions, adult_exclusions, adult_ppp = _validated_distributions(db, resolved_year, "adult_20_plus")
    reference, targets = scenario_references(distributions, basis, scenario)
    reference.update({"ppp_currency": ppp["ppp_currency"], "price_year": ppp["price_year"]})
    results = [country_result(iso3, rows, scenario, targets[iso3]) for iso3, rows in sorted(distributions.items())]
    global_summary = {**global_result(results), "population_basis": basis}
    fingerprint = _fingerprint(scenario_id, scenario, resolved_year, database_hash, basis)
    experiment_id = f"{scenario_id}_{resolved_year}_{fingerprint}"
    output = Path(output_root) if output_root else root / "outputs/experiments" / experiment_id
    if output.exists():
        raise FileExistsError(f"Experiment output already exists: {output}")
    output.mkdir(parents=True)
    metadata = {"experiment_id": experiment_id, "scenario_id": scenario_id, "scenario": scenario,
                "calculation_date": datetime.now(timezone.utc).isoformat(), "database": str(database),
                "data_version": database.parent.name, "database_sha256": database_hash,
                "engine_sha256": digest_file(Path(__file__)), "year": resolved_year,
                "reference": reference, "population_basis": basis, "ppp": ppp, "source": "WID bulk country exports",
                "distribution_method": "adult_shape_scaled_to_total_population" if basis == "full_population" else "published adult 1-percentile bins",
                "distribution_status": "estimated" if basis == "full_population" else "source_published",
                "assumption": "Each country income percentile has its country-wide adult-to-total-population ratio." if basis == "full_population" else None,
                "coverage": {"included_countries": sorted(distributions), "excluded_countries": exclusions,
                             "included_country_count": len(distributions), "adult_eligible_country_count": len(adult_distributions),
                             "adult_exclusions": adult_exclusions},
                "input_lineage_file": "input_lineage.json",
                "budget_conservation": {"before": global_summary["income_before"], "after": global_summary["income_after"],
                                        "gap": global_summary["budget_gap"], "balanced": global_summary["budget_balanced"],
                                        "undistributed_surplus": global_summary["undistributed_surplus"],
                                        "funding_requirement": global_summary["funding_requirement"]}}
    write_json(output / "config.json", scenario)
    write_json(output / "country_results.json", results)
    reference_iso3 = set(read_yaml(root / "config/countries.yml")["reference_countries"])
    write_json(output / "reference_country_results.json", [result for result in results if result["iso3"] in reference_iso3])
    write_json(output / "global_results.json", global_summary)
    write_json(output / "input_lineage.json", _input_lineage(distributions))
    if basis == "full_population":
        common = sorted(set(distributions) & set(adult_distributions))
        comparison = _comparison({iso3: adult_distributions[iso3] for iso3 in common}, {iso3: distributions[iso3] for iso3 in common}, scenario)
        comparison.update({"year": resolved_year, "adult_ppp": adult_ppp, "full_population_ppp": ppp})
        write_json(output / "basis_comparison.json", comparison)
        write_json(output / "reference_basis_comparison.json", {**comparison, "results": [result for result in comparison["results"] if result["iso3"] in reference_iso3]})
    write_json(output / "metadata.json", metadata)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(results), output / "country_results.parquet", compression="zstd")
    return output, metadata, results, global_summary
