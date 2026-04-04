"""
Approval service — manages proposal state transitions.

Architecture note (Layer 6 - Action):
  This service is the control boundary between the agent and checkout.
  Only this service can advance a proposal from APPROVAL_REQUIRED → APPROVED.
  The agent cannot trigger checkout; only a human approval through this service can.

  Valid transitions:
    APPROVAL_REQUIRED → APPROVED  (user approves)
    APPROVAL_REQUIRED → REJECTED  (user rejects)
    APPROVED → CHECKOUT_CREATED   (backend creates checkout after approval)
    CHECKOUT_CREATED → COMPLETED  (merchant confirms order — out of scope for demo)
"""

from fastapi import HTTPException

from app.models.common import ProposalStatus, TraceStep, TraceStatus
from app.models.proposal import PurchaseProposal
from app.services import trace_logger
from app.services.repositories import proposal_repo


def get_proposal_or_404(proposal_id: str) -> PurchaseProposal:
    proposal = proposal_repo.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal '{proposal_id}' not found.")
    return proposal


def approve(proposal: PurchaseProposal) -> PurchaseProposal:
    """Transition proposal from APPROVAL_REQUIRED → APPROVED."""
    if proposal.status != ProposalStatus.APPROVAL_REQUIRED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve proposal in status '{proposal.status}'. "
                   f"Expected '{ProposalStatus.APPROVAL_REQUIRED}'.",
        )

    proposal.status = ProposalStatus.APPROVED
    trace_logger.log(
        proposal,
        TraceStep.USER_APPROVED,
        "User explicitly approved the purchase proposal.",
        TraceStatus.SUCCESS,
    )
    proposal.touch()
    proposal_repo.save(proposal)
    return proposal


def reject(proposal: PurchaseProposal) -> PurchaseProposal:
    """Transition proposal from APPROVAL_REQUIRED → REJECTED."""
    if proposal.status != ProposalStatus.APPROVAL_REQUIRED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject proposal in status '{proposal.status}'. "
                   f"Expected '{ProposalStatus.APPROVAL_REQUIRED}'.",
        )

    proposal.status = ProposalStatus.REJECTED
    trace_logger.log(
        proposal,
        TraceStep.USER_REJECTED,
        "User rejected the purchase proposal. No checkout will be created.",
        TraceStatus.INFO,
    )
    proposal.touch()
    proposal_repo.save(proposal)
    return proposal


def mark_checkout_created(proposal: PurchaseProposal, checkout_session_id: str) -> PurchaseProposal:
    """
    Transition proposal from APPROVED → CHECKOUT_CREATED.
    Called internally by the checkout service after generating the session.
    """
    if proposal.status != ProposalStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot create checkout for proposal in status '{proposal.status}'. "
                   f"Expected '{ProposalStatus.APPROVED}'.",
        )

    proposal.status = ProposalStatus.CHECKOUT_CREATED
    trace_logger.log(
        proposal,
        TraceStep.CHECKOUT_CREATED,
        f"Mock checkout session '{checkout_session_id}' created with merchant '{proposal.merchant}'. "
        f"User can now complete purchase at the merchant checkout URL.",
        TraceStatus.SUCCESS,
    )
    proposal.touch()
    proposal_repo.save(proposal)
    return proposal
