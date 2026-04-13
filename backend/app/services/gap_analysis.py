"""
Gap analysis: computes how much of each recipe ingredient is missing from the pantry.
Applies a 0.7x conservative buffer to pantry items with confidence < 0.75.
"""

import re

CONFIDENCE_BUFFER = 0.7
CONFIDENCE_THRESHOLD = 0.75
OPTIONAL_UNITS = {"as desired", "to taste", "as needed", "optional"}
OPTIONAL_ITEM_PATTERNS = (
    r"\boptional\b",
    r"\bas desired\b",
    r"\bto taste\b",
    r"\bas needed\b",
    r"\byour choice of\b",
    r"\bchoice of\b",
    r"\bdesired toppings?\b",
    r"\btoppings?\b",
    r"\bfor serving\b",
    r"\bto serve\b",
)


def _normalize(name: str) -> str:
    """Normalize an item name for fuzzy matching."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", name.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _normalize_words(name: str) -> set[str]:
    """Tokenize and lightly singularize words for fuzzy matching."""
    words = set()
    for word in _normalize(name).split():
        if word.endswith("es") and len(word) > 3:
            words.add(word[:-2])
        elif word.endswith("s") and len(word) > 2:
            words.add(word[:-1])
        words.add(word)
    return words


def _is_optional_or_placeholder(item_name: str, unit: str) -> bool:
    """Return True for optional/free-form ingredient lines that should not become cart items."""
    normalized_item = _normalize(item_name)
    normalized_unit = _normalize(unit)
    if normalized_unit in OPTIONAL_UNITS:
        return True
    return any(re.search(pattern, normalized_item) for pattern in OPTIONAL_ITEM_PATTERNS)


def _looks_like_recipe_echo(item_name: str, recipe_name: str | None) -> bool:
    """Return True when an ingredient line just repeats the dish name."""
    if not recipe_name:
        return False
    item_words = _normalize_words(item_name)
    recipe_words = _normalize_words(recipe_name)
    if not item_words or not recipe_words:
        return False
    return item_words.issubset(recipe_words)


def _find_pantry_item(ingredient_name: str, pantry: list) -> dict | None:
    """
    Find a pantry item that matches the ingredient name.
    Uses exact normalized match first, then substring match.
    """
    normalized = _normalize(ingredient_name)
    ingredient_words = _normalize_words(ingredient_name)

    # Exact match
    for p_item in pantry:
        if _normalize(p_item["item"]) == normalized:
            return p_item

    # Phrase containment for genuinely close names only.
    # Single-word pantry items should not satisfy multi-word recipe ingredients like
    # "tomato sauce" -> "tomato".
    for p_item in pantry:
        p_norm = _normalize(p_item["item"])
        if p_norm in normalized or normalized in p_norm:
            if " " not in normalized and " " not in p_norm:
                return p_item
            ingredient_word_count = len(normalized.split())
            pantry_word_count = len(p_norm.split())
            if ingredient_word_count >= 2 and pantry_word_count >= 2:
                return p_item

    # Multi-word token subset match, e.g. "extra virgin olive oil" should satisfy
    # "olive oil", but "tomato" should not satisfy "tomato sauce".
    for p_item in pantry:
        p_words = _normalize_words(p_item["item"])
        if len(ingredient_words) >= 2 and ingredient_words.issubset(p_words):
            return p_item
        if len(p_words) >= 2 and p_words.issubset(ingredient_words):
            return p_item

    return None


def _estimate_available_in_recipe_units(
    item_name: str,
    raw_available: float,
    pantry_unit: str,
    recipe_unit: str,
) -> float:
    """
    Estimate pantry availability expressed in the recipe's unit.

    Handles direct unit conversion and package/container pantry units when the
    resolved product tells us the package size.
    """
    if raw_available <= 0:
        return 0.0
    if not recipe_unit:
        return raw_available

    from app.services import product_resolver as pr

    direct = pr.convert_recipe_to_package_units(
        raw_available,
        pantry_unit,
        1.0,
        recipe_unit,
        ingredient_name=item_name,
    )
    if direct is not None:
        available_base, recipe_unit_base = direct
        if recipe_unit_base > 0:
            return available_base / recipe_unit_base

    product = pr.get_product(item_name)
    if product and product.get("package_amount") and product.get("package_unit"):
        if pr._unit_family(pantry_unit) == "count":
            converted = pr.convert_recipe_to_package_units(
                1.0,
                recipe_unit,
                float(product["package_amount"]),
                str(product["package_unit"]),
                ingredient_name=item_name,
            )
            if converted is not None:
                recipe_unit_base, pkg_base = converted
                if recipe_unit_base > 0:
                    return (raw_available * pkg_base) / recipe_unit_base

    return raw_available


def compute_gaps(recipe_ingredients: list, pantry: list, recipe_name: str | None = None) -> list:
    """
    For each recipe ingredient, compute how much is missing from pantry.
    Apply 0.7x buffer to any pantry item with confidence < 0.75.
    Return list of gaps: [{"item": str, "required": float, "available": float, "gap": float, "unit": str}]
    Items fully covered by pantry are excluded from the return list.
    """
    gaps = []

    for ingredient in recipe_ingredients:
        item_name = ingredient.get("item", "")
        unit = ingredient.get("unit", "")
        if _is_optional_or_placeholder(item_name, unit):
            continue
        if _looks_like_recipe_echo(item_name, recipe_name):
            continue
        try:
            required = float(ingredient.get("quantity", 1.0))
        except (ValueError, TypeError):
            required = 0.0  # "to taste", "as needed", etc. — treat as no fixed quantity
        pantry_match = _find_pantry_item(item_name, pantry)

        if pantry_match is None:
            available = 0.0
        else:
            raw_available = float(pantry_match.get("quantity", 0.0))
            confidence = float(pantry_match.get("confidence", 1.0))
            # Apply conservative buffer for low-confidence items
            if confidence < CONFIDENCE_THRESHOLD:
                available = raw_available * CONFIDENCE_BUFFER
            else:
                available = raw_available
            available = _estimate_available_in_recipe_units(
                item_name=item_name,
                raw_available=available,
                pantry_unit=str(pantry_match.get("unit", "")),
                recipe_unit=unit,
            )

        gap = max(0.0, required - available)

        # Only include items where there is an actual gap
        if gap > 0.0:
            gaps.append({
                "item": item_name,
                "required": required,
                "available": available,
                "gap": gap,
                "unit": unit,
            })

    return gaps
