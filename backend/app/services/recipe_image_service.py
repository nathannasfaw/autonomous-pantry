"""
Helpers for filling in missing recipe images from the recipe source page.
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

META_PATTERNS = [
    re.compile(
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
        re.IGNORECASE,
    ),
]


def populate_recipe_image(recipe: dict) -> dict:
    """
    Fill recipe["image_url"] from its source page when the recipe payload does
    not already include a usable image.
    """
    if not recipe:
        return recipe

    existing = str(recipe.get("image_url", "")).strip()
    if existing:
        return recipe

    source_url = str(recipe.get("source_url", "")).strip()
    if not source_url:
        return recipe

    fallback_url = extract_page_image(source_url)
    if fallback_url:
        recipe["image_url"] = fallback_url
        logger.info("Resolved fallback recipe image from source page: %s", fallback_url)
    else:
        logger.info("No fallback recipe image found for source page: %s", source_url)

    return recipe


def extract_page_image(source_url: str) -> str:
    """
    Fetch the recipe page and try common metadata tags used for social previews.
    """
    try:
        request = Request(
            source_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ""
            html_text = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Recipe image fallback fetch failed for %s: %s", source_url, exc)
        return ""

    for pattern in META_PATTERNS:
        match = pattern.search(html_text)
        if match:
            candidate = html.unescape(match.group(1).strip())
            if candidate:
                return urljoin(source_url, candidate)

    return ""
