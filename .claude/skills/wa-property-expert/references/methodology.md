# Methodology - how the forecast is built

## Why a hybrid (and not one method)

House-price methods sit on a spectrum from pure measurement to pure prediction.
For a **single city, suburb-level, ≤5-year horizon**, no single method dominates,
so professional forecasters use hybrids. This model uses four layers, each placed
where it is strongest.

| Method | Strength | Weakness | Where we use it |
|---|---|---|---|
| **Hedonic regression** (Cotality HVI) | Controls compositional bias; gold standard for *measuring* today's value of attributes (land, beds, location) | Not a multi-year forecaster | Layer 4 - property-level adjustment (land size, KDR optionality) |
| **Repeat-sales** (Case-Shiller lineage) | Removes quality bias | Discards single-sale homes; thin at suburb level in a city Perth's size | Cross-check only |
| **Error-correction / cointegration (ECM/VECM)** | Ties price to fundamentals via a long-run equilibrium; models mean-reversion; judges over/under-valuation | Data-hungry; over-fits at suburb level | Layer 1 - city spine |
| **VAR/VECM systems** | Adds feedback (price→construction→supply→price) | Over-fits at suburb level | City/state spine only |
| **Machine learning** (gradient boosting / random forests) | Excellent cross-sectional suburb ranking on rich features | Cannot extrapolate regime shifts (rates, migration, policy) | Layer 3 - suburb spread, *not* city level |
| **Scenario-weighted Monte Carlo** | Expresses bear/base/bull as a *distribution*, shows a trough | Only as good as its scenario design | Layer 2 - the fan chart |

## The four layers

**Layer 1 - City VECM / error-correction spine.** Anchor Perth price to its
fundamentals - real household income, rents, construction costs, the real cash
rate - via a long-run cointegrating relationship, with short-run dynamics that
"error-correct" back toward equilibrium. This is what decides whether Perth is
over- or under-valued today and how fast it reverts. Its output calibrates the
scenario anchor paths. (In this repo the spine is represented by the calibrated
`ANCHORS` in `model/scenario_model.py`, with the analyst overlay applied; a full
re-estimation would use ABS income/rent/cost series + RBA F1.)

**Layer 2 - Scenario-weighted Monte Carlo.** The buyer thinks in base/bear/bull,
so the model does too. Three anchor paths (bear/base/bull) from now to Mid-29,
weighted **30/50/20**, produce a probability-weighted **expected path** and a
**spread band**. This is `model/scenario_model.py` and the fan chart. The
expected value at each period = round-half-up to the nearest $1,000 of the
weighted average.

**Layer 3 - Suburb gradient-boosted panel.** Relative suburb performance from
features: school zone, distance to Como, land size, KDR economics, growth, family
fit, postcode. In this repo it is implemented as a transparent weighted composite
(`model/scoring.py`) that mirrors the tool exactly; the production version is a
GBM trained on a suburb panel with the enriched features in `variables.md`.

**Layer 4 - Hedonic property adjustment.** Applied at the individual listing:
what an extra 100sqm of land, a 4th bedroom, or KDR optionality adds. This is
where the 500sqm filter and the KDR criterion bite, per-listing, via Landgate
attributes.

## Horizon choice - 3 years primary, 5-year tail

- Forecast error compounds; rate and policy uncertainty beyond ~3 years is large.
- The buyer asked for ≤5 years and wants to act around the soft patch.
- The 2027 soft patch and the bear trough (late-27/mid-28) both sit **inside 3
  years**, so a 3-year primary horizon captures the decision, with the 4th-5th
  year as scenario commentary (NG/CGT full effect, Simandou at scale).

So the spine runs to **Mid-29 (t=3.0)**; the tail is discussed, not plotted.

## How the scenarios are designed

- **Base (50%)** - RBA holds 4.35% into 2027 then eases; iron ore ~US$95/t in
  2026 → ~US$85-90 in 2027; undersupply floors prices; NG/CGT drag ~0.6-1.0ppt
  in investor stock. Flat-to-modest growth, re-acceleration from 2028.
- **Bear (30%)** - renewed RBA hiking (Westpac's Aug/Sep 2026 scenario) + iron
  ore <US$85/t + faster Simandou volumes + sharper investor pull-back. Trough
  ~**-7%** late-27/mid-28; undersupply prevents a 2014-style crash.
- **Bull (20%)** - RBA cuts in 2027, migration stays >2% with completions still
  short, construction-cost relief, resources hold. Prices re-accelerate;
  family-corridor school suburbs lead.

The weights are slightly more cautious than a naive prior because of two
genuinely new headwinds: the **Simandou ramp** and the **NG/CGT change**.

## The baseline contract

`data/baseline.json` is canonical. `model/scenario_model.py` regenerates the
expected path and headline metrics from `ANCHORS` and **self-verifies** against
it (prints `PASS`/`FAIL`). The web tool's `BASELINE` object must match. The
**Reset button restores exactly this.** Never hand-edit outputs - change an
assumption and re-run.

## What would change the call

- **Renewed hiking cycle** → deeper, earlier dip → buy later.
- **2027 RBA cuts + completions still <22k** → re-acceleration → buy sooner.
- **Iron ore sustained <US$70 or a migration reversal** → breaks the undersupply
  floor; revisit the whole base case.
