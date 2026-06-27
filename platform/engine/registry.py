"""
Strategy + Registry: map an asset_class to its feature pack.

Adding a vertical = adding a module under assets/ and one line here. The shared
engine and the UI never need to change. This is the scalability seam.
"""
from .assets import residential, commercial

_STRATEGIES = {
    "residential": residential,
    "commercial": commercial,
}


def get_strategy(asset_class):
    if asset_class not in _STRATEGIES:
        raise ValueError(f"unknown asset_class '{asset_class}'. "
                         f"known: {sorted(_STRATEGIES)}")
    return _STRATEGIES[asset_class]


def known_asset_classes():
    return sorted(_STRATEGIES)
