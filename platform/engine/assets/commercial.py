"""
Commercial asset-class strategy (feature pack) - proof of the second tier.

Same shared engine, a completely different valuation basis and input set. This
is what makes the product two-tier: the user picks asset_class in their profile,
the registry swaps this module in, and nothing in the shared engine changes.
"""

MANIFEST = {
    "asset_class": "commercial",
    "valuation_basis": "capitalisation rate / net yield / NOI / WALE",
    "score_dimensions": ["cap_rate", "wale", "covenant", "location", "reposition"],
    "required_inputs": ["noi", "cap_rate", "market_cap_rate", "wale_years", "vacancy"],
    "leading_indicators": ["cap_rate_trend", "vacancy_trend", "incentive_levels", "transaction_volume"],
}

# Demo market read for Perth metro commercial, mid-2026 (illustrative).
MARKET = {
    "valuation_gap_pct": -8.0,   # cap rates have softened; assets look cheap vs trend
    "signal_score": 0.10,        # stabilising and firming
}


# Illustrative anchor paths for a ~$2.5M Perth metro asset (capital value).
# Clearly a placeholder until the commercial data adapter (NOI/cap-rate) is wired.
ANCHORS = [
    ("Now", 0.0, 2_500_000, 2_500_000, 2_500_000),
    ("Yr1", 1.0, 2_450_000, 2_560_000, 2_680_000),
    ("Yr2", 2.0, 2_480_000, 2_660_000, 2_880_000),
    ("Yr3", 3.0, 2_560_000, 2_780_000, 3_080_000),
    ("Yr5", 5.0, 2_700_000, 2_980_000, 3_400_000),
]


def market_inputs(profile):
    return MARKET["valuation_gap_pct"], MARKET["signal_score"]


def datasets(profile):
    """No commercial suburb/listing adapter yet - returns nothing (UI shows a note)."""
    return {"suburbs": None, "listings": None}
