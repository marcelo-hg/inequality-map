# Implementation plan: global median target and national-mean equalization

Status: implemented. See `docs/scenarios.md` for execution and output details.

## Objective

Add two experiment types, each with adult and full-population variants. Use the frozen 2024 dataset in 2025 PPP dollars for the initial runs, matching the existing experiments. Compute references from the modeled distributions; do not substitute the unverified WIR 2026 euro benchmark.

| Experiment | Target | Budget treatment |
|---|---|---|
| Global median target | Everyone receives the baseline population-weighted world median | Report undistributed income or funding shortfall; do not automatically allocate the residual |
| National-mean equalization | Everyone receives their country's baseline population-weighted mean | Preserve total income within each country |

“World” means the eligible countries in the dataset. Record country coverage and exclusions. Full-population distributions remain modeled estimates based on the existing adult-to-total-population scaling.

## 1. Scenario configuration

Extend `config/scenarios.yml` with an explicit reference definition:

```yaml
reference:
  scope: global       # global or national
  statistic: median   # mean or median
```

Keep `redistribution.type: equal` for both new experiments. Existing scenarios without a reference definition default to global mean and retain their behavior. Validate supported combinations explicitly; this work requires global mean, global median, and national mean, not national median.

Suggested scenario IDs:

- `global_median_target`
- `global_median_target_full_population`
- `national_mean_equalization`
- `national_mean_equalization_full_population`

Retain the existing population-basis conventions. Set target multipliers to 1 and classification tolerance to 0 for the initial experiments. Pin the initial execution year to 2024 through the existing CLI rather than silently selecting a newer release.

## 2. Reference calculation

Update `src/inequality_map/experiments.py` to separate reference calculation from redistribution.

### Global median

1. Combine all eligible country percentile bins after population-basis transformation.
2. Sort bins by `income_before_ppp` and accumulate their `population` weights.
3. Select the first income whose cumulative weight reaches at least half of total weight: the lower weighted median, or inverse empirical CDF at 0.5.
4. Document the exact-half boundary and tie convention. Do not interpolate or average country medians.

The result is an estimate from percentile-bin means, not an exact individual-level median. Treat each bin's population as having its recorded mean, consistently with the current experiment engine. Ties can produce unchanged people and fewer than 50% winners. A global median must be recomputed after full-population scaling because that scaling can change cross-country income ranks.

### National means

For each country, calculate:

`target = sum(income_before_ppp × population) / sum(population)`

Pass that country's target to the existing equalization calculation. Use the same validated distributions for both the target and the results.

Update `_comparison` to apply the selected reference rule independently to adult and full-population distributions on common country coverage. Avoid retaining a global-mean assumption in comparison outputs.

## 3. Output schema and budget accounting

Preserve existing result fields and backward compatibility for old experiment outputs. Add:

- The actual target income to every country result.
- Reference scope, statistic, population basis, currency, price year, and estimation method.
- A single global reference for global scenarios; a country-to-target mapping or equivalent explicit representation for national scenarios. Do not present a global average as the national scenario's universal target.
- Explicit undistributed surplus `max(income_before - income_after, 0)` and funding requirement `max(income_after - income_before, 0)`.
- Per-country budget-balance results for national equalization, using scale-aware numerical tolerance.

Keep the existing signed budget gap (`after - before`). Distinguish aggregate budget residuals from gross gains and losses: gross transfers within a country do not imply a national funding shortfall.

The median scenario is not guaranteed to conserve income. Report whichever residual the data produce. National equalization should conserve income both nationally and globally, with no net international transfers.

Version the calculation engine fingerprint to distinguish new runs. Preserve immutable existing experiment directories and raw data.

## 4. Maps and comparison outputs

Reuse `src/inequality_map/maps.py` and the existing map workflow. Ensure titles and sidecar metadata distinguish global-median and national-mean targets and their population bases. Handle national reference metadata without assuming a single scalar target.

Generate a comparison table for BRA, USA, FRA, CHN, NOR, IND, and NGA, showing:

- Experiment, year, population basis, and target income.
- Winner, unchanged, and loser shares.
- Average gain and loss among the respective groups.
- National net income change and global budget residual.

Compare against existing global-mean equalization on matching year, basis, database release, and eligible country coverage. Do not silently compare results from different releases.

## 5. Tests and acceptance checks

Extend `tests/test_experiments.py` with meaningful synthetic cases:

1. Unequal country populations that distinguish a population-weighted median from an unweighted median and from a median of country medians.
2. Tied incomes, an exact 50% cumulative boundary, shuffled input order, and all-equal incomes.
3. Median equalization with a known surplus and another distribution demonstrating that conservation is not assumed.
4. Two countries with distinct national means: verify correct targets, national and global income conservation, approximately zero net national transfers, and zero within-country post-equalization Gini for positive-income cases.
5. Adult/full-population variants: verify national-equalization winner shares are invariant under each country's positive scaling when coverage matches; do not assume global-median winner shares are invariant.
6. Accounting identities: winner/unchanged/loser shares sum to one; gains minus losses agree with income changes; residual fields agree with the signed budget gap.
7. Updated comparison metadata and map generation for both reference scopes.
8. Regression tests: existing global-mean and clamp scenarios retain their numerical results and existing saved outputs remain readable.

Run the relevant experiment/map tests, then the repository's applicable full test suite. No new external dataset or statistical dependency should be necessary.

## 6. Execute and document

After tests pass:

1. Run the four new scenarios on the frozen database for 2024.
2. Generate maps and reference-country comparison outputs.
3. Independently reconcile selected targets, national conservation, and global residuals against input totals.
4. Inspect map titles and comparison tables for misleading units, basis labels, or target descriptions.
5. Update `docs/scenarios.md` and `docs/methodology.md`, plus CLI usage examples where appropriate.

Final acceptance: every target is reproducible from recorded inputs, every budget difference is explained, and median precision limitations are visible. No unverified report benchmark enters the calculation.

## Implementation ownership

Use one implementation agent for configuration, calculation, metadata, comparisons, and tests: these changes share the same engine and should remain coordinated. Follow with an independent statistical review focused on weighted-median conventions, population scaling, and budget accounting. The plan does not authorize or initiate agent delegation by itself.
