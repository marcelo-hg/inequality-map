# PROJECT_CONTEXT.md

## Project: Equal-Earth / Inequality Map

This repository develops a reproducible research and visualization platform for the **Equal-Earth thought experiment** discussed in ChatGPT.

The central question is:

> If humanity's current productive capacity and income were distributed differently, what share of people in each country would experience a higher or lower material standard of living?

The project should eventually combine:

1. global income-distribution experiments,
2. country-level winner/loser maps,
3. local PPP equivalents,
4. interactive web visualizations,
5. configurable redistribution scenarios,
6. physical planetary constraints.

This file is **context, not authoritative data**. All numerical values from the conversation must eventually be rebuilt from versioned source datasets.

---

# 1. Core economic concepts

Do not mix these concepts.

## GDP

Annual economic production.

Useful for measuring total productive capacity, but not the same as household income or disposable income.

## National income

Income accruing to residents.

This is the preferred basis for the redistribution experiment.

## Wealth

A stock of assets such as housing, land, equities, pensions, and financial assets.

Wealth distribution is important but should be analyzed separately from annual income flows.

## Household consumption

Private consumption by households.

Potentially closer to direct living standards than GDP.

## Actual Individual Consumption (AIC)

Household consumption plus government-provided individual services such as health and education.

Potential future welfare metric.

## PPP

Purchasing Power Parity.

Used to compare real purchasing power across countries.

PPP values must **not** be converted using market FX rates.

---

# 2. Equal-Earth reference

The exploratory benchmark developed in the conversation was:

```text
E ≈ PPP 30,100 per adult per year
```

Interpretation:

```text
E = Equal-Earth reference income
```

Important:

- `30,100` is provisional.
- It must NOT be permanently hard-coded.
- The production system should recompute `E` from source data for a selected year.

---

# 3. Hard equality scenario

Definition:

```text
income_new = E
```

Everyone is moved to exactly one Equal-Earth share.

Classification:

```python
if income_old < E:
    winner
elif income_old > E:
    loser
else:
    unchanged
```

Optional tolerance bands can be added later, for example:

```text
0.9E <= income <= 1.1E
```

to classify a group as approximately unchanged.

## Population bases

The project supports two separate income experiments. They must never be compared as though they shared the same denominator.

- `adult_20_plus` uses WID's published equal-split adult percentile distribution and `npopul992i`.
- `full_population` is a modeled per-person distribution. For each country and year, it scales every adult percentile income by `npopul992i / npopul999i` and assigns each percentile one percent of `npopul999i`.

For adult population \(A_c\), total population \(N_c\), and adult-bin income \(y_{c,p}\), the full-population calculation is:

```text
y_person[c,p] = y_adult[c,p] × A_c / N_c
population[c,p] = N_c / 100
```

This preserves country income in every bin. It assumes the same adult-to-total-population ratio in every income group. It is therefore labeled `estimated` with method `adult_shape_scaled_to_total_population`; it does not observe household size, children, or age composition by income percentile.

### Exploratory global result from the conversation

Without a tolerance band:

```text
~76% below 1E
~24% above 1E
```

With an illustrative ±10% unchanged band:

```text
~74% winners
~5% roughly unchanged
~21% losers
```

These are **exploratory model estimates**, not production outputs.

They must be recomputed.

---

# 4. Relaxed redistribution scenario

The proposed relaxed income range is:

```text
0.6E <= income <= 3E
```

Using the provisional `E = 30,100`:

```text
floor     ≈ PPP 18,060 / adult / year
reference ≈ PPP 30,100 / adult / year
ceiling   ≈ PPP 90,300 / adult / year
```

Naive transformation:

```python
income_new = min(max(income_old, 0.6 * E), 3.0 * E)
```

Classification:

```python
if income_old < 0.6 * E:
    winner
elif income_old > 3.0 * E:
    loser
else:
    unchanged
```

## Critical budget-balance caveat

A simple `clip()` operation does **not necessarily conserve total income**.

The production model must calculate:

```text
cost of raising everyone below 0.6E
revenue from reducing everyone above 3E
```

Then determine whether:

```text
floor cost == ceiling revenue
```

If not, solve for one or more of:

- the budget-balanced floor,
- the budget-balanced ceiling,
- a progressive compression rule,
- residual taxes/transfers,
- changes in the target range.

This is one of the most important unresolved research questions.

---

# 5. Correct map logic

The analytical maps must use the following definitions.

## Hard equality map

Color by:

```text
share of population currently below 1E
```

This is the share that would be better off under full equality.

## Relaxed winners map

Color by:

```text
share currently below 0.6E
```

## Relaxed unchanged map

Color by:

```text
share currently between 0.6E and 3E
```

## Relaxed losers map

Color by:

```text
share currently above 3E
```

The relaxed scenario should affect **fewer people than hard equality**, because it primarily changes the tails rather than moving everyone toward 1E.

---

# 6. Preliminary country validation targets

The conversation produced approximate hard-equality winner shares for seven countries.

Treat these only as **validation targets** until rebuilt from source distributions.

```text
Brazil         ~91%
United States  ~59%
France         ~60%
China          ~89%
Norway         ~25%
India          ~96%
Nigeria        ~96%
```

Interpretation:

```text
winner share = population currently below 1E
```

Important correction from the conversation:

For the United States, the hard-equality winner share is approximately:

```text
~59–60%
```

not ~11%.

The earlier generated-map value was wrong.

The ~59% USA value came from an exploratory lognormal reconstruction using full-population PPP-euro aggregates and a per-adult PPP-dollar reference. It is not a validation target for either production basis. Production comparisons must use the same country-year, income concept, PPP unit, and population denominator.

---

# 7. Preliminary local PPP equivalents

Approximate Equal-Earth local purchasing-power equivalents discussed:

| Country | Approx. local equivalent of 1E |
|---|---:|
| Brazil | ~R$6,250/month/adult |
| United States | ~$2,508/month/adult |
| France | ~€1,830/month/adult |
| China | ~¥10,500/month/adult |
| Norway | ~NOK 19,000/month/adult |
| India | ~₹53,600/month/adult |
| Nigeria | ~₦710,000/month/adult |

These are:

- approximate,
- PPP-based,
- not market-FX conversions,
- not necessarily equivalent to take-home salary.

They must be recalculated from current PPP conversion factors.

---

# 8. Previous economic framing

Before shifting to national-income distribution, the conversation also explored world productive capacity using GDP PPP.

An earlier benchmark was approximately:

```text
world GDP PPP per capita ≈ Int$23,049/person/year
```

For a family of four:

```text
~Int$92,196/year
~Int$7,683/month
```

This was used to construct an illustrative household production envelope.

Do not confuse this GDP-per-person benchmark with the national-income-per-adult benchmark `E ≈ 30,100`.

They answer different questions.

---

# 9. Equal-Earth lifestyle hypothesis

The conversation suggested that current global productive capacity could plausibly support a **comfortable modern middle-class lifestyle for everyone**, but not the resource intensity of today's richest populations.

Illustrative household characteristics:

## Housing

```text
~80–100 m² for a family of four
~20–25 m²/person
```

## Electricity

Previous discussion:

```text
~4–6 MWh/person/year total economy-wide electricity
```

Direct household use may be roughly:

```text
~5–7 MWh/year for a family of four
```

## Food

Illustrative target:

```text
~30–45 kg meat/person/year
```

with lower beef/lamb intensity and low food waste.

## Mobility

Approximate target:

```text
~0–1 private car per household in cities
```

with strong public transport, rail, cycling, and shared mobility.

## Aviation

Illustrative target:

```text
~1 round-trip flight per person every 1–2 years
```

## Services

Universal or near-universal access to:

- healthcare,
- education,
- internet,
- sanitation,
- basic infrastructure,
- digital devices,
- recreation and culture.

---

# 10. Planetary-constraint extension

After the income model is stable, impose physical constraints separately from monetary income.

Core variables:

```text
GHG emissions
electricity
primary energy
material footprint
land
cropland
freshwater
food
meat
beef
steel
cement/concrete
vehicle stock
aviation
housing floor area
```

Two separate physical experiments are needed.

## A. Equal share of today's throughput

Question:

> What if today's physical resource consumption were distributed equally?

## B. Sustainable planetary allocation

Question:

> What level of consumption can everyone have while respecting planetary limits?

These are not the same.

Current global throughput may already exceed sustainable limits.

---

# 11. Provisional planetary targets discussed

These are **illustrative design targets only** and must be replaced by source-backed values.

```text
material footprint:
~7–9 tonnes/person/year

electricity:
~4–6 MWh/person/year

GHG emissions:
~2.5–3 tCO2e/person/year by mid-2030s
falling toward <1 tCO2e/person/year long-run

housing:
~20–25 m²/person

meat:
~30–45 kg/person/year

cars:
~0.2–0.3 vehicles/person globally,
with large urban/rural variation

aviation:
~0.5 round trips/person/year average
```

Again: these are not official planetary boundaries.

---

# 12. Data sources to prioritize

## Income / wealth / inequality

- World Inequality Database (WID)
- World Inequality Report (WIR)
- WIID / UNU-WIDER

Use for percentile incomes, income shares, wealth shares, and mean national income.

## Macroeconomics / PPP

- World Bank
- IMF WEO
- UN

Use for population, PPP conversion factors, GDP PPP, national accounts, Gini, and demographics.

## Physical / environmental

- UNEP International Resource Panel
- UNEP Emissions Gap Report
- IPCC
- IEA
- Ember
- FAO
- Our World in Data

Use OWID mainly as a harmonized integration layer while retaining original-source metadata.

---

# 13. Distribution reconstruction strategy

Best case:

```text
observed percentile-level country distribution
```

Preferred internal format:

```text
country × year × percentile × PPP income
```

At least:

```text
100 percentiles
```

If direct percentiles are unavailable:

1. interpolate known quantiles,
2. fit a flexible distribution,
3. use a Pareto-style upper tail where appropriate.

Potential models:

```text
lognormal
Dagum
Singh-Maddala
generalized beta
body distribution + Pareto upper tail
```

A pure lognormal is useful for exploration but may underestimate the extreme upper tail.

Every reconstructed distribution must be validated against known source aggregates.

---

# 14. Data-quality principle

Every value should be tagged as one of:

```text
measured
derived
estimated
assumption
```

For fitted distributions also store:

```text
model_type
fit_parameters
fit_error
confidence
```

Suggested country quality grades:

```text
A — direct percentile data
B — good interpolation
C — fitted from detailed aggregates
D — weak/extrapolated data
```

---

# 15. Analytical map requirements

Final maps must be deterministic.

Do NOT use generative image models for quantitative maps.

The earlier generative maps were visually attractive but unreliable:

- geography could be approximate,
- colors were not mechanically tied to data,
- country bins became inconsistent.

Use:

```text
GeoPandas
Natural Earth
Matplotlib
```

or an equivalent deterministic GIS pipeline.

Use a fixed legend across comparable maps.

Suggested bins:

```text
0–10%
10–30%
30–50%
50–70%
70–90%
90–100%
```

Missing data:

```text
gray
```

Never fill missing countries by visual inference.

---

# 16. Initial website concept

The webpage should eventually support:

## World map

Select:

```text
scenario
year
metric
```

Metrics:

```text
better off
unchanged
worse off
average gain
average loss
```

## Country details

Show:

```text
current mean income
Equal-Earth threshold
local PPP equivalent
winner share
unchanged share
loser share
distribution quality
sources
```

## Distribution chart

X-axis:

```text
population percentile
```

Y-axis:

```text
PPP income
```

Overlay:

```text
0.6E
1E
3E
```

## Experiment controls

Eventually allow parameters such as:

```text
floor multiplier
ceiling multiplier
reference E
unchanged tolerance
target Gini
country-only vs global redistribution
```

---

# 17. Main unresolved research questions

## Economic

1. What is the best current source for percentile-level national-income distributions globally?
2. What is the correct source-consistent value of `E` for each target year?
3. Does the `0.6E–3E` relaxed scenario balance globally?
4. If not, what floor/ceiling pair is budget-balanced?
5. Should redistribution use adults, equivalized households, or total population?
6. How should public services and household income be combined without double counting?
7. Should global and within-country redistribution be modeled separately?

## Statistical

1. Which fitted distribution best reproduces observed income shares?
2. How sensitive are winner/loser shares to the upper-tail model?
3. How should uncertainty be propagated onto maps?

## Physical

1. What physical lifestyle is feasible under current global throughput?
2. What lifestyle is feasible under sustainable planetary limits?
3. Which constraints bind first?
4. How much income inequality can remain while ecological footprints remain bounded?

---

# 18. Initial Codex priorities

When starting development, Codex should:

1. create the data/source architecture,
2. ingest population and PPP data,
3. ingest the most detailed available income distributions,
4. build standardized country percentile distributions,
5. calculate `E` from source data,
6. reproduce the seven validation countries,
7. implement hard equality,
8. implement relaxed floor/ceiling redistribution,
9. test global budget conservation,
10. generate deterministic maps,
11. expose static results to a web frontend,
12. only then add planetary constraints.

For the full-population extension, the implementation must validate exact-year adult and total WID populations, preserve percentile income totals after scaling, report excluded countries, retain PPP lineage, and publish an adult/full-population comparison for the same country set.

---

# 19. Seven development/validation countries

Use these throughout early development:

```text
Brazil
United States
France
China
Norway
India
Nigeria
```

They provide useful variation in average income, inequality, development level, data availability, and geographic region.

---

# 20. Do not trust these numbers blindly

The following values came from exploratory conversation work and should be treated only as targets or hypotheses:

```text
E ≈ PPP 30,100/adult/year

Global hard equality:
~76% below 1E
~24% above 1E

Approx. hard-equality winner shares:
Brazil ~91%
USA ~59%
France ~60%
China ~89%
Norway ~25%
India ~96%
Nigeria ~96%
```

Likewise, all local-currency PPP equivalents and planetary targets are provisional.

The production project must:

```text
download source data
store versioned raw inputs
recompute every derived value
validate results
record provenance
show uncertainty
```

If the recomputed results disagree with the exploratory figures, investigate the discrepancy and prefer the source-backed result.

---

# 21. Guiding principle

The project is not intended to prove a political conclusion.

It is intended to answer a quantitative question:

> Given current global production, observed inequality, and eventually physical planetary limits, what distribution of resources could provide the highest broadly shared material standard of living?

The system should therefore remain:

- transparent,
- configurable,
- reproducible,
- source-backed,
- explicit about assumptions,
- explicit about uncertainty.
