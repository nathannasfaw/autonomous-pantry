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
import re
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
_FIELDS = "product_name,brands,quantity,_id,categories_tags"
_TIMEOUT = 8  # seconds
_IGNORE_QUERY_WORDS = {"organic", "fresh", "dried", "plain", "natural", "pure"}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


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

    query_tokens = _tokenize(query)
    core_query_words = {word for word in query_tokens if word not in _IGNORE_QUERY_WORDS}
    if not core_query_words:
        core_query_words = set(query_tokens)

    best_score = float("-inf")
    best = None

    for product in products:
        name = product.get("product_name") or ""
        has_qty = bool(product.get("quantity", "").strip())
        has_brand = bool(product.get("brands", "").strip())

        name_words = set(_tokenize(name))
        overlap = core_query_words & name_words
        if not overlap:
            continue

        overlap_ratio = len(overlap) / max(1, len(core_query_words))
        precision_ratio = len(overlap) / max(1, len(name_words))

        score = overlap_ratio * 4.0
        score += precision_ratio * 3.0
        score += 1.0 if has_qty else 0.0
        score += 0.5 if has_brand else 0.0

        if overlap == core_query_words:
            score += 2.0

        if score > best_score:
            best_score = score
            best = product

    if best is None:
        return None

    best_name_words = set(_tokenize(best.get("product_name") or ""))
    best_overlap = core_query_words & best_name_words
    best_overlap_ratio = len(best_overlap) / max(1, len(core_query_words))
    best_precision_ratio = len(best_overlap) / max(1, len(best_name_words))

    if best_overlap_ratio < 0.6:
        return None
    if len(core_query_words) == 1 and best_precision_ratio < 0.34:
        return None
    if len(core_query_words) >= 2 and best_precision_ratio < 0.25:
        return None
    return best
