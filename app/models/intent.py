"""
User intent and context models.

Architecture note (Layer 2 - Context / Layer 3 - Intent):
  UserIntent is the structured output of the conversational interface.
  The agent parses natural language ("make sushi for 5 people tomorrow under $30")
  into this structured form before any planning logic runs.

  ContextState captures ambient facts (calendar, budget, schedule) that the
  meta-reasoning layer uses to evaluate feasibility and flag conflicts.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class UserIntent(BaseModel):
    """Structured representation of what the user wants to cook."""
    dish: str
    date: str                           # human-readable, e.g. "tomorrow night"
    budget: float = Field(gt=0)
    servings: int = Field(gt=0)
    user_id: str = "user_001"


class ContextState(BaseModel):
    """
    Ambient context gathered from calendar, preferences, and schedule.
    Used by meta-reasoning to detect events, conflicts, or budget pressure.
    """
    budget_limit: float
    event_detected: bool = False
    guest_count: int = 1
    delivery_window: str = "standard"
    allowed_merchants: List[str] = Field(default_factory=lambda: ["Instacart", "Walmart", "Kroger"])
    restricted_items: List[str] = Field(default_factory=list)
    preferred_merchant: Optional[str] = "Instacart"
