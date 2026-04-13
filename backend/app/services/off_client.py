"""
Thin Open Food Facts search client.

Design principles
-----------------
* Uses stdlib urllib only — no new dependencies.
* Never raises — network/parse failures return an empty list.
* Caller is responsible for caching; this module makes no cache decisions.
* Rate-limit safety is enforced by the caller (product_resolver) which only
  calls this module on a cache miss, and persists the result so it never
  calls again for the same ingredient.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
_FIELDS = "product_name,brands,quantity,_id,categories_tags"
_TIMEOUT = 8  # seconds


def search_product(query: str, max_results: int = 5) -> list[dict]:
    """
    Search Open Food Facts for query. Returns up to max_results raw product dicts.
    Returns [] on any error (network, timeout, bad JSON, etc.).
    """
    params = urllib.parse.urlencode({
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": max_results,
        "fields": _FIELDS,
    })
    url = f"{_SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        products = data.get("products", [])
        logger.debug("OFF search %r → %d results", query, len(products))
        return products
    except Exception as exc:
        logger.warning("OFF search failed for %r: %s", query, exc)
        return []


def pick_best_candidate(products: list[dict], query: str) -> dict | None:
    """
    Score and return the best product from an OFF search result list.
    Returns None if the list is empty or no candidate scores above zero.

    Scoring (higher = better):
      +2  product_name contains all query words
      +1  product_name contains at least one query word
      +1  quantity field is present and non-empty
      +0.5 brands field is present and non-empty
    """
    if not products:
        return None

    query_words = set(query.lower().split())
    best_score = -1
    best = None

    for product in products:
        name = (product.get("product_name") or "").lower()
        has_qty = bool(product.get("quantity", "").strip())
        has_brand = bool(product.get("brands", "").strip())

        name_words = set(name.split())
        if query_words and query_words.issubset(name_words):
            name_score = 2
        elif query_words & name_words:
            name_score = 1
        else:
            name_score = 0

        score = name_score + (1 if has_qty else 0) + (0.5 if has_brand else 0)
        if score > best_score:
            best_score = score
            best = product

    return best if best_score > 0 else None
