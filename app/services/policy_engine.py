"""
Policy engine — the supervisory gate between proposal and checkout.

Architecture note (Layer 4 - Meta-Reasoning):
  The policy engine enforces hard rules that the agent cannot override:
    1. Total must be within budget
    2. Merchant must be on the allowed list
    3. No restricted items in the cart
    4. Low-confidence inventory readings require approval
    5. Method B ALWAYS requires explicit user approval (invariant)

  A proposal that fails any rule is blocked (allowed=False).
  A proposal that passes all rules is marked approval_required=True,
  meaning the user must explicitly confirm before checkout is created.

  The agent has NO path to checkout that bypasses this gate.
"""

from app.models.intent import ContextState
from app.models.policy import PolicyDecision
from app.models.proposal import PurchaseProposal
from app.services import trace_logger
from app.models.common import TraceStep, TraceStatus


LOW_CONFIDENCE_THRESHOLD = 0.70


def evaluate(proposal: PurchaseProposal, context: ContextState) -> PolicyDecision:
    """
    Run all policy rules against the proposal and return a PolicyDecision.
    Appends trace entries for each rule evaluated.
    """
    reasons: list[str] = []
    violations: list[str] = []

    # --- Rule 1: Budget check ---
    if proposal.estimated_total <= context.budget_limit:
        reasons.append(
            f"Within budget: ${proposal.estimated_total:.2f} <= ${context.budget_limit:.2f}"
        )
    else:
        violations.append(
            f"Exceeds budget: ${proposal.estimated_total:.2f} > ${context.budget_limit:.2f}"
        )

    # --- Rule 2: Merchant allowlist ---
    if proposal.merchant in context.allowed_merchants:
        reasons.append(f"Merchant '{proposal.merchant}' is on the allowed list")
    else:
        violations.append(
            f"Merchant '{proposal.merchant}' is not in allowed merchants: {context.allowed_merchants}"
        )

    # --- Rule 3: Restricted items check ---
    item_names = [item.name for item in proposal.missing_items]
    flagged = [name for name in item_names if name in context.restricted_items]
    if flagged:
        violations.append(f"Cart contains restricted items: {flagged}")
    else:
        reasons.append("No restricted items in cart")

    # --- Rule 4: Low-confidence inventory check ---
    low_conf_items = [
        item.name
        for item in proposal.missing_items
        if item.substituted_from is None  # already handled via substitution
    ]
    # We check the original snapshot confidence via the trace (already logged upstream).
    # Here we just add a generic note if any uncertainty was flagged during diff.
    uncertainty_entries = [
        e for e in proposal.reasoning_trace if e.step == TraceStep.UNCERTAINTY_DETECTED
    ]
    if uncertainty_entries:
        reasons.append(
            f"Low-confidence inventory detected ({len(uncertainty_entries)} item(s)) — approval enforced"
        )

    # --- Rule 5: Method B invariant — approval always required ---
    reasons.append("Method B: explicit user approval required before checkout")

    allowed = len(violations) == 0

    trace_logger.log(
        proposal,
        TraceStep.APPROVAL_REQUESTED if allowed else TraceStep.CONFLICT_RESOLVED,
        "Policy evaluation complete. "
        + (f"Proposal allowed. Awaiting approval." if allowed else f"Proposal BLOCKED: {'; '.join(violations)}"),
        TraceStatus.INFO if allowed else TraceStatus.ERROR,
    )

    return PolicyDecision(
        allowed=allowed,
        approval_required=True,   # Method B invariant: always True
        reasons=reasons,
        violations=violations,
    )
