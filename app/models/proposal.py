"""
Purchase proposal model.

Architecture note (Layer 6 - Action):
  A PurchaseProposal is the agent's concrete recommendation for what to buy.
  It is NOT a payment instruction — it is a structured proposal that must pass
  the policy gate and receive explicit user approval before any checkout is created.

  The reasoning_trace field makes the agent's decision explainable to the user,
  satisfying the transparency requirement for agentic purchasing systems.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from app.models.common import ProposalStatus, TraceStep, TraceStatus
from app.models.inventory import MissingIngredient


class ReasoningTraceEntry(BaseModel):
    """A single step in the agent's decision log."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    step: TraceStep
    status: TraceStatus
    message: str


class PurchaseProposal(BaseModel):
    """
    The full proposal produced by the agent after inventory diff, meta-reasoning,
    and optimization. Stored in memory until approved or rejected.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    recipe_name: str
    merchant: str
    missing_items: List[MissingIngredient]
    estimated_total: float
    delivery_window: str
    rationale: str
    reasoning_trace: List[ReasoningTraceEntry] = Field(default_factory=list)
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        """Update the updated_at timestamp on any state change."""
        self.updated_at = datetime.now(timezone.utc)
