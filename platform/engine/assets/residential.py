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


def market_inputs(profile):
    """Return the (valuation_gap_pct, signal_score) the timing spine consumes."""
    return MARKET["valuation_gap_pct"], MARKET["signal_score"]
