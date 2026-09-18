# Investigating the WIR 2026 global reference of 30,100 PPP euros

Investigation date: 2026-09-16. No experiment reference or scenario was changed.

## Conclusion

The figure is confirmed as a published number, and its rounding can be reproduced exactly from the report's archived workbook. It is **not independently confirmed as a correct 2025 PPP-euro mean**. There is a large inconsistency with the report's own macroeconomic totals and evidence suggesting that dollar-denominated world distribution values were labeled as euros. The exact input vintage used for the final figure remains unavailable in the files inspected, so the currency-error explanation remains a strong hypothesis rather than a fully reproduced upstream diagnosis.

Do not replace our computed reference with 30,100 PPP euros on this evidence.

## Exact location and reproduction

The local `docs/World_Inequality_Report_2026.pdf`, page 39, Figure 1.4, contains the figure supplied by the user. It is an embedded image, inspected separately from the page's extractable text. Its units are explicitly 2025 PPP euros per adult per year; the population is approximately 5.6 billion adults.

The official archive `WIR_2026_Chapters_1_to_8.zip` contains `WIR_2026_Chapter1.xlsx`:

| Location | Value or formula |
|---|---|
| `data-F1.4.!D3` | `30094.60546875`, stored as a number, without a formula |
| `F1.4!D4` | `MROUND('data-F1.4.'!D3,100)` |
| Cached result in `F1.4!D4` | `30100` |
| `data-F1.4.!G3` | `5563443159.4114895` adults |

This reproduces the displayed rounding, not the underlying world distribution from the original micro/bracket inputs.

The unrounded group averages also reconcile internally:

`0.5 × 5092.0029296875 + 0.4 × 29054.82421875 + 0.1 × 159266.734375 = 30094.60458984375`

The difference from the stored overall mean is less than 0.001. Unlike the country-sheet issue, this figure has consistent group weights and means. Internal consistency alone does not establish the monetary unit.

## What the published replication code does

`WIR2026_Chapter1.do`, Figure 1.4 section:

1. Loads WID world (`WO`) and world-at-market-exchange-rates (`WO-MER`) pre-tax income distributions, `aptinc992j`, for equal-split adults.
2. Selects a non-overlapping set of percentile brackets, with increasingly fine brackets at the top.
3. Calls R package `gpinter` with `shares_fit(bracketavg=..., p=...)`, then `generate_tabulation(...)`.
4. Uses the fitted distribution's `top_average` for the full-population row, and bracket averages for the bottom 50% and middle 40%.
5. Exports the tabulation. There is no PPP-euro conversion in this figure's code block.

The provided replication configuration sets `year_output` to 2024, and the embedded R loop explicitly iterates over 1980 and 2024. It also writes the figure to the Chapter 2 workbook, whereas the distributed final figure is in Chapter 1. Consequently, running the downloadable scripts unchanged is not an exact replication of the final 2025 workbook.

The PDF's Appendix 6, page 203, describes a 2025 extension using UN population projections, previous-decade average growth for macro aggregates, and recent two-year averages for other indicators. The inspected Figure 1.4 code does not document a complete implementation reconciling its 2024 settings with the final 2025 figure.

## Independent check against the report's own totals

The same Chapter 1 workbook, `data-F1.1`, has a 2025 row:

| Input | Cell | Value |
|---|---|---:|
| Annual national income per person, PPP euros | B228 | 14,031.12109375 |
| Total population, millions | C228 | 8,230.533476 |
| Adult population from Figure 1.4 | `data-F1.4.!G3` | 5,563,443,159.4114895 |

The Figure 1.1 construction is documented in `WIR2026_Chapter2.do`. It converts national income totals to PPP euros, aggregates them, then divides by total population. Thus the matching income-per-adult calculation is:

`14,031.12109375 × (8,230.533476 × 1,000,000) / 5,563,443,159.4114895 = 20,757.579175147923 PPP EUR/adult/year`

The macro series implies total income of 115.484 trillion PPP euros. Interpreting Figure 1.4's 30,094.60546875 as euros implies 167.430 trillion PPP euros. These cannot describe the same global income total on the same population, year and currency basis. A one-year change or rounding does not reconcile this within-report discrepancy.

## Evidence for a currency mismatch

The official WID bulk world files downloaded during this investigation are retained separately under `outputs/reference_tables/investigation/`:

- `WID_metadata_WO.csv.gz` labels `aptincj992`, `anninci992`, and `anninci999` as **USD**.
- `WID_data_WO.csv.gz` gives `xlcuspi999 = 1`, and a non-unit `xlceupi999` conversion factor.
- This particular endpoint's downloaded monetary data use a 2024 price base and do not provide the final 2025 report distribution. It must not be represented as the report's original input snapshot.
- The Figure 1.4 code reads world distributions without dividing by `xlceup999i`; the Figure 1.1 code does explicitly divide country income totals by euro PPP factors.

This combination suggests a dollar/euro labeling or conversion mismatch in Figure 1.4. It does not establish the exact historical currency or value of every input used to produce the final workbook. If 30,094.61 were 2025 PPP dollars, dividing by our saved 2025 euro factor gives about 20,404.29 PPP euros. That is a diagnostic, not a verified correction of the report.

Earlier generic descriptions that world-region WID data are always in PPP euros are unsafe for this file. Inspect the series metadata and conversion factors for the specific download.

## Comparison with our reference

Our 2024 adult reference is computed from 213 validated country distributions:

`171,328,886,095,390.5 PPP USD / 5,493,121,381 adults = 31,189.714228415756 PPP USD/adult/year`

Using the saved US 2025 PPP-euro factor, `1.474915623664856 USD / PPP EUR`, this is approximately **21,146.78 PPP EUR/adult/year**. This is a currency expression of our 2024 reference, not a 2025 estimate. The corresponding full-population reference remains **20,994.38 PPP USD/person/year**.

Read-only calls to the experiment's validation and reference functions reproduced the saved 2024 values. The current normalized database has no eligible 2025 percentile distributions, so an equivalent 2025 experiment reference cannot yet be computed through that pipeline.

If 30,100 PPP euros were imposed on the existing adult distributions, it would mean approximately **44,394.96 PPP dollars per adult**, **42.34% above** their current mean. In an equal-income scenario on that same adult population, this would require 42.34% more aggregate income than the modeled baseline. It is not a neutral replacement of the budget-balanced reference. An adult benchmark also cannot be used directly as a per-person target in the full-population scenario.

Recommended disposition: retain the reference calculated from the modeled distribution. An external report benchmark could be a separately labeled comparison, but adopting it as the conservation target requires resolving its units, year, source vintage, and consistency with the income total first.

## Sources and retained evidence

- Local PDF: `docs/World_Inequality_Report_2026.pdf`, pages 39 and 203.
- [Official methodology and downloads](https://wir2026.wid.world/methodology/).
- [Chapter workbooks](https://wir2026.wid.world/www-site/uploads/2025/11/WIR_2026_Chapters_1_to_8.zip).
- [Replication code](https://wir2026.wid.world/www-site/uploads/2025/11/WIR2026_computer_codes.zip).
- [Technical notes](https://wir2026.wid.world/www-site/uploads/2025/12/WIR26_TechnicalReport.pdf), Figure 1.4, printed page 15.
- [World metadata](https://wid.world/bulk_download/WID_metadata_WO.csv) and [world data](https://wid.world/bulk_download/WID_data_WO.csv).
- Archived workbook, relevant extracted cells, local figure image, downloaded world files, and scripts are retained in `outputs/reference_tables/investigation/`.
