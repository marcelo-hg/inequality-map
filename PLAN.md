Below is a Codex-ready plan you can save as `PLAN.md` at the repository root.

# Equal-Earth Inequality Map

## 1. Project Objective

Build a reproducible research and visualization platform for the **Equal-Earth thought experiment** developed in the ChatGPT discussion.

The project should make it possible to:

1. Build and maintain a database containing all source data used in the experiment.
2. Reproduce all calculations programmatically.
3. Generate deterministic world maps from the calculated results.
4. Build an interactive website for exploring countries and scenarios.
5. Run new redistribution experiments by changing assumptions.
6. Extend the model later with physical planetary constraints.

The project should distinguish clearly between:

- **raw measured data**
- **processed data**
- **derived indicators**
- **model estimates**
- **scenario assumptions**

No value shown to the user should exist only as manually entered presentation data unless explicitly labeled as an assumption.

---

# 2. Core Research Question

The initial experiment asks:

> If humanity's current productive capacity were distributed differently, what percentage of people in each country would experience a higher or lower material standard of living?

The initial reference quantity is:

```text
E = Equal-Earth reference income
E ≈ PPP 30,100 per adult per year
```

This value should NOT be hard-coded permanently.

It must be stored as a scenario parameter.

---

# 3. Initial Scenarios

## 3.1 Hard Equality

Every adult receives:

```text
income_new = E
```

Initial reference:

```text
E = 30,100 PPP international units / adult / year
```

For each country calculate:

```text
winner_share
unchanged_share
loser_share
average_gain
average_loss
net_transfer
```

Basic classification:

```python
if income < E:
    winner
elif income > E:
    loser
else:
    unchanged
```

Because exact equality has effectively zero probability in a continuous distribution, allow an optional tolerance:

```text
unchanged_band = ±X%
```

For example:

```text
0.9E <= income <= 1.1E
```

---

## 3.2 Relaxed Redistribution

Initial proposal:

```text
minimum income = 0.6E
maximum income = 3E
```

Therefore:

```text
floor = 18,060 PPP
reference = 30,100 PPP
ceiling = 90,300 PPP
```

Transformation:

```python
income_new = min(max(income_old, floor), ceiling)
```

Classification:

```python
if income_old < floor:
    winner
elif income_old > ceiling:
    loser
else:
    unchanged
```

This interpretation is important.

The relaxed scenario does **not** redistribute everyone toward 1E.

It changes mainly the tails of the distribution.

The website must make this distinction explicit.

---

# 4. Important Conceptual Distinctions

Do not mix these variables.

## GDP

Annual economic production.

## National income

Income accruing to residents.

This is currently the preferred basis for the redistribution experiment.

## Wealth

Stock of assets.

Examples:

- real estate
- equities
- pensions
- land
- financial assets

Wealth distribution can be analyzed separately but should not be substituted for income distribution.

## Household consumption

Closer to direct material living standards.

Potential future model.

## Actual Individual Consumption

Includes private household consumption plus some government-provided individual services.

Potentially useful for welfare comparisons.

## PPP

Purchasing Power Parity.

Used to compare real purchasing power between countries.

Do not convert PPP quantities using foreign-exchange rates.

---

# 5. Main Data Sources

Prefer primary sources whenever possible.

Initial priority:

## World Inequality Database / World Inequality Report

Use for:

- income distribution
- wealth distribution
- percentile income
- income shares
- national income
- top 1%
- top 10%
- middle 40%
- bottom 50%

Website:

```text
https://wid.world/
```

Recent World Inequality Report data should be versioned.

---

## WIID / UNU-WIDER

Potentially useful for percentile-level or decile-level distributions.

Especially useful if country-level WID percentile data are incomplete.

---

## World Bank

Use for:

- population
- PPP conversion factors
- GDP
- household consumption
- Gini
- national accounts

Example indicators:

```text
NY.GDP.MKTP.CD
PA.NUS.PPP
SP.POP.TOTL
SI.POV.GINI
```

---

## IMF WEO

Use for:

- GDP PPP
- GDP per capita PPP
- global production benchmarks
- current macroeconomic estimates

---

## UN

Use for:

- population
- demographic projections
- development indicators

---

# 6. Future Environmental Sources

Planetary constraints should be implemented as a separate model layer.

Likely sources:

## UNEP International Resource Panel

Material footprint.

## IPCC

Carbon pathways and remaining carbon budgets.

## UNEP Emissions Gap Report

Required global emissions reductions.

## IEA

Energy and electricity.

## Ember

Electricity generation and consumption.

## FAO

Agriculture and food.

## Our World in Data

Useful harmonized datasets derived from primary sources.

Use OWID primarily as an integration layer and retain the original source metadata.

---

# 7. Repository Structure

Recommended initial layout:

```text
inequality-map/
│
├── README.md
├── PLAN.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── config/
│   ├── sources.yml
│   ├── scenarios.yml
│   └── countries.yml
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── external/
│
├── database/
│   ├── schema.sql
│   ├── migrations/
│   └── inequality.duckdb
│
├── src/
│   └── inequality_map/
│       ├── __init__.py
│       │
│       ├── data/
│       │   ├── world_bank.py
│       │   ├── wid.py
│       │   ├── wiid.py
│       │   ├── imf.py
│       │   └── population.py
│       │
│       ├── pipelines/
│       │   ├── ingest.py
│       │   ├── clean.py
│       │   ├── harmonize.py
│       │   └── build_database.py
│       │
│       ├── models/
│       │   ├── distribution.py
│       │   ├── redistribution.py
│       │   ├── scenarios.py
│       │   └── planetary.py
│       │
│       ├── geo/
│       │   ├── boundaries.py
│       │   └── choropleth.py
│       │
│       ├── analysis/
│       │   ├── country.py
│       │   ├── global.py
│       │   └── validation.py
│       │
│       └── api/
│           └── schemas.py
│
├── experiments/
│   ├── hard_equality.yml
│   ├── relaxed_06_30.yml
│   └── README.md
│
├── scripts/
│   ├── download_data.py
│   ├── build_database.py
│   ├── run_experiment.py
│   └── generate_maps.py
│
├── outputs/
│   ├── maps/
│   ├── tables/
│   ├── experiments/
│   └── reports/
│
├── web/
│   ├── package.json
│   ├── src/
│   └── public/
│
├── notebooks/
│   └── exploratory/
│
└── tests/
    ├── test_data.py
    ├── test_distribution.py
    ├── test_scenarios.py
    ├── test_redistribution.py
    └── test_geo.py
```

---

# 8. Recommended Technology Stack

## Research / backend

Python 3.12+

Libraries:

```text
pandas
numpy
scipy
duckdb
pyarrow
pydantic
requests
httpx
pyyaml
geopandas
shapely
matplotlib
plotly
pytest
```

Optional:

```text
polars
pandera
```

---

## Database

Use:

```text
DuckDB + Parquet
```

initially.

Reasons:

- simple local development
- excellent analytical SQL
- very good Parquet integration
- easy use from Python
- no database server
- reproducible in Codex
- can later migrate to PostgreSQL

Do not begin with a complex production database.

---

## Geographic data

Use:

```text
Natural Earth
```

for global country boundaries.

Use ISO-3 country codes as the main geographic key.

Never join geographic data using country display names.

---

## Website

Recommended:

```text
Next.js
TypeScript
React
MapLibre GL
Plotly or ECharts
```

Alternative:

```text
React + Vite
```

The website should initially consume static JSON/Parquet-derived outputs.

A server backend is not required for MVP.

---

# 9. Database Design

Every observation should retain provenance.

## countries

```text
country_id
iso3
iso2
country_name
region
subregion
world_bank_code
wid_code
imf_code
geometry_id
```

---

## sources

```text
source_id
provider
dataset
dataset_version
url
download_date
publication_date
license
citation
notes
```

---

## indicators

```text
indicator_id
indicator_code
indicator_name
description
unit
category
```

Examples:

```text
population
gdp_ppp_pc
national_income_ppp_pc
ppp_conversion_factor
gini
bottom50_income_share
middle40_income_share
top10_income_share
top1_income_share
```

---

## observations

```text
country_id
year
indicator_id
value
source_id
data_status
method
```

`data_status` should be one of:

```text
measured
derived
estimated
assumption
```

---

# 10. Income Distribution Storage

The ideal format is percentile-level data.

## income_percentiles

```text
country_id
year
percentile
income_ppp
population_share
source_id
method
confidence
```

Example:

```text
BRA | 2024 | 1 | ...
BRA | 2024 | 2 | ...
...
BRA | 2024 | 100 | ...
```

Prefer 100 percentiles.

If source data allow:

```text
1000 quantiles
```

can be used internally.

---

# 11. Distribution Reconstruction

Some countries may not have full percentile-level distributions.

Do NOT silently invent missing values.

Implement several methods.

## Method A — observed percentile distribution

Highest priority.

```text
method = observed
```

---

## Method B — interpolation

When several quantile points are available.

Possible approaches:

```text
monotonic cubic interpolation
piecewise log interpolation
```

---

## Method C — fitted distribution

If only aggregates are available:

```text
bottom50 share
middle40 share
top10 share
top1 share
mean income
```

Possible models:

```text
lognormal
generalized beta
Singh-Maddala
Dagum
lognormal + Pareto upper tail
```

Prefer:

```text
flexible body distribution + Pareto top tail
```

because a simple lognormal tends to underestimate extreme inequality.

Store:

```text
model_type
fit_parameters
fit_error
confidence
```

---

# 12. Distribution Validation

For every reconstructed country distribution, reproduce known source statistics.

For example:

```text
calculated mean ≈ source mean
calculated top10 share ≈ source top10 share
calculated bottom50 share ≈ source bottom50 share
calculated top1 share ≈ source top1 share
```

Define tolerance.

Example:

```text
mean error < 2%
income-share error < 1 percentage point
```

Flag countries that fail validation.

Never include silently failing distributions in final maps.

---

# 13. Experiment Configuration

Scenarios should live in YAML.

Example:

```yaml
experiment:
  id: relaxed_06_30
  name: Relaxed Equal-Earth

reference:
  type: global_mean_income
  value_ppp: 30100

redistribution:
  type: clamp
  floor_multiplier: 0.6
  ceiling_multiplier: 3.0

classification:
  unchanged_tolerance: 0.0

population:
  basis: adult

year:
  target: 2025
```

Hard equality:

```yaml
redistribution:
  type: equal
  target_multiplier: 1.0
```

---

# 14. Experiment Engine

Implement a generic function such as:

```python
run_scenario(
    distribution,
    scenario
)
```

Return:

```text
winner_share
unchanged_share
loser_share

winner_population
unchanged_population
loser_population

original_mean
new_mean

average_winner_income_before
average_winner_income_after

average_loser_income_before
average_loser_income_after

average_gain
average_loss

total_gain
total_loss

required_transfer
surplus_transfer

gini_before
gini_after
```

---

# 15. Budget Conservation

This is critical.

A scenario cannot distribute more income than exists.

Always calculate:

```text
sum(income_before)
sum(income_after)
```

For pure redistribution:

```text
total_after == total_before
```

within numerical tolerance.

---

# 16. Important Issue With the Relaxed Scenario

The naive clamp:

```python
new_income = clip(old_income, 0.6E, 3E)
```

does NOT necessarily conserve total global income.

Therefore implement two modes.

## Mode 1 — diagnostic clamp

Simply applies floor and ceiling.

Useful to determine:

```text
cost of floor
revenue from ceiling
```

---

## Mode 2 — budget-balanced redistribution

Find parameters or apply transfers so:

```text
money removed from upper tail
=
money needed for lower tail
```

Possible approach:

1. establish floor
2. calculate cost of raising everyone to floor
3. calculate revenue from proposed ceiling
4. if revenue differs, solve for budget-balanced ceiling
5. alternatively apply progressive compression above 1E

This should become one of the central experimental tools.

---

# 17. New Experiment Types

The engine should eventually support:

## Equal

```text
everyone = 1E
```

## Floor only

```text
income >= X
```

## Floor + ceiling

```text
X <= income <= Y
```

## Progressive compression

Example:

```text
<0.6E → raise strongly
0.6–1E → raise moderately
1–3E → mostly unchanged
>3E → progressively compressed
```

## Maximum ratio

Example:

```text
maximum / minimum = 5
```

## Gini target

Solve redistribution necessary to achieve:

```text
Gini = 0.25
Gini = 0.30
Gini = 0.35
```

## Universal basic income

Transfer fixed PPP amount.

## Country-local redistribution

Redistribute only within each country.

## Global redistribution

Redistribute across all humans.

These two must be clearly distinguished.

---

# 18. Geographic Output

Map generation must be deterministic.

Do NOT use generative images for analytical maps.

Use:

```text
GeoPandas
Natural Earth
Matplotlib
```

for static output.

---

# 19. Core Maps

Generate at least:

## Hard Equality — Winners

Color:

```text
percentage better off
```

## Hard Equality — Losers

```text
percentage worse off
```

## Relaxed — Winners

```text
percentage below floor
```

## Relaxed — Unchanged

```text
percentage within floor/ceiling
```

## Relaxed — Losers

```text
percentage above ceiling
```

---

# 20. Fixed Map Scale

Never let Matplotlib independently normalize each map.

Use identical bins.

Recommended:

```text
0–10%
10–30%
30–50%
50–70%
70–90%
90–100%
```

The exact same percentage must always produce the same color.

Missing data:

```text
gray
```

Never infer missing countries just to complete the visual.

---

# 21. Map Metadata

Each generated map should contain metadata:

```text
experiment_id
data_version
calculation_date
threshold
income_definition
population_basis
distribution_method
source_version
```

Save metadata as JSON next to the image.

Example:

```text
outputs/maps/hard_winners.png
outputs/maps/hard_winners.json
```

---

# 22. Interactive Website

Initial route:

```text
/
```

Main view:

```text
interactive world map
```

---

# 23. Website Controls

Allow user to choose:

```text
scenario
year
metric
```

Metric:

```text
better off
unchanged
worse off
average gain
average loss
```

---

# 24. Country Interaction

Clicking Brazil should open something like:

```text
Brazil

Current mean income
Equal-Earth reference

Hard equality
91% better
9% worse

Relaxed
X% better
Y% unchanged
Z% worse
```

Also show:

```text
income distribution curve
current distribution
new distribution
```

---

# 25. Local PPP Conversion

Show the Equal-Earth threshold in local currency.

Example:

```text
Brazil

1E:
PPP 30,100

Local purchasing-power equivalent:
~R$6,250/month/adult
```

Important UI label:

```text
PPP equivalent — not FX conversion
```

---

# 26. Distribution Visualization

For each country show:

```text
income percentile curve
```

X:

```text
population percentile
```

Y:

```text
PPP income
```

Overlay:

```text
0.6E
1E
3E
```

This gives an immediate visual interpretation of:

```text
winner population
unchanged population
loser population
```

---

# 27. Global Dashboard

Show:

```text
world population
world adult population
global income
Equal-Earth reference
```

Then:

```text
winners
unchanged
losers
```

in:

```text
percentage
billions of people
```

Also show:

```text
total redistributed income
average gain
average loss
```

---

# 28. Experiment Builder

Eventually create UI controls:

```text
Floor:
[0.6] E

Ceiling:
[3.0] E

Equality target:
[1.0] E
```

Changing the inputs should rerun the experiment.

Initially this can use precomputed server-side results.

Later it can execute dynamically.

---

# 29. Reproducibility

Every experiment must generate a unique ID.

Example:

```text
eq_floor060_cap300_2025_v001
```

Store:

```text
scenario
input datasets
versions
parameters
code commit
timestamp
results
```

---

# 30. Experiment Output

Recommended format:

```text
outputs/experiments/{experiment_id}/
```

Example:

```text
config.yml
country_results.parquet
global_results.json
map_winners.png
map_losers.png
metadata.json
```

---

# 31. Data Versioning

Raw source datasets should never be modified.

Example:

```text
data/raw/wid/2026-09-08/
data/raw/world_bank/2026-09-08/
```

Processed datasets may be regenerated.

Avoid storing huge reproducible intermediate files in Git.

Consider:

```text
DVC
```

later if data volume becomes significant.

---

# 32. Provenance

Every processed variable should be traceable back to:

```text
source
dataset
year
original variable
transformation
code version
```

Example:

```yaml
indicator: equal_earth_reference
type: derived

sources:
  - wid_global_income_2025

formula:
  global_national_income / global_adult_population
```

---

# 33. Confidence / Quality Layer

Give each country a quality flag.

Example:

```text
A — direct percentile data
B — good interpolation
C — fitted from detailed aggregates
D — weak data / extrapolation
```

Display this on the website.

This prevents estimates from looking more precise than they are.

---

# 34. Planetary Constraints — Phase 2

Once income experiments work, add physical constraints.

Do not mix this code with the first redistribution implementation.

Create separate modules.

Possible quantities:

```text
GHG emissions
electricity
primary energy
material footprint
land
cropland
freshwater
meat
beef
steel
cement
vehicle stock
aviation
housing floor area
```

---

# 35. Planetary Budget Model

For each variable define:

```text
current global total
current per-capita average
sustainable global limit
sustainable per-capita allocation
source
target year
uncertainty
```

Example:

```yaml
carbon:
  current:
    unit: tCO2e/person/year
  target_2035:
    value: 2.7
  target_long_run:
    value: 1.0
```

Values here are illustrative until backed by datasets.

---

# 36. Distinguish Two Physical Experiments

This is important.

## Equal current throughput

Question:

> What if today's physical resource consumption were equally distributed?

and separately:

## Sustainable planetary allocation

Question:

> What level of consumption could everyone have while respecting planetary limits?

These are not the same calculation.

Current global resource use may already be unsustainable.

---

# 37. Combined Income + Planetary Model

Eventually each person/household has two constraints:

```text
economic budget
ecological budget
```

Conceptually:

```text
income ∈ [0.6E, 3E]
```

while:

```text
carbon <= planetary carbon allocation
materials <= material allocation
land <= land allocation
```

This enables an important research question:

> How unequal can income remain while resource consumption stays within planetary boundaries?

---

# 38. Household Archetypes

Later create standardized households:

```text
0.6E
1E
2E
3E
```

For each estimate:

```text
housing
food
transport
cars
flights
energy
electronics
leisure
health
education
material footprint
carbon footprint
```

This converts abstract PPP numbers into understandable lifestyles.

---

# 39. Testing

Minimum required tests.

## Data

```text
country codes unique
no impossible negative income
population > 0
percentiles monotonic
```

## Distribution

```text
income percentile monotonic
population sums to 1
integrated mean matches source mean
```

## Redistribution

```text
hard equality produces identical incomes
floor correctly raises lower incomes
ceiling correctly reduces upper incomes
```

## Conservation

```text
budget-balanced scenarios conserve total income
```

## Maps

```text
same percentage always gives same color
missing country always gray
all ISO joins validated
```

---

# 40. Validation Countries

Use these seven countries throughout development:

```text
Brazil
United States
France
China
Norway
India
Nigeria
```

These provide useful variation in:

```text
income level
inequality
development
data quality
```

---

# 41. Reference Results From the Conversation

Treat these only as validation targets until rebuilt from the source database.

Approximate hard-equality better-off shares discussed:

```text
Brazil       ~91%
USA          ~59%
France       ~60%
China        ~89%
Norway       ~25%
India        ~96%
Nigeria      ~96%
```

Do NOT hard-code these into final outputs.

They should be reproduced from the dataset.

If the database produces significantly different results, investigate the difference rather than forcing agreement.

---

# 42. Global Validation Target

The previous exploratory model suggested:

```text
~76% below 1E
~24% above 1E
```

with a ±10% unchanged band approximately:

```text
~74% winners
~5% roughly unchanged
~21% losers
```

Again:

These are **exploratory estimates**, not authoritative outputs.

The production model must recompute them.

---

# 43. MVP Scope

The first usable version should include only:

### Data

- WID/WIID income distributions
- World Bank population
- PPP conversion data
- country metadata
- geographic boundaries

### Experiments

- hard equality
- relaxed floor + ceiling

### Countries

All countries for which reliable distributions can be constructed.

### Maps

- hard equality winners
- relaxed scenario winners
- relaxed scenario losers

### Website

- world map
- scenario selector
- country selection
- basic country statistics
- sources
- methodology

Planetary constraints are **not required for MVP**.

---

# 44. Development Phases

## Phase 1 — Repository and data architecture

Deliver:

```text
project skeleton
DuckDB schema
source configuration
country dimension
```

---

## Phase 2 — Data ingestion

Implement:

```text
World Bank
WID/WIID
IMF if necessary
Natural Earth
```

Deliver:

```text
raw datasets
normalized tables
provenance
```

---

## Phase 3 — Distribution engine

Deliver:

```text
percentile distributions
distribution fitting
validation metrics
quality grades
```

Validate initially against:

```text
Brazil
USA
France
China
Norway
India
Nigeria
```

---

## Phase 4 — Hard Equality

Implement:

```text
E calculation
country winners
country losers
global winners
global losers
gain/loss magnitude
```

---

## Phase 5 — Relaxed Scenario

Implement:

```text
floor = 0.6E
ceiling = 3E
```

Calculate:

```text
winners
unchanged
losers
cost of floor
revenue from cap
budget balance
```

---

## Phase 6 — Maps

Produce deterministic choropleths.

Validate color consistency.

---

## Phase 7 — Web MVP

Implement:

```text
interactive world map
scenario switch
country details
distribution chart
sources
methodology
```

---

## Phase 8 — Experiment framework

Generalize YAML configuration.

Allow CLI:

```bash
python scripts/run_experiment.py \
  --config experiments/relaxed_06_30.yml
```

---

## Phase 9 — Planetary constraints

Add physical-resource datasets and model.

---

# 45. CLI Design

Examples:

```bash
python scripts/download_data.py
```

```bash
python scripts/build_database.py
```

```bash
python scripts/run_experiment.py \
    --config experiments/hard_equality.yml
```

```bash
python scripts/generate_maps.py \
    --experiment hard_equality
```

Potential unified CLI later:

```bash
equal-earth data update
equal-earth data validate
equal-earth experiment run relaxed_06_30
equal-earth map generate relaxed_06_30
```

---

# 46. API Boundary

Research code should not depend on the frontend.

Export stable outputs.

Example:

```json
{
  "iso3": "BRA",
  "experiment": "hard_equality",
  "reference_income_ppp": 30100,
  "winner_share": 0.91,
  "loser_share": 0.09,
  "quality": "B"
}
```

The frontend consumes these outputs.

---

# 47. Website Transparency

Every result should expose:

```text
source
source year
model method
scenario parameters
quality grade
last update
```

Users should be able to answer:

> Where did this number come from?

without reading the source code.

---

# 48. Documentation

Create:

```text
README.md
docs/methodology.md
docs/data_sources.md
docs/scenarios.md
docs/limitations.md
```

The methodology should distinguish:

```text
fact
estimate
assumption
scenario
```

---

# 49. Scientific Principles

The project should follow these rules:

1. Never present modeled values as observed values.
2. Never silently substitute one year's data for another.
3. Never silently fill missing countries.
4. Never use generative images for quantitative maps.
5. Always preserve dataset provenance.
6. Always expose scenario assumptions.
7. Always check redistribution budget conservation.
8. Prefer reproducibility over visual polish.
9. Keep economic and physical constraints separate.
10. Make uncertainty visible.

---

# 50. Initial Codex Tasks

Start implementation in this order.

## Task 1

Create repository structure and Python package.

## Task 2

Create:

```text
config/sources.yml
```

with initial sources.

## Task 3

Create DuckDB schema.

## Task 4

Build country dimension using ISO-3 codes.

## Task 5

Implement World Bank population and PPP ingestion.

## Task 6

Investigate WID/WIID APIs/download formats and ingest the most detailed available income distributions.

## Task 7

Build a standardized country percentile table.

Target:

```text
100 percentiles × country × year
```

For each validated adult distribution, also support an explicitly modeled full-population representation when `npopul992i` and `npopul999i` exist for the same country-year. Scale each adult-bin income by `adult_population / total_population` and weight each bin by one percent of total population. Preserve the original adult distribution separately.

## Task 8

Implement distribution validation.

## Task 9

Reproduce the seven reference countries.

## Task 10

Calculate global Equal-Earth reference \(E\) from source data rather than hard-coding 30,100.

Calculate and label separate references by population basis. The adult reference is the weighted mean of adult bins; the full-population reference is the weighted mean of modeled per-person bins. Each reference must state included countries, excluded countries, PPP currency, price year, and PPP benchmark metadata.

## Task 11

Implement hard equality.

Implement it independently for `adult_20_plus` and `full_population`; each result must retain its denominator, distribution method, and data-status label.

## Task 12

Implement relaxed 0.6E–3E scenario.

Apply the same basis-specific reference to the full-population diagnostic clamp.

## Task 13

Check whether the proposed floor and ceiling are globally budget-balanced.

This is a key research result.

Report conservation before and after the adult-to-full-population transformation, then separately report the clamp budget gap. Do not present a diagnostic clamp as budget balanced.

## Task 14

Generate deterministic world choropleths.

Map metadata and titles must state the population basis, PPP unit, whether the distribution is published or modeled, and the fixed color scale. Full-population maps must state the constant adult-to-total-population-ratio assumption.

## Task 15

Build static JSON output for frontend.

Publish basis-neutral population fields plus `adult_population`, `total_population`, `scaling_factor`, PPP lineage, coverage, and exclusions. Produce same-year adult/full-population comparison output for the seven reference countries.

## Task 16

Create initial interactive website.

---

# 51. First Research Milestone

The first major milestone should answer, reproducibly:

> Using the latest available global income distributions, if current world national income were distributed equally, what percentage of the population of every country would gain or lose?

Then:

> If a global income range from 0.6E to 3E were imposed instead, what percentage would gain, remain unaffected, or lose, and is that redistribution budget-balanced?

These should be treated as the project's first publishable results.

---

# 52. Second Research Milestone

Once the economic model is stable:

> What level of universal material living standard is compatible with both the world's productive capacity and physical planetary constraints?

Test:

```text
income
housing
electricity
food
transport
aviation
materials
carbon
land
```

together.

---

# 53. Long-Term Research Question

The project should eventually be capable of exploring:

> What combination of inequality, productive capacity, technological efficiency, and ecological limits maximizes global living standards without exceeding planetary constraints?

This transforms the original thought experiment into a configurable quantitative simulation platform rather than a single redistribution calculation.

