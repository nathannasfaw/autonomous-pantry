"""
In-memory repositories for proposals and checkout sessions.

These are simple dict-backed stores. In production, replace with
a database (Postgres, DynamoDB, etc.) by swapping out these classes
while keeping the same interface.
"""

from typing import Dict, Optional
from app.models.proposal import PurchaseProposal
from app.models.checkout import CheckoutSession


class ProposalRepository:
    def __init__(self) -> None:
        self._store: Dict[str, PurchaseProposal] = {}

    def save(self, proposal: PurchaseProposal) -> PurchaseProposal:
        self._store[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str) -> Optional[PurchaseProposal]:
        return self._store.get(proposal_id)

    def all(self) -> list[PurchaseProposal]:
        return list(self._store.values())


class CheckoutRepository:
    def __init__(self) -> None:
        self._store: Dict[str, CheckoutSession] = {}

    def save(self, session: CheckoutSession) -> CheckoutSession:
        self._store[session.checkout_session_id] = session
        return session

    def get_by_proposal(self, proposal_id: str) -> Optional[CheckoutSession]:
        return next(
            (s for s in self._store.values() if s.proposal_id == proposal_id),
            None,
        )


# Module-level singletons — shared across all requests for the lifetime of the process.
proposal_repo = ProposalRepository()
checkout_repo = CheckoutRepository()
