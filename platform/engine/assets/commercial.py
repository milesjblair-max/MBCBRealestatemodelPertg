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


def market_inputs(profile):
    return MARKET["valuation_gap_pct"], MARKET["signal_score"]
