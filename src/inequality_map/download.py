"""Bounded, resumable downloads. Raw HTTP payloads are losslessly gzip-compressed."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pycountry

from .common import code_version, digest_file, read_yaml, utc_now, write_json


def read_payload(snapshot, item):
    path = Path(snapshot) / item["path"]
    if digest_file(path) != item["sha256"]:
        raise ValueError(f"Raw checksum mismatch: {path}")
    return gzip.decompress(path.read_bytes())


def wb_page(payload):
    obj = json.loads(payload)
    if not isinstance(obj, list) or len(obj) != 2 or not isinstance(obj[0], dict):
        raise ValueError("Invalid World Bank envelope (possibly an API error)")
    meta, rows = obj
    if not all(k in meta for k in ("page", "pages", "total")):
        raise ValueError("Missing World Bank pagination metadata")
    if rows is None and int(meta["total"]) == 0:
        rows = []
    if not isinstance(rows, list):
        raise ValueError("Invalid World Bank rows")
    return meta, rows


class Downloader:
    def __init__(self, snapshot, config, client=None):
        self.snapshot = Path(snapshot)
        self.config = config
        self.client = client or httpx.Client(timeout=config["timeout_seconds"], follow_redirects=True,
                                              headers={"User-Agent": "equal-earth-research/0.1"})

    def fetch(self, key, url, provider, kind, validator=None, area=None):
        target = self.snapshot / provider / (key + ".gz")
        receipt = target.with_suffix(".receipt.json")
        if receipt.exists():
            item = json.loads(receipt.read_text(encoding="utf-8"))
            if item["url"] != url or not target.exists() or digest_file(target) != item["sha256"]:
                raise ValueError(f"Immutable raw file changed: {target}")
            return item
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".part")
        error = None
        for attempt in range(1, self.config["attempts"] + 1):
            try:
                sha = hashlib.sha256()
                size = 0
                with self.client.stream("GET", url) as response:
                    response.raise_for_status()
                    with temp.open("wb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
                        for chunk in response.iter_bytes():
                            sha.update(chunk)
                            size += len(chunk)
                            zipped.write(chunk)
                    if not size:
                        raise ValueError("Empty response")
                    if validator:
                        validator(temp)
                    item = {"key": key, "provider": provider, "kind": kind, "area": area,
                            "url": url, "resolved_url": str(response.url), "downloaded_at": utc_now(),
                            "last_modified": response.headers.get("last-modified"),
                            "etag": response.headers.get("etag"), "payload_sha256": sha.hexdigest(),
                            "payload_bytes": size, "sha256": digest_file(temp),
                            "path": str(target.relative_to(self.snapshot)).replace("\\", "/"), "attempts": attempt}
                # A finished raw file is never overwritten, including after a crash before its receipt.
                if target.exists():
                    if digest_file(target) != item["sha256"]:
                        raise ValueError(f"Unregistered raw file differs: {target}")
                    temp.unlink()
                else:
                    temp.replace(target)
                write_json(receipt, item)
                return item
            except (httpx.HTTPError, OSError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                if temp.exists():
                    temp.unlink()
                if attempt < self.config["attempts"]:
                    time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(f"{url}: {error}")

    def pages(self, key, route, kind):
        base = self.config["world_bank"]["base_url"] + route
        separator = "&" if "?" in base else "?"
        items, rows, page, total = [], [], 1, None
        while True:
            url = base + separator + urlencode({"format": "json", "per_page": self.config["world_bank"]["per_page"], "page": page})
            def validate(path):
                with gzip.open(path, "rb") as f:
                    meta, _ = wb_page(f.read())
                if int(meta["page"]) != page:
                    raise ValueError("World Bank returned the wrong page")
            item = self.fetch(f"{key}_page{page}.json", url, "world_bank", kind, validate)
            meta, chunk = wb_page(read_payload(self.snapshot, item))
            if total is not None and total != int(meta["total"]):
                raise ValueError("World Bank pagination total changed during download")
            total = int(meta["total"])
            items.append(item)
            rows.extend(chunk)
            if page >= int(meta["pages"]):
                break
            page += 1
        if len(rows) != total:
            raise ValueError(f"World Bank pagination truncated: {len(rows)} != {total}")
        return items, rows


def validate_csv(required):
    def validate(path):
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream, delimiter=";"), [])
        if not set(required).issubset(header):
            raise ValueError(f"Unexpected CSV columns: {header}")
    return validate


def download(root, sources=None, countries=None, start=None, end=None, snapshot=None, workers=None):
    root = Path(root)
    if snapshot:
        snapshot = Path(snapshot).resolve()
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        if any(x is not None for x in (sources, countries, start, end)):
            raise ValueError("Resume uses frozen filters; do not pass source/country/year filters")
        if manifest["status"] == "complete":
            for item in manifest["files"]:
                if digest_file(snapshot / item["path"]) != item["sha256"]:
                    raise ValueError("Raw checksum mismatch")
            return snapshot
    else:
        cfg = read_yaml(root / "config/sources.yml")
        cfg["start_year"] = start if start is not None else cfg["start_year"]
        cfg["end_year"] = end if end is not None else cfg["end_year"] or datetime.now(timezone.utc).year
        if cfg["start_year"] > cfg["end_year"]:
            raise ValueError("Start year exceeds end year")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        snapshot = root / "data/raw" / run_id
        manifest = {"run_id": run_id, "started_at": utc_now(), "status": "running", "config": cfg,
                    "country_config": read_yaml(root / "config/countries.yml"),
                    "sources": sources or ["wid", "world_bank"], "countries": countries or [],
                    "code": code_version(root), "files": [], "failures": [], "expected_wid": []}
        write_json(snapshot / "manifest.json", manifest)
    cfg = manifest["config"]
    downloader = Downloader(snapshot, cfg)
    files, failures = {}, []
    def remember(items):
        for item in items:
            files[item["provider"] + "/" + item["key"]] = item
        manifest["files"] = sorted(files.values(), key=lambda x: (x["provider"], x["key"]))
        manifest["failures"] = failures
        write_json(snapshot / "manifest.json", manifest)
    try:
        # Both catalogs are required for harmonization even in a single-provider load.
        items, wb_countries = downloader.pages("countries", "country", "countries")
        remember(items)
        base = cfg["wid"]["base_url"]
        item = downloader.fetch("countries.csv", base + "WID_countries.csv", "wid", "countries", validate_csv(["alpha2", "shortname", "region"]))
        remember([item])
        wid_countries = list(csv.DictReader(io.StringIO(read_payload(snapshot, item).decode("utf-8-sig")), delimiter=";"))
        if "world_bank" in manifest["sources"]:
            for indicator in cfg["world_bank"]["indicators"]:
                try:
                    items, _ = downloader.pages("metadata_" + indicator, "indicator/" + indicator, "indicator_metadata")
                    remember(items)
                    route = f"country/all/indicator/{indicator}?source=2&date={cfg['start_year']}:{cfg['end_year']}&footnote=y"
                    items, _ = downloader.pages(indicator, route, "observations")
                    remember(items)
                except Exception as exc:
                    failures.append({"provider": "world_bank", "key": indicator, "error": str(exc)})
        if "wid" in manifest["sources"]:
            remember([downloader.fetch("README.md", base + "README.md", "wid", "documentation")])
            selected = set(manifest["countries"])
            known = {c["iso2Code"]: c["id"] for c in wb_countries if c["region"]["id"] != "NA"}
            def matches(code):
                override = manifest["country_config"]["overrides"]["wid"].get(code)
                iso = pycountry.countries.get(alpha_2=code)
                iso3 = override["iso3"] if override else iso.alpha_3 if iso else known.get(code)
                return not selected or iso3 in selected
            codes = sorted({r["alpha2"] for r in wid_countries if r["region"] and re.fullmatch("[A-Z]{2}", r["alpha2"]) and matches(r["alpha2"])})
            manifest["expected_wid"] = codes
            remember([])
            def fetch_country(code):
                result = []
                for kind in ("metadata", "data"):
                    name = f"WID_{kind}_{code}.csv"
                    result.append(downloader.fetch(name, base + name, "wid", kind,
                                                   validate_csv(["country", "variable", "age", "pop"]), code))
                return result
            with ThreadPoolExecutor(max_workers=workers or cfg["workers"]) as pool:
                pending = {pool.submit(fetch_country, code): code for code in codes}
                for n, future in enumerate(as_completed(pending), 1):
                    code = pending[future]
                    try:
                        remember(future.result())
                    except Exception as exc:
                        failures.append({"provider": "wid", "key": code, "error": str(exc)})
                        remember([])
                    if n % 10 == 0 or n == len(codes):
                        print(f"WID: {n}/{len(codes)} countries attempted; {len(failures)} failures", flush=True)
    except Exception as exc:
        failures.append({"provider": "catalog", "key": "discovery", "error": str(exc)})
    finally:
        downloader.client.close()
    manifest["status"] = "incomplete" if failures else "complete"
    manifest["finished_at"] = utc_now()
    remember([])
    print(f"Download {manifest['status']}: {snapshot}", flush=True)
    return snapshot
