"""
Residential asset-class strategy (feature pack).

Swapped per vertical via the registry. Declares the residential valuation basis
and the market inputs that drive the timing spine. The shared engine
(timing.py, scoring) never changes between verticals; only this module does.
"""

MANIFEST = {
    "asset_class": "residential",
    "valuation_basis": "hedonic + land value + knock-down-rebuild optionality",
    "score_dimensions": ["growth", "family", "land", "kdr", "proximity", "post"],
    "required_inputs": ["median_price", "household_income", "rents", "build_cost", "real_cash_rate"],
    "leading_indicators": ["days_on_market", "stock_vs_avg", "pool_permits", "cadastre_ratio", "school_zone_pressure"],
}

# Demo market read for Perth WA residential, mid-2026. In production these come
# from the data adapters (ABS/RBA/Cotality/Landgate), not a literal.
MARKET = {
    "valuation_gap_pct": 4.0,    # modestly above fundamentals fair-value
    "signal_score": -0.10,       # gently cooling (iron ore, NG/CGT, decelerating growth)
}


# Layer-1 calibrated anchor paths (bear/base/bull) for Perth WA residential.
# label, t, bear, base, bull. The DERIVED weights blend these into the expected path.
ANCHORS = [
    ("Now", 0.0, 1_000_000, 1_000_000, 1_000_000),
    ("End-26", 0.5, 1_020_000, 1_055_000, 1_080_000),
    ("Mid-27", 1.0, 975_000, 1_080_000, 1_150_000),
    ("End-27", 1.5, 935_000, 1_085_000, 1_210_000),
    ("Mid-28", 2.0, 930_000, 1_110_000, 1_280_000),
    ("End-28", 2.5, 955_000, 1_145_000, 1_340_000),
    ("Mid-29", 3.0, 1_000_000, 1_180_000, 1_400_000),
]


def market_inputs(profile):
    """Return the (valuation_gap_pct, signal_score) the timing spine consumes."""
    return MARKET["valuation_gap_pct"], MARKET["signal_score"]


def datasets(profile):
    """Where this vertical reads its suburb + listing data (read-only, shared)."""
    return {"suburbs": "data/suburbs.json", "listings": "data/listings.json"}
