import json
import gzip
import hashlib

import pytest

from inequality_map.build import build
from inequality_map.common import digest_file, write_json
from inequality_map.experiments import (run_experiment, weighted_median, scenario_references,
                                        country_result, global_result, _comparison, load_scenario)
from inequality_map.maps import generate_maps


def scenario_config(root):
    (root / "config/scenarios.yml").write_text("""
hard_equality:
  name: Hard equality
  redistribution: {type: equal, target_multiplier: 1.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: adult_20_plus}
  year: {target: 2020}
relaxed_06_30:
  name: Relaxed
  redistribution: {type: clamp, floor_multiplier: 0.6, ceiling_multiplier: 3.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: adult_20_plus}
  year: {target: 2020}
hard_equality_full_population:
  name: Full population hard equality
  redistribution: {type: equal, target_multiplier: 1.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: full_population}
  year: {target: 2020}
global_median_target:
  name: Global median target
  reference: {scope: global, statistic: median}
  redistribution: {type: equal, target_multiplier: 1.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: adult_20_plus}
  year: {target: 2020}
national_mean_equalization:
  name: National mean equalization
  reference: {scope: national, statistic: mean}
  redistribution: {type: equal, target_multiplier: 1.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: adult_20_plus}
  year: {target: 2020}
relaxed_06_30_full_population:
  name: Full population relaxed
  redistribution: {type: clamp, floor_multiplier: 0.6, ceiling_multiplier: 3.0}
  classification: {unchanged_tolerance: 0.0}
  population: {basis: full_population}
  year: {target: 2020}
""", encoding="utf-8")


def test_hard_equality_uses_source_derived_reference_and_conserves(snapshot):
    root, raw, _ = snapshot
    scenario_config(root)
    build(root, raw)
    output, metadata, results, global_summary = run_experiment(root, "hard_equality")
    assert metadata["reference"]["value_ppp"] == pytest.approx(10)
    assert results[0]["winner_share"] == pytest.approx(0.5)
    assert results[0]["loser_share"] == pytest.approx(0.5)
    assert global_summary["budget_balanced"]
    assert global_summary["budget_gap"] == pytest.approx(0)
    assert (output / "country_results.parquet").exists()
    assert [row["iso3"] for row in json.loads((output / "reference_country_results.json").read_text())] == ["BRA"]
    assert json.loads((output / "metadata.json").read_text())["year"] == 2020


def test_full_population_scaling_preserves_income_and_reports_comparison(snapshot):
    root, raw, _ = snapshot
    scenario_config(root)
    build(root, raw)
    output, metadata, results, global_summary = run_experiment(root, "hard_equality_full_population")
    result = results[0]
    assert metadata["reference"]["value_ppp"] == pytest.approx(8)
    assert result["population_basis"] == "full_population"
    assert result["distribution_status"] == "estimated"
    assert result["distribution_method"] == "adult_shape_scaled_to_total_population"
    assert result["adult_population"] == 80
    assert result["total_population"] == 100
    assert result["scaling_factor"] == pytest.approx(.8)
    assert result["income_before"] == pytest.approx(800)
    lineage = json.loads((output / "input_lineage.json").read_text())
    assert len(lineage[0]["income_observation_ids"]) == 100
    assert lineage[0]["price_year"] == 2025
    assert global_summary["income_before"] == pytest.approx(global_summary["income_after"])
    comparison = json.loads((output / "basis_comparison.json").read_text())
    assert comparison["adult_reference_ppp"] == pytest.approx(10)
    assert comparison["full_population_reference_ppp"] == pytest.approx(8)
    assert [row["iso3"] for row in json.loads((output / "reference_basis_comparison.json").read_text())["results"]] == ["BRA"]
    with pytest.raises(FileExistsError):
        run_experiment(root, "hard_equality_full_population")


def test_full_population_excludes_invalid_total_population(snapshot):
    root, raw, manifest = snapshot
    scenario_config(root)
    item = next(item for item in manifest["files"] if item["provider"] == "wid" and item["kind"] == "data")
    path = raw / item["path"]
    content = gzip.decompress(path.read_bytes()).decode("utf-8").replace("npopuli999;p0p100;2020;100", "npopuli999;p0p100;2020;70")
    payload = content.encode("utf-8")
    path.write_bytes(gzip.compress(payload, mtime=0))
    item.update(sha256=digest_file(path), payload_sha256=hashlib.sha256(payload).hexdigest(), payload_bytes=len(payload))
    write_json(raw / "manifest.json", manifest)
    build(root, raw)
    with pytest.raises(ValueError, match="No eligible full_population"):
        run_experiment(root, "hard_equality_full_population")


def test_relaxed_clamp_reports_nonconservation_and_svg_map(snapshot, tmp_path):
    root, raw, _ = snapshot
    scenario_config(root)
    build(root, raw)
    output, _, results, global_summary = run_experiment(root, "relaxed_06_30")
    assert results[0]["winner_share"] == pytest.approx(0.5)
    assert results[0]["unchanged_share"] == pytest.approx(0.5)
    assert results[0]["loser_share"] == pytest.approx(0)
    assert not global_summary["budget_balanced"]
    boundary = tmp_path / "countries.geojson"
    boundary.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ISO_A3": "BRA"}, "geometry": {"type": "Polygon", "coordinates": [[[-70, -20], [-35, -20], [-35, 5], [-70, -20]]]}}]}), encoding="utf-8")
    maps = generate_maps(root, output, boundary)
    assert [path.name for path in maps] == ["winner_share.svg", "unchanged_share.svg", "loser_share.svg"]
    assert 'data-iso3="BRA"' in maps[0].read_text(encoding="utf-8")  # join uses ISO-3; labels may use display names
    svg = maps[0].read_text(encoding="utf-8")
    sidecar = json.loads(maps[0].with_suffix(".json").read_text())
    assert sidecar["fixed_bins_percent"] == [0, 10, 30, 50, 70, 90, 100]
    assert sidecar["design"] == "editorial_equal_earth_v3"
    assert sidecar["palette"] == ["#f13b28", "#ff9828", "#f7cf36", "#91cb32", "#28a344", "#007e62"]
    assert "Covered adults 20+" in svg and "Reading this map" in svg


def _bins(iso3, incomes, population, scale=1):
    return [{"iso3": iso3, "country_name": iso3, "year": 2024,
             "income_before_ppp": income * scale, "population": population / len(incomes),
             "population_basis": "adult_20_plus", "adult_population": population,
             "total_population": population, "scaling_factor": scale, "source_quality": "A"}
            for income in incomes]


def test_weighted_median_uses_people_not_countries_and_has_lower_boundary():
    data = {"A": _bins("A", [1, 1], 80), "B": _bins("B", [10, 20], 10),
            "C": _bins("C", [100, 200], 10)}
    assert weighted_median(data) == 1
    assert weighted_median({"A": _bins("A", [4, 9], 100)}) == 4
    assert weighted_median({"A": list(reversed(_bins("A", [4, 9], 100)))}) == 4
    assert weighted_median({"A": _bins("A", [7, 7, 7], 100)}) == 7


def test_median_and_national_mean_accounting_with_distinct_country_targets():
    rows = {"A": _bins("A", [2, 4], 100), "B": _bins("B", [10, 30], 300)}
    median_scenario = {"reference": {"scope": "global", "statistic": "median"},
                       "redistribution": {"type": "equal"}}
    reference, targets = scenario_references(rows, "adult_20_plus", median_scenario)
    assert reference["value_ppp"] == 10
    median_results = [country_result(k, v, median_scenario, targets[k]) for k, v in rows.items()]
    median_global = global_result(median_results)
    assert median_global["undistributed_surplus"] == pytest.approx(2300)
    assert median_global["funding_requirement"] == 0
    assert sum(r["total_gain"] - r["total_loss"] for r in median_results) == pytest.approx(median_global["budget_gap"])
    assert all(sum(r[f"{kind}_share"] for kind in ("winner", "unchanged", "loser")) == pytest.approx(1) for r in median_results)

    national_scenario = {"reference": {"scope": "national", "statistic": "mean"},
                         "redistribution": {"type": "equal"}}
    reference, targets = scenario_references(rows, "adult_20_plus", national_scenario)
    assert reference["value_ppp"] is None
    assert targets == {"A": 3, "B": 20}
    results = [country_result(k, v, national_scenario, targets[k]) for k, v in rows.items()]
    assert all(r["budget_balanced"] and r["gini_after"] == 0 for r in results)
    assert all(r["net_transfer"] == pytest.approx(0) for r in results)
    assert global_result(results)["budget_balanced"]
    scaled = {"A": _bins("A", [2, 4], 100, .8), "B": _bins("B", [10, 30], 300, .7)}
    _, scaled_targets = scenario_references(scaled, "full_population", national_scenario)
    for iso3 in rows:
        assert country_result(iso3, rows[iso3], national_scenario, targets[iso3])["winner_share"] == \
               country_result(iso3, scaled[iso3], national_scenario, scaled_targets[iso3])["winner_share"]
    comparison = _comparison(rows, scaled, national_scenario)
    assert comparison["adult_reference"]["scope"] == "national"
    assert comparison["adult_reference_ppp"] is None


def test_median_can_require_funding_and_new_map_metadata_identifies_reference(snapshot, tmp_path):
    rows = {"A": _bins("A", [0, 10, 10, 10, 10], 100)}
    scenario = {"reference": {"scope": "global", "statistic": "median"},
                "redistribution": {"type": "equal"}}
    reference, targets = scenario_references(rows, "adult_20_plus", scenario)
    summary = global_result([country_result("A", rows["A"], scenario, targets["A"])])
    assert reference["value_ppp"] == 10
    assert summary["funding_requirement"] == pytest.approx(200)
    assert summary["undistributed_surplus"] == 0

    root, raw, _ = snapshot
    scenario_config(root)
    build(root, raw)
    boundary = tmp_path / "countries.geojson"
    boundary.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"ISO_A3": "BRA"}, "geometry": {
            "type": "Polygon", "coordinates": [[[-70, -20], [-35, -20], [-35, 5], [-70, -20]]]}}]}), encoding="utf-8")
    for scenario_id, scope, statistic in (("global_median_target", "global", "median"),
                                          ("national_mean_equalization", "national", "mean")):
        output, metadata, results, _ = run_experiment(root, scenario_id)
        assert metadata["reference"]["scope"] == scope
        assert metadata["reference"]["statistic"] == statistic
        assert results[0]["target_income_ppp"] > 0
        map_path = generate_maps(root, output, boundary)[0]
        sidecar = json.loads(map_path.with_suffix(".json").read_text(encoding="utf-8"))
        assert sidecar["reference"]["scope"] == scope
        assert f"{scope.title()} {statistic}" in sidecar["map_title"]
        assert sidecar["map_title"] in map_path.read_text(encoding="utf-8")


def test_reference_validation_rejects_unsupported_and_unfunded_national_multiplier(tmp_path):
    root = tmp_path
    (root / "config").mkdir()
    (root / "config/scenarios.yml").write_text("""bad:
  reference: {scope: national, statistic: median}
  redistribution: {type: equal}
  population: {basis: adult_20_plus}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported reference"):
        load_scenario(root, "bad")
    (root / "config/scenarios.yml").write_text("""bad:
  reference: {scope: national, statistic: mean}
  redistribution: {type: equal, target_multiplier: 1.1}
  population: {basis: adult_20_plus}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="target_multiplier=1"):
        load_scenario(root, "bad")
