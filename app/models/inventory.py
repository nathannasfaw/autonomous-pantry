"""
Inventory domain models.

Architecture note (Layer 1 - Perception):
  These models represent the structured output of the computer vision layer.
  confidence scores indicate how certain the system is about each item's count.
  Low confidence (< 0.70) triggers a warning in the meta-reasoning layer and
  forces approval even if the order would otherwise be auto-approvable.
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field


class InventoryItem(BaseModel):
    name: str
    count: float
    confidence: float = Field(ge=0.0, le=1.0, description="CV confidence score 0-1")
    unit: str = "unit"

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.70


class InventorySnapshot(BaseModel):
    inventory: Dict[str, InventoryItem]
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "computer_vision"


class RecipeRequirement(BaseModel):
    """A single ingredient requirement for a recipe."""
    name: str
    required_quantity: float
    unit: str = "unit"


class MissingIngredient(BaseModel):
    """
    Computed by the inventory diff service.
    Represents what must be purchased to fulfill the recipe.
    """
    name: str
    required_quantity: float
    available_quantity: float
    missing_quantity: float
    unit: str = "unit"
    estimated_price: float = 0.0
    substituted_from: Optional[str] = None  # e.g. "salmon" -> shrimp
    substitution_reason: Optional[str] = None
