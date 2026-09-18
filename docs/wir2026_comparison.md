# WIR 2026 country-sheet reconciliation

Investigated 2026-09-16 against the official archived country-table workbook, report replication code, and this project's frozen WID snapshot `20260910T175500Z-e657c22a`.

## Finding

The large bottom-50% discrepancy is a numerical inconsistency in the report's country tables. It cannot be explained by choosing PPP dollars versus euros or adults versus all ages: the income shares and group means must satisfy the identity below within any consistent population and currency basis.

`group mean = national mean × group income share / group population share`

For the bottom 50%, the population share is 0.5. For the top 10%, it is 0.1. The report's bottom-half incomes are approximately national mean × bottom-half share, missing approximately a factor of two. The same pattern occurs in all seven reference-country tables. For wealth, the missing factor of two is explicitly present in the published replication code. For income, the archived table is demonstrably inconsistent, but the precise upstream operation that produced the erroneous source average has not been located.

## United States

| Quantity | WIR 2026 country sheet | Our table |
|---|---:|---:|
| National mean income, PPP EUR/year | 47,358.88 | 49,149.46 |
| Bottom 50% mean income, PPP EUR/year | 6,395.35 | 13,207.94 |
| Bottom 50% income share | 13.4% | 13.44% |
| Top 10% mean income, PPP EUR/year | 221,437.77 | 229,810.10 |
| Top 10% / bottom 50% income ratio | 34.6248 | about 17.4 |

Using the report's own national mean and rounded bottom-half share gives:

`47,358.880952 × 0.134 / 0.5 = 12,692.18 PPP EUR/year`

Its reported 6,395.35 instead implies a bottom-half income share of approximately 6.75%, contradicting the displayed 13.4%. Rounding the share to one decimal percentage point cannot account for this difference. The implied ratio using the report's rounded shares is `5 × 0.468 / 0.134 = 17.46`, rather than 34.62.

Our source observations are `aptincj999`, 2024: national mean 72,491.3 USD, bottom-half mean 19,480.6 USD, top-decile mean 338,950.5 USD. The 2025 euro PPP factor is 1.474915623664856 USD per PPP EUR; the dollar factor is 1. Our exporter divides each monetary value by the same appropriate factor. No extra factor of two is applied by our exporter.

An independent query of the experiment database's 100 adult percentile bins gives bottom-half mean 25,603.978 PPP USD and top-decile mean 445,494.01 PPP USD. Their ratio is approximately 17.4. Scaling both by the same adult-to-total-population ratio preserves this result. The experiments and the new reference tables therefore agree on the income gap.

Doubling the report's bottom-half income yields 12,790.70 PPP EUR. Our 13,207.94 is 3.26% above that; the national averages differ by 3.78%. These smaller differences remain after the factor-of-two issue is separated out. They reflect differing source vintages and conversion inputs, rather than a universal doubling in our conversion. The exact contribution of each revision has not been isolated.

## All reference countries

All monetary values below are PPP EUR. “Twice report” is a diagnostic, not a replacement estimate. It does not resolve remaining inconsistencies between the report's published means and shares.

| Country | Report bottom-half income | Our bottom-half income | Our difference from twice report |
|---|---:|---:|---:|
| Brazil | 1,167.33 | 2,385.19 | +2.16% |
| United States | 6,395.35 | 13,207.94 | +3.26% |
| France | 7,238.41 | 15,021.36 | +3.76% |
| China | 1,987.95 | 4,094.57 | +2.98% |
| Norway | 17,444.20 | 34,063.78 | -2.36% |
| India | 939.56 | 1,730.53 | -7.91% |
| Nigeria | 681.66 | 1,840.22 | +34.98% |

Nigeria has a substantial additional difference: our national mean is 46.23% above the archived report's. A factor-of-two correction alone does not reconcile its levels. Norway and India also have changes in distribution shares, so their ratio discrepancies are not exactly two.

## Confirmed report-code differences

In `WIR2026_Country_sheets_data.do`, the report computes wealth group levels as the national average multiplied by each group's wealth share. It then multiplies top 1% values by 100, top 10% by 10, and middle 40% by 2.5. It omits the corresponding multiplier of 2 for the bottom 50%.

For the US this reproduces the report exactly: `264,685.71875 × 0.01 = 2,646.8571875`. A mean for the bottom-half population consistent with that rounded share would be twice this value.

The same script selects wealth shares (`shweal999j`) from 2023 and changes their year label to 2024. It combines them with 2024 average wealth (`ahweal999i`), then constructs group means. Our tables instead read 2024 published group means and shares (`ahwealj999` and `shwealj999`). Thus the wealth comparison also involves different years and construction methods.

For income, the report selects `aptinc999j` and divides by its 2024 euro PPP factor; the provided VBA then copies values without another numerical transformation. The available scripts do not show an income division by two. The error could be in the report's input vintage or another preparation step. Do not describe the exact income-code cause as confirmed.

The report rounds source values, including shares and conversion factors, to 0.001. Our exporter keeps full source precision until display. Our monetary series have a validated 2025 price base, so we use the 2025 PPP factor. Simply substituting a 2024 factor into our 2025-price incomes would mix price bases and is not a valid reconciliation.

The current source also contains some internally inconsistent published wealth group means and shares (including the US middle 40%). These are already identified in our table footnotes and retained as published. Agreement on the income calculation is not a claim that every source wealth field is consistent.

## Disposition

No experiment parameters or table values were changed during this investigation. The current bottom-half income calculation should not be halved to reproduce the report. For exact report replication, a separate version should preserve its archived inputs and explicitly identify its inconsistencies rather than silently incorporate them into the experiment.

## Evidence

- [Official WIR 2026 methodology and downloads](https://wir2026.wid.world/methodology/)
- [Official country-sheet PDF, US page 39](https://wir2026.wid.world/www-site/uploads/2025/11/WIR26_Country_Sheets.pdf)
- [Official archived country-sheet workbooks](https://wir2026.wid.world/www-site/uploads/2025/11/WIR_2026_country_sheets.zip), `country_sheets_table1_in_excel.xlsx`, `USA_DATA_Table!B3:E10` and equivalent reference-country tabs.
- [Official replication code](https://wir2026.wid.world/www-site/uploads/2025/11/WIR2026_computer_codes.zip), `WIR2026_Country_sheets_data.do`, wealth reconstruction and year selection; nested `country_sheets_complement.zip/export_t1_to_excel.bas`.
- Downloaded code, workbook, and extracted cells are retained under `outputs/reference_tables/investigation/`.
- Our raw observations, conversion factors, hashes, and source metadata are in `outputs/reference_tables/reference_tables.json`.
