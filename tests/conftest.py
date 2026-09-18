import csv
import gzip
import io
import json
from pathlib import Path

import pytest
import yaml

from inequality_map.common import digest_file, stable_id, write_json


@pytest.fixture
def snapshot(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    root = tmp_path
    (root / "config").mkdir()
    for name in ("sources.yml", "countries.yml"):
        (root / "config" / name).write_bytes((repo / "config" / name).read_bytes())
    cfg = yaml.safe_load((root / "config/sources.yml").read_text())
    cfg.update(start_year=2020, end_year=2021)
    raw = root / "data/raw/fixture"
    manifest = {"run_id": "fixture", "status": "complete", "started_at": "2026-01-01T00:00:00Z",
                "finished_at": "2026-01-01T00:00:01Z", "sources": ["wid", "world_bank"], "countries": [],
                "config": cfg, "country_config": yaml.safe_load((root / "config/countries.yml").read_text()),
                "files": [], "failures": [], "expected_wid": ["BR"]}
    def add(provider, key, kind, payload, area=None):
        if isinstance(payload, (list, dict)):
            payload = json.dumps(payload)
        data = payload.encode()
        path = raw / provider / (key + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data, mtime=0))
        import hashlib
        item = {"provider": provider, "key": key, "kind": kind, "area": area, "url": "https://example.test/" + key,
                "downloaded_at": "2026-01-01T00:00:00Z", "last_modified": None, "sha256": digest_file(path),
                "payload_sha256": hashlib.sha256(data).hexdigest(), "payload_bytes": len(data),
                "path": path.relative_to(raw).as_posix()}
        manifest["files"].append(item)
    def envelope(rows):
        return [{"page": 1, "pages": 1, "total": len(rows)}, rows]
    add("world_bank", "countries.json", "countries", envelope([
        {"id": "BRA", "iso2Code": "BR", "name": "Brazil", "region": {"id": "LCN", "value": "Latin America"}},
        {"id": "WLD", "iso2Code": "1W", "name": "World", "region": {"id": "NA", "value": "Aggregates"}},
        {"id": "USA", "iso2Code": "US", "name": "United States", "region": {"id": "NAC", "value": "North America"}},
        {"id": "HIC", "iso2Code": "XD", "name": "High income", "region": {"id": "NA", "value": "Aggregates"}},
    ]))
    add("wid", "countries.csv", "countries", "alpha2;titlename;shortname;region;region2\nBR;Brazil;Brazil;Americas;South America\nUS;USA;USA;Americas;North America\nWO;World;World;;\nZZ;Unknown;Unknown;Americas;\n")
    for code, val in (("SP.POP.TOTL", 100), ("PA.NUS.PPP", 900)):
        add("world_bank", "metadata_"+code, "indicator_metadata", envelope([{"id": code, "sourceNote": "Fixture estimate", "sourceOrganization": "Test"}]))
        add("world_bank", code, "observations", envelope([
            {"indicator": {"id": code}, "countryiso3code": "BRA", "country": {"id": "BR"}, "date": "2020", "value": val},
            {"indicator": {"id": code}, "countryiso3code": "BRA", "country": {"id": "BR"}, "date": "2021", "value": None},
            {"indicator": {"id": code}, "countryiso3code": "WLD", "country": {"id": "1W"}, "date": "2020", "value": val * 2},
            {"indicator": {"id": code}, "countryiso3code": "", "country": {"id": "XD"}, "date": "2020", "value": None},
        ]))
    data = []
    def obs(code, group, year, val, quality="estimated"):
        data.append(["BR", code[:6]+code[-1]+code[6:9], group, year, val, code[6:9], code[-1], quality])
    obs("aptinc992j", "p0p100", 2020, 20)
    for p in range(100):
        obs("aptinc992j", f"p{p}p{p+1}", 2020, 10 if p < 50 else 30)
    obs("aptinc992j", "p0p50", 2020, 10)
    obs("aptinc992j", "p50p100", 2020, 30)
    for p, val in (("p0p50", .25), ("p90p100", .15), ("p99p100", .015)):
        obs("sptinc992j", p, 2020, val)
    obs("tptinc992j", "p0p100", 2020, -1)
    obs("npopul992i", "p0p100", 2020, 80)
    obs("npopul999i", "p0p100", 2020, 100)
    obs("inyixx999i", "p0p100", 2020, .8)
    obs("inyixx999i", "p0p100", 2025, 1)
    obs("xlcusp999i", "p0p100", 2020, 1.5)
    obs("xlcusp999i", "p0p100", 2025, 2)
    def csv_text(fields, rows):
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(fields)
        writer.writerows(rows)
        return buf.getvalue()
    add("wid", "WID_data_BR.csv", "data", csv_text(["country", "variable", "percentile", "year", "value", "age", "pop", "data_quality"], data), "BR")
    meta = []
    for code in cfg["wid"]["variables"]:
        meta.append(["BR", code[:6]+code[-1]+code[6:9], code[6:9], code[-1], "BRL" if code[0] in "amt" else "", "Test source", "Estimated using ICP (2021)", ""])
    add("wid", "WID_metadata_BR.csv", "metadata", csv_text(["country", "variable", "age", "pop", "unit", "source", "method", "avg_quality"], meta), "BR")
    write_json(raw / "manifest.json", manifest)
    return root, raw, manifest
