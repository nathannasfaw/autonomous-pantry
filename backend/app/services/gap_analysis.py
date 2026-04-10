"""
Gap analysis: computes how much of each recipe ingredient is missing from the pantry.
Applies a 0.7x conservative buffer to pantry items with confidence < 0.75.
"""

CONFIDENCE_BUFFER = 0.7
CONFIDENCE_THRESHOLD = 0.75


def _normalize(name: str) -> str:
    """Normalize an item name for fuzzy matching."""
    return name.lower().strip()


def _find_pantry_item(ingredient_name: str, pantry: list) -> dict | None:
    """
    Find a pantry item that matches the ingredient name.
    Uses exact normalized match first, then substring match.
    """
    normalized = _normalize(ingredient_name)

    # Exact match
    for p_item in pantry:
        if _normalize(p_item["item"]) == normalized:
            return p_item

    # Substring match: pantry item name is contained in ingredient name or vice versa
    for p_item in pantry:
        p_norm = _normalize(p_item["item"])
        if p_norm in normalized or normalized in p_norm:
            return p_item

    # Word overlap match: share at least one significant word
    ingredient_words = set(normalized.split())
    for p_item in pantry:
        p_words = set(_normalize(p_item["item"]).split())
        overlap = ingredient_words & p_words
        # Filter out common trivial words
        trivial = {"of", "the", "a", "an", "and", "or", "with"}
        meaningful_overlap = overlap - trivial
        if meaningful_overlap:
            return p_item

    return None


def compute_gaps(recipe_ingredients: list, pantry: list) -> tuple[list, list]:
    """
    For each recipe ingredient, compute how much is missing from pantry.
    Apply 0.7x buffer to any pantry item with confidence < 0.75.

    Returns:
        (gaps, pantry_used)
        gaps: [{"item": str, "required": float, "available": float, "gap": float, "unit": str}]
        pantry_used: [{"item": str, "quantity": float, "unit": str}] — ingredients fully covered by pantry
    """
    gaps = []
    pantry_used = []

    for ingredient in recipe_ingredients:
        item_name = ingredient.get("item", "")
        try:
            required = float(ingredient.get("quantity", 1.0))
        except (ValueError, TypeError):
            required = 0.0  # "to taste", "as needed", etc. — treat as no fixed quantity
        unit = ingredient.get("unit", "")

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

        gap = max(0.0, required - available)

        if gap > 0.0:
            gaps.append({
                "item": item_name,
                "required": required,
                "available": available,
                "gap": gap,
                "unit": unit,
            })
        elif pantry_match is not None:
            # Fully covered by pantry — track it
            pantry_used.append({
                "item": pantry_match["item"],
                "quantity": required if required > 0 else raw_available,
                "unit": unit or pantry_match.get("unit", ""),
            })

    return gaps, pantry_used
