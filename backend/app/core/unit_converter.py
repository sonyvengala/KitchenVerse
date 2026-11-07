"""
Unit of Measurement Conversion Module for Inventory Management.
Supports standard commercial kitchen conversions for mass, volume, and count units.
"""
from typing import Optional, Tuple


# Normalized canonical unit mappings and conversion factors to base unit
# Base units:
# - Mass: 'kg'
# - Volume: 'l'
# - Count: 'pcs'

MASS_UNITS = {
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "kgs": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
    "gm": 0.001,
    "gms": 0.001,
    "mg": 0.000001,
    "milligram": 0.000001,
    "milligrams": 0.000001,
}

VOLUME_UNITS = {
    "l": 1.0,
    "liter": 1.0,
    "liters": 1.0,
    "litre": 1.0,
    "litres": 1.0,
    "ltr": 1.0,
    "ltrs": 1.0,
    "ml": 0.001,
    "milliliter": 0.001,
    "milliliters": 0.001,
    "millilitre": 0.001,
    "millilitres": 0.001,
}

COUNT_UNITS = {
    "pcs": 1.0,
    "pc": 1.0,
    "piece": 1.0,
    "pieces": 1.0,
    "unit": 1.0,
    "units": 1.0,
    "item": 1.0,
    "items": 1.0,
    "count": 1.0,
    "packet": 1.0,
    "packets": 1.0,
    "pack": 1.0,
    "packs": 1.0,
    "box": 1.0,
    "boxes": 1.0,
    "bottle": 1.0,
    "bottles": 1.0,
    "can": 1.0,
    "cans": 1.0,
}


def normalize_unit(unit: Optional[str]) -> str:
    """Normalize unit string for matching."""
    if not unit:
        return ""
    return unit.strip().lower().replace(".", "")


def get_unit_family_and_factor(unit: str) -> Tuple[Optional[str], float]:
    """
    Determine the unit family ('mass', 'volume', 'count') and conversion factor to the base unit.
    Returns (family, factor) or (None, 1.0) if unrecognized.
    """
    norm = normalize_unit(unit)
    if norm in MASS_UNITS:
        return ("mass", MASS_UNITS[norm])
    if norm in VOLUME_UNITS:
        return ("volume", VOLUME_UNITS[norm])
    if norm in COUNT_UNITS:
        return ("count", COUNT_UNITS[norm])
    return (None, 1.0)


def are_units_compatible(from_unit: str, to_unit: str) -> bool:
    """Check if two units can be converted to one another."""
    norm_from = normalize_unit(from_unit)
    norm_to = normalize_unit(to_unit)
    if norm_from == norm_to:
        return True

    fam_from, _ = get_unit_family_and_factor(norm_from)
    fam_to, _ = get_unit_family_and_factor(norm_to)

    if fam_from and fam_to and fam_from == fam_to:
        return True

    return False


def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> float:
    """
    Convert a quantity from `from_unit` to `to_unit`.
    Raises ValueError if units are incompatible.
    """
    if quantity == 0.0:
        return 0.0

    norm_from = normalize_unit(from_unit)
    norm_to = normalize_unit(to_unit)

    if norm_from == norm_to:
        return float(quantity)

    fam_from, factor_from = get_unit_family_and_factor(norm_from)
    fam_to, factor_to = get_unit_family_and_factor(norm_to)

    if fam_from is None or fam_to is None or fam_from != fam_to:
        raise ValueError(
            f"Cannot convert between incompatible units: '{from_unit}' and '{to_unit}'."
        )

    # Convert to base unit then to target unit:
    # base_qty = quantity * factor_from
    # target_qty = base_qty / factor_to
    converted = quantity * (factor_from / factor_to)
    return round(converted, 6)
