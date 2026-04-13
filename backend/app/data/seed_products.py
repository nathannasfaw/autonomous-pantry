"""
Pre-seeded product catalogue for common grocery ingredients.

Called once at startup via seed_common_ingredients(). Uses bulk_put() which
skips any record already in the cache, so this is safe to run every startup.

Each record must include:
  ingredient_key  — normalized lookup key (lowercase, stripped)
  product_name    — human-readable label
  package_amount  — size of the smallest purchasable unit
  package_unit    — unit for package_amount
  estimated_price — what you'd pay for one package
  source          — always 'seeded' here
  confidence      — always 1.0 for seeded records
"""

from __future__ import annotations

import logging
from app.services import product_cache

logger = logging.getLogger(__name__)

SEED_CATALOGUE: list[dict] = [
    # ------------------------------------------------------------------
    # Baking & leavening
    # ------------------------------------------------------------------
    {"ingredient_key": "yeast",            "product_name": "Active Dry Yeast",         "brand": "Fleischmann's", "package_amount": 2.25,  "package_unit": "tsp",   "estimated_price": 0.75},
    {"ingredient_key": "active dry yeast", "product_name": "Active Dry Yeast",         "brand": "Fleischmann's", "package_amount": 2.25,  "package_unit": "tsp",   "estimated_price": 0.75},
    {"ingredient_key": "instant yeast",    "product_name": "Instant Yeast",            "brand": "Fleischmann's", "package_amount": 2.25,  "package_unit": "tsp",   "estimated_price": 0.75},
    {"ingredient_key": "flour",            "product_name": "All-Purpose Flour",        "brand": "King Arthur",   "package_amount": 5.0,   "package_unit": "lb",    "estimated_price": 4.49},
    {"ingredient_key": "all-purpose flour","product_name": "All-Purpose Flour",        "brand": "King Arthur",   "package_amount": 5.0,   "package_unit": "lb",    "estimated_price": 4.49},
    {"ingredient_key": "all purpose flour","product_name": "All-Purpose Flour",        "brand": "King Arthur",   "package_amount": 5.0,   "package_unit": "lb",    "estimated_price": 4.49},
    {"ingredient_key": "bread flour",      "product_name": "Bread Flour",              "brand": "King Arthur",   "package_amount": 5.0,   "package_unit": "lb",    "estimated_price": 5.49},
    {"ingredient_key": "whole wheat flour","product_name": "Whole Wheat Flour",        "brand": "King Arthur",   "package_amount": 5.0,   "package_unit": "lb",    "estimated_price": 5.49},
    {"ingredient_key": "sugar",            "product_name": "Granulated White Sugar",   "brand": "Domino",        "package_amount": 4.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "granulated sugar", "product_name": "Granulated White Sugar",   "brand": "Domino",        "package_amount": 4.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "white sugar",      "product_name": "Granulated White Sugar",   "brand": "Domino",        "package_amount": 4.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "caster sugar",     "product_name": "Granulated White Sugar",   "brand": "Domino",        "package_amount": 4.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "brown sugar",      "product_name": "Light Brown Sugar",        "brand": "Domino",        "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 2.99},
    {"ingredient_key": "powdered sugar",   "product_name": "Confectioners Sugar",      "brand": "Domino",        "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 2.79},
    {"ingredient_key": "confectioners sugar","product_name": "Confectioners Sugar",    "brand": "Domino",        "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 2.79},
    {"ingredient_key": "icing sugar",      "product_name": "Confectioners Sugar",      "brand": "Domino",        "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 2.79},
    {"ingredient_key": "baking soda",      "product_name": "Baking Soda",             "brand": "Arm & Hammer",  "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 1.29},
    {"ingredient_key": "baking powder",    "product_name": "Baking Powder",           "brand": "Clabber Girl",  "package_amount": 8.1,   "package_unit": "oz",    "estimated_price": 2.49},
    {"ingredient_key": "salt",             "product_name": "Iodized Table Salt",       "brand": "Morton",        "package_amount": 26.0,  "package_unit": "oz",    "estimated_price": 1.49},
    {"ingredient_key": "table salt",       "product_name": "Iodized Table Salt",       "brand": "Morton",        "package_amount": 26.0,  "package_unit": "oz",    "estimated_price": 1.49},
    {"ingredient_key": "kosher salt",      "product_name": "Kosher Salt",              "brand": "Morton",        "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 2.49},
    {"ingredient_key": "sea salt",         "product_name": "Sea Salt",                 "brand": "Morton",        "package_amount": 17.6,  "package_unit": "oz",    "estimated_price": 2.99},
    {"ingredient_key": "fine sea salt",    "product_name": "Sea Salt",                 "brand": "Morton",        "package_amount": 17.6,  "package_unit": "oz",    "estimated_price": 2.99},
    {"ingredient_key": "coarse salt",      "product_name": "Kosher Salt",              "brand": "Morton",        "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 2.49},
    {"ingredient_key": "oregano",          "product_name": "Oregano Leaves",           "brand": "McCormick",     "package_amount": 0.75,  "package_unit": "oz",    "estimated_price": 3.49},
    {"ingredient_key": "vanilla extract",  "product_name": "Pure Vanilla Extract",     "brand": "McCormick",     "package_amount": 2.0,   "package_unit": "fl oz", "estimated_price": 5.49},
    {"ingredient_key": "vanilla",          "product_name": "Pure Vanilla Extract",     "brand": "McCormick",     "package_amount": 2.0,   "package_unit": "fl oz", "estimated_price": 5.49},
    {"ingredient_key": "cocoa powder",     "product_name": "Unsweetened Cocoa Powder", "brand": "Hershey's",     "package_amount": 8.0,   "package_unit": "oz",    "estimated_price": 3.99},
    {"ingredient_key": "cornstarch",       "product_name": "Cornstarch",              "brand": "Argo",           "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 2.49},

    # ------------------------------------------------------------------
    # Dairy & eggs
    # ------------------------------------------------------------------
    {"ingredient_key": "eggs",             "product_name": "Large Eggs",              "brand": None,            "package_amount": 12.0,  "package_unit": "count", "estimated_price": 4.49},
    {"ingredient_key": "egg",              "product_name": "Large Eggs",              "brand": None,            "package_amount": 12.0,  "package_unit": "count", "estimated_price": 4.49},
    {"ingredient_key": "milk",             "product_name": "Whole Milk",              "brand": None,            "package_amount": 64.0,  "package_unit": "fl oz", "estimated_price": 3.99},
    {"ingredient_key": "whole milk",       "product_name": "Whole Milk",              "brand": None,            "package_amount": 64.0,  "package_unit": "fl oz", "estimated_price": 3.99},
    {"ingredient_key": "butter",           "product_name": "Unsalted Butter",         "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 4.99},
    {"ingredient_key": "unsalted butter",  "product_name": "Unsalted Butter",         "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 4.99},
    {"ingredient_key": "heavy cream",      "product_name": "Heavy Whipping Cream",    "brand": None,            "package_amount": 16.0,  "package_unit": "fl oz", "estimated_price": 4.49},
    {"ingredient_key": "cream",            "product_name": "Heavy Whipping Cream",    "brand": None,            "package_amount": 16.0,  "package_unit": "fl oz", "estimated_price": 4.49},
    {"ingredient_key": "cream cheese",     "product_name": "Cream Cheese",            "brand": "Philadelphia",  "package_amount": 8.0,   "package_unit": "oz",    "estimated_price": 3.49},
    {"ingredient_key": "sour cream",       "product_name": "Sour Cream",              "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 2.99},
    {"ingredient_key": "yogurt",           "product_name": "Plain Greek Yogurt",      "brand": "Chobani",       "package_amount": 32.0,  "package_unit": "oz",    "estimated_price": 5.49},
    {"ingredient_key": "mozzarella",       "product_name": "Low-Moisture Mozzarella", "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 4.49},
    {"ingredient_key": "mozzarella cheese","product_name": "Low-Moisture Mozzarella", "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 4.49},
    {"ingredient_key": "parmesan",         "product_name": "Parmesan Cheese",         "brand": "Kraft",         "package_amount": 8.0,   "package_unit": "oz",    "estimated_price": 5.99},
    {"ingredient_key": "cheddar",          "product_name": "Sharp Cheddar Cheese",    "brand": None,            "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 4.49},
    {"ingredient_key": "ricotta",          "product_name": "Whole Milk Ricotta",      "brand": None,            "package_amount": 15.0,  "package_unit": "oz",    "estimated_price": 3.99},
    {"ingredient_key": "feta",             "product_name": "Feta Cheese",             "brand": None,            "package_amount": 6.0,   "package_unit": "oz",    "estimated_price": 3.99},

    # ------------------------------------------------------------------
    # Oils & fats
    # ------------------------------------------------------------------
    {"ingredient_key": "olive oil",              "product_name": "Extra Virgin Olive Oil", "brand": None, "package_amount": 16.9,  "package_unit": "fl oz", "estimated_price": 7.99},
    {"ingredient_key": "extra virgin olive oil", "product_name": "Extra Virgin Olive Oil", "brand": None, "package_amount": 16.9,  "package_unit": "fl oz", "estimated_price": 8.99},
    {"ingredient_key": "vegetable oil",          "product_name": "Vegetable Oil",          "brand": None, "package_amount": 48.0,  "package_unit": "fl oz", "estimated_price": 4.49},
    {"ingredient_key": "sesame oil",             "product_name": "Toasted Sesame Oil",     "brand": None, "package_amount": 8.0,   "package_unit": "fl oz", "estimated_price": 4.99},
    {"ingredient_key": "coconut oil",            "product_name": "Coconut Oil",            "brand": None, "package_amount": 14.0,  "package_unit": "oz",    "estimated_price": 6.99},

    # ------------------------------------------------------------------
    # Grains, pasta & starches
    # ------------------------------------------------------------------
    {"ingredient_key": "pasta",          "product_name": "Spaghetti",               "brand": "Barilla",  "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 1.99},
    {"ingredient_key": "spaghetti",      "product_name": "Spaghetti",               "brand": "Barilla",  "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 1.99},
    {"ingredient_key": "rice",           "product_name": "Long Grain White Rice",   "brand": None,       "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "white rice",     "product_name": "Long Grain White Rice",   "brand": None,       "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 3.49},
    {"ingredient_key": "sushi rice",     "product_name": "Japanese Short Grain Rice","brand": None,      "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 4.99},
    {"ingredient_key": "brown rice",     "product_name": "Brown Rice",              "brand": None,       "package_amount": 2.0,   "package_unit": "lb",    "estimated_price": 3.99},
    {"ingredient_key": "breadcrumbs",    "product_name": "Italian Breadcrumbs",     "brand": None,       "package_amount": 15.0,  "package_unit": "oz",    "estimated_price": 2.99},
    {"ingredient_key": "panko breadcrumbs","product_name": "Panko Breadcrumbs",     "brand": None,       "package_amount": 8.0,   "package_unit": "oz",    "estimated_price": 3.29},

    # ------------------------------------------------------------------
    # Proteins
    # ------------------------------------------------------------------
    {"ingredient_key": "chicken breast", "product_name": "Boneless Skinless Chicken Breast", "brand": None, "package_amount": 2.0, "package_unit": "lb", "estimated_price": 7.49},
    {"ingredient_key": "chicken",        "product_name": "Whole Chicken",                     "brand": None, "package_amount": 4.0, "package_unit": "lb", "estimated_price": 9.99},
    {"ingredient_key": "ground beef",    "product_name": "80/20 Ground Beef",                 "brand": None, "package_amount": 1.0, "package_unit": "lb", "estimated_price": 5.99},
    {"ingredient_key": "salmon",         "product_name": "Atlantic Salmon Fillet",            "brand": None, "package_amount": 1.0, "package_unit": "lb", "estimated_price": 12.99},
    {"ingredient_key": "shrimp",         "product_name": "Medium Shrimp",                     "brand": None, "package_amount": 1.0, "package_unit": "lb", "estimated_price": 10.99},
    {"ingredient_key": "tuna",           "product_name": "Chunk Light Tuna in Water",         "brand": None, "package_amount": 5.0, "package_unit": "oz", "estimated_price": 1.29},
    {"ingredient_key": "tofu",           "product_name": "Extra Firm Tofu",                   "brand": None, "package_amount": 14.0,"package_unit": "oz", "estimated_price": 2.99},
    {"ingredient_key": "bacon",          "product_name": "Thick Cut Bacon",                   "brand": None, "package_amount": 12.0,"package_unit": "oz", "estimated_price": 6.99},

    # ------------------------------------------------------------------
    # Produce
    # ------------------------------------------------------------------
    {"ingredient_key": "garlic",      "product_name": "Garlic Bulb",       "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.75},
    {"ingredient_key": "onion",       "product_name": "Yellow Onion",      "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.99},
    {"ingredient_key": "red onion",   "product_name": "Red Onion",         "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 1.29},
    {"ingredient_key": "tomato",      "product_name": "Beefsteak Tomato",  "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.99},
    {"ingredient_key": "tomatoes",    "product_name": "Roma Tomatoes",     "brand": None, "package_amount": 1.0,  "package_unit": "lb",    "estimated_price": 1.99},
    {"ingredient_key": "lemon",       "product_name": "Lemon",             "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.69},
    {"ingredient_key": "lime",        "product_name": "Lime",              "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.49},
    {"ingredient_key": "avocado",     "product_name": "Hass Avocado",      "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 1.50},
    {"ingredient_key": "bell pepper", "product_name": "Bell Pepper",       "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 1.29},
    {"ingredient_key": "spinach",     "product_name": "Baby Spinach",      "brand": None, "package_amount": 5.0,  "package_unit": "oz",    "estimated_price": 3.49},
    {"ingredient_key": "mushrooms",   "product_name": "White Button Mushrooms", "brand": None, "package_amount": 8.0, "package_unit": "oz", "estimated_price": 2.99},
    {"ingredient_key": "carrot",      "product_name": "Carrots",           "brand": None, "package_amount": 1.0,  "package_unit": "lb",    "estimated_price": 1.49},
    {"ingredient_key": "carrots",     "product_name": "Carrots",           "brand": None, "package_amount": 1.0,  "package_unit": "lb",    "estimated_price": 1.49},
    {"ingredient_key": "celery",      "product_name": "Celery Bunch",      "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 1.99},
    {"ingredient_key": "potato",      "product_name": "Russet Potato",     "brand": None, "package_amount": 5.0,  "package_unit": "lb",    "estimated_price": 3.99},
    {"ingredient_key": "sweet potato","product_name": "Sweet Potato",      "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 1.49},
    {"ingredient_key": "ginger",      "product_name": "Fresh Ginger Root", "brand": None, "package_amount": 0.25, "package_unit": "lb",    "estimated_price": 0.99},
    {"ingredient_key": "cilantro",    "product_name": "Fresh Cilantro",    "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 0.99},

    # ------------------------------------------------------------------
    # Canned & jarred
    # ------------------------------------------------------------------
    {"ingredient_key": "black beans",      "product_name": "Black Beans",          "brand": None,       "package_amount": 15.0,  "package_unit": "oz",    "estimated_price": 1.49},
    {"ingredient_key": "chickpeas",        "product_name": "Chickpeas / Garbanzo", "brand": None,       "package_amount": 15.0,  "package_unit": "oz",    "estimated_price": 1.49},
    {"ingredient_key": "lentils",          "product_name": "Green Lentils",        "brand": None,       "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 1.99},
    {"ingredient_key": "tomato sauce",     "product_name": "Tomato Sauce",         "brand": "Hunts",    "package_amount": 15.0,  "package_unit": "oz",    "estimated_price": 1.49},
    {"ingredient_key": "pizza sauce",      "product_name": "Pizza Sauce",          "brand": "Hunts",    "package_amount": 14.0,  "package_unit": "oz",    "estimated_price": 1.79},
    {"ingredient_key": "tomato paste",     "product_name": "Tomato Paste",         "brand": "Hunts",    "package_amount": 6.0,   "package_unit": "oz",    "estimated_price": 1.29},
    {"ingredient_key": "diced tomatoes",   "product_name": "Diced Tomatoes",       "brand": "Hunts",    "package_amount": 14.5,  "package_unit": "oz",    "estimated_price": 1.69},
    {"ingredient_key": "canned tomatoes",  "product_name": "Whole Peeled Tomatoes","brand": "Hunts",    "package_amount": 28.0,  "package_unit": "oz",    "estimated_price": 2.29},
    {"ingredient_key": "coconut milk",     "product_name": "Coconut Milk",         "brand": None,       "package_amount": 13.5,  "package_unit": "fl oz", "estimated_price": 2.29},
    {"ingredient_key": "vegetable broth",  "product_name": "Vegetable Broth",      "brand": None,       "package_amount": 32.0,  "package_unit": "fl oz", "estimated_price": 2.99},
    {"ingredient_key": "chicken broth",    "product_name": "Chicken Broth",        "brand": None,       "package_amount": 32.0,  "package_unit": "fl oz", "estimated_price": 2.99},

    # ------------------------------------------------------------------
    # Sauces & condiments
    # ------------------------------------------------------------------
    {"ingredient_key": "soy sauce",    "product_name": "Soy Sauce",          "brand": "Kikkoman",  "package_amount": 10.0,  "package_unit": "fl oz", "estimated_price": 3.49},
    {"ingredient_key": "fish sauce",   "product_name": "Fish Sauce",         "brand": None,        "package_amount": 6.76,  "package_unit": "fl oz", "estimated_price": 3.99},
    {"ingredient_key": "sriracha",     "product_name": "Sriracha Hot Sauce", "brand": "Huy Fong",  "package_amount": 17.0,  "package_unit": "fl oz", "estimated_price": 3.99},
    {"ingredient_key": "mirin",        "product_name": "Sweet Mirin",        "brand": None,        "package_amount": 10.0,  "package_unit": "fl oz", "estimated_price": 4.99},
    {"ingredient_key": "miso paste",   "product_name": "White Miso Paste",   "brand": None,        "package_amount": 17.6,  "package_unit": "oz",    "estimated_price": 4.99},
    {"ingredient_key": "rice vinegar", "product_name": "Rice Vinegar",       "brand": None,        "package_amount": 12.0,  "package_unit": "fl oz", "estimated_price": 2.99},
    {"ingredient_key": "honey",        "product_name": "Pure Honey",         "brand": None,        "package_amount": 12.0,  "package_unit": "oz",    "estimated_price": 4.99},
    {"ingredient_key": "maple syrup",  "product_name": "Pure Maple Syrup",   "brand": None,        "package_amount": 12.0,  "package_unit": "fl oz", "estimated_price": 8.99},
    {"ingredient_key": "tahini",       "product_name": "Tahini Sesame Paste","brand": None,        "package_amount": 16.0,  "package_unit": "oz",    "estimated_price": 5.49},
    {"ingredient_key": "hoisin sauce", "product_name": "Hoisin Sauce",       "brand": None,        "package_amount": 8.0,   "package_unit": "fl oz", "estimated_price": 3.99},
    {"ingredient_key": "oyster sauce", "product_name": "Oyster Sauce",       "brand": None,        "package_amount": 9.0,   "package_unit": "fl oz", "estimated_price": 3.99},

    # ------------------------------------------------------------------
    # Specialty
    # ------------------------------------------------------------------
    {"ingredient_key": "nori",         "product_name": "Roasted Seaweed Nori",  "brand": None, "package_amount": 10.0, "package_unit": "count", "estimated_price": 4.49},
    {"ingredient_key": "pizza dough",  "product_name": "Pizza Dough Ball",      "brand": None, "package_amount": 1.0,  "package_unit": "count", "estimated_price": 3.99},
    {"ingredient_key": "tortillas",    "product_name": "Flour Tortillas",        "brand": None, "package_amount": 10.0, "package_unit": "count", "estimated_price": 3.49},
    {"ingredient_key": "pita",         "product_name": "Pita Bread",             "brand": None, "package_amount": 6.0,  "package_unit": "count", "estimated_price": 3.49},
    {"ingredient_key": "bread",        "product_name": "Sandwich Bread",         "brand": None, "package_amount": 20.0, "package_unit": "count", "estimated_price": 3.49},
]

# Stamp all seeded records with common fields
for _rec in SEED_CATALOGUE:
    _rec.setdefault("search_terms", _rec["ingredient_key"])
    _rec.setdefault("off_product_id", None)
    _rec.setdefault("source", "seeded")
    _rec.setdefault("confidence", 1.0)


def seed_common_ingredients(db_path: str | None = None) -> int:
    """
    Insert all seeded records into the product cache (skips existing ones).
    Returns the number of new records inserted.
    """
    inserted = product_cache.bulk_put(SEED_CATALOGUE, db_path)
    if inserted:
        logger.info("Seeded %d product cache records", inserted)
    else:
        logger.debug("Product cache already seeded — no new records inserted")
    return inserted
