"""
Policy decision model.

Architecture note (Layer 4 - Meta-Reasoning / Layer 6 - Action):
  The PolicyDecision is the output of the policy engine, which acts as a
  supervisory gate between the agent's proposal and any checkout action.

  Key invariant: for Method B, approval_required is ALWAYS true.
  The policy engine may also block proposals outright (allowed=False) if they
  violate hard rules (over budget, restricted items, unknown merchant).
"""

from typing import List
from pydantic import BaseModel


class PolicyDecision(BaseModel):
    allowed: bool
    approval_required: bool
    reasons: List[str]
    violations: List[str] = []  # populated when allowed=False
