"""Publication-style SVG choropleths joined exclusively on ISO-3 codes."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

import httpx

from .common import digest_file, read_yaml, write_json


# Green means a large share, then lime, gold, orange, and red as it declines.
BINS = (0, 10, 30, 50, 70, 90, 100)
COLORS = ("#f13b28", "#ff9828", "#f7cf36", "#91cb32", "#28a344", "#007e62")
MISSING_COLOR = "#aeb8bd"
NAVY = "#0b265f"
PANEL = "#e5f1fb"


def download_boundaries(root, path=None):
    root = Path(root)
    target = Path(path) if path else root / "data/external/natural_earth/ne_110m_admin_0_countries.geojson"
    if target.exists():
        return target
    config = read_yaml(root / "config/sources.yml")["natural_earth"]
    response = httpx.get(config["boundary_url"], follow_redirects=True, timeout=90)
    response.raise_for_status()
    data = response.json()
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("Natural Earth response is not a GeoJSON FeatureCollection")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    write_json(target.with_suffix(".metadata.json"), {"source": config["boundary_url"], "citation": config["citation"],
                                                        "sha256": digest_file(target)})
    return target


def _iso3(feature):
    properties = feature.get("properties") or {}
    for key in ("ISO_A3_EH", "ISO_A3", "ADM0_A3"):
        value = properties.get(key)
        if isinstance(value, str) and len(value) == 3 and value != "-99":
            return value
    return None


def _rings(geometry):
    if geometry.get("type") == "Polygon":
        return geometry.get("coordinates", [])
    if geometry.get("type") == "MultiPolygon":
        return [ring for polygon in geometry.get("coordinates", []) for ring in polygon]
    return []


def _project(longitude, latitude):
    """Spherical Equal Earth, with ONE scale for both axes (PROJ eqearth).

    https://proj.org/en/stable/operations/projections/eqearth.html
    Country paths and annotation anchors must use this same transform.
    """
    a1, a2, a3, a4 = 1.340264, -.081106, .000893, .003796
    m = math.sqrt(3) / 2
    theta = math.asin(m * math.sin(math.radians(float(latitude))))
    t2, t6 = theta ** 2, theta ** 6
    x = math.radians(float(longitude)) * math.cos(theta) / (m * (a1 + 3*a2*t2 + t6*(7*a3 + 9*a4*t2)))
    y = theta * (a1 + a2*t2 + t6*(a3 + a4*t2))
    return 900 + 270*x, 580 - 270*y


def _path(ring):
    points = [_project(longitude, latitude) for longitude, latitude, *_ in ring]
    if not points:
        return ""
    return "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in points) + " Z"


def _color(value):
    if value is None:
        return MISSING_COLOR, "No data"
    if not math.isfinite(value) or not 0 <= value <= 1 + 1e-10:
        raise ValueError(f"Invalid map share: {value}")
    # Remove arithmetic noise at published percentile boundaries.
    percent = round(min(100, max(0, value * 100)), 9)
    for index, upper in enumerate(BINS[1:]):
        if percent < upper or upper == 100:
            return COLORS[index], _bin_label(index)


def _bin_label(index):
    if index == 5:
        return "90–100%"
    return f"{BINS[index]}–<{BINS[index + 1]}%"


def _metric_words(metric):
    return {
        "winner_share": ("better off", "Share of each country's population that would be better off", "Better off"),
        "loser_share": ("worse off", "Share of each country's population that would be worse off", "Worse off"),
        "unchanged_share": ("roughly unchanged", "Share of each country's population that would be roughly unchanged", "Unchanged"),
    }.get(metric, (metric.replace("_", " "), metric.replace("_", " ").title(), metric.replace("_share", "").title()))


def _format_people(value):
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f} billion"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.0f} million"
    return f"{value:,.0f}"


def _reference_income(metadata):
    reference = metadata.get("reference", {})
    value = reference.get("value_ppp")
    unit = "adult" if metadata.get("population_basis") == "adult_20_plus" else "person"
    currency = reference.get("ppp_currency", metadata.get("ppp", {}).get("ppp_currency", "unspecified currency")).removesuffix("_PPP")
    year = reference.get("price_year", metadata.get("ppp", {}).get("price_year"))
    money_unit = f"{year} PPP {currency}" if year else f"PPP {currency} (price year unavailable)"
    rule = metadata["scenario"]["redistribution"]
    if value is None:
        return f"Each {unit} receives their country's mean income • {money_unit} per year"
    if rule["type"] == "equal":
        value *= rule.get("target_multiplier", 1)
        return f"Equal income: {value:,.0f} {money_unit} per {unit} per year"
    floor, ceiling = value * rule["floor_multiplier"], value * rule["ceiling_multiplier"]
    return f"Income floor: {floor:,.0f} • Ceiling: {ceiling:,.0f} {money_unit} per {unit} per year"


def _global_summary(experiment_directory, results):
    summary_path = Path(experiment_directory) / "global_results.json"
    stored = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    if len({row["iso3"] for row in results}) != len(results):
        raise ValueError("Duplicate country ISO-3 codes")
    for row in results:
        pop = row.get("population", row.get("adult_population", 0))
        if not math.isfinite(pop) or pop <= 0:
            raise ValueError(f"Invalid population for {row['iso3']}")
        shares = [row[f"{kind}_share"] for kind in ("winner", "unchanged", "loser")]
        if not math.isclose(math.fsum(shares), 1, abs_tol=1e-9):
            raise ValueError(f"Shares do not sum to 100% for {row['iso3']}")
        for kind, share in zip(("winner", "unchanged", "loser"), shares):
            _color(share)
            count = row.get(f"{kind}_population", share * pop)
            if not math.isclose(count, share * pop, rel_tol=1e-9, abs_tol=1e-5):
                raise ValueError(f"Population/share mismatch: {row['iso3']} {kind}")
    population = math.fsum(row.get("population", row.get("adult_population", 0)) for row in results)
    summary = {"population": population}
    for kind in ("winner", "unchanged", "loser"):
        summary[f"{kind}_population"] = math.fsum(
            row.get(f"{kind}_share", 0) * row.get("population", row.get("adult_population", 0)) for row in results
        )
        summary[f"{kind}_share"] = summary[f"{kind}_population"] / population
    for key, value in summary.items():
        recorded = stored.get(key, stored.get("adult_population") if key == "population" else None)
        if recorded is not None and not math.isclose(value, recorded, rel_tol=1e-9, abs_tol=1e-8):
            raise ValueError(f"Global summary disagrees with country results: {key}")
    return summary


def _summary_panel(summary, basis):
    kinds = (("winner", "Better off", "#179a45"), ("unchanged", "Unchanged", "#f4cb38"), ("loser", "Worse off", "#ef3b27"))
    total = summary.get("population", summary.get("adult_population", 0))
    if not total:
        total = sum(summary.get(f"{kind}_population", 0) for kind, _, _ in kinds)
    x, y, width, bar_y, bar_height = 1200, 26, 560, 70, 38
    pieces, labels = [], []
    offset = x + 18
    usable = width - 36
    for index, (kind, label, color) in enumerate(kinds):
        people = summary.get(f"{kind}_population", 0)
        share = people / total if total else 0
        piece_width = usable * share
        pieces.append(f'<rect x="{offset:.1f}" y="{bar_y}" width="{piece_width:.1f}" height="{bar_height}" fill="{color}"/>')
        # Fixed columns keep labels legible even when the unchanged share is zero.
        center = x + 18 + usable * (index + .5) / 3
        labels.append(f'<text x="{center:.1f}" y="130" class="summary-value">{share:.1%}</text>'
                      f'<text x="{center:.1f}" y="151" class="summary-label">{_format_people(people)}</text>'
                      f'<text x="{center:.1f}" y="171" class="summary-label">{label.lower()}</text>')
        offset += piece_width
    return (f'<g><rect x="{x}" y="{y}" width="{width}" height="166" rx="15" class="panel"/>'
            f'<text x="{x + width / 2}" y="52" class="summary-title">Covered {basis}: {_format_people(total)}</text>'
            f'<clipPath id="summary-bar"><rect x="{x + 18}" y="{bar_y}" width="{usable}" height="{bar_height}" rx="5"/></clipPath>'
            f'<g clip-path="url(#summary-bar)">{"".join(pieces)}</g>{"".join(labels)}</g>')


def _legend(metric):
    _, _, short = _metric_words(metric)
    x, y = 30, 580
    rows = []
    for index, color in enumerate(reversed(COLORS)):
        label = html.escape(_bin_label(5 - index))
        rows.append(f'<rect x="{x + 18}" y="{y + 66 + index * 25}" width="31" height="20" rx="2" fill="{color}"/>'
                    f'<text x="{x + 62}" y="{y + 82 + index * 25}" class="legend-text">{label}</text>')
    rows.append(f'<rect x="{x + 18}" y="{y + 216}" width="31" height="20" rx="2" fill="{MISSING_COLOR}"/>'
                f'<text x="{x + 62}" y="{y + 232}" class="legend-text">No data</text>')
    return (f'<g><rect x="{x}" y="{y}" width="250" height="254" rx="14" class="panel"/>'
            f'<text x="{x + 17}" y="{y + 25}" class="legend-title">Share of population</text>'
            f'<text x="{x + 17}" y="{y + 46}" class="legend-title">{html.escape(short.lower())}</text>{"".join(rows)}</g>')


# (interior longitude, latitude, label x, y). Anchor locations are geographic.
CALLOUTS = {
    "USA": (-100, 39, 285, 405), "BRA": (-52, -12, 800, 785), "FRA": (2, 46, 780, 310),
    "CHN": (104, 35, 1505, 465), "NOR": (10, 64, 1015, 220), "IND": (79, 22, 1215, 695),
    "NGA": (8, 9, 840, 675),
}


def _callouts(results, metric):
    descriptor, _, _ = _metric_words(metric)
    by_iso = {row["iso3"]: row for row in results}
    output = []
    for iso3, (longitude, latitude, text_x, text_y) in CALLOUTS.items():
        x, y = _project(longitude, latitude)
        row = by_iso.get(iso3)
        value = row.get(metric) if row else None
        if value is None:
            continue
        name = html.escape(row.get("country_name", iso3))
        anchor = "end" if text_x < x else "start"
        line_end_x = text_x + (-8 if anchor == "start" else 8)
        line_end_y = text_y + 6
        if iso3 == "NGA":
            anchor, line_end_x, line_end_y = "middle", text_x, text_y - 13
        output.append(f'<g class="callout"><path d="M {x} {y} L {line_end_x} {line_end_y}"/>'
                      f'<circle cx="{x}" cy="{y}" r="5"/><circle cx="{x}" cy="{y}" r="2.4" class="callout-dot"/>'
                      f'<text x="{text_x}" y="{text_y}" text-anchor="{anchor}" class="callout-name">{name}</text>'
                      f'<text x="{text_x}" y="{text_y + 22}" text-anchor="{anchor}" class="callout-value">{value:.1%}</text>'
                      f'<text x="{text_x}" y="{text_y + 42}" text-anchor="{anchor}" class="callout-detail">{descriptor}</text></g>')
    return "".join(output)


def _selected_countries(results, metric):
    by_iso = {row["iso3"]: row for row in results}
    selected = [by_iso[iso3] for iso3 in ("BRA", "USA", "FRA", "CHN", "NOR", "IND", "NGA") if iso3 in by_iso]
    if not selected:
        return ""
    x, y, width = 28, 908, 760
    columns = min(len(selected), 7)
    cell_width = (width - 30) / columns
    cells = []
    for index, row in enumerate(selected):
        center = x + 15 + cell_width * (index + .5)
        if index:
            divider = x + 15 + cell_width * index
            cells.append(f'<path d="M {divider:.1f} {y + 54} L {divider:.1f} {y + 136}" class="divider"/>')
        cells.append(f'<text x="{center:.1f}" y="{y + 80}" text-anchor="middle" class="country-name">{html.escape(row["country_name"])}</text>'
                     f'<text x="{center:.1f}" y="{y + 111}" text-anchor="middle" class="country-value">{row[metric]:.1%}</text>')
    _, _, short = _metric_words(metric)
    return (f'<g><rect x="{x}" y="{y}" width="{width}" height="162" rx="14" class="panel"/>'
            f'<text x="{x + 20}" y="{y + 32}" class="bottom-title">Selected countries (% {html.escape(short.lower())})</text>{"".join(cells)}</g>')


def _notes(metadata, summary, metric):
    descriptor, _, _ = _metric_words(metric)
    scenario = metadata.get("scenario", {})
    balanced = metadata.get("budget_conservation", {}).get("balanced")
    balance = "The redistribution is budget-balanced." if balanced else "The redistribution is not budget-balanced."
    total = summary.get("population", summary.get("adult_population", 0))
    kind = metric.removesuffix("_share")
    share = summary.get(f"{kind}_population", 0) / total if total else 0
    return (f'<g><rect x="810" y="908" width="950" height="162" rx="14" class="panel"/>'
            f'<text x="832" y="940" class="bottom-title">Reading this map</text>'
            f'<text x="832" y="970" class="note">• Color shows the share of people in each country who would be {html.escape(descriptor)}.</text>'
            f'<text x="832" y="995" class="note">• Across covered countries, {share:.1%} of {_format_people(total)} would be {html.escape(descriptor)}.</text>'
            f'<text x="832" y="1020" class="note">• {html.escape(balance)} Estimates use published percentile-bin incomes.</text>'
            f'<text x="832" y="1045" class="note">{("• Full-population estimates use the scaled adult income shape." if metadata.get("population_basis") == "full_population" else "• Population and income targets refer to adults aged 20+.")} Percentages are rounded.</text></g>')


def render_map(results, metric, output, metadata, boundary_path, global_summary=None):
    values = {row["iso3"]: row.get(metric) for row in results}
    geojson = json.loads(Path(boundary_path).read_text(encoding="utf-8"))
    width, height = 1800, 1130
    paths, seen = [], set()
    for feature in geojson["features"]:
        iso3 = _iso3(feature)
        if not iso3 or iso3 == "ATA":
            continue
        seen.add(iso3)
        color, label = _color(values.get(iso3))
        value = values.get(iso3)
        title = f"{iso3}: {value:.1%} ({label})" if value is not None else f"{iso3}: no data"
        # One compound path preserves holes within country polygons.
        d = " ".join(_path(ring) for ring in _rings(feature.get("geometry") or {}))
        if d:
            paths.append(f'<path data-iso3="{iso3}" data-share="{value if value is not None else ""}" d="{d}" fill="{color}" fill-rule="evenodd" class="country"><title>{html.escape(title)}</title></path>')
    unused = sorted(set(values) - seen)
    _, subtitle, short = _metric_words(metric)
    scenario = metadata.get("scenario", {})
    title = scenario.get("name", metadata.get("scenario_id", "Equal-Earth")).replace("Hard Equal-Earth", "Hard equality")
    if not title.startswith("Equal-Earth:"):
        title = f"Equal-Earth: {title}"
    reference = metadata.get("reference", {})
    reference_label = f"{reference.get('scope', 'global').title()} {reference.get('statistic', 'mean')}"
    basis = metadata.get("population_basis", "unspecified")
    basis_label = "Adults 20+" if basis == "adult_20_plus" else "Full population"
    if basis == "adult_20_plus":
        subtitle = subtitle.replace("population", "adults (20+)")
    title_size = min(44, 1100 / max(len(title), 1) / .57)
    price_year = reference.get("price_year", metadata.get("ppp", {}).get("price_year", "?"))
    currency = reference.get("ppp_currency", metadata.get("ppp", {}).get("ppp_currency", "PPP")).removesuffix("_PPP")
    map_title = f"{short} | {reference_label} | {basis_label} | {metadata['year']} income, {price_year} PPP {currency}"
    summary = global_summary or _global_summary(Path(output).parent.parent, results)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="map-title map-subtitle">
<title id="map-title">{html.escape(map_title)}</title><desc id="map-subtitle">{html.escape(subtitle)} under {html.escape(scenario.get("name", "the selected scenario"))}.</desc>
<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f8fcff"/><stop offset="1" stop-color="#dff2fb"/></linearGradient></defs>
<style>
text {{ fill: {NAVY}; font-family: Georgia, 'Times New Roman', serif; }}
.headline {{ font-size: {title_size:.1f}px; font-weight: 700; }} .subtitle {{ font-size: 23px; }} .detail {{ font-size: 18px; }}
.panel {{ fill: {PANEL}; fill-opacity: .91; }} .summary-title {{ font-size: 20px; font-weight: 700; text-anchor: middle; }}
.summary-value {{ font-size: 22px; font-weight: 700; text-anchor: middle; }} .summary-label {{ font-size: 15px; text-anchor: middle; }}
.country {{ stroke: #ffffff; stroke-width: .5; stroke-linejoin: round; }} .legend-title {{ font-size: 17px; font-weight: 700; }} .legend-text {{ font-size: 16px; }}
.callout path {{ fill: none; stroke: {NAVY}; stroke-width: 1.25; }} .callout circle {{ fill: {NAVY}; stroke: #ffffff; stroke-width: 1.3; }} .callout .callout-dot {{ fill: #ffffff; stroke: none; }}
.callout text {{ paint-order: stroke; stroke: #f4fbff; stroke-width: 4px; stroke-linejoin: round; }}
.callout-name {{ font-size: 17px; font-weight: 700; }} .callout-value {{ font-size: 20px; font-weight: 700; }} .callout-detail {{ font-size: 16px; }}
.bottom-title {{ font-size: 21px; font-weight: 700; }} .country-name {{ font-size: 15px; }} .country-value {{ font-size: 21px; font-weight: 700; }} .divider {{ stroke: #91b7d6; }} .note {{ font-size: 17px; }}
</style>
<rect width="100%" height="100%" fill="url(#sky)"/>
<text x="30" y="64" class="headline">{html.escape(title)}</text>
<text x="30" y="104" class="subtitle">{html.escape(subtitle)}</text>
<text x="30" y="136" class="detail">{html.escape(_reference_income(metadata))}</text>
<text x="30" y="165" class="detail">{html.escape(map_title)}</text>
{_summary_panel(summary, "adults 20+" if basis == "adult_20_plus" else "people")}
<g id="geography">{"".join(paths)}</g>
{_legend(metric)}{_callouts(results, metric)}{_selected_countries(results, metric)}{_notes(metadata, summary, metric)}
<text x="30" y="1092" class="detail">Source: WID country distributions; Natural Earth boundaries. Equal Earth projection. Green indicates a higher share of the selected outcome.</text>
<text x="30" y="1118" class="detail">{html.escape(metadata.get("experiment_id", ""))} • {len(results)} countries/territories in totals; {len(unused)} without a matching map polygon.</text>
</svg>'''
    output = Path(output)
    output.write_text(svg, encoding="utf-8")
    sidecar = {**metadata, "metric": metric, "map_title": map_title, "design": "editorial_equal_earth_v3",
               "projection": "spherical Equal Earth; uniform scale", "global_summary": summary,
               "bin_convention": "lower inclusive, upper exclusive; final bin includes 100%",
               "fixed_bins_percent": list(BINS), "palette": list(COLORS), "missing_color": MISSING_COLOR,
               "boundary_file": str(boundary_path), "boundary_sha256": digest_file(boundary_path), "unmatched_result_iso3": unused}
    write_json(output.with_suffix(".json"), sidecar)
    return output


def generate_maps(root, experiment_directory, boundaries=None):
    root, experiment_directory = Path(root), Path(experiment_directory)
    boundary_path = download_boundaries(root, boundaries)
    results = json.loads((experiment_directory / "country_results.json").read_text(encoding="utf-8"))
    metadata = json.loads((experiment_directory / "metadata.json").read_text(encoding="utf-8"))
    # Legacy releases stored currency/price year only in the source lineage.
    lineage_path = experiment_directory / "input_lineage.json"
    if "ppp" not in metadata and lineage_path.exists():
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        if lineage:
            metadata["ppp"] = {key: lineage[0][key] for key in ("ppp_currency", "price_year") if key in lineage[0]}
    if "ppp" not in metadata and metadata.get("database") and Path(metadata["database"]).exists():
        import duckdb
        with duckdb.connect(metadata["database"], read_only=True) as db:
            units = db.execute("SELECT DISTINCT ppp_currency, price_year FROM income_percentiles WHERE year=?",
                               [metadata["year"]]).fetchall()
        if len(units) == 1 and all(value is not None for value in units[0]):
            metadata["ppp"] = dict(zip(("ppp_currency", "price_year"), units[0]))
    if metadata["scenario"]["redistribution"]["type"] == "equal":
        reference = metadata.get("reference", {})
        for row in results:
            value = reference.get("value_ppp")
            if value is None:
                value = reference.get("country_targets_ppp", {}).get(row["iso3"])
            if value is not None:
                target = value * metadata["scenario"]["redistribution"].get("target_multiplier", 1)
                if not math.isclose(target, row["new_mean"], rel_tol=1e-9, abs_tol=1e-6):
                    raise ValueError(f"Income target disagrees with results: {row['iso3']}")
    summary = _global_summary(experiment_directory, results)
    kind = metadata["scenario"]["redistribution"]["type"]
    metrics = ["winner_share", "loser_share"] if kind == "equal" else ["winner_share", "unchanged_share", "loser_share"]
    map_directory = experiment_directory / "maps"
    map_directory.mkdir(exist_ok=True)
    return [render_map(results, metric, map_directory / f"{metric}.svg", metadata, boundary_path, summary) for metric in metrics]
