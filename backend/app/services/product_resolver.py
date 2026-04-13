"""
Product resolver: the single entry point for ingredient-to-price lookups.

Resolution chain
----------------
1. Normalize ingredient name to a stable cache key.
2. Check local product_cache (SQLite).
   - Cache hit with real data: return immediately.
   - Cache hit with source='off_miss': ingredient was already tried; fall back.
   - Cache miss: proceed to step 3.
3. Search Open Food Facts (OFF) once.
   - Good result: normalize, store in cache, return.
   - No good result: store off_miss record, fall back.
4. Fallback: call nn_service._get_price() (legacy heuristic pricing).

Package-based pricing
---------------------
When a cached product has package_amount + package_unit we compute:

    packages_needed = ceil(recipe_qty_in_pkg_units / package_amount)
    basket_cost     = packages_needed x estimated_price

This replaces the old fractional math for any ingredient that can be
resolved to a purchasable package.
"""

from __future__ import annotations

import logging
import re
from math import ceil
from typing import Optional

from app.services import off_client, product_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit conversion tables
# ---------------------------------------------------------------------------

_TO_ML: dict[str, float] = {
    "ml": 1,
    "milliliter": 1,
    "millilitre": 1,
    "milliliters": 1,
    "millilitres": 1,
    "l": 1000,
    "liter": 1000,
    "litre": 1000,
    "liters": 1000,
    "litres": 1000,
    "tsp": 4.929,
    "teaspoon": 4.929,
    "teaspoons": 4.929,
    "tbsp": 14.787,
    "tablespoon": 14.787,
    "tablespoons": 14.787,
    "fl oz": 29.574,
    "fluid ounce": 29.574,
    "fluid ounces": 29.574,
    "cup": 236.588,
    "cups": 236.588,
    "pt": 473.176,
    "pint": 473.176,
    "pints": 473.176,
    "qt": 946.353,
    "quart": 946.353,
    "quarts": 946.353,
    "gal": 3785.41,
    "gallon": 3785.41,
    "gallons": 3785.41,
}

_TO_G: dict[str, float] = {
    "g": 1,
    "gram": 1,
    "grams": 1,
    "kg": 1000,
    "kilogram": 1000,
    "kilograms": 1000,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
    # Dry volume approximations (rough average for baking ingredients)
    "tsp": 4.2,
    "teaspoon": 4.2,
    "teaspoons": 4.2,
    "tbsp": 12.6,
    "tablespoon": 12.6,
    "tablespoons": 12.6,
    "cup": 201.6,
    "cups": 201.6,
}

_VOLUME_UNITS = set(_TO_ML)
_MASS_UNITS = set(_TO_G)
_COUNT_UNITS = {
    "",
    "count",
    "piece",
    "pieces",
    "item",
    "items",
    "whole",
    "each",
    "ea",
    "unit",
    "units",
    "egg",
    "eggs",
    "clove",
    "cloves",
    "slice",
    "slices",
    "packet",
    "packets",
    "pack",
    "packs",
    "can",
    "cans",
    "jar",
    "jars",
    "bottle",
    "bottles",
    "bag",
    "bags",
    "bunch",
    "bunches",
    "head",
    "heads",
    "sprig",
    "sprigs",
    "stalk",
    "stalks",
    "leaf",
    "leaves",
}


def _unit_family(unit: str) -> str:
    """Return 'volume', 'mass', 'count', or 'unknown'."""
    u = unit.lower().strip()
    if u in _VOLUME_UNITS:
        return "volume"
    if u in _MASS_UNITS:
        return "mass"
    if u in _COUNT_UNITS:
        return "count"
    return "unknown"


def convert_recipe_to_package_units(
    recipe_qty: float,
    recipe_unit: str,
    pkg_amount: float,
    pkg_unit: str,
) -> Optional[tuple[float, float]]:
    """
    Convert recipe_qty (in recipe_unit) and pkg_amount (in pkg_unit) into a
    common base unit so we can compute ceil(recipe / pkg).

    Returns (recipe_in_base, pkg_in_base) or None if families do not match.
    """
    r_unit = recipe_unit.lower().strip()
    p_unit = pkg_unit.lower().strip()

    if r_unit in _TO_G and p_unit in _TO_G:
        return recipe_qty * _TO_G[r_unit], pkg_amount * _TO_G[p_unit]
    if r_unit in _TO_ML and p_unit in _TO_ML:
        return recipe_qty * _TO_ML[r_unit], pkg_amount * _TO_ML[p_unit]
    if _unit_family(r_unit) == "count" and _unit_family(p_unit) == "count":
        return recipe_qty, pkg_amount
    return None


# ---------------------------------------------------------------------------
# Ingredient key normalization
# ---------------------------------------------------------------------------

_CACHE_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "all purpose flour": ("all-purpose flour", "flour"),
    "ap flour": ("all-purpose flour", "flour"),
    "evoo": ("olive oil", "extra virgin olive oil"),
    "extra virgin olive oil": ("extra virgin olive oil", "olive oil"),
    "egg": ("egg", "eggs"),
    "eggs": ("eggs", "egg"),
    "mozzarella cheese": ("mozzarella",),
    "kosher salt": ("salt",),
    "sea salt": ("salt",),
    "table salt": ("salt",),
    "fine sea salt": ("salt",),
    "coarse salt": ("salt",),
    "granulated sugar": ("sugar",),
    "white sugar": ("sugar",),
    "caster sugar": ("sugar",),
    "confectioners sugar": ("powdered sugar",),
    "icing sugar": ("powdered sugar",),
    "pizza sauce": ("tomato sauce",),
}


def normalize_ingredient_key(name: str) -> str:
    """Lower-case, strip, collapse whitespace, and smooth punctuation."""
    lowered = name.lower().strip()
    lowered = re.sub(r"[-_/]+", " ", lowered)
    lowered = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", lowered)


def _candidate_cache_keys(name: str) -> list[str]:
    """Return cache lookup candidates from most to least specific."""
    key = normalize_ingredient_key(name)
    candidates: list[str] = [key]

    for alias in _CACHE_KEY_ALIASES.get(key, ()):
        if alias not in candidates:
            candidates.append(alias)

    if key.endswith("es") and len(key) > 2:
        singular = key[:-2]
        if singular not in candidates:
            candidates.append(singular)
    elif key.endswith("s") and len(key) > 1:
        singular = key[:-1]
        if singular not in candidates:
            candidates.append(singular)

    return candidates


# ---------------------------------------------------------------------------
# OFF result normalization
# ---------------------------------------------------------------------------

_QTY_PATTERNS = [
    re.compile(r"(\d+)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z ]+)", re.IGNORECASE),
]

_UNIT_ALIASES: dict[str, str] = {
    "milliliter": "ml",
    "millilitre": "ml",
    "milliliters": "ml",
    "millilitres": "ml",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litres": "l",
    "gram": "g",
    "grams": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "cup": "cup",
    "cups": "cup",
}


def parse_package_quantity(qty_str: str) -> Optional[tuple[float, str]]:
    """
    Parse an OFF quantity string into (amount, unit).

    Handles:
      "21 g"        -> (21.0, "g")
      "8 oz"        -> (8.0, "oz")
      "500 ml"      -> (500.0, "ml")
      "2 x 10 g"    -> (20.0, "g")
      "6 x 29.5 ml" -> (177.0, "ml")
      "12 eggs"     -> (12.0, "count")
      "250g"        -> (250.0, "g")
    """
    if not qty_str:
        return None
    s = qty_str.strip()

    m = _QTY_PATTERNS[0].match(s)
    if m:
        count = int(m.group(1))
        amount = float(m.group(2))
        raw_unit = m.group(3).strip().lower()
        unit = _UNIT_ALIASES.get(raw_unit, raw_unit)
        return round(count * amount, 4), unit

    m = _QTY_PATTERNS[1].match(s)
    if m:
        amount = float(m.group(1))
        raw_unit = m.group(2).strip().lower()
        unit = _UNIT_ALIASES.get(raw_unit, raw_unit)
        if unit in _COUNT_UNITS:
            unit = "count"
        if unit and _unit_family(unit) != "unknown":
            return amount, unit

    return None


def _normalize_off_product(raw: dict, ingredient_name: str) -> dict:
    """
    Convert a raw OFF product dict into our internal cache schema.
    Pricing is not taken from OFF; we supply estimated_price ourselves.
    """
    key = normalize_ingredient_key(ingredient_name)
    product_name = (raw.get("product_name") or "").strip() or None
    brand = (raw.get("brands") or "").strip() or None
    off_id = raw.get("_id") or raw.get("id") or None

    qty_str = (raw.get("quantity") or "").strip()
    parsed = parse_package_quantity(qty_str)
    package_amount = parsed[0] if parsed else None
    package_unit = parsed[1] if parsed else None

    estimated_price = _heuristic_price(ingredient_name, package_amount, package_unit)

    return {
        "ingredient_key": key,
        "search_terms": ingredient_name,
        "product_name": product_name,
        "brand": brand,
        "off_product_id": str(off_id) if off_id else None,
        "package_amount": package_amount,
        "package_unit": package_unit,
        "estimated_price": estimated_price,
        "source": "off_search",
        "confidence": 0.7 if parsed else 0.4,
    }


def _heuristic_price(item_name: str, pkg_amount: Optional[float], pkg_unit: Optional[str]) -> float:
    """Use nn_service._get_price as a legacy heuristic for an ingredient."""
    try:
        from app.services.nn_service import _get_price

        qty = pkg_amount if pkg_amount else 1.0
        unit = pkg_unit if pkg_unit else ""
        return _get_price(item_name, qty, unit)
    except Exception:
        return 2.99


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_product(ingredient_name: str, db_path: str | None = None) -> dict | None:
    """
    Resolve an ingredient to a cached product record.

    Returns the product dict (may have source='off_miss'; caller should check),
    or None if we have no data at all.
    """
    key = normalize_ingredient_key(ingredient_name)
    saw_off_miss = False

    for candidate in _candidate_cache_keys(ingredient_name):
        cached = product_cache.get(candidate, db_path)
        if cached is None:
            continue
        if cached["source"] == "off_miss":
            saw_off_miss = True
            logger.debug("Cache miss-record for %r; continuing alias lookup", candidate)
            continue
        logger.debug("Cache hit for %r via %r (source=%s)", key, candidate, cached["source"])
        return cached

    if saw_off_miss:
        logger.debug("All cache candidates for %r resolved to off_miss; skipping OFF", key)
        return None

    logger.info("Cache miss for %r; querying OFF", key)
    raw_products = off_client.search_product(ingredient_name)
    best = off_client.pick_best_candidate(raw_products, ingredient_name)

    if best:
        normalised = _normalize_off_product(best, ingredient_name)
        product_cache.put(normalised, db_path)
        logger.info(
            "OFF result cached for %r (pkg=%s %s)",
            key,
            normalised.get("package_amount"),
            normalised.get("package_unit"),
        )
        return normalised

    product_cache.put_miss(key, db_path)
    logger.info("No OFF result for %r; miss recorded", key)
    return None


def resolve_basket_pricing(
    item_name: str,
    recipe_qty: float,
    recipe_unit: str,
    db_path: str | None = None,
) -> dict:
    """
    Return structured basket pricing for buying enough of item_name.

    The result always contains:
      estimated_price
      pricing_source
      fallback_reason
      package_amount
      package_unit
      required_amount
      required_unit
    """
    product = get_product(item_name, db_path)
    result = {
        "item_name": item_name,
        "estimated_price": 0.0,
        "pricing_source": "fallback_fractional_pricing",
        "fallback_reason": None,
        "required_amount": float(recipe_qty),
        "required_unit": recipe_unit,
        "package_amount": None,
        "package_unit": None,
        "package_price": None,
        "packages_needed": None,
        "brand": product.get("brand") if product else None,
        "product_name": product.get("product_name") if product else None,
        "product_source": product.get("source") if product else None,
    }

    if product is None:
        result["estimated_price"] = round(_heuristic_price(item_name, recipe_qty, recipe_unit), 2)
        result["fallback_reason"] = "no_product_match"
        logger.info("Pricing fallback for %r: %s", item_name, result["fallback_reason"])
        return result

    package_amount = product.get("package_amount")
    package_unit = product.get("package_unit")
    if package_amount is None or not package_unit:
        result["estimated_price"] = round(_heuristic_price(item_name, recipe_qty, recipe_unit), 2)
        result["fallback_reason"] = "missing_package_metadata"
        logger.info("Pricing fallback for %r: %s", item_name, result["fallback_reason"])
        return result

    pkg_amount = float(package_amount)
    pkg_unit = str(package_unit)
    pkg_price = float(product.get("estimated_price", 0.0))
    result["package_amount"] = pkg_amount
    result["package_unit"] = pkg_unit
    result["package_price"] = round(pkg_price, 2)

    converted = convert_recipe_to_package_units(recipe_qty, recipe_unit, pkg_amount, pkg_unit)
    if converted is None:
        result["estimated_price"] = round(_heuristic_price(item_name, recipe_qty, recipe_unit), 2)
        result["fallback_reason"] = "unit_conversion_failed"
        logger.info(
            "Pricing fallback for %r: %s (required=%s %s, package=%s %s)",
            item_name,
            result["fallback_reason"],
            recipe_qty,
            recipe_unit,
            pkg_amount,
            pkg_unit,
        )
        return result

    recipe_in_base, pkg_in_base = converted
    if pkg_in_base <= 0:
        result["estimated_price"] = round(_heuristic_price(item_name, recipe_qty, recipe_unit), 2)
        result["fallback_reason"] = "invalid_package_amount"
        logger.info("Pricing fallback for %r: %s", item_name, result["fallback_reason"])
        return result

    packages_needed = max(1, ceil(recipe_in_base / pkg_in_base))
    cost = round(packages_needed * pkg_price, 2)
    logger.debug(
        "%r: %g %s -> %d pkg x $%.2f = $%.2f",
        item_name,
        recipe_qty,
        recipe_unit,
        packages_needed,
        pkg_price,
        cost,
    )
    result["estimated_price"] = cost
    result["pricing_source"] = "package_pricing"
    result["packages_needed"] = packages_needed
    return result


def get_basket_price(
    item_name: str,
    recipe_qty: float,
    recipe_unit: str,
    db_path: str | None = None,
) -> float:
    """Compatibility wrapper returning only the resolved basket price."""
    return float(resolve_basket_pricing(item_name, recipe_qty, recipe_unit, db_path)["estimated_price"])
