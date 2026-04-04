"""
Demo seed data for the Autonomous Pantry demo narrative.

Scenario:
  "I want to make sushi tomorrow night for 5 people under $30."

  Pantry state (from CV):
    - rice:  1 bag,  confidence 61%  (uncertain — buffer applied)
    - eggs:  8,      confidence 96%
    - milk:  1,      confidence 88%

  Recipe requirements for sushi (5 servings):
    - shrimp, nori, rice, cucumber

  Meta-reasoning decisions:
    - salmon exceeds $30 budget → substitute shrimp
    - rice confidence is low → apply 0.7 buffer (treat as 0.7 available)

  Expected outcome:
    - rice is partially available but uncertain → small purchase needed
    - shrimp, nori, cucumber must be purchased
    - estimated total ≈ $24.50 (under $30 budget)
    - policy: allowed, approval_required = True
"""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from app.models.intent import UserIntent, ContextState
from app.models.inventory import InventoryItem, InventorySnapshot, RecipeRequirement


# ─── Layer 3: User Intent ────────────────────────────────────────────────────

MOCK_INTENT = UserIntent(
    dish="Sushi",
    date="tomorrow night",
    budget=30.00,
    servings=5,
    user_id="user_001",
)

# ─── Layer 2: Context ────────────────────────────────────────────────────────

MOCK_CONTEXT = ContextState(
    budget_limit=30.00,
    event_detected=True,
    guest_count=5,
    delivery_window="tomorrow 4pm-6pm",
    allowed_merchants=["Instacart", "Walmart", "Kroger"],
    restricted_items=[],
    preferred_merchant="Instacart",
)

# ─── Layer 1: Inventory Snapshot (from CV) ───────────────────────────────────

MOCK_INVENTORY = InventorySnapshot(
    captured_at=datetime.now(timezone.utc),
    source="computer_vision",
    inventory={
        "rice": InventoryItem(name="rice", count=1.0, confidence=0.61, unit="bag"),
        "eggs": InventoryItem(name="eggs", count=8.0, confidence=0.96, unit="unit"),
        "milk": InventoryItem(name="milk", count=1.0, confidence=0.88, unit="carton"),
    },
)

# ─── Recipe Requirements (5 servings sushi) ──────────────────────────────────

# Note: salmon is NOT in this list because meta-reasoning already substituted shrimp.
# The substitution is recorded in MOCK_SUBSTITUTIONS and applied during inventory diff.

MOCK_RECIPE_REQUIREMENTS: List[RecipeRequirement] = [
    RecipeRequirement(name="salmon", required_quantity=1.0, unit="lb"),  # will be substituted
    RecipeRequirement(name="nori",   required_quantity=5.0, unit="sheet"),
    RecipeRequirement(name="rice",   required_quantity=2.0, unit="bag"),
    RecipeRequirement(name="cucumber", required_quantity=2.0, unit="unit"),
]

# ─── Layer 4: Meta-Reasoning — Substitutions ─────────────────────────────────

# Format: { original_ingredient: (substitute, reason) }
MOCK_SUBSTITUTIONS: Dict[str, Tuple[str, str]] = {
    "salmon": (
        "shrimp",
        "Salmon ($18.99/lb) exceeds budget when combined with other items. "
        "Shrimp ($9.99/lb) satisfies recipe requirement at lower cost.",
    ),
}

# ─── Layer 5: Pricing (per unit/bag/sheet/lb) ────────────────────────────────

MOCK_PRICING: Dict[str, float] = {
    "shrimp":    9.99,    # per lb (substituted for salmon)
    "salmon":   18.99,    # per lb (rejected — over budget)
    "nori":      0.75,    # per sheet
    "rice":      3.49,    # per bag
    "cucumber":  1.29,    # per unit
    "eggs":      0.25,    # per unit
    "milk":      3.99,    # per carton
}

# ─── Proposal narrative ──────────────────────────────────────────────────────

MOCK_RATIONALE = (
    "Recipe: Sushi for 5 guests tomorrow night. "
    "Salmon was substituted with shrimp to stay within the $30 budget. "
    "Rice inventory confidence was low (61%), so a conservative available quantity was applied. "
    "All remaining ingredients must be purchased via Instacart."
)

MOCK_MERCHANT = "Instacart"
