"""
Neural network service: feedforward MLP that scores grocery items for purchase.
Trains on synthetic data and saves/loads weights from nn_weights.pth.
"""

import os
import random
import math
import logging

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from app.data import pricing_db

logger = logging.getLogger(__name__)

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "nn_weights.pth")

INPUT_SIZE = 50
HIDDEN1 = 64
HIDDEN2 = 32
OUTPUT_SIZE = 1  # single score per item

# ---------------------------------------------------------------------------
# Zero-cost staples: items most kitchens already have. Filtered from cart
# but reported back so the LLM can mention them in the response text.
# ---------------------------------------------------------------------------
ZERO_COST_STAPLES = {
    "water", "ice", "tap water", "cold water", "warm water", "hot water",
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


def _get_price(item_name: str, quantity: float = 1.0, unit: str = "",
               quality_priority: float = 0.5,
               preferred_organic: bool = True) -> tuple[float, str | None, str | None]:
    """
    Category-aware price estimation using the pricing spreadsheet.
    Returns (price, brand, store) tuple.
    brand/store are None when using hardcoded fallback.
    """
    normalized = item_name.lower().strip()
    unit_lower = unit.lower().strip()

    # Zero-cost staples
    if normalized in ZERO_COST_STAPLES:
        return 0.00, None, None

    # Spices & dried herbs: price by measured quantity (not in spreadsheet)
    if _is_spice(normalized, unit_lower):
        if unit_lower in ("pinch", "dash", "to taste", "sprinkle"):
            return round(0.05 * max(quantity, 1), 2), None, None
        elif unit_lower in ("tsp", "teaspoon", "teaspoons"):
            return round(SPICE_PRICE_PER_TSP * quantity, 2), None, None
        elif unit_lower in ("tbsp", "tablespoon", "tablespoons"):
            return round(SPICE_PRICE_PER_TSP * 3 * quantity, 2), None, None
        else:
            return 3.99, None, None

    # Try spreadsheet lookup first
    db_result = pricing_db.lookup(item_name, quality_priority=quality_priority,
                                  preferred_organic=preferred_organic)
    if db_result:
        return db_result["price"], db_result["brand"], db_result["store"]

    # Baking basics: cheap per recipe quantity
    if normalized in BAKING_BASICS:
        price_per = BAKING_PRICE_PER_UNIT.get(unit_lower, 0.35)
        return round(price_per * quantity, 2), None, None

    # Hardcoded fallback: exact match
    if normalized in PRICE_PER_ITEM:
        return PRICE_PER_ITEM[normalized], None, None

    # Partial match
    for key, price in PRICE_PER_ITEM.items():
        if key in normalized or normalized in key:
            return price, None, None

    # Category fallback based on unit
    if unit_lower in ("lb", "lbs", "pound", "pounds"):
        return round(4.99 * quantity, 2), None, None
    elif unit_lower in ("oz", "ounce", "ounces"):
        return round(0.50 * quantity, 2), None, None
    elif unit_lower in ("cup", "cups"):
        return round(1.50 * quantity, 2), None, None
    elif unit_lower in SMALL_UNITS:
        return round(0.25 * quantity, 2), None, None

    # Final fallback
    return 2.99, None, None


def recommend(ingredient_gaps: list, calendar: dict, preferences: dict) -> tuple[list[dict], list[str]]:
    """
    Score each ingredient gap with the NN and return items with score >= 0.5,
    sorted by score descending. Zero-cost staples are separated out.

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
    budget = float(preferences.get("budget_per_order", 80.0))
    disliked = [d.lower() for d in preferences.get("disliked_ingredients", [])]
    quality_priority = float(preferences.get("quality_priority", 0.5))
    preferred_organic = bool(preferences.get("preferred_organic", True))

    tonight_guests = int(calendar.get("tonight_guests", 2))
    events = calendar.get("events_this_week", [])

    # Derive cuisine score: average cuisine weight across events
    cuisine_scores = list(cuisine_weights.values())
    avg_cuisine_score = sum(cuisine_scores) / len(cuisine_scores) if cuisine_scores else 0.5

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

            # Check dietary conflict
            item_lower = item_name.lower()
            dietary_conflict = False
            for flag in dietary_flags:
                # "no shellfish" → check if item contains shellfish keywords
                flag_ingredient = flag.replace("no ", "").strip()
                if flag_ingredient in item_lower:
                    dietary_conflict = True
                    break
            if any(d in item_lower for d in disliked):
                dietary_conflict = True

            estimated_price, brand, store = _get_price(
                item_name, gap_qty, unit, quality_priority=quality_priority,
                preferred_organic=preferred_organic,
            )
            budget_remaining_ratio = max(0.0, (budget - estimated_spend) / budget) if budget > 0 else 0.0

            # Historical reorder: simulate with a fixed seed based on item name
            historical_reorder = (hash(item_name) % 3) == 0

            # Confidence: use pantry confidence if available (gap items may carry it)
            confidence = float(gap_item.get("confidence", 0.8))

            features = _build_feature_vector(
                gap_ratio=gap_ratio,
                guest_count=tonight_guests,
                day_of_week=day_of_week,
                cuisine_score=avg_cuisine_score,
                budget_remaining_ratio=budget_remaining_ratio,
                dietary_conflict=dietary_conflict,
                confidence=confidence,
                historical_reorder=historical_reorder,
            )

            feature_tensor = torch.tensor([features], dtype=torch.float32)
            score = float(_model(feature_tensor).squeeze().item())

            if score >= 0.5:
                entry = {
                    "item": item_name,
                    "quantity": round(gap_qty, 2),
                    "unit": unit,
                    "score": round(score, 4),
                    "estimated_price": estimated_price,
                }
                if brand:
                    entry["brand"] = brand
                entry["store"] = store if store else "both"
                results.append(entry)
                estimated_spend += estimated_price

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, staples_assumed
