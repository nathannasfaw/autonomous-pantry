"""
Neural network service: feedforward MLP that scores grocery items for purchase.
Trains on synthetic data and saves/loads weights from nn_weights.pth.
"""

import os
import re
import random
import math
import logging

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "nn_weights.pth")

INPUT_SIZE = 50
HIDDEN1 = 64
HIDDEN2 = 32
OUTPUT_SIZE = 1  # single score per item

# ---------------------------------------------------------------------------
# Produce items: fresh fruits, vegetables, and herbs that should carry an
# "organic" prefix when the user has preferred_organic=True.
# ---------------------------------------------------------------------------
PRODUCE_KEYWORDS: set[str] = {
    # Vegetables
    "avocado", "cucumber", "tomato", "tomatoes", "onion", "red onion",
    "garlic", "ginger", "lemon", "lime", "cilantro", "parsley",
    "green onion", "scallion", "mushroom", "mushrooms", "spinach", "broccoli",
    "bell pepper", "jalapeño", "jalapeno", "serrano", "lettuce", "cabbage",
    "carrot", "carrots", "celery", "potato", "potatoes", "sweet potato",
    "corn", "zucchini", "eggplant", "kale", "arugula", "chard", "beet",
    "radish", "turnip", "squash", "pumpkin", "asparagus", "artichoke",
    "leek", "shallot", "fennel", "bok choy", "napa cabbage",
    "snap peas", "snow peas", "green beans", "edamame", "bean sprouts",
    # Fruits
    "apple", "banana", "orange", "strawberry", "blueberry", "raspberry",
    "peach", "pear", "mango", "pineapple", "watermelon", "grape",
    "cherry", "apricot", "plum", "pomegranate", "kiwi", "papaya",
    # Fresh herbs (not dried spices — those stay as-is)
    "basil", "mint", "dill", "chives", "thyme", "rosemary", "sage",
}


def _maybe_organic(item_name: str, prefer_organic: bool) -> str:
    """
    Return 'organic <item>' when the user prefers organic AND the item is produce.
    Avoids double-prefixing items already labelled 'organic'.
    """
    if not prefer_organic:
        return item_name
    normalized = item_name.lower().strip()
    if normalized.startswith("organic"):
        return item_name
    if any(kw in normalized for kw in PRODUCE_KEYWORDS):
        return f"organic {item_name}"
    return item_name


# ---------------------------------------------------------------------------
# Zero-cost staples: items most kitchens already have. Filtered from cart
# but reported back so the LLM can mention them in the response text.
# ---------------------------------------------------------------------------
ZERO_COST_STAPLES = {
    "water", "ice", "tap water", "cold water", "warm water", "lukewarm water", "hot water",
    "boiling water", "cooking spray", "nonstick spray", "nonstick cooking spray",
}

# ---------------------------------------------------------------------------
# Category-aware pricing engine
# ---------------------------------------------------------------------------
# Prices are per PURCHASE UNIT (the smallest package you'd buy at a store),
# not per recipe-quantity. _get_price returns the cost for the gap quantity.

# Per-item prices: what you'd pay for a single store package
PRICE_PER_ITEM = {
    # Proteins (per lb or typical package)
    "salmon": 12.99, "tuna": 10.99, "shrimp": 11.99,
    "chicken breast": 7.49, "chicken thigh": 5.49, "chicken": 6.49,
    "ground beef": 6.99, "steak": 14.99, "beef": 8.99,
    "pork chops": 7.99, "pork": 6.99, "bacon": 6.99, "sausage": 5.49,
    "tofu": 2.99, "tempeh": 3.99,
    # Grains & starches
    "sushi rice": 4.99, "rice": 3.49, "pasta": 1.99, "noodles": 2.49,
    "ramen noodles": 1.49, "bread": 3.49, "flour": 3.99,
    "pizza dough": 3.99, "tortillas": 3.49, "pita": 3.49,
    "panko breadcrumbs": 3.29, "breadcrumbs": 2.99, "cornstarch": 2.49,
    # Dairy & eggs
    "eggs": 4.49, "milk": 3.99, "heavy cream": 4.49, "cream": 4.49,
    "butter": 4.99, "cream cheese": 3.49, "sour cream": 2.99,
    "yogurt": 4.49, "mozzarella": 4.49, "parmesan": 5.99,
    "cheddar": 4.49, "cheese": 4.49,
    # Produce (per piece / bunch / lb)
    "avocado": 1.50, "cucumber": 0.99, "tomato": 0.99, "tomatoes": 1.99,
    "onion": 0.99, "red onion": 1.29, "garlic": 0.75, "ginger": 0.99,
    "lemon": 0.69, "lime": 0.49, "cilantro": 0.99, "parsley": 0.99,
    "green onion": 0.99, "scallion": 0.99, "mushrooms": 2.99,
    "spinach": 2.99, "broccoli": 2.49, "bell pepper": 1.29,
    "jalapeño": 0.49, "serrano pepper": 0.39, "lettuce": 1.99,
    "cabbage": 2.49, "carrot": 0.99, "carrots": 1.49, "celery": 1.99,
    "potato": 0.99, "potatoes": 3.49, "sweet potato": 1.49,
    "corn": 0.79, "zucchini": 1.29, "eggplant": 2.49,
    # Canned / jarred
    "black beans": 1.49, "kidney beans": 1.49, "chickpeas": 1.49,
    "lentils": 1.99, "canned tomatoes": 1.69, "diced tomatoes": 1.69,
    "tomato sauce": 1.49, "tomato paste": 1.29, "coconut milk": 2.29,
    "vegetable broth": 2.99, "chicken broth": 2.99, "beef broth": 2.99,
    # Sauces & condiments (per bottle)
    "soy sauce": 3.49, "fish sauce": 3.99, "oyster sauce": 3.99,
    "hoisin sauce": 3.99, "teriyaki sauce": 3.99, "sriracha": 3.99,
    "hot sauce": 2.99, "salsa": 3.49, "ketchup": 2.99, "mustard": 2.49,
    "mayonnaise": 3.99, "guacamole": 4.49, "tahini": 5.49,
    "rice vinegar": 2.99, "balsamic vinegar": 4.99, "vinegar": 2.49,
    "mirin": 4.99, "sake": 7.99, "dashi": 4.49, "miso paste": 4.99,
    "wasabi": 3.49, "pickled ginger": 3.49,
    # Oils & fats
    "olive oil": 7.99, "extra virgin olive oil": 8.99,
    "vegetable oil": 4.49, "sesame oil": 4.99, "coconut oil": 6.99,
    # Specialty / Asian
    "nori": 4.49, "seaweed": 3.99,
}

# Spices & dried herbs: these are cheap per recipe-quantity even though
# the jar costs a few dollars. Price is per tsp/tbsp used.
SPICE_KEYWORDS = {
    "salt", "pepper", "black pepper", "white pepper", "cayenne",
    "cumin", "paprika", "smoked paprika", "chili powder", "curry powder",
    "turmeric", "cinnamon", "nutmeg", "cloves", "allspice", "cardamom",
    "coriander", "fennel seed", "mustard seed", "celery seed",
    "oregano", "basil", "thyme", "rosemary", "dill", "bay leaf",
    "bay leaves", "sage", "tarragon", "marjoram", "italian seasoning",
    "garlic powder", "onion powder", "ginger powder",
    "red pepper flakes", "crushed red pepper", "chili flakes",
    "sesame seeds", "poppy seeds", "everything bagel seasoning",
    "five spice", "chinese five spice", "garam masala", "za'atar",
    "herbes de provence", "old bay", "tajin",
}
SPICE_PRICE_PER_TSP = 0.15  # ~$4 jar ÷ ~27 tsp

# Sugar & baking basics: cheap per recipe quantity
BAKING_BASICS = {"sugar", "brown sugar", "powdered sugar", "confectioners sugar",
                 "baking soda", "baking powder", "vanilla extract", "vanilla",
                 "yeast", "active dry yeast", "cocoa powder", "honey", "maple syrup"}
BAKING_PRICE_PER_UNIT = {"tsp": 0.10, "tbsp": 0.25, "cup": 0.60, "packet": 0.75}

# Units that indicate small/measured quantities (spice-scale)
SMALL_UNITS = {"tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon", "tablespoons",
               "pinch", "dash", "to taste", "sprinkle"}

# ---------------------------------------------------------------------------
# Dietary flag → ingredient keyword mapping.
#
# Each key is a dietary flag (lowercase) from the frontend.
# Each value is a set of ingredient keywords that conflict with that flag.
#
# Includes hidden/processed ingredients (surimi, gelatin, whey, anchovy paste,
# worcestershire, etc.) to reduce false negatives.
#
# Matching strategy (see _has_dietary_conflict):
#   - Single-word keywords → whole-word regex (\b...\b) to avoid "ham" matching "chamomile"
#   - Multi-word keywords  → phrase substring match
#   - Custom "no X" flags  → substring fallback (user-typed, may be partial)
# ---------------------------------------------------------------------------
DIETARY_CONFLICT_MAP: dict[str, set[str]] = {
    "vegan": {
        # Meats & poultry
        "meat", "beef", "pork", "chicken", "turkey", "lamb", "duck",
        "bison", "venison", "veal", "goat",
        # Processed meats
        "bacon", "ham", "sausage", "prosciutto", "lard", "pancetta",
        "pepperoni", "salami", "chorizo", "mortadella", "hot dog",
        # Seafood
        "shrimp", "salmon", "tuna", "cod", "fish", "seafood", "anchovy",
        "lobster", "crab", "clam", "oyster", "mussel", "scallop",
        "prawn", "squid", "octopus", "surimi",
        # Hidden seafood
        "fish sauce", "oyster sauce", "anchovy paste", "worcestershire",
        # Dairy
        "milk", "cheese", "butter", "cream", "yogurt", "mozzarella",
        "parmesan", "cheddar", "ricotta", "brie", "feta", "ghee",
        "whey", "casein", "lactose", "cream cheese", "half and half",
        "heavy cream", "sour cream",
        # Eggs & bee products
        "egg", "eggs", "honey", "beeswax", "albumen",
        # Animal-derived additives
        "gelatin", "lard", "rennet",
    },
    "vegetarian": {
        # Meats & poultry
        "meat", "beef", "pork", "chicken", "turkey", "lamb", "duck",
        "bison", "venison", "veal", "goat",
        # Processed meats
        "bacon", "ham", "sausage", "prosciutto", "lard", "pancetta",
        "pepperoni", "salami", "chorizo", "mortadella", "hot dog",
        # Seafood
        "shrimp", "salmon", "tuna", "cod", "fish", "seafood", "anchovy",
        "lobster", "crab", "clam", "oyster", "mussel", "scallop",
        "prawn", "squid", "octopus", "surimi",
        # Hidden seafood (common recipe ingredients)
        "fish sauce", "oyster sauce", "anchovy paste", "worcestershire",
        "dashi",  # traditional dashi contains fish flakes
    },
    "gluten-free": {
        # Direct gluten sources
        "bread", "pasta", "flour", "wheat", "barley", "rye", "spelt",
        "noodles", "breadcrumbs", "panko", "tortillas", "pita",
        "couscous", "semolina", "bulgur", "farro", "seitan",
        "udon", "ramen", "wonton", "dumpling wrapper", "malt",
        # Soy sauce contains wheat — flag it
        "soy sauce",
    },
    "dairy-free": {
        "milk", "cheese", "butter", "cream", "yogurt", "mozzarella",
        "parmesan", "cheddar", "ricotta", "brie", "feta", "ghee",
        "whey", "casein", "lactose", "cream cheese", "half and half",
        "heavy cream", "sour cream", "queso",
    },
    "no shellfish": {
        "shrimp", "lobster", "crab", "clam", "oyster", "mussel",
        "scallop", "prawn", "crawfish", "crayfish", "squid", "octopus",
        "abalone",
    },
    "no pork": {
        "pork", "bacon", "ham", "prosciutto", "lard", "pancetta",
        "sausage", "pepperoni", "salami", "chorizo", "mortadella",
        "pork belly", "pork chop", "pork loin", "pork rib",
    },
    "no red meat": {
        "beef", "pork", "lamb", "steak", "bison", "veal", "venison",
        "ground beef", "pork chop",
    },
    "nut-free": {
        "peanut", "almond", "walnut", "cashew", "pecan", "pistachio",
        "hazelnut", "macadamia", "pine nut", "tahini", "nut butter",
        "peanut butter", "almond flour", "almond milk",
    },
    "keto": {
        "bread", "pasta", "flour", "rice", "potato", "sugar", "tortillas",
        "noodles", "corn", "oats", "cereal", "honey", "maple syrup",
        "banana", "mango", "pineapple", "apple juice", "orange juice",
        "beans", "lentils", "chickpeas", "quinoa",
    },
    "low-carb": {
        "bread", "pasta", "rice", "potato", "tortillas", "noodles", "corn",
        "oats", "cereal", "beans", "lentils",
    },
    "halal": {
        "pork", "bacon", "ham", "lard", "pancetta", "gelatin",
        "wine", "beer", "alcohol",
    },
    "kosher": {
        "pork", "bacon", "ham", "shrimp", "lobster", "crab",
        "clam", "oyster", "mussel", "scallop",
    },
}


def _normalize_ingredient(name: str) -> str:
    """
    Prepare an ingredient name for dietary conflict matching.

    Strips parenthetical notes first so clarifications like
    '(for flax egg)' or '(optional)' don't contaminate the match —
    the ingredient is the text BEFORE the parenthesis.
    """
    # Remove all parenthetical content, e.g. "water (for flax egg)" → "water"
    name = re.sub(r"\([^)]*\)", "", name)
    return re.sub(r"[^a-z0-9 ]", " ", name.lower()).strip()


def _has_dietary_conflict(item_name: str, dietary_flags: list[str]) -> bool:
    """
    Check if an item conflicts with any dietary flag using DIETARY_CONFLICT_MAP.

    Matching rules:
    - Single-word keywords: whole-word regex (\b...\b) — prevents "ham" matching "chamomile"
    - Multi-word keywords: phrase substring — "fish sauce" in "fish sauce bottle"
    - Custom "no X" flags not in map: simple substring fallback
    """
    normalized = _normalize_ingredient(item_name)

    for flag in dietary_flags:
        conflict_keywords = DIETARY_CONFLICT_MAP.get(flag, set())
        for kw in conflict_keywords:
            kw_norm = _normalize_ingredient(kw)
            if " " in kw_norm:
                # Multi-word phrase: substring match
                if kw_norm in normalized:
                    return True
            else:
                # Single word: whole-word boundary match
                if re.search(r"\b" + re.escape(kw_norm) + r"\b", normalized):
                    return True

        # Fallback for custom "no X" flags (user-typed free text) not in the map
        if flag not in DIETARY_CONFLICT_MAP and flag.startswith("no "):
            ingredient = flag[3:].strip()
            if ingredient and ingredient in normalized:
                return True

    return False


def check_recipe_dietary_violations(recipe: dict, dietary_flags: list[str]) -> list[str]:
    """
    Post-generation validation: inspect every ingredient in a recipe dict
    and return the names of any that violate the user's hard dietary constraints.

    Args:
        recipe: recipe dict with an "ingredients" list of {"item": str, ...}
        dietary_flags: list of lowercase flag strings (e.g. ["vegan", "gluten-free"])

    Returns:
        List of violating ingredient names (empty = recipe is clean).
    """
    if not dietary_flags:
        return []
    violations = []
    for ing in recipe.get("ingredients", []):
        item_name = ing.get("item", "")
        if item_name and _has_dietary_conflict(item_name, dietary_flags):
            violations.append(item_name)
    return violations


_model = None


class GroceryMLP(nn.Module):
    """Feedforward MLP for grocery purchase scoring."""

    def __init__(self, input_size: int = INPUT_SIZE):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, HIDDEN1),
            nn.ReLU(),
            nn.Linear(HIDDEN1, HIDDEN2),
            nn.ReLU(),
            nn.Linear(HIDDEN2, OUTPUT_SIZE),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def _build_feature_vector(
    gap_ratio: float,
    guest_count: int,
    day_of_week: int,
    cuisine_score: float,
    budget_remaining_ratio: float,
    dietary_conflict: bool,
    confidence: float,
    historical_reorder: bool,
) -> list[float]:
    """
    Build a flat feature vector of length INPUT_SIZE (50).

    Slots:
      0      - gap_ratio (0..1)
      1      - guest_count normalized (/10)
      2-8    - day of week one-hot (7 values)
      9      - cuisine_score (0..1)
      10     - budget_remaining_ratio (0..1)
      11     - dietary_conflict (0 or 1)
      12     - confidence (0..1)
      13     - historical_reorder (0 or 1)
      14-49  - padding zeros (36 values)
    """
    features = [0.0] * INPUT_SIZE
    features[0] = float(max(0.0, min(1.0, gap_ratio)))
    features[1] = float(min(1.0, guest_count / 10.0))

    # One-hot day of week (0=Monday ... 6=Sunday)
    dow = max(0, min(6, day_of_week))
    features[2 + dow] = 1.0

    features[9] = float(max(0.0, min(1.0, cuisine_score)))
    features[10] = float(max(0.0, min(1.0, budget_remaining_ratio)))
    features[11] = 1.0 if dietary_conflict else 0.0
    features[12] = float(max(0.0, min(1.0, confidence)))
    features[13] = 1.0 if historical_reorder else 0.0
    # features[14:50] remain 0.0 (padding)
    return features


def generate_synthetic_data(n_samples: int = 500):
    """Generate synthetic training examples for the MLP."""
    X = []
    y = []

    for _ in range(n_samples):
        gap_ratio = random.uniform(0.0, 1.0)
        guest_count = random.randint(0, 10)
        day_of_week = random.randint(0, 6)
        cuisine_score = random.uniform(0.0, 1.0)
        budget_remaining_ratio = random.uniform(0.0, 1.0)
        dietary_conflict = random.random() < 0.2
        confidence = random.uniform(0.5, 1.0)
        historical_reorder = random.random() < 0.4

        features = _build_feature_vector(
            gap_ratio,
            guest_count,
            day_of_week,
            cuisine_score,
            budget_remaining_ratio,
            dietary_conflict,
            confidence,
            historical_reorder,
        )

        # Add Gaussian noise
        noisy_features = [f + random.gauss(0, 0.05) for f in features]
        X.append(noisy_features)

        # Label rules
        if dietary_conflict:
            label = 0.0
        elif gap_ratio > 0.5:
            label = 1.0
        elif gap_ratio > 0.2 and guest_count > 3:
            label = 1.0
        else:
            label = 0.3

        y.append(label)

    return X, y


def _train_model(model: GroceryMLP) -> None:
    """Train the model on synthetic data for 100 epochs."""
    logger.info("Generating synthetic training data...")
    X, y = generate_synthetic_data(500)

    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).unsqueeze(1)

    dataset = TensorDataset(X_tensor, y_tensor)
    loader = DataLoader(dataset, batch_size=32, shuffle=True)

    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()

    logger.info("Training NN for 100 epochs...")
    model.train()
    for epoch in range(100):
        total_loss = 0.0
        for batch_X, batch_y in loader:
            optimizer.zero_grad()
            preds = model(batch_X)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if (epoch + 1) % 20 == 0:
            avg_loss = total_loss / len(loader)
            logger.info(f"Epoch {epoch + 1}/100 — loss: {avg_loss:.4f}")

    logger.info("Training complete.")


def initialize_nn() -> None:
    """Load weights if available, otherwise train fresh and save."""
    global _model
    _model = GroceryMLP(input_size=INPUT_SIZE)

    if os.path.exists(WEIGHTS_PATH):
        logger.info(f"Loading NN weights from {WEIGHTS_PATH}")
        state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
        _model.load_state_dict(state)
        _model.eval()
        logger.info("NN weights loaded successfully.")
    else:
        logger.info("No weights file found — training from scratch.")
        _train_model(_model)
        torch.save(_model.state_dict(), WEIGHTS_PATH)
        logger.info(f"Weights saved to {WEIGHTS_PATH}")
        _model.eval()


def _is_staple(item_name: str) -> bool:
    """Check if an item is a zero-cost kitchen staple."""
    normalized = item_name.lower().strip()
    if "water" in normalized and any(
        word in normalized for word in ("water", "warm", "lukewarm", "hot", "cold", "tap", "boiling")
    ):
        return True
    return normalized in ZERO_COST_STAPLES


def _is_spice(item_name: str, unit: str) -> bool:
    """Check if an item is a spice/dried herb."""
    normalized = item_name.lower().strip()
    if normalized in SPICE_KEYWORDS:
        return True
    # Also treat anything in small-measure units with spice-like names
    if unit.lower() in SMALL_UNITS:
        for kw in SPICE_KEYWORDS:
            if kw in normalized or normalized in kw:
                return True
    return False


def _get_price(item_name: str, quantity: float = 1.0, unit: str = "") -> float:
    """
    Category-aware price estimation.
    Returns the total price for the given quantity, not per-unit.
    """
    normalized = item_name.lower().strip()
    unit_lower = unit.lower().strip()

    # Zero-cost staples
    if normalized in ZERO_COST_STAPLES:
        return 0.00

    # Spices & dried herbs: price by measured quantity
    if _is_spice(normalized, unit_lower):
        if unit_lower in ("pinch", "dash", "to taste", "sprinkle"):
            return round(0.05 * max(quantity, 1), 2)
        elif unit_lower in ("tsp", "teaspoon", "teaspoons"):
            return round(SPICE_PRICE_PER_TSP * quantity, 2)
        elif unit_lower in ("tbsp", "tablespoon", "tablespoons"):
            return round(SPICE_PRICE_PER_TSP * 3 * quantity, 2)  # 1 tbsp = 3 tsp
        else:
            # Whole jar / unspecified — return jar price
            return 3.99

    # Baking basics: cheap per recipe quantity
    if normalized in BAKING_BASICS:
        price_per = BAKING_PRICE_PER_UNIT.get(unit_lower, 0.35)
        return round(price_per * quantity, 2)

    # Exact match in price table
    if normalized in PRICE_PER_ITEM:
        return PRICE_PER_ITEM[normalized]

    # Partial match
    for key, price in PRICE_PER_ITEM.items():
        if key in normalized or normalized in key:
            return price

    # Category fallback based on unit
    if unit_lower in ("lb", "lbs", "pound", "pounds"):
        return round(4.99 * quantity, 2)  # generic per-lb
    elif unit_lower in ("oz", "ounce", "ounces"):
        return round(0.50 * quantity, 2)  # generic per-oz
    elif unit_lower in ("cup", "cups"):
        return round(1.50 * quantity, 2)
    elif unit_lower in SMALL_UNITS:
        return round(0.25 * quantity, 2)

    # Final fallback: modest generic price
    return 2.99


def recommend(
    ingredient_gaps: list,
    calendar: dict,
    preferences: dict,
    recipe_cuisine: str | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Score each ingredient gap with the NN and return items with score >= 0.5,
    sorted by score descending. Zero-cost staples are separated out.

    Args:
        ingredient_gaps: list of gap dicts from gap_analysis.compute_gaps()
        calendar: calendar context dict
        preferences: user preferences dict
        recipe_cuisine: cuisine type of the current recipe (e.g. "Japanese").
            When provided, the user's cuisine_weights[recipe_cuisine] is used
            directly as the NN cuisine_score feature, giving accurate per-recipe
            personalization. Falls back to the average weight if unrecognised.

    Returns:
        (cart_items, staples_assumed)
        cart_items: [{"item": str, "quantity": float, "unit": str, "score": float, "estimated_price": float}]
        staples_assumed: ["water", "salt", ...] — items assumed to be on hand
    """
    global _model
    if _model is None:
        initialize_nn()

    dietary_flags = [f.lower() for f in preferences.get("dietary_flags", [])]
    cuisine_weights = preferences.get("cuisine_weights", {})
    disliked = [d.lower() for d in preferences.get("disliked_ingredients", [])]
    prefer_organic = bool(preferences.get("preferred_organic", False))

    # Effective budget: the stricter of the total order cap and per-person × servings
    budget_per_order = float(preferences.get("budget_per_order", 80.0))
    budget_per_person = float(preferences.get("budget_per_person", 40.0))
    serving_size = int(preferences.get("serving_size", 2))
    budget = min(budget_per_order, budget_per_person * serving_size)

    tonight_guests = int(calendar.get("tonight_guests", 2))

    # Derive cuisine score:
    # If the recipe's cuisine type is known, look it up directly (case-insensitive).
    # This preserves the specificity of the user's cuisine preferences rather than
    # averaging them all into a single number.
    cuisine_score_values = list(cuisine_weights.values())
    avg_cuisine_score = (
        sum(cuisine_score_values) / len(cuisine_score_values)
        if cuisine_score_values else 0.5
    )
    if recipe_cuisine:
        recipe_cuisine_lower = recipe_cuisine.strip().lower()
        matched_weight = next(
            (v for k, v in cuisine_weights.items() if k.lower() == recipe_cuisine_lower),
            None,
        )
        cuisine_score = matched_weight if matched_weight is not None else avg_cuisine_score
        logger.debug(
            "Cuisine score for %r: %.2f (explicit=%s)",
            recipe_cuisine, cuisine_score, matched_weight is not None,
        )
    else:
        cuisine_score = avg_cuisine_score

    # Day of week: use today's weekday (0=Mon)
    import datetime
    day_of_week = datetime.datetime.now().weekday()

    estimated_spend = 0.0
    results = []
    staples_assumed = []

    _model.eval()
    with torch.no_grad():
        for gap_item in ingredient_gaps:
            item_name = gap_item.get("item", "")
            required = float(gap_item.get("required", 1.0))
            available = float(gap_item.get("available", 0.0))
            unit = gap_item.get("unit", "")
            gap_qty = float(gap_item.get("gap", required - available))

            # Filter zero-cost staples
            if _is_staple(item_name):
                staples_assumed.append(item_name)
                continue

            # Gap ratio: how much is missing relative to required
            gap_ratio = gap_qty / required if required > 0 else 1.0

            # Hard-skip items that conflict with dietary flags or disliked ingredients.
            # Dietary restrictions are non-negotiable constraints, not NN features.
            item_lower = item_name.lower()
            if _has_dietary_conflict(item_name, dietary_flags) or any(d in item_lower for d in disliked):
                continue

            dietary_conflict = False  # passed as NN feature; always False here after hard filter

            from app.services import product_resolver as _pr
            pricing = _pr.resolve_basket_pricing(item_name, gap_qty, unit)
            estimated_price = float(pricing["estimated_price"])
            budget_remaining_ratio = max(0.0, (budget - estimated_spend) / budget) if budget > 0 else 0.0

            # Historical reorder: simulate with a fixed seed based on item name
            historical_reorder = (hash(item_name) % 3) == 0

            # Confidence: use pantry confidence if available (gap items may carry it)
            confidence = float(gap_item.get("confidence", 0.8))

            features = _build_feature_vector(
                gap_ratio=gap_ratio,
                guest_count=tonight_guests,
                day_of_week=day_of_week,
                cuisine_score=cuisine_score,
                budget_remaining_ratio=budget_remaining_ratio,
                dietary_conflict=dietary_conflict,
                confidence=confidence,
                historical_reorder=historical_reorder,
            )

            feature_tensor = torch.tensor([features], dtype=torch.float32)
            score = float(_model(feature_tensor).squeeze().item())

            results.append({
                "item": _maybe_organic(item_name, prefer_organic),
                "brand": pricing["brand"],
                "product_name": pricing["product_name"],
                "quantity": round(gap_qty, 2),
                "unit": unit,
                "score": round(score, 4),
                "estimated_price": estimated_price,
                "pricing_source": pricing["pricing_source"],
                "fallback_reason": pricing["fallback_reason"],
                "package_amount": pricing["package_amount"],
                "package_unit": pricing["package_unit"],
                "package_price": pricing["package_price"],
                "packages_needed": pricing["packages_needed"],
                "required_amount": pricing["required_amount"],
                "required_unit": pricing["required_unit"],
            })
            estimated_spend += estimated_price

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, staples_assumed
