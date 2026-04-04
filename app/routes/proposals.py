"""
Proposal routes — the primary API surface for Method B payment flow.

All four endpoints map to the approval-based flow:
  POST   /proposals/create               → build + policy-gate a new proposal
  GET    /proposals/{id}                 → inspect proposal state
  POST   /proposals/{id}/approve         → user approves → checkout created
  POST   /proposals/{id}/reject          → user rejects
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.mock_data import (
    MOCK_CONTEXT,
    MOCK_INTENT,
    MOCK_INVENTORY,
    MOCK_MERCHANT,
    MOCK_PRICING,
    MOCK_RATIONALE,
    MOCK_RECIPE_REQUIREMENTS,
    MOCK_SUBSTITUTIONS,
)
from app.services.approval_service import (
    approve,
    get_proposal_or_404,
    mark_checkout_created,
    reject,
)
from app.services.checkout_service import create_checkout_session
from app.services.proposal_builder import build_proposal
from app.services.repositories import proposal_repo
from app.services.trace_logger import trace_summary

router = APIRouter(prefix="/proposals", tags=["Proposals"])


# ─── Response models ─────────────────────────────────────────────────────────

class CreateProposalResponse(BaseModel):
    proposal: Any
    policy_decision: Any
    reasoning_trace: list


class ApproveProposalResponse(BaseModel):
    proposal: Any
    checkout_session: Any
    reasoning_trace: list


class RejectProposalResponse(BaseModel):
    proposal: Any
    reasoning_trace: list


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/create", response_model=CreateProposalResponse, status_code=201)
def create_proposal():
    """
    Build a purchase proposal from mock inventory + mock recipe intent.

    Flow:
      1. Load mock intent, context, inventory, recipe requirements
      2. Run inventory diff (with substitutions)
      3. Evaluate policy
      4. If allowed → status = approval_required, saved to memory
      5. Return proposal + policy decision + reasoning trace
    """
    proposal, policy = build_proposal(
        intent=MOCK_INTENT,
        context=MOCK_CONTEXT,
        snapshot=MOCK_INVENTORY,
        requirements=MOCK_RECIPE_REQUIREMENTS,
        pricing=MOCK_PRICING,
        merchant=MOCK_MERCHANT,
        rationale=MOCK_RATIONALE,
        substitutions=MOCK_SUBSTITUTIONS,
    )

    if not policy.allowed:
        # Save the blocked proposal for audit purposes but return 422
        proposal_repo.save(proposal)
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Proposal blocked by policy engine.",
                "violations": policy.violations,
                "proposal_id": proposal.id,
            },
        )

    proposal_repo.save(proposal)

    return CreateProposalResponse(
        proposal=proposal.model_dump(),
        policy_decision=policy.model_dump(),
        reasoning_trace=trace_summary(proposal),
    )


@router.get("/{proposal_id}", response_model=dict)
def get_proposal(proposal_id: str):
    """Return the current state of a proposal including its reasoning trace."""
    proposal = get_proposal_or_404(proposal_id)
    return {
        "proposal": proposal.model_dump(),
        "reasoning_trace": trace_summary(proposal),
    }


@router.post("/{proposal_id}/approve", response_model=ApproveProposalResponse)
def approve_proposal(proposal_id: str):
    """
    Approve a proposal and create the mock checkout session.

    Flow:
      1. Fetch proposal — must be in APPROVAL_REQUIRED status
      2. Transition to APPROVED
      3. Create mock checkout session
      4. Transition to CHECKOUT_CREATED
      5. Return updated proposal + checkout session + trace
    """
    proposal = get_proposal_or_404(proposal_id)

    # Step 1–2: User approval transition
    proposal = approve(proposal)

    # Step 3: Create checkout session (only possible after approval)
    session = create_checkout_session(proposal)

    # Step 4: Mark checkout created on proposal
    proposal = mark_checkout_created(proposal, session.checkout_session_id)

    return ApproveProposalResponse(
        proposal=proposal.model_dump(),
        checkout_session=session.model_dump(),
        reasoning_trace=trace_summary(proposal),
    )


@router.post("/{proposal_id}/reject", response_model=RejectProposalResponse)
def reject_proposal(proposal_id: str):
    """
    Reject a proposal. No checkout will be created.

    Flow:
      1. Fetch proposal — must be in APPROVAL_REQUIRED status
      2. Transition to REJECTED
      3. Log trace entry
      4. Return updated proposal + trace
    """
    proposal = get_proposal_or_404(proposal_id)
    proposal = reject(proposal)

    return RejectProposalResponse(
        proposal=proposal.model_dump(),
        reasoning_trace=trace_summary(proposal),
    )
