# Suburb playbook - the buyer-facing answer

Anchor: **Como 6152.** Budget: **$800k-$1.0M** for a **house** on **500sqm+**,
KDR-capable, family, near Como, good postcode. Premium river suburbs are out of
budget for a house; the play is the **fringe of the best school catchments** and
**near-in Canning value**.

## The shortlist

### Primary - Rossmoyne SHS catchment fringe (highest conviction)
The Rossmoyne Senior High School intake covers Bateman, Brentwood, Bull Creek,
Oberthur, Riverton, **Shelley**, Willetton. The catchment adds ~**10-15%** to
value. Rossmoyne itself (~$1.9M) and Willetton are out of reach, but the **fringe**
is affordable:
- **Shelley (~$960k)** - *the pick.* In-band, river-close, Rossmoyne zone, scarce
  land. Grandfathered owner-occupier status + school demand insulate it from the
  NG/CGT investor drag. Best growth-after-dip hold. **Model rank #1 at balanced.**
- **Riverton (~$1.02-1.09M)** - same zone, family-friendly, just over budget;
  watch for soft-patch pricing in the 2027 window.
- **Bull Creek / Bateman-adjacent** - same logic; confirm block size per-listing.

### Near-in value - City of Canning (closest to Como at budget)
- **Wilson (~$940-955k)** - larger blocks, Curtin-adjacent, among the closest
  at-budget options to Como, strong KDR margin. **Model rank #2 at balanced.**
- **St James (~$855-890k)** - Victoria Park / Curtin precinct, genuinely close to
  Como, KDR upside.
- **Parkwood (~$920-960k)** - big blocks, value, strong recent growth; a touch
  further out.
- **Bentley (~$780-820k)** - the value play: cheapest near-in, biggest margin of
  safety, strongest KDR economics; some pockets less polished.

### North-of-river land (more land per dollar; the catch is distance)
- **Dianella (~$970k-1.15M)** - best northern balance of land + location,
  Mt Lawley-adjacent, big original blocks.
- **Bayswater (~$980k-1.18M)** - METRONET hub, gentrifying, near the river;
  borderline budget.
- **Embleton (~$900-970k)** / **Balcatta (~$910-970k)** - 500sqm+ green-title,
  KDR upside.
- **Nollamara / Westminster (~$710-800k)** - biggest northern margin of safety;
  target original un-subdivided lots.

## Out of budget for a house (reference only)
Como ~$1.5M+ · Manning ~$1.55M · South Perth ~$2.0M · Applecross ~$2.4M ·
Mount Pleasant ~$2.1M · Ardross ~$1.86M · Salter Point ~$1.63M · Winthrop
~$1.75M · Kensington ~$1.44M · Booragoon ~$1.6M. Only villas/units sit under
$1.0M here.

## How the heat map / score works

Each suburb gets a 0-100 **Buyer-Fit** score from six weighted dimensions -
growth (25%), near-Como proximity (20%), family (15%), land/backyard (15%),
postcode (15%), KDR (10%) - with over-budget suburbs penalised (×0.55 if median
>$1.0M). The **proximity-vs-schools slider** redistributes a 0.20 swing between
Como-proximity and school-catchment weight:
- Drag **toward Como** → Wilson, St James, Bentley rise (near-in).
- Drag **toward schools** → Shelley, Riverton (Rossmoyne zone) rise.
- **Balanced (50)** → **Shelley #1, Wilson #2** - the model's default answer.

`model/scoring.py` reproduces this exactly; run `python3 scoring.py 0` /
`100` to see the extremes.

## Timing & triggers

Posture: **patient/opportunistic** - low holding costs remove the penalty for
waiting. The 2027 soft patch (not a crash) is the entry window. Act when **any
two** confirm:
1. Perth monthly growth flat/negative for 2+ months.
2. Advertised stock rising back toward the 5-year average.
3. Iron ore sustained <US$85/t with rising FIFO unemployment.
4. Days-on-market past ~20 in target suburbs.

## Per-listing checks (Layer 4, before offering)
- **Confirm 500sqm+** via Landgate cadastre (no public median block size exists).
- **Green-title** preferred over survey-strata for KDR optionality.
- **KDR economics:** land value ≥ improved value → old stock is fine.
- **In-zone:** verify the address sits inside the live Rossmoyne/Willetton intake
  boundary (boundaries shift).
