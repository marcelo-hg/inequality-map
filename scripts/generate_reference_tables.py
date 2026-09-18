"""Build paired PPP USD/EUR outlook tables from the frozen WID bulk snapshot."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
from pathlib import Path

import pycountry
import yaml


GROUPS = [('p0p100', 'Full pop.', 1), ('p0p50', 'Bottom 50%', .5),
          ('p50p90', 'Middle 40%', .4), ('p90p100', 'Top 10%', .1),
          ('p99p100', 'Top 1%', .01)]
SERIES = ['aptincj999', 'sptincj999', 'ahwealj999', 'shwealj999',
          'spllinf992', 'inyixxi999', 'xlcuspi999', 'xlceupi999']


def read_csv(path):
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream, delimiter=';')


def load_country(snapshot, iso3, year):
    country = pycountry.countries.get(alpha_3=iso3)
    code = country.alpha_2
    paths = [snapshot / 'wid' / f'WID_{kind}_{code}.csv.gz' for kind in ('data', 'metadata')]
    sources = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = json.loads(path.with_suffix('.receipt.json').read_text(encoding='utf-8'))
        if digest != receipt['sha256']:
            raise ValueError(f'Checksum mismatch: {path}')
        sources.append({'path': str(path), 'sha256': digest, 'url': receipt['url'],
                        'downloaded_at': receipt['downloaded_at']})
    values = {}
    for line, row in enumerate(read_csv(paths[0]), 2):
        if row['variable'] not in SERIES or row['percentile'] not in {g[0] for g in GROUPS}:
            continue
        key = (row['variable'], int(row['year']), row['percentile'])
        if key in values:
            raise ValueError(f'Duplicate observation: {code} {key}')
        values[key] = {**row, 'source_line': line}
    metadata = {r['variable']: r for r in read_csv(paths[1]) if r['variable'] in SERIES}

    def value(variable, date, group='p0p100'):
        result = float(values[variable, date, group]['value'])
        if not math.isfinite(result):
            raise ValueError(f'Non-finite input: {code} {variable}')
        return result

    bases = [date for (var, date, group) in values if var == 'inyixxi999'
             and group == 'p0p100' and abs(value(var, date) - 1) < 1e-10]
    if len(bases) != 1:
        raise ValueError(f'Ambiguous price base: {code} {bases}')
    base = bases[0]
    units = {metadata[v]['unit'] for v in ['aptincj999', 'ahwealj999']}
    if len(units) != 1 or not next(iter(units)).isupper():
        raise ValueError(f'Unexpected income/wealth currency: {code} {units}')
    factors = {currency: value(var, base) for currency, var in
               [('USD', 'xlcuspi999'), ('EUR', 'xlceupi999')]}
    if any(f <= 0 for f in factors.values()):
        raise ValueError('PPP factors must be positive')
    tables = {}
    consistency_notes = []
    for currency, factor in factors.items():
        rows = []
        for group, label, size in GROUPS:
            item = {'group': group, 'label': label}
            for concept, avg, share in [('income', 'aptincj999', 'sptincj999'),
                                        ('wealth', 'ahwealj999', 'shwealj999')]:
                item[concept + '_average'] = value(avg, year, group) / factor
                item[concept + '_share'] = value(share, year, group)
                implied_share = value(avg, year, group) * size / value(avg, year)
                if abs(implied_share - item[concept + '_share']) > .001:
                    note = (f'{concept.title()}, {label}: published share {item[concept + "_share"]:.2%}; '
                            f'share implied by published means {implied_share:.2%}. Published values retained.')
                    if note not in consistency_notes:
                        consistency_notes.append(note)
            rows.append(item)
        for concept in ('income', 'wealth'):
            if abs(sum(r[concept + '_share'] for r in rows[1:4]) - 1) > .001:
                raise ValueError(f'Shares do not sum to one: {code} {concept}')
        tables[currency] = rows
    comparison = [{'year': date,
                   'top10_bottom50_income_ratio': value('aptincj999', date, 'p90p100') / value('aptincj999', date, 'p0p50'),
                   'female_labor_income_share': value('spllinf992', date)}
                  for date in (year - 10, year)]
    selected = [row for (var, date, group), row in values.items()
                if (date == base and var in ('inyixxi999', 'xlcuspi999', 'xlceupi999'))
                or (date in (year - 10, year) and var not in ('inyixxi999', 'xlcuspi999', 'xlceupi999'))]
    return {'iso3': iso3, 'country': country.name, 'year': year, 'price_year': base,
            'local_currency': next(iter(units)), 'ppp_factors_lcu_per_unit': factors,
            'tables': tables, 'comparison': comparison, 'sources': sources,
            'consistency_notes': consistency_notes,
            'series_metadata': metadata, 'source_observations': selected}


def table(country, currency):
    symbol = '$' if currency == 'USD' else '€'
    body = ''.join('<tr><th scope="row">' + r['label'] + '</th>' +
                   ''.join(f'<td>{r[k]:,.0f}</td>' if k.endswith('average') else
                           f'<td>{r[k]:.1%}</td>' for k in
                           ['income_average', 'income_share', 'wealth_average', 'wealth_share']) + '</tr>'
                   for r in country['tables'][currency])
    years = country['comparison']
    return f'''<article><h3>{currency} PPP <span>{country['price_year']} prices</span></h3>
<table><thead><tr class="band"><th></th><th colspan="2">Income</th><th colspan="2">Wealth</th></tr>
<tr class="labels"><th>Population<br>group</th><th>Avg. income<br>(PPP {symbol}/year)</th><th>Share of<br>total (%)</th><th>Avg. wealth<br>(PPP {symbol})</th><th>Share of<br>total (%)</th></tr></thead><tbody>{body}</tbody>
<tbody class="comparison"><tr class="band"><th colspan="3">Year</th><th>{years[0]['year']}</th><th>{years[1]['year']}</th></tr>
<tr><th colspan="3">Top 10% / Bottom 50% income gap</th><td>{years[0]['top10_bottom50_income_ratio']:.1f}</td><td>{years[1]['top10_bottom50_income_ratio']:.1f}</td></tr>
<tr><th colspan="3">Female labor income share</th><td>{years[0]['female_labor_income_share']:.1%}</td><td>{years[1]['female_labor_income_share']:.1%}</td></tr></tbody></table></article>'''


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year', type=int, default=2024)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=root / 'outputs/reference_tables')
    args = parser.parse_args()
    snapshots = sorted((root / 'data/raw').glob('*/wid'))
    if args.snapshot is None and len(snapshots) != 1:
        parser.error('Specify --snapshot when there is not exactly one frozen snapshot')
    snapshot = args.snapshot or snapshots[0].parent
    countries = yaml.safe_load((root / 'config/countries.yml').read_text())['reference_countries']
    result = [load_country(snapshot, country, args.year) for country in countries]
    if len({c['price_year'] for c in result}) != 1:
        raise ValueError('Countries have different price bases')
    ratio = [c['ppp_factors_lcu_per_unit']['EUR'] / c['ppp_factors_lcu_per_unit']['USD'] for c in result]
    if max(ratio) - min(ratio) > 1e-5:
        raise ValueError('Cross-country USD/EUR PPP ratios disagree')
    args.output.mkdir(parents=True, exist_ok=True)
    notes = '''Income and wealth use WID’s published all-age, equal-split series (aptincj999 / ahwealj999), before redistribution.
Income is annual; wealth is a stock. Full pop. means all ages. Group shares use sptincj999 / shwealj999;
income and wealth groups are ranked separately. The top 1% is included in the top 10%.
Female labor income share uses spllinf992 (adults aged 20+). The income gap is the top 10% mean divided by the bottom 50% mean.
Amounts are divided by each country’s WID PPP factor at the price-base year: xlcuspi999 for dollars and xlceupi999 for euros.
No market exchange rate is used. Values are rounded only for display. Published WID data may include estimates and revisions;
this frozen snapshot can differ from the report image. Source codes here retain the bulk export ordering.'''
    payload = {'year': args.year, 'snapshot': str(snapshot), 'methodology': notes,
               'usd_per_eur_ppp': sum(ratio) / len(ratio), 'countries': result}
    (args.output / 'reference_tables.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    sections = ''.join(f'<section><h2>Inequality outlook — {html.escape(c["country"])}</h2><div class="pair">' +
                       table(c, 'USD') + table(c, 'EUR') + '</div><p class="country-note">'
                       f'Source currency: {c["local_currency"]}. PPP conversion: 1 PPP € ≈ {ratio[i]:.6f} PPP $.</p>' +
                       (f'<p class="country-note">Source consistency: {html.escape(" ".join(c["consistency_notes"]))}</p>' if c['consistency_notes'] else '') + '</section>'
                       for i, c in enumerate(result))
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reference countries — {args.year} inequality outlook, USD and EUR PPP</title><style>
*{{box-sizing:border-box}}body{{font:15px/1.45 Arial,sans-serif;color:#17212b;background:#f3f5f4;margin:0;padding:32px}}
main{{max-width:1200px;margin:auto}}h1{{font-size:30px;margin:0 0 8px}}header p{{max-width:950px;color:#4a565d}}
section{{background:white;padding:24px;margin:24px 0;border:1px solid #d4ddd7;break-inside:avoid}}
h2{{font-size:20px;margin:0 0 16px}}h3{{font-size:16px;margin:0 0 8px}}h3 span{{font-size:12px;font-weight:normal;float:right;color:#56645c}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}table{{border-collapse:collapse;table-layout:fixed;width:100%;font-size:13px;border:2px solid #17212b}}
th,td{{border:1px solid #17212b;padding:9px 5px;text-align:center;font-variant-numeric:tabular-nums}}td{{white-space:nowrap}}
.band{{background:#258a36;color:white}}.labels{{background:#c61926;color:white}}.labels th:first-child{{background:#f4f7f4;color:#17212b}}
tbody th{{background:#f4f7f4}}.comparison .band th{{background:#258a36}}.comparison .band th:nth-child(n+2){{background:#c61926}}
.country-note{{font-size:12px;color:#56645c;margin:10px 0 0}}footer{{font-size:13px;color:#4a565d}}a{{color:#146032}}
@media(max-width:950px){{.pair{{grid-template-columns:1fr}}body{{padding:16px}}}}
@media print{{body{{background:white;padding:0}}section{{page-break-after:always;margin:0;border:0;padding:12px 0}}.pair{{grid-template-columns:1fr 1fr;gap:16px}}th,td{{padding:7px 4px}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style><main><header><h1>Reference countries · Inequality outlook</h1><p>{args.year} income and wealth · {result[0]['price_year']} prices · Full population, before redistribution.<br>Paired tables in PPP dollars and PPP euros, with {args.year-10}/{args.year} comparisons.</p></header>
{sections}<footer><p>{html.escape(notes)}</p><p>Frozen snapshot: {snapshot.name}. Source: <a href="https://wid.world/bulk_download/">WID country bulk exports</a> · <a href="https://wid.world/document/convert-wid-world-series/">WID currency conversion methodology</a>.</p></footer></main></html>'''
    (args.output / 'reference_tables.html').write_text(document, encoding='utf-8')
    print(f'Generated {len(result) * 2} tables: {args.output / "reference_tables.html"}')
    print(f'PPP USD per PPP EUR: {payload["usd_per_eur_ppp"]:.8f}')
    for c in result:
        print(c['iso3'], 'mean income:', {k: round(v[0]['income_average'], 2) for k, v in c['tables'].items()})


if __name__ == '__main__':
    main()
