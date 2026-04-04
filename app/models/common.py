"""
Common enums and base types shared across the domain.

Architecture note: these enums represent the lifecycle states of a purchase proposal
in the Method B (approval-based) payment flow. The state machine is:
  draft -> approval_required -> approved -> checkout_created -> completed
                             -> rejected
"""

from enum import Enum


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHECKOUT_CREATED = "checkout_created"
    COMPLETED = "completed"


class TraceStep(str, Enum):
    INTENT_PARSED = "intent_parsed"
    CONTEXT_CHECKED = "context_checked"
    INVENTORY_ASSESSED = "inventory_assessed"
    UNCERTAINTY_DETECTED = "uncertainty_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    PROPOSAL_CREATED = "proposal_created"
    APPROVAL_REQUESTED = "approval_requested"
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    CHECKOUT_CREATED = "checkout_created"


class TraceStatus(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
