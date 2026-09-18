from __future__ import annotations

import csv
import gzip
import io
import json
import math
import re
from pathlib import Path

import pyarrow as pa
import pycountry

from .common import stable_id
from .download import read_payload, wb_page


def insert_rows(db, table, rows):
    if not rows:
        return
    # Explicit Arrow schema preserves nullable columns even when a batch is entirely null.
    fields = db.execute(f"SELECT * FROM {table} LIMIT 0").fetch_arrow_table().schema
    arrow = pa.Table.from_pylist(rows, schema=fields)
    db.register("incoming_batch", arrow)
    try:
        db.execute(f"INSERT INTO {table} SELECT * FROM incoming_batch")
    finally:
        db.unregister("incoming_batch")


def issue(db, code, details, area=None, year=None, indicator=None, severity="warning"):
    db.execute("INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
               [stable_id(code, area, year, indicator, details), severity, code, area, year, indicator, details])


def canonical_wid(variable, age, pop):
    """Bulk exports use sixlet+pop+age; dictionary uses sixlet+age+pop."""
    canonical = variable[:6] + age + pop
    if variable not in (canonical, variable[:6] + pop + age):
        raise ValueError(f"Variable/age/pop mismatch: {variable}/{age}/{pop}")
    return canonical


def percentile(code):
    match = re.fullmatch(r"p(\d+(?:\.\d+)?)(?:p(\d+(?:\.\d+)?))?", code)
    if not match:
        raise ValueError(f"Unknown percentile syntax: {code}")
    low, high = float(match[1]), float(match[2]) if match[2] is not None else None
    if low < 0 or low > 100 or high is not None and not low < high <= 100:
        raise ValueError(f"Invalid percentile bounds: {code}")
    return {"group_id": code, "original_code": code, "lower_bound": low, "upper_bound": high,
            "population_share": (high - low) / 100 if high is not None else None, "is_interval": high is not None}


def number(value):
    if value is None or str(value).strip().lower() in ("", "na", "nan", "null", ".."):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Nonfinite number: {value}")
    return result


def country_dimensions(db, snapshot, manifest, file_ids):
    countries, areas = {}, []
    overrides = manifest["country_config"]["overrides"]
    for item in manifest["files"]:
        if item["kind"] != "countries":
            continue
        provider = item["provider"]
        payload = read_payload(snapshot, item)
        rows = wb_page(payload)[1] if provider == "world_bank" else list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";"))
        for row in rows:
            code = row["id"] if provider == "world_bank" else row["alpha2"]
            name = row["name"] if provider == "world_bank" else row["shortname"]
            is_aggregate = row["region"]["id"] == "NA" if provider == "world_bank" else not row["region"]
            override = overrides.get(provider, {}).get(code)
            iso = pycountry.countries.get(**({"alpha_3": code} if provider == "world_bank" else {"alpha_2": code}))
            iso3 = None
            kind = "aggregate" if is_aggregate else "unmapped"
            if not is_aggregate and (override or iso):
                iso3 = override["iso3"] if override else iso.alpha_3
                iso2 = override["iso2"] if override else iso.alpha_2
                kind = "country"
                region = row["region"]["value"] if provider == "world_bank" else row["region"]
                subregion = None if provider == "world_bank" else row["region2"]
                existing = countries.get(iso3)
                # WID supplies a geographic region, whereas WB regions are operational groupings.
                if existing is None or provider == "wid":
                    countries[iso3] = {"iso3": iso3, "iso2": iso2, "country_name": name, "region": region,
                                       "subregion": subregion, "code_status": override.get("code_status", "override") if override else "ISO_3166_1"}
            areas.append({"area_id": provider + ":" + code, "provider": provider, "original_code": code,
                          "alternate_code": row["iso2Code"] if provider == "world_bank" else None,
                          "area_name": name, "area_type": kind, "iso3": iso3, "file_id": file_ids[item["path"]]})
    insert_rows(db, "countries", list(countries.values()))
    insert_rows(db, "areas", areas)
    for area in areas:
        if area["area_type"] == "unmapped":
            issue(db, "unmapped_country_code", area["original_code"] + ": " + area["area_name"], area["area_id"])
    return {a["area_id"]: a for a in areas}


def series_record(area, source, code, original, metadata, meta_file, price_year=None):
    wid = source.startswith("wid:")
    if wid:
        statistic = {"a": "mean", "s": "share", "t": "threshold", "m": "total", "n": "population", "i": "index", "x": "ppp_factor"}[code[0]]
        monetary = code[0] in "amt"
        income = {"ptinc": "pretax_national_income", "nninc": "net_national_income"}.get(code[1:6])
        unit = metadata.get("unit") or {"s": "fraction", "n": "people", "i": "index", "x": "LCU_per_USD_PPP"}.get(code[0])
        return {"series_id": area + ":" + code, "area_id": area, "source_id": source, "indicator_code": code,
                "original_variable": original, "statistic": statistic, "income_definition": income,
                "population_basis": "adult_20_plus" if code[6:9] == "992" else "all_ages" if code[0] in "anms" else "not_applicable",
                "statistical_unit": "equal_split_adults" if code[-1] == "j" else "individuals",
                "unit": unit, "currency": unit if monetary and unit and re.fullmatch("[A-Z]{3}", unit) else None,
                "price_basis": "constant" if monetary else "not_applicable", "price_year": price_year if monetary else None,
                "method": metadata.get("method"), "citation": metadata.get("source"), "quality": metadata.get("avg_quality"),
                "metadata_json": json.dumps(metadata, ensure_ascii=False), "metadata_file_id": meta_file}
    return {"series_id": area + ":" + code, "area_id": area, "source_id": source, "indicator_code": code,
            "original_variable": original, "statistic": "population" if code == "SP.POP.TOTL" else "ppp_factor",
            "income_definition": None, "population_basis": "all_ages" if code == "SP.POP.TOTL" else "not_applicable",
            "statistical_unit": "individuals" if code == "SP.POP.TOTL" else "not_applicable",
            "unit": "people" if code == "SP.POP.TOTL" else "LCU_per_international_dollar_GDP",
            "currency": None, "price_basis": "not_applicable" if code == "SP.POP.TOTL" else "current",
            "price_year": None, "method": metadata.get("sourceNote"), "citation": metadata.get("sourceOrganization"),
            "quality": None, "metadata_json": json.dumps(metadata, ensure_ascii=False), "metadata_file_id": meta_file}


def ingest_wb(db, snapshot, manifest, file_ids, areas):
    alternate_codes = {a["alternate_code"]: a["area_id"] for a in areas.values()
                       if a["provider"] == "world_bank" and a["alternate_code"]}
    metadata = {}
    for item in manifest["files"]:
        if item["kind"] == "indicator_metadata":
            for row in wb_page(read_payload(snapshot, item))[1]:
                metadata[row["id"]] = (row, file_ids[item["path"]])
    seen_series = set()
    selected = set(manifest["build_filters"]["countries"])
    start, end = manifest["build_filters"]["start_year"], manifest["build_filters"]["end_year"]
    for item in manifest["files"]:
        if item["provider"] != "world_bank" or item["kind"] != "observations":
            continue
        batch, series = [], []
        for index, row in enumerate(wb_page(read_payload(snapshot, item))[1], 1):
            code, year = row["indicator"]["id"], int(row["date"])
            raw_code = row.get("countryiso3code") or row["country"]["id"]
            area = "world_bank:" + raw_code
            if area not in areas and not row.get("countryiso3code"):
                area = alternate_codes.get(row["country"]["id"], area)
            if area not in areas:
                issue(db, "unmapped_observation", json.dumps(row), area, year, code)
                continue
            if selected and areas[area]["iso3"] not in selected or not start <= year <= end:
                continue
            sid = area + ":" + code
            if sid not in seen_series:
                meta, meta_file = metadata.get(code, ({}, None))
                series.append(series_record(area, "world_bank:" + manifest["run_id"], code, code, meta, meta_file))
                seen_series.add(sid)
            batch.append({"observation_id": stable_id(sid, year, "p0p100"), "series_id": sid, "year": year, "group_id": "p0p100",
                          "value": number(row["value"]), "original_value": None if row["value"] is None else str(row["value"]),
                          "data_status": "source_reported", "source_quality": None,
                          "source_status": json.dumps({k: row.get(k) for k in ("obs_status", "footnote", "unit", "decimal")}),
                          "is_requested": True, "file_id": file_ids[item["path"]], "source_row": index})
        insert_rows(db, "series", series)
        insert_rows(db, "observations", batch)


def ingest_wid(db, snapshot, manifest, file_ids, areas):
    config = manifest["config"]
    start, end = manifest["build_filters"]["start_year"], manifest["build_filters"]["end_year"]
    selected = set(manifest["build_filters"]["countries"])
    variables = set(config["wid"]["variables"])
    physical = sorted(variables | {x[:6] + x[-1] + x[6:9] for x in variables})
    metadata_items = {f["area"]: f for f in manifest["files"] if f["kind"] == "metadata" and f["provider"] == "wid"}
    groups = {"p0p100"}
    for n, item in enumerate([f for f in manifest["files"] if f["provider"] == "wid" and f["kind"] == "data"], 1):
        area = "wid:" + item["area"]
        if selected and areas[area]["iso3"] not in selected:
            continue
        db.execute("BEGIN TRANSACTION")
        meta_item = metadata_items.get(item["area"])
        metadata = {}
        if meta_item:
            for row in csv.DictReader(io.StringIO(read_payload(snapshot, meta_item).decode("utf-8-sig")), delimiter=";"):
                if row["variable"] in physical:
                    code = canonical_wid(row["variable"], row["age"], row["pop"])
                    metadata[code] = row
        # DuckDB streams the large raw country file and filters before materializing Python rows.
        path = str(Path(snapshot) / item["path"])
        marks = ",".join("?" for _ in physical)
        db.execute("CREATE OR REPLACE TEMP TABLE raw_country AS SELECT * FROM (SELECT *, row_number() OVER () AS source_row FROM read_csv(?, delim=';', header=true, all_varchar=true, compression='gzip')) WHERE variable IN (" + marks + ")", [path, *physical])
        rows = db.execute("SELECT * FROM raw_country").fetch_arrow_table().to_pylist()
        for row in rows:
            row["canonical"] = canonical_wid(row["variable"], row["age"], row["pop"])
        base_years = sorted({int(r["year"]) for r in rows if r["canonical"] == "inyixx999i" and r["percentile"] == "p0p100" and number(r["value"]) is not None and abs(number(r["value"]) - 1) < 1e-10})
        price_year = base_years[0] if len(base_years) == 1 else None
        if price_year is None:
            issue(db, "unknown_price_year", f"Years with price index = 1: {base_years}", area)
        # Keep exact conversion inputs even when the user requests an earlier observation period.
        keep = [r for r in rows if start <= int(r["year"]) <= end or
                r["canonical"] in ("inyixx999i", "xlcusp999i") and int(r["year"]) == price_year]
        original = {r["canonical"]: r["variable"] for r in keep}
        series = []
        for code in sorted(original):
            meta = metadata.get(code, {})
            if not meta:
                issue(db, "missing_series_metadata", "No matching WID metadata", area, indicator=code)
            series.append(series_record(area, "wid:" + manifest["run_id"], code, original[code], meta,
                                        file_ids[meta_item["path"]] if meta_item else None, price_year))
            if code[0] in "amt" and not series[-1]["currency"]:
                issue(db, "unknown_income_currency", "No unambiguous currency code in WID metadata; PPP conversion excluded", area, indicator=code)
        insert_rows(db, "series", series)
        new_groups = {r["percentile"] for r in keep} - groups
        insert_rows(db, "percentile_groups", [percentile(p) for p in sorted(new_groups)])
        groups.update(new_groups)
        batch = []
        for row in keep:
            if row["country"] != item["area"]:
                raise ValueError(f"Unexpected country in {path}: {row['country']}")
            year, code = int(row["year"]), row["canonical"]
            sid = area + ":" + code
            batch.append({"observation_id": stable_id(sid, year, row["percentile"]), "series_id": sid,
                          "year": year, "group_id": row["percentile"], "value": number(row["value"]),
                          "original_value": row["value"], "data_status": "source_reported",
                          "source_quality": row.get("data_quality"), "source_status": None,
                          "is_requested": start <= year <= end, "file_id": file_ids[item["path"]], "source_row": row["source_row"]})
        insert_rows(db, "observations", batch)
        db.execute("COMMIT")
        if n % 20 == 0:
            print(f"Normalized WID: {n} country files", flush=True)
    db.execute("DROP TABLE IF EXISTS raw_country")


def derive_ppp(db):
    rows = db.execute("""SELECT DISTINCT s.area_id, s.currency, s.price_year FROM series s
        JOIN areas a USING(area_id) WHERE a.provider='wid' AND s.currency IS NOT NULL AND s.price_year IS NOT NULL""").fetchall()
    for area, currency, year in rows:
        factors = db.execute("""SELECT o.observation_id, o.value, s.method FROM observations o JOIN series s USING(series_id)
            WHERE s.area_id=? AND s.indicator_code='xlcusp999i' AND o.year=? AND o.group_id='p0p100'""", [area, year]).fetchall()
        price = db.execute("""SELECT o.observation_id FROM observations o JOIN series s USING(series_id)
            WHERE s.area_id=? AND s.indicator_code='inyixx999i' AND o.year=? AND o.group_id='p0p100' AND abs(o.value-1)<1e-10""", [area, year]).fetchall()
        if len(factors) != 1 or factors[0][1] is None or factors[0][1] <= 0 or len(price) != 1:
            issue(db, "ppp_conversion_unavailable", f"No positive WID PPP factor and unit price index at {year}", area)
            continue
        factor_id, factor, method = factors[0]
        benchmarks = sorted(set(re.findall(r"ICP\s*\(?\s*(\d{4})", method or "")))
        reference = "ICP " + benchmarks[0] if len(benchmarks) == 1 else "WID source methodology; benchmark unspecified"
        insert_rows(db, "ppp_conversions", [{"conversion_id": stable_id(area, currency, year), "area_id": area,
            "currency": currency, "price_year": year, "ppp_reference": reference, "factor": factor,
            "ppp_observation_id": factor_id, "price_observation_id": price[0][0],
            "method": "income_lcu_constant / WID_xlcusp_at_price_base_year; no FX or WB substitution",
            "data_status": "derived"}])
