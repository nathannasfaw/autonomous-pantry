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

logger = logging.getLogger(__name__)

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "nn_weights.pth")

INPUT_SIZE = 50
HIDDEN1 = 64
HIDDEN2 = 32
OUTPUT_SIZE = 1  # single score per item

# Price lookup for common grocery items
PRICE_LOOKUP = {
    "salmon": 18.00,
    "tuna": 12.00,
    "shrimp": 14.00,
    "chicken breast": 8.00,
    "chicken thigh": 6.00,
    "ground beef": 7.00,
    "steak": 20.00,
    "pork chops": 9.00,
    "tofu": 4.00,
    "tempeh": 5.00,
    "sushi rice": 6.00,
    "rice": 4.00,
    "pasta": 3.00,
    "noodles": 3.00,
    "bread": 4.00,
    "flour": 3.00,
    "soy sauce": 4.00,
    "sesame oil": 6.00,
    "olive oil": 9.00,
    "vegetable oil": 5.00,
    "butter": 5.00,
    "cream cheese": 4.00,
    "mozzarella": 6.00,
    "parmesan": 7.00,
    "cheddar": 5.00,
    "nori": 5.00,
    "seaweed": 4.00,
    "avocado": 2.00,
    "cucumber": 2.00,
    "tomato": 2.00,
    "onion": 2.00,
    "garlic": 3.00,
    "ginger": 3.00,
    "lemon": 1.00,
    "lime": 1.00,
    "eggs": 5.00,
    "milk": 4.00,
    "heavy cream": 5.00,
    "yogurt": 5.00,
    "wasabi": 4.00,
    "pickled ginger": 4.00,
    "rice vinegar": 4.00,
    "mirin": 6.00,
    "sake": 8.00,
    "dashi": 5.00,
    "miso paste": 6.00,
    "panko breadcrumbs": 4.00,
    "cornstarch": 3.00,
    "sugar": 3.00,
    "salt": 2.00,
    "black pepper": 3.00,
    "red pepper flakes": 3.00,
    "basil": 3.00,
    "oregano": 3.00,
    "thyme": 3.00,
    "rosemary": 3.00,
    "cilantro": 2.00,
    "green onion": 2.00,
    "scallion": 2.00,
    "mushrooms": 4.00,
    "spinach": 3.00,
    "broccoli": 3.00,
    "bell pepper": 2.00,
    "jalapeño": 1.00,
    "serrano pepper": 1.00,
    "black beans": 3.00,
    "kidney beans": 3.00,
    "chickpeas": 3.00,
    "lentils": 4.00,
    "vegetable broth": 4.00,
    "chicken broth": 4.00,
    "coconut milk": 3.00,
    "tomato sauce": 3.00,
    "tomato paste": 2.00,
    "canned tomatoes": 3.00,
    "pizza dough": 5.00,
    "tortillas": 4.00,
    "sour cream": 4.00,
    "salsa": 4.00,
    "guacamole": 5.00,
    "cheese": 5.00,
    "fish sauce": 5.00,
    "oyster sauce": 5.00,
    "hoisin sauce": 5.00,
    "teriyaki sauce": 5.00,
}

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


def _get_price(item_name: str) -> float:
    """Look up estimated price for an item."""
    normalized = item_name.lower().strip()
    if normalized in PRICE_LOOKUP:
        return PRICE_LOOKUP[normalized]
    # Partial match
    for key, price in PRICE_LOOKUP.items():
        if key in normalized or normalized in key:
            return price
    return 5.00


def recommend(ingredient_gaps: list, calendar: dict, preferences: dict) -> list[dict]:
    """
    Score each ingredient gap with the NN and return items with score >= 0.5,
    sorted by score descending.

    Returns: [{"item": str, "quantity": float, "unit": str, "score": float, "estimated_price": float}]
    """
    global _model
    if _model is None:
        initialize_nn()

    dietary_flags = [f.lower() for f in preferences.get("dietary_flags", [])]
    cuisine_weights = preferences.get("cuisine_weights", {})
    budget = float(preferences.get("budget_per_order", 80.0))
    disliked = [d.lower() for d in preferences.get("disliked_ingredients", [])]

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

    _model.eval()
    with torch.no_grad():
        for gap_item in ingredient_gaps:
            item_name = gap_item.get("item", "")
            required = float(gap_item.get("required", 1.0))
            available = float(gap_item.get("available", 0.0))
            unit = gap_item.get("unit", "")
            gap_qty = float(gap_item.get("gap", required - available))

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

            estimated_price = _get_price(item_name)
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
                results.append({
                    "item": item_name,
                    "quantity": round(gap_qty, 2),
                    "unit": unit,
                    "score": round(score, 4),
                    "estimated_price": estimated_price,
                })
                estimated_spend += estimated_price * gap_qty

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
