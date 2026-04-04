"""
Autonomous Pantry — Method B: Approval-Based Payment Flow
FastAPI application entrypoint.

Architecture overview (6 layers):
  1. Perception   → InventorySnapshot (CV output, mock in demo)
  2. Context      → ContextState (calendar, budget, schedule)
  3. Intent       → UserIntent (parsed from conversation)
  4. Meta-Reason  → PolicyEngine, substitution decisions, uncertainty handling
  5. Optimize     → InventoryDiff + pricing, substitution selection
  6. Action       → ProposalBuilder, ApprovalService, CheckoutService (this app)

Key invariant:
  The LLM/agent NEVER triggers checkout directly.
  Checkout is created ONLY after explicit user approval through this API.

Run locally:
  pip install -r requirements.txt
  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.proposals import router as proposals_router

app = FastAPI(
    title="Autonomous Pantry — Method B Payment Flow",
    description=(
        "Agentic kitchen inventory and grocery purchasing system. "
        "Demonstrates approval-based payment flow where the agent proposes, "
        "the policy gate evaluates, and the user approves before any checkout is created."
    ),
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(proposals_router)


@app.get("/", tags=["System"])
def root():
    return {
        "service": "autonomous-pantry",
        "method": "B — approval-based payment flow",
        "docs": "/docs",
        "health": "/health",
    }
