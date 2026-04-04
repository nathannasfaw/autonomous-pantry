"""
Proposal builder service.

Architecture note (Layer 6 - Action):
  Orchestrates the full proposal creation pipeline:
    1. Log intent parsing
    2. Log context check
    3. Run inventory diff (with substitutions)
    4. Compute estimated total
    5. Construct the PurchaseProposal with reasoning trace
    6. Run policy engine
    7. Set final status based on policy decision

  This is the entry point called by the POST /proposals/create endpoint.
  It does NOT create a checkout — that only happens after explicit approval.
"""

from typing import Dict, List, Tuple

from app.models.common import ProposalStatus, TraceStep, TraceStatus
from app.models.intent import UserIntent, ContextState
from app.models.inventory import InventorySnapshot, RecipeRequirement
from app.models.policy import PolicyDecision
from app.models.proposal import PurchaseProposal
from app.services import trace_logger
from app.services.inventory_diff import compute_missing
from app.services.policy_engine import evaluate


def build_proposal(
    intent: UserIntent,
    context: ContextState,
    snapshot: InventorySnapshot,
    requirements: List[RecipeRequirement],
    pricing: Dict[str, float],
    merchant: str,
    rationale: str,
    substitutions: Dict[str, Tuple[str, str]] | None = None,
) -> Tuple[PurchaseProposal, PolicyDecision]:
    """
    Build a PurchaseProposal from intent + context + inventory, then run policy.

    Returns:
        (proposal, policy_decision) tuple.
        The proposal status will be APPROVAL_REQUIRED if policy allows it,
        or DRAFT if blocked (with violations recorded in policy_decision).
    """
    # Construct shell proposal so trace entries can be attached from the start
    proposal = PurchaseProposal(
        user_id=intent.user_id,
        recipe_name=intent.dish,
        merchant=merchant,
        missing_items=[],
        estimated_total=0.0,
        delivery_window=context.delivery_window,
        rationale=rationale,
    )

    # Layer 3 — Intent trace
    trace_logger.log(
        proposal,
        TraceStep.INTENT_PARSED,
        f"User intent parsed: '{intent.dish}' for {intent.servings} people on {intent.date}, budget ${intent.budget:.2f}.",
        TraceStatus.INFO,
    )

    # Layer 2 — Context trace
    event_note = f"Event detected: {context.guest_count} guests." if context.event_detected else "No special event detected."
    trace_logger.log(
        proposal,
        TraceStep.CONTEXT_CHECKED,
        f"Context loaded. Budget limit: ${context.budget_limit:.2f}. {event_note} Delivery: {context.delivery_window}.",
        TraceStatus.INFO,
    )

    # Layer 1/5 — Inventory diff + substitution
    missing_items = compute_missing(
        snapshot=snapshot,
        requirements=requirements,
        pricing=pricing,
        substitutions=substitutions,
        proposal=proposal,
    )

    estimated_total = round(sum(item.estimated_price for item in missing_items), 2)

    # Populate the proposal with computed values
    proposal.missing_items = missing_items
    proposal.estimated_total = estimated_total

    trace_logger.log(
        proposal,
        TraceStep.PROPOSAL_CREATED,
        f"Proposal created: {len(missing_items)} item(s) to purchase, estimated total ${estimated_total:.2f}.",
        TraceStatus.SUCCESS,
    )

    # Layer 4 — Policy gate
    policy = evaluate(proposal, context)

    if policy.allowed:
        proposal.status = ProposalStatus.APPROVAL_REQUIRED
    # If not allowed, leave as DRAFT so the caller can communicate the violations

    proposal.touch()
    return proposal, policy
