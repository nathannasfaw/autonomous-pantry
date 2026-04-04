"""
Reasoning trace logger.

Architecture note (Layer 6 - Action / cross-cutting):
  Every meaningful decision the agent makes is logged as a ReasoningTraceEntry.
  This makes the agent's behavior explainable: users and auditors can follow the
  chain of reasoning from intent → inventory check → conflict resolution → approval.

  Trace entries are embedded directly in the PurchaseProposal so the full
  reasoning chain travels with the proposal through every state transition.
"""

from app.models.common import TraceStep, TraceStatus
from app.models.proposal import ReasoningTraceEntry, PurchaseProposal


def log(
    proposal: PurchaseProposal,
    step: TraceStep,
    message: str,
    status: TraceStatus = TraceStatus.INFO,
) -> ReasoningTraceEntry:
    """Append a trace entry to the proposal and return it."""
    entry = ReasoningTraceEntry(step=step, status=status, message=message)
    proposal.reasoning_trace.append(entry)
    return entry


def trace_summary(proposal: PurchaseProposal) -> list[dict]:
    """Return a compact list of trace entries suitable for API responses."""
    return [
        {
            "step": e.step.value,
            "status": e.status.value,
            "message": e.message,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in proposal.reasoning_trace
    ]
