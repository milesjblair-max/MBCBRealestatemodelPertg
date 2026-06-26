# Variable catalogue — standard inputs, enriched signals, and the discipline

The model takes every **stock-standard** input and **enriches** it with leading
indicators most analysts ignore. The art is signal-vs-noise: prioritise data that
**leads** prices and is **family-buyer specific**; demote anything slow or noisy
to corroboration. Tiers below.

## Standard inputs (the spine — everyone uses these)

Cash rate (RBA F1) · CPI (ABS 6401.0) · household income (ABS/RBA) · population &
migration (ABS 3101.0) · dwelling approvals (8731.0) & completions (8752.0) ·
construction costs (ABS / Cordell) · vacancy & rents (SQM/REIWA/Cotality) ·
advertised stock & days-on-market · lending/serviceability (APRA, ABS 5601.0) ·
iron-ore price & WA royalties (WA Budget) · auction clearance (Cotality).

These set the **city spine** and the base/bear/bull scenarios. They are necessary
but not differentiating — every analyst has them.

---

## Tier A — high-signal, genuinely leading (prioritise)

| Variable | What it predicts | Source | How to ingest |
|---|---|---|---|
| **Backyard pool-building-permit rate** (BA lodgements per 100 dwellings) | Family-home entrenchment → owner-occupier price floor; leads medians **6–18 months**. Discretionary, family-coded, recorded *before* any sale. Almost nobody uses it. | LGA building-services registers (Gosnells, Canning, Joondalup, Wanneroo…) | Scrape/FOI monthly DA/BA logs; geocode to SA2; rate per dwelling stock |
| **School in-zone rejection events** | The binary "catchment is now full" moment (Rossmoyne/Willetton refusing in-zone kids) → premium spills into fringe suburbs (Shelley/Riverton/Bull Creek). Sharper than a static catchment dummy. | WA Dept of Education intake areas; ACARA enrolment vs capacity | Track enrolment vs capacity by intake polygon; flag turn-aways |
| **Childcare occupancy / waitlist density** | Young-family in-migration *before* they buy; <70% viability = oversupply, >90% = under-served growth corridor. | ACECQA NQF register (≈daily CSV) | Places vs ABS 0–4 population per suburb; trend occupancy |
| **Subdivision pipeline: lodged-vs-registered cadastre ratio** | Developer conviction & future supply **12–24 months** ahead of completions/ABS approvals; green-title lots command a premium. | Landgate SLIP cadastre (lodged vs registered polygons); WAPC subdivisions | Count lodged polygons per SA2 as a forward pipeline |
| **Days-on-market velocity & vendor discounting** | Turn **before** medians do — the cleanest leading market-temperature read. | REIWA / Cotality / SQM | Track DOM and discount % per suburb; flag inflections |

## Tier B — useful, conditional or slower

| Variable | What it predicts | Source | Ingest |
|---|---|---|---|
| **FIFO-share × iron-ore interaction** | Suburb-level mining-cashflow beta — which suburbs carry hidden cyclical downside in the 5-yr tail as iron ore softens. Orthogonal to the citywide median. | ATO postcode occupation × iron-ore price | Build FIFO share per postcode; interact with commodity price |
| **STRA register de-listing velocity** | Rental-supply relief, current — WA's mandatory register + $10k conversion incentive + 90-night cap flip short-stay back to long-term. | WA STRA register (DLGSC) | Count active STRA per SA2; falling = supply easing |
| **Cafe / specialty-coffee density change** | Gentrification nowcast — new-cafe openings *lead* price growth. | Google Places / OSM POI; ABS business counts | Quarterly POI delta per SA2 |
| **Building-approval pipeline by suburb** | Future supply that caps growth (e.g. Cannington apartment TOD pipeline). | ABS 8731.0 (LGA); LGA registers | Approvals per dwelling stock; lead 12–24mo |
| **EV registrations per capita** | Forward affluence & renovation/new-build propensity. | DoT WA registrations | Registrations per dwelling by postcode; YoY |

## Tier C — corroboration only (never a primary driver)

- **Google Trends** suburb search interest — noisy; confirms, doesn't lead.
- **Crime statistics by locality** (WA Police) — matters to family buyers but slow-moving.
- **Tree canopy / urban-heat** (Landgate/DPLH) — livability premium; static.
- **Birth / household-formation / divorce rates by SA2** — genuinely predictive
  of family demand but **slow**; use as a structural control, not a trigger.

---

## The buyer's "child rates" hint — operationalised

The buyer's intuition that "child rates might affect the horizon" is correct.
Family-formation demand is real and specific to this buyer's segment. We capture
it through **four** channels, ordered fast→slow:

1. **Pool-permit rate** (Tier A) — fastest, discretionary, family-coded.
2. **Childcare occupancy/waitlist** (Tier A) — leads the buy decision.
3. **School in-zone pressure** (Tier A) — drives the catchment premium.
4. **SA2 family-cohort share / birth rate** (Tier C) — slow structural backdrop.

Net rule: **permit/register/roster data leads; demographic counts lag.** Weight
accordingly. Never let a slow Tier-C series move a near-term call on its own.

## Why this beats a stock-standard model

A generic Perth model stops at rates, migration and approvals and produces a
citywide number. This model adds **family-buyer-specific leading indicators**
(pools, childcare, school pressure) and a **cyclical-risk overlay** (FIFO×iron
ore, STRA supply) that together explain *which suburbs* hold up through the 2027
soft patch and re-accelerate after — which is the only question this buyer
actually needs answered.
