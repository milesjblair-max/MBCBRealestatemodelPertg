# Data sources - what to use, what it gives, how to ingest

Bias toward **free, official, automatable** sources for the spine; use paid/
subscription only where there's no public substitute. Verify the headline macro
block before relying on it - figures move.

## Free / public (the backbone)

| Source | Dataset | Gives | Cadence | Ingest |
|---|---|---|---|---|
| **RBA** | Cash Rate table **F1**; statistics | Cash rate, rate history | Per meeting | CSV/API, automatable |
| **ABS** | **3101.0** National/state population | Migration, population by state; SA2 annually | Quarterly/annual | ABS Data API (SDMX/JSON) |
| **ABS** | **8731.0** Building Approvals | Dwelling approvals by state/LGA | Monthly | ABS Data API |
| **ABS** | **8752.0** Building Activity | Completions | Quarterly | Download/API |
| **ABS** | **6401.0** CPI + monthly indicator | Inflation, capital-city | Monthly/quarterly | ABS Data API |
| **ABS** | **5601.0** Lending Indicators | First-home-buyer & investor lending | Monthly | ABS Data API |
| **ABS** | Census occupancy, family/age by SA2 | Household formation, family-cohort share | 5-yearly | TableBuilder/API |
| **ATO** | Taxation Statistics (postcode, Table 7/25) | Income & occupation by postcode (FIFO/mining share) | Annual (lagged) | CSV download |
| **APRA** | ADI property exposures | Serviceability, investor/owner mix | Quarterly | CSV |
| **data.wa.gov.au / Landgate SLIP** | Cadastre, residential attributes, sales evidence, basemaps | Block size, beds/baths, lot polygons (lodged vs registered), sales | Continuous | WFS/WMS/ArcGIS REST; some free, premium fee-based |
| **WA Dept of Education** | Schools Online intake areas; "WA Schools List" | Catchment polygons, school list | Annual | data.wa.gov.au layers |
| **ACARA / My School** | Enrolment, ICSEA | School enrolment vs capacity | Annual | Download |
| **ACECQA** | National Quality Framework register (ITS) | Childcare centres, places, ratings by suburb | ~Daily CSV | CSV pull |
| **DLGSC (WA)** | Short-Term Rental Accommodation register | Active STRA listings by area | Continuous (mandatory since 2025) | Register export |
| **WA Police** | Crime statistics by locality | Crime rate trend | Monthly/quarterly | Portal/CSV |
| **DoT WA** | Vehicle registrations | EV share by postcode (affluence proxy) | Periodic | data.wa.gov.au |
| **BOM / DPLH** | Climate, flood/bushfire overlays, tree canopy | Livability/risk layers | Static/periodic | Spatial layers |
| **WA Budget papers** | Iron-ore assumption, royalties | State fiscal exposure to iron ore | Annual + mid-year | PDF/data |
| **LGA planning registers** | DA/BA lodgements (incl. **pool permits**, subdivisions) | Leading permit data per suburb | Monthly | Scrape/FOI per council; not standardised |

## Paywalled / subscription (use sparingly)

- **Cotality (CoreLogic)** - Home Value Index (hedonic), auction clearance,
  Cordell construction costs. The consistent cross-source growth metric.
- **SQM Research** - vacancy, rents, advertised stock, weekly.
- **REIWA member data** - suburb medians, days-on-market, discounting.
- **Landgate premium extracts** - bulk sales/attributes.

**Source discipline:** suburb medians diverge 10-20% (REIWA tiles vs Cotality vs
propertyvalue). Pick **one** source per metric and hold it constant; use Cotality
growth as the cross-source comparator; treat single-suburb medians as ranges.

## Listings & a genuinely "live" feed - the compliant path

**Scraping realestate.com.au, Domain and REIWA is prohibited by their terms.**
They accept listings only from approved feed providers (REAXML). Do **not** build
a scraper. Two compliant routes:

1. **Saved-search deep-links (implemented).** The tool builds portal URLs that
   always open *current* results, sorted newest-first, pre-filtered to house /
   3+ bed / <$1.0M / target suburb. Zero infrastructure, always fresh on click.

2. **Domain Developer API (the upgrade path).** Tiered: free dev tier; paid
   business tiers add live listings, AVM/price estimates, and school &
   demographic endpoints. REA's API is largely partner/agent-only, so Domain is
   the realistic live-listings route. Implementation:
   - Register a Domain developer app; store the key as a GitHub **repository
     secret** (never commit it).
   - A **scheduled GitHub Action** (e.g. every 6-12h) calls the listings
     endpoint for the target suburbs/filters and writes `data/listings.json`.
   - The tool `fetch()`es `data/listings.json` and renders cards + "new since
     last refresh" flags. Property suggestions (current and upcoming) surface
     here, with street-level matches drawn from Landgate cadastre (500sqm+
     green-title inside target catchments).

This gives the buyer a real refreshing feed without breaching any terms.

## Refresh cadence (suggested)

- **Macro block:** after each RBA meeting and monthly Cotality print.
- **Iron ore:** weekly during volatility.
- **Listings (if Domain API wired):** every 6-12 hours via the Action.
- **Enriched layers:** pool permits & STRA monthly; childcare occupancy quarterly;
  ATO/Census on release (annual/5-yearly).
