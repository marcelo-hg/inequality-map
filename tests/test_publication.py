import gzip
import hashlib
import json

import duckdb
import pytest

from inequality_map.build import build
from inequality_map.common import digest_file, write_json
from inequality_map.validate import validate_database


def change_raw(raw, manifest, transform):
    item = next(f for f in manifest["files"] if f["kind"] == "data")
    path = raw/item["path"]
    content = transform(gzip.decompress(path.read_bytes()).decode()).encode()
    path.write_bytes(gzip.compress(content, mtime=0))
    item.update(sha256=digest_file(path), payload_sha256=hashlib.sha256(content).hexdigest(), payload_bytes=len(content))
    write_json(raw/"manifest.json", manifest)


def test_duplicate_source_key_blocks_publication(snapshot):
    root, raw, manifest = snapshot
    build(root, raw)
    pointer = (root/"database/current.json").read_bytes()
    change_raw(raw, manifest, lambda text: text + text.splitlines(keepends=True)[1])
    with pytest.raises(duckdb.ConstraintException):
        build(root, raw)
    assert (root/"database/current.json").read_bytes() == pointer
    failed = [json.loads(p.read_text()) for p in (root/"data/processed/releases").glob('*/build_manifest.json')]
    assert any(p["status"] == "failed" for p in failed)


def test_missing_ppp_never_uses_world_bank_factor(snapshot):
    root, raw, manifest = snapshot
    change_raw(raw, manifest, lambda text: "\n".join(line for line in text.splitlines() if not ("xlcuspi999" in line and ";2025;" in line)) + "\n")
    release = build(root, raw)
    with duckdb.connect(str(release/"inequality.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM income_ppp").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM issues WHERE code='ppp_conversion_unavailable'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM observations o JOIN series s USING(series_id) WHERE s.indicator_code='aptinc992j'").fetchone()[0] == 103


def test_nonpositive_population_retained_and_flagged(snapshot):
    root, raw, manifest = snapshot
    change_raw(raw, manifest, lambda text: text.replace("npopuli992;p0p100;2020;80", "npopuli992;p0p100;2020;0"))
    release = build(root, raw)
    with duckdb.connect(str(release/"inequality.duckdb"), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM issues WHERE code='nonpositive_population_ppp_or_index'").fetchone()[0] == 1
        assert db.execute("SELECT value FROM observations o JOIN series s USING(series_id) WHERE s.indicator_code='npopul992i'").fetchone()[0] == 0


def test_running_capture_and_invalid_filters_rejected(snapshot):
    root, raw, manifest = snapshot
    with pytest.raises(ValueError, match="years"):
        build(root, raw, start=1999)
    with pytest.raises(ValueError, match="Unknown ISO"):
        build(root, raw, countries=["ZZZ"])
    manifest['status'] = 'running'
    write_json(raw/'manifest.json', manifest)
    with pytest.raises(ValueError, match="still running"):
        build(root, raw, allow_incomplete=True)


def test_published_parquet_corruption_is_detected(snapshot):
    root, raw, _ = snapshot
    release = build(root, raw)
    (release/'observations.parquet').write_bytes(b'corrupted')
    with pytest.raises(ValueError, match="checksum"):
        validate_database(release/'inequality.duckdb')
