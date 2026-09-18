import json

import duckdb
import pytest

from inequality_map.build import build, current_database
from inequality_map.common import write_json
from inequality_map.normalize import canonical_wid, number, percentile
from inequality_map.validate import choose_partition, validate_database, validate_distribution


def test_codes_bounds_and_missing():
    assert canonical_wid("aptincj992", "992", "j") == "aptinc992j"
    assert canonical_wid("aptinc992j", "992", "j") == "aptinc992j"
    with pytest.raises(ValueError):
        canonical_wid("aptinci999", "992", "j")
    assert percentile("p99.9p100")["population_share"] == pytest.approx(.001)
    assert percentile("p99")["upper_bound"] is None
    with pytest.raises(ValueError):
        percentile("p100p99")
    assert number("..") is None
    assert number("-1") == -1
    with pytest.raises(ValueError):
        number("inf")


def test_distribution_validation_and_overlapping_groups():
    all_groups = [(0, 100, 20), (0, 50, 10), (50, 100, 30), (90, 100, 30)]
    partition = choose_partition(all_groups)
    assert partition == [(0, 50, 10), (50, 100, 30)]
    assert validate_distribution(partition, 20, {(0, 50): .25})["status"] == "unverifiable"
    assert validate_distribution(all_groups, 20)["status"] == "invalid"
    assert choose_partition([(0, 40, 10), (50, 100, 30)]) == []
    assert choose_partition([(0, 40, 8), (0, 50, 10), (50, 100, 30)]) == [(0, 50, 10), (50, 100, 30)]
    assert validate_distribution([(0, 50, 30), (50, 100, 10)], 20)["status"] == "invalid"
    assert validate_distribution(partition, 10)["mean_error"] == 1


def test_offline_build_ppp_provenance_and_rebuild(snapshot, monkeypatch):
    root, raw, _ = snapshot
    monkeypatch.setattr("httpx.Client.send", lambda *a, **kw: pytest.fail("Offline build attempted network"))
    release = build(root, raw)
    path = current_database(root)
    assert path == release / "inequality.duckdb"
    with duckdb.connect(str(path), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM countries").fetchone()[0] == 2
        assert db.execute("SELECT area_type FROM areas WHERE original_code='WLD'").fetchone()[0] == "aggregate"
        assert db.execute("SELECT count(*) FROM observations o JOIN series s USING(series_id) WHERE s.area_id='world_bank:HIC'").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM issues WHERE code='unmapped_observation'").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM coverage WHERE iso3='USA' AND status='absent'").fetchone()[0] > 0
        assert db.execute("SELECT status FROM coverage WHERE iso3='BRA' AND indicator_code='SP.POP.TOTL' AND year=2021").fetchone()[0] == "missing_values"
        assert db.execute("SELECT income_ppp FROM income_ppp WHERE percentile='p0p100' AND indicator_code='aptinc992j'").fetchone()[0] == 10
        assert db.execute("SELECT price_year FROM ppp_conversions").fetchone()[0] == 2025
        assert db.execute("SELECT count(*) FROM observations WHERE NOT is_requested").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM observations WHERE data_status='measured'").fetchone()[0] == 0
        assert db.execute("SELECT status FROM distribution_checks").fetchone()[0] == "passed"
        assert db.execute("SELECT count(*) FROM income_percentiles").fetchone()[0] == 100
        assert db.execute("SELECT count(*) FROM issues WHERE code='negative_income_or_share'").fetchone()[0] == 1
        count = db.execute("SELECT count(*) FROM observations").fetchone()[0]
        observations = db.execute("SELECT * FROM observations ORDER BY observation_id").fetchall()
        parquet_count = db.execute("SELECT count(*) FROM read_parquet(?)", [str(release / "observations.parquet")]).fetchone()[0]
        assert count == parquet_count
    assert not any(validate_database(path).values())
    second = build(root, raw)
    assert release.exists() and second != release
    with duckdb.connect(str(second / "inequality.duckdb"), read_only=True) as db:
        assert observations == db.execute("SELECT * FROM observations ORDER BY observation_id").fetchall()


def test_failed_build_does_not_publish(snapshot):
    root, raw, manifest = snapshot
    release = build(root, raw)
    pointer = (root/"database/current.json").read_bytes()
    item = next(f for f in manifest["files"] if f["kind"] == "data")
    (raw/item["path"]).write_bytes(b"bad")
    with pytest.raises(ValueError, match="integrity"):
        build(root, raw)
    assert (root/"database/current.json").read_bytes() == pointer


def test_filters_and_incomplete_load(snapshot):
    root, raw, manifest = snapshot
    manifest["status"] = "incomplete"
    manifest["failures"] = [{"provider": "wid", "key": "US", "error": "503"}]
    write_json(raw/"manifest.json", manifest)
    with pytest.raises(ValueError, match="incomplete"):
        build(root, raw)
    release = build(root, raw, countries=["BRA"], sources=["world_bank"], start=2020, end=2020, allow_incomplete=True)
    with duckdb.connect(str(release/"inequality.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == 2
        assert db.execute("SELECT DISTINCT iso3 FROM coverage").fetchall() == [("BRA",)]
    assert json.loads((root/"database/current.json").read_text())["status"] == "validated_incomplete"
