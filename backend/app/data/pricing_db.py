"""
Pricing database: loads the grocery ingredient spreadsheet and provides
quality-aware, store-aware price lookups.

Store rules:
  - Brand contains "greenwise" or "publix" → Publix only
  - Brand contains "simple truth", "private selection", or "kroger" → Kroger only
  - Otherwise → available at both
"""

import os
import logging
from difflib import SequenceMatcher

import openpyxl

logger = logging.getLogger(__name__)

XLSX_PATH = os.path.join(os.path.dirname(__file__), "Grocery Ingredient Spreadsheet.xlsx")

# Quality tier → numeric score (0–1)
QUALITY_SCORES = {
    "budget": 0.2,
    "standard": 0.4,
    "premium": 0.7,
    "excellent": 1.0,
    # Variants
    "convenience": 0.35,
    "convenience/premium": 0.6,
    "specialty/excellent": 1.0,
    "standard (flash frozen)": 0.4,
    "excellent (flash frozen)": 1.0,
}

PUBLIX_KEYWORDS = {"greenwise", "publix"}
KROGER_KEYWORDS = {"simple truth", "private selection", "kroger"}


def _detect_store(brand: str) -> str:
    """Detect store from brand name. Returns 'publix', 'kroger', or 'both'."""
    brand_lower = brand.lower()
    for kw in PUBLIX_KEYWORDS:
        if kw in brand_lower:
            return "publix"
    for kw in KROGER_KEYWORDS:
        if kw in brand_lower:
            return "kroger"
    return "both"


def _quality_score(quality_str: str) -> float:
    """Convert quality string to numeric score."""
    return QUALITY_SCORES.get(quality_str.lower().strip(), 0.5)


# ---------------------------------------------------------------------------
# In-memory database (loaded once at import time)
# ---------------------------------------------------------------------------
# Structure: list of dicts with keys:
#   meal, category, brand, price, quality, quality_score, store
_DB: list[dict] = []

# category → list of entries (for fast lookup)
_BY_CATEGORY: dict[str, list[dict]] = {}


def _load():
    """Load the spreadsheet into memory."""
    global _DB, _BY_CATEGORY

    if not os.path.exists(XLSX_PATH):
        logger.warning(f"Pricing spreadsheet not found at {XLSX_PATH}")
        return

    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
        for row in rows[1:]:  # skip header
            if not row[0] or not row[2]:
                continue
            entry = {
                "meal": str(row[0]).strip(),
                "category": str(row[1]).strip(),
                "brand": str(row[2]).strip(),
                "price": float(row[3]) if row[3] else 0.0,
                "quality": str(row[4]).strip() if row[4] else "Standard",
                "quality_score": _quality_score(str(row[4]).strip() if row[4] else "Standard"),
                "store": _detect_store(str(row[2]).strip()),
            }
            _DB.append(entry)

            cat_key = entry["category"].lower()
            _BY_CATEGORY.setdefault(cat_key, []).append(entry)

    wb.close()
    logger.info(f"Pricing DB loaded: {len(_DB)} entries across {len(_BY_CATEGORY)} categories")


# Load on import
_load()


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def _similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _find_category(item_name: str) -> list[dict] | None:
    """
    Find the best matching category for a given ingredient name.
    Uses word-boundary-aware matching to avoid false substring hits
    (e.g. "salt" matching "salsa").
    """
    normalized = item_name.lower().strip()
    trivial = {"of", "the", "a", "an", "and", "or", "with", "fresh", "dried",
               "whole", "ground", "chopped", "sliced", "diced", "minced"}
    item_words = set(normalized.split()) - trivial
    # Keep a version with "fresh" for categories that use it like "mozzarella (fresh)"
    item_words_all = set(normalized.split()) - {"of", "the", "a", "an", "and", "or", "with"}

    # 1. Exact match
    if normalized in _BY_CATEGORY:
        return _BY_CATEGORY[normalized]

    # 2. Score each category
    candidates: list[tuple[float, str]] = []

    for cat_key in _BY_CATEGORY:
        cat_words = set(cat_key.replace("(", "").replace(")", "").split()) - {"of", "the", "a", "an", "and", "or", "with"}

        # Exact category-in-item or item-in-category (whole word boundary)
        # Only count if ALL words of the shorter string are in the longer
        if cat_words and cat_words.issubset(item_words_all):
            # All category words found in item — great match
            # Score by how specific the match is (more cat words = better)
            score = 0.95 * (len(cat_words) / max(len(item_words_all), 1))
            # Bonus for matching more words
            score = max(score, 0.7 + 0.1 * len(cat_words))
            candidates.append((min(score, 0.99), cat_key))
            continue

        if item_words and item_words.issubset(cat_words):
            score = 0.85 * (len(item_words) / max(len(cat_words), 1))
            score = max(score, 0.6 + 0.1 * len(item_words))
            candidates.append((min(score, 0.95), cat_key))
            continue

        # Word overlap
        overlap = item_words & cat_words
        if overlap:
            overlap_ratio = len(overlap) / max(min(len(item_words), len(cat_words)), 1)
            # Penalize if there are non-overlapping content words on both sides
            penalty = 0
            extra_item = item_words - cat_words - trivial
            extra_cat = cat_words - item_words - trivial
            if extra_item and extra_cat:
                penalty = 0.15  # both sides have unmatched content words
            score = overlap_ratio * 0.8 - penalty
            if score > 0.3:
                candidates.append((score, cat_key))

    # 3. Brand name search as fallback
    if not candidates:
        for cat_key, entries in _BY_CATEGORY.items():
            for entry in entries:
                brand_lower = entry["brand"].lower()
                # Check if any significant item word appears in brand
                matches = sum(1 for w in item_words if w in brand_lower and len(w) > 3)
                if matches >= 1:
                    candidates.append((0.4, cat_key))
                    break

    if not candidates:
        return None

    # Pick highest scoring category
    candidates.sort(key=lambda x: x[0], reverse=True)
    return _BY_CATEGORY[candidates[0][1]]


def lookup(item_name: str, quality_priority: float = 0.5,
           preferred_store: str | None = None,
           preferred_organic: bool = True) -> dict | None:
    """
    Look up the best product for an ingredient given quality_priority (0–1).

    quality_priority maps to a target quality score:
      0.0 → Budget (0.2)
      0.5 → Standard (0.4)
      1.0 → Excellent (1.0)

    When preferred_organic is False, the target is capped at Standard (0.4)
    and premium/excellent entries are deprioritized.

    Returns the entry whose quality_score is closest to the target,
    filtered by preferred_store if given.

    Returns dict with: brand, price, quality, quality_score, store, category, meal
    or None if no match found.
    """
    entries = _find_category(item_name)
    if not entries:
        return None

    # Filter by store preference if given
    if preferred_store:
        store_lower = preferred_store.lower()
        filtered = [e for e in entries if e["store"] == store_lower or e["store"] == "both"]
        if filtered:
            entries = filtered

    # Target quality score
    if not preferred_organic:
        # Cap at Standard (0.4) — prefer budget/standard items
        target = 0.2 + (quality_priority * 0.2)  # 0.2 to 0.4
    else:
        target = 0.2 + (quality_priority * 0.8)  # 0.2 to 1.0

    # When not organic-preferred, try budget/standard items first
    if not preferred_organic:
        budget_entries = [e for e in entries if e["quality_score"] <= 0.4]
        if budget_entries:
            entries = budget_entries

    # Pick entry closest to target quality
    best = min(entries, key=lambda e: abs(e["quality_score"] - target))
    return best


def get_all_categories() -> list[str]:
    """Return all known category names."""
    return list(_BY_CATEGORY.keys())
