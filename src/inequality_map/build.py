"""Offline builds into immutable releases, published through one atomic pointer."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import duckdb

from .common import code_version, digest_file, utc_now, write_json
from .normalize import country_dimensions, derive_ppp, ingest_wb, ingest_wid, insert_rows, issue, percentile
from .validate import validate_and_report


def build(root, snapshot, sources=None, countries=None, start=None, end=None, allow_incomplete=False):
    root, snapshot = Path(root).resolve(), Path(snapshot).resolve()
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] == "running":
        raise ValueError("Download is still running; wait for it to finish before building")
    if manifest["status"] != "complete" and not allow_incomplete:
        raise ValueError("Download incomplete: resume first, or explicitly pass --allow-incomplete")
    cfg = manifest["config"]
    filters = {"sources": sources or manifest["sources"], "countries": countries if countries is not None else manifest["countries"],
               "start_year": start if start is not None else cfg["start_year"], "end_year": end if end is not None else cfg["end_year"]}
    if not set(filters["sources"]) <= set(manifest["sources"]):
        raise ValueError("Requested provider not downloaded")
    if manifest["countries"] and not set(filters["countries"]) <= set(manifest["countries"]):
        raise ValueError("Requested countries outside download scope")
    if not cfg["start_year"] <= filters["start_year"] <= filters["end_year"] <= cfg["end_year"]:
        raise ValueError("Requested years outside download scope")
    manifest["build_filters"] = filters
    for item in manifest["files"]:
        path = (snapshot / item["path"]).resolve()
        if not path.is_relative_to(snapshot) or digest_file(path) != item["sha256"]:
            raise ValueError(f"Raw file integrity failure: {path}")
    release_id = manifest["run_id"] + "-" + uuid.uuid4().hex[:8]
    release = root / "data/processed/releases" / release_id
    release.mkdir(parents=True)
    db_path = release / "inequality.duckdb"
    build_info = {"release_id": release_id, "snapshot": str(snapshot.relative_to(root)) if snapshot.is_relative_to(root) else str(snapshot),
                  "source_manifest_sha256": digest_file(manifest_path), "filters": filters, "code": code_version(root),
                  "started_at": utc_now(), "status": "building"}
    write_json(release / "build_manifest.json", build_info)
    try:
        with duckdb.connect(str(db_path)) as db:
            db.execute("SET threads=4")
            db.execute("SET memory_limit='2GB'")
            # Bulk analytical builds otherwise checkpoint and rewrite growing ART
            # indexes after nearly every country under the default 16 MiB limit.
            db.execute("SET checkpoint_threshold='1GB'")
            db.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            insert_rows(db, "ingestion_runs", [{"run_id": manifest["run_id"], "status": manifest["status"],
                "started_at": manifest["started_at"], "finished_at": manifest.get("finished_at"),
                "code_json": json.dumps(build_info["code"]), "config_json": json.dumps(manifest),
                "manifest_sha256": digest_file(manifest_path)}])
            for provider in ("wid", "world_bank"):
                source = cfg[provider]
                insert_rows(db, "sources", [{"source_id": provider + ":" + manifest["run_id"], "provider": provider,
                    "dataset": source["dataset"], "dataset_version": "retrieval:" + manifest["run_id"],
                    "url": source["base_url"], "publication_date": None, "license": source.get("license"),
                    "citation": source["citation"], "notes": "Version is a retrieval snapshot, not an upstream release; per-file Last-Modified is preserved."}])
            file_ids = {f["path"]: f["provider"] + ":" + f["key"] for f in manifest["files"]}
            insert_rows(db, "source_files", [{"file_id": file_ids[f["path"]], "source_id": f["provider"] + ":" + manifest["run_id"],
                "run_id": manifest["run_id"], **{k: f.get(k) for k in ("path", "url", "downloaded_at", "last_modified", "sha256", "payload_sha256", "payload_bytes", "kind", "area")}}
                for f in manifest["files"]])
            areas = country_dimensions(db, snapshot, manifest, file_ids)
            unknown = set(filters["countries"]) - {a["iso3"] for a in areas.values()}
            if unknown:
                raise ValueError(f"Unknown ISO-3 filters: {sorted(unknown)}")
            insert_rows(db, "percentile_groups", [percentile("p0p100")])
            for failure in manifest["failures"]:
                issue(db, "download_failure", json.dumps(failure), severity="warning")
            if "world_bank" in filters["sources"]:
                ingest_wb(db, snapshot, manifest, file_ids, areas)
            if "wid" in filters["sources"]:
                ingest_wid(db, snapshot, manifest, file_ids, areas)
                derive_ppp(db)
            summary = validate_and_report(db, manifest, release)
            tables = [r[0] for r in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_catalog=current_database() ORDER BY table_name").fetchall()]
            for table in tables:
                path = str(release / (table + ".parquet"))
                db.execute(f"COPY (SELECT * FROM {table} ORDER BY ALL) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [path])
            db.execute("CHECKPOINT")
        build_info.update({"status": "validated_incomplete" if manifest["status"] != "complete" else "validated",
                           "finished_at": utc_now(), "summary": {k: summary[k] for k in ("observations", "countries_with_data", "distribution_status")},
                           "artifacts": {p.name: digest_file(p) for p in sorted(release.iterdir()) if p.is_file() and p.name != "build_manifest.json"}})
        write_json(release / "build_manifest.json", build_info)
        # Only this pointer changes: readers resolve a consistent DB + Parquet + report release.
        write_json(root / "database/current.json", {"release_id": release_id, "release_path": str(release.relative_to(root)).replace("\\", "/"),
                   "database": str(db_path.relative_to(root)).replace("\\", "/"), "status": build_info["status"]})
    except Exception as exc:
        build_info.update({"status": "failed", "finished_at": utc_now(), "error": f"{type(exc).__name__}: {exc}"})
        write_json(release / "build_manifest.json", build_info)
        raise
    print(f"Published {build_info['status']}: {release}", flush=True)
    return release


def current_database(root):
    root = Path(root)
    pointer = json.loads((root / "database/current.json").read_text(encoding="utf-8"))
    path = (root / pointer["database"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Database pointer escapes project")
    return path
