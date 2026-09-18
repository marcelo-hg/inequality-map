from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import duckdb

from .common import digest_file, write_json
from .normalize import insert_rows, issue


def choose_partition(groups):
    """Select the finest published adjacent intervals. Never split or interpolate a bin."""
    by_low = defaultdict(list)
    for low, high, value in groups:
        if value is not None and high is not None and high > low and high - low < 100:
            by_low[low].append((low, high, value))
    # Prefer fine bins only when they lead to a complete path; a fine dead end must
    # not hide a coarser but complete published distribution.
    paths = {100.0: []}
    for low in sorted(by_low, reverse=True):
        for candidate in sorted(by_low[low], key=lambda x: x[1]):
            if candidate[1] in paths:
                paths[low] = [candidate, *paths[candidate[1]]]
                break
    return paths.get(0.0, [])


def validate_distribution(groups, source_mean=None, source_shares=None):
    if not groups:
        return {"status": "incomplete", "bin_count": 0, "mean_error": None, "max_share_error": None, "details": "No complete disjoint partition"}
    ordered = sorted(groups)
    if ordered[0][0] != 0 or ordered[-1][1] != 100 or any(a[1] != b[0] for a, b in zip(ordered, ordered[1:])):
        return {"status": "invalid", "bin_count": len(groups), "mean_error": None, "max_share_error": None, "details": "Gap or overlap"}
    weights = [(hi - lo) / 100 for lo, hi, _ in ordered]
    if any(w <= 0 for w in weights) or not math.isclose(sum(weights), 1, abs_tol=1e-10):
        return {"status": "invalid", "bin_count": len(groups), "mean_error": None, "max_share_error": None, "details": "Invalid population weights"}
    mean = sum(v * w for (_, _, v), w in zip(ordered, weights))
    mean_error = abs(mean - source_mean) / abs(source_mean) if source_mean is not None and source_mean != 0 else None
    errors = []
    for (low, high), share in (source_shares or {}).items():
        subset = [(lo, hi, val) for lo, hi, val in ordered if lo >= low and hi <= high]
        if share is not None and mean != 0 and subset and subset[0][0] == low and subset[-1][1] == high:
            errors.append(abs(sum(val * (hi-lo) / 100 for lo, hi, val in subset) / mean - share))
    max_error = max(errors) if errors else None
    flags = []
    if any(a[2] > b[2] + 1e-8 * max(1, abs(a[2]), abs(b[2])) for a, b in zip(ordered, ordered[1:])):
        flags.append("nonmonotonic_income")
    if mean_error is not None and mean_error > 0.02:
        flags.append("mean_error_above_2pct")
    if max_error is not None and max_error > 0.01:
        flags.append("share_error_above_1pp")
    status = "invalid" if flags else "passed" if mean_error is not None and len(errors) == 3 else "unverifiable"
    details = ", ".join(flags) or f"Finest adjacent published partition; {len(errors)}/3 source share comparisons"
    return {"status": status, "bin_count": len(groups), "mean_error": mean_error, "max_share_error": max_error, "details": details}


def structural_checks(db):
    checks = {
        "duplicate_observations": "SELECT count(*) FROM (SELECT series_id,year,group_id FROM observations GROUP BY ALL HAVING count(*)>1)",
        "orphan_series": "SELECT count(*) FROM observations o LEFT JOIN series s USING(series_id) WHERE s.series_id IS NULL",
        "orphan_files": "SELECT count(*) FROM observations o LEFT JOIN source_files f USING(file_id) WHERE f.file_id IS NULL",
        "orphan_groups": "SELECT count(*) FROM observations o LEFT JOIN percentile_groups g USING(group_id) WHERE g.group_id IS NULL",
        "nonfinite_values": "SELECT count(*) FROM observations WHERE value IS NOT NULL AND NOT isfinite(value)",
        "duplicate_iso3": "SELECT count(*) FROM (SELECT iso3 FROM countries GROUP BY iso3 HAVING count(*)>1)",
        "invalid_ppp_lineage": """SELECT count(*) FROM ppp_conversions c
            JOIN observations o ON o.observation_id=c.ppp_observation_id JOIN series s ON s.series_id=o.series_id
            JOIN observations p ON p.observation_id=c.price_observation_id JOIN series ps ON ps.series_id=p.series_id
            WHERE s.indicator_code<>'xlcusp999i' OR ps.indicator_code<>'inyixx999i'
            OR s.area_id<>c.area_id OR ps.area_id<>c.area_id OR o.year<>c.price_year OR p.year<>c.price_year
            OR c.factor<>o.value OR abs(p.value-1)>1e-10""",
    }
    return {name: db.execute(sql).fetchone()[0] for name, sql in checks.items()}


def validate_and_report(db, manifest, output):
    structural = structural_checks(db)
    if any(structural.values()):
        raise ValueError(f"Structural validation failed: {structural}")
    for area, year, code, n in db.execute("""SELECT s.area_id,o.year,s.indicator_code,count(*) FROM observations o
        JOIN series s USING(series_id) WHERE s.statistic IN ('population','ppp_factor','index') AND o.value<=0 GROUP BY ALL""").fetchall():
        issue(db, "nonpositive_population_ppp_or_index", f"{n} source values <= 0; retained, not usable", area, year, code)
    for area, year, code, n in db.execute("""SELECT s.area_id,o.year,s.indicator_code,count(*) FROM observations o
        JOIN series s USING(series_id) WHERE s.income_definition IS NOT NULL AND o.value<0 GROUP BY ALL""").fetchall():
        issue(db, "negative_income_or_share", f"{n} negative source values retained for methodological review", area, year, code)
    db.execute("""CREATE TABLE distribution_checks (
        area_id VARCHAR, iso3 VARCHAR, year INTEGER, status VARCHAR, bin_count INTEGER,
        mean_error DOUBLE, max_share_error DOUBLE, details VARCHAR, PRIMARY KEY(area_id,year))""")
    grouped = defaultdict(lambda: {"groups": [], "mean": None, "shares": {}})
    for area, iso3, year, code, lo, hi, value in db.execute("""SELECT s.area_id,a.iso3,o.year,s.indicator_code,
        g.lower_bound,g.upper_bound,o.value FROM observations o JOIN series s USING(series_id)
        JOIN areas a USING(area_id) JOIN percentile_groups g USING(group_id)
        WHERE o.is_requested AND s.indicator_code IN ('aptinc992j','sptinc992j') ORDER BY s.area_id,o.year""").fetchall():
        entry = grouped[area, iso3, year]
        if code == "aptinc992j":
            if lo == 0 and hi == 100:
                entry["mean"] = value
            else:
                entry["groups"].append((lo, hi, value))
        elif (lo, hi) in ((0, 50), (90, 100), (99, 100)):
            entry["shares"][lo, hi] = value
    results = []
    for (area, iso3, year), entry in sorted(grouped.items()):
        check = validate_distribution(choose_partition(entry["groups"]), entry["mean"], entry["shares"])
        results.append({"area_id": area, "iso3": iso3, "year": year, **check})
        if check["status"] != "passed":
            issue(db, "distribution_" + check["status"], check["details"], area, year, "aptinc992j")
    insert_rows(db, "distribution_checks", results)
    filters = manifest["build_filters"]
    expected = []
    for provider in filters["sources"]:
        codes = manifest["config"][provider]["variables" if provider == "wid" else "indicators"]
        expected.extend({"provider": provider, "indicator_code": code} for code in codes)
    db.execute("CREATE TEMP TABLE expected_series(provider VARCHAR,indicator_code VARCHAR)")
    insert_rows(db, "expected_series", expected)
    selected = filters["countries"]
    db.execute("CREATE TEMP TABLE selected_countries AS SELECT * FROM countries")
    if selected:
        db.execute("DELETE FROM selected_countries WHERE iso3 NOT IN (" + ",".join("?" for _ in selected) + ")", selected)
    db.execute("""CREATE TABLE coverage AS
        WITH counts AS (SELECT s.area_id, s.indicator_code,o.year,count(*) AS rows, count(o.value) AS nonnull_rows
            FROM observations o JOIN series s USING(series_id) WHERE o.is_requested GROUP BY ALL)
        SELECT c.iso3, c.country_name,e.provider,e.indicator_code,y.year,a.area_id,
            coalesce(n.rows,0) AS rows,coalesce(n.nonnull_rows,0) AS nonnull_rows,
            CASE WHEN a.area_id IS NULL THEN 'no_provider_country' WHEN n.rows IS NULL THEN 'absent'
                 WHEN n.nonnull_rows=0 THEN 'missing_values' ELSE 'available' END AS status
        FROM selected_countries c CROSS JOIN expected_series e CROSS JOIN range(?,?) y(year)
        LEFT JOIN areas a ON a.iso3=c.iso3 AND a.provider=e.provider
        LEFT JOIN counts n ON n.area_id=a.area_id AND n.indicator_code=e.indicator_code AND n.year=y.year
        ORDER BY c.iso3,e.provider,e.indicator_code,y.year""", [filters["start_year"], filters["end_year"] + 1])
    summary = {
        "run_id": manifest["run_id"], "download_status": manifest["status"], "filters": filters,
        "structural_checks": structural, "download_failures": manifest["failures"],
        "countries_catalogued": db.execute("SELECT count(*) FROM countries").fetchone()[0],
        "countries_with_data": db.execute("SELECT count(DISTINCT a.iso3) FROM observations o JOIN series s USING(series_id) JOIN areas a USING(area_id) WHERE o.is_requested AND o.value IS NOT NULL").fetchone()[0],
        "observations": db.execute("SELECT count(*) FROM observations").fetchone()[0],
        "requested_observations": db.execute("SELECT count(*) FROM observations WHERE is_requested").fetchone()[0],
        "income_ppp_rows": db.execute("SELECT count(*) FROM income_ppp WHERE is_requested").fetchone()[0],
        "coverage_status": dict(db.execute("SELECT status,count(*) FROM coverage GROUP BY status ORDER BY status").fetchall()),
        "distribution_status": dict(db.execute("SELECT status,count(*) FROM distribution_checks GROUP BY status ORDER BY status").fetchall()),
        "issues": dict(db.execute("SELECT code,count(*) FROM issues GROUP BY code ORDER BY code").fetchall()),
        "reference_countries": [],
    }
    for iso3 in manifest["country_config"]["reference_countries"]:
        detail = {"iso3": iso3, "series": [], "distribution_years": []}
        detail["series"] = db.execute("""SELECT provider, indicator_code, min(year) FILTER(WHERE nonnull_rows>0) AS first_year,
            max(year) FILTER(WHERE nonnull_rows>0) AS last_year, cast(sum(nonnull_rows) AS BIGINT) AS nonnull_rows,
            count(*) FILTER(WHERE nonnull_rows=0) AS missing_years FROM coverage WHERE iso3=? GROUP BY ALL ORDER BY 1,2""", [iso3]).fetch_arrow_table().to_pylist()
        detail["distribution_years"] = db.execute("SELECT * FROM distribution_checks WHERE iso3=? ORDER BY year", [iso3]).fetch_arrow_table().to_pylist()
        summary["reference_countries"].append(detail)
    output = Path(output)
    write_json(output / "coverage_summary.json", summary)
    lines = ["# Cobertura das bases de dados", "", f"Carga: `{manifest['run_id']}`. Estado do download: **{manifest['status']}**.", "",
             f"Países/territórios com dados: **{summary['countries_with_data']}**. Observações: **{summary['observations']:,}**.",
             f"Linhas monetárias convertidas em PPP: **{summary['income_ppp_rows']:,}**.", "",
             "Os valores publicados pelas fontes são classificados como `source_reported`: isso não significa observação direta. Notas metodológicas e qualidade originais permanecem no banco.", "",
             "## Cobertura por país, ano e série", "", "Detalhamento completo em `coverage.parquet`; ausência não é zero. Agregados não integram a contagem de países.", "",
             "| Estado | Combinações país/ano/série |", "|---|---:|"]
    lines.extend(f"| {k} | {v:,} |" for k, v in summary["coverage_status"].items())
    lines += ["", "## Distribuições", "", "Validação usa a partição mais detalhada de intervalos adjacentes publicados, sem interpolação. Grupos agregados sobrepostos ficam fora dessa partição.", "",
              "| Resultado | Países/anos |", "|---|---:|"]
    lines.extend(f"| {k} | {v:,} |" for k, v in summary["distribution_status"].items())
    lines += ["", "## Sete países de referência", "", "| País | Último ano com renda média | Último ano validado |", "|---|---:|---:|"]
    for detail in summary["reference_countries"]:
        latest = next((s["last_year"] for s in detail["series"] if s["indicator_code"] == "aptinc992j"), None)
        valid = max((r["year"] for r in detail["distribution_years"] if r["status"] == "passed"), default=None)
        lines.append(f"| {detail['iso3']} | {latest or 'ausente'} | {valid or 'nenhum'} |")
    lines += ["", "## Alertas", "", "| Alerta | Ocorrências |", "|---|---:|"]
    lines.extend(f"| {k} | {v:,} |" for k, v in summary["issues"].items())
    lines += ["", "Falhas de download e detalhes dos sete países estão em `coverage_summary.json`; alertas individuais estão em `issues.parquet`.",
              "A base de preços e o benchmark PPP constam nas conversões; séries com bases diferentes não devem ser somadas sem harmonização adicional.",
              "Nenhum resultado de redistribuição foi calculado nesta etapa.", ""]
    (output / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def validate_database(path):
    path = Path(path).resolve()
    manifest_path = path.parent / "build_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["status"] not in ("validated", "validated_incomplete"):
            raise ValueError("The database build has not completed validation")
        for name, expected in manifest["artifacts"].items():
            artifact = (path.parent / name).resolve()
            if not artifact.is_relative_to(path.parent) or digest_file(artifact) != expected:
                raise ValueError(f"Published artifact checksum mismatch: {name}")
    with duckdb.connect(str(path), read_only=True) as db:
        result = structural_checks(db)
    if any(result.values()):
        raise ValueError(result)
    return result
