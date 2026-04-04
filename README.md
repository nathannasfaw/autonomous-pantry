# Autonomous Pantry Method B: Approval-Based Payment Flow

An agentic kitchen inventory and grocery purchasing system that demonstrates
**approval-gated checkout**: the agent reasons and proposes, the user decides,
the backend acts.

---

## Quickstart

```bash
cd autonomous-pantry
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

---

## Architecture — 6 Layers

| Layer | Name | What it does |
|-------|------|-------------|
| 1 | **Perception** | CV detects pantry items with confidence scores |
| 2 | **Context** | Calendar, budget, guest count, schedule |
| 3 | **Intent** | Conversation parsed into structured dish goal |
| 4 | **Meta-Reasoning** | Feasibility, uncertainty, conflict, substitution |
| 5 | **Optimization** | Cheapest plan satisfying recipe + constraints |
| 6 | **Action** | Proposal → policy gate → approval → checkout ← **this app** |

### Method B invariant

> The agent **never** creates a checkout directly.
> Checkout is created **only** after explicit user approval.
> The policy engine is a hard gate that the agent cannot bypass.

---

## Demo Narrative

> "I want to make sushi tomorrow night for 5 people under $30."

1. System checks pantry — rice (61% confidence), eggs, milk present.
2. Detects missing: shrimp (subbed for salmon — over budget), nori, rice buffer, cucumber.
3. Meta-reasoning: rice confidence low → apply 70% buffer.
4. Meta-reasoning: salmon $18.99/lb exceeds budget → substitute shrimp $9.99/lb.
5. Proposal created, estimated total ~$24.50 (under $30).
6. Policy engine: allowed ✓, approval_required ✓ (Method B invariant).
7. Frontend shows proposal summary. User reviews.
8. User approves → backend creates mock Instacart checkout session.
9. Full reasoning trace logged throughout.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/proposals/create` | Build proposal from mock data |
| `GET`  | `/proposals/{id}` | Get proposal + trace |
| `POST` | `/proposals/{id}/approve` | Approve → create checkout |
| `POST` | `/proposals/{id}/reject` | Reject proposal |

---

## Sample curl Commands (demo flow)

### 1. Health check
```bash
curl http://localhost:8000/health
```

### 2. Create a purchase proposal
```bash
curl -s -X POST http://localhost:8000/proposals/create \
  -H "Content-Type: application/json" | python3 -m json.tool
```

Save the `id` field from the response as `PROPOSAL_ID`:
```bash
PROPOSAL_ID="<id from response>"
```

### 3. Inspect the proposal
```bash
curl -s http://localhost:8000/proposals/$PROPOSAL_ID | python3 -m json.tool
```

### 4a. Approve the proposal (creates mock checkout)
```bash
curl -s -X POST http://localhost:8000/proposals/$PROPOSAL_ID/approve \
  -H "Content-Type: application/json" | python3 -m json.tool
```

### 4b. Or reject the proposal
```bash
curl -s -X POST http://localhost:8000/proposals/$PROPOSAL_ID/reject \
  -H "Content-Type: application/json" | python3 -m json.tool
```

---

## Sample Request/Response

### POST /proposals/create → 201

```json
{
  "proposal": {
    "id": "a1b2c3d4-...",
    "user_id": "user_001",
    "recipe_name": "Sushi",
    "merchant": "Instacart",
    "missing_items": [
      {
        "name": "shrimp",
        "required_quantity": 1.0,
        "available_quantity": 0.0,
        "missing_quantity": 1.0,
        "unit": "lb",
        "estimated_price": 9.99,
        "substituted_from": "salmon",
        "substitution_reason": "Salmon ($18.99/lb) exceeds budget..."
      },
      {
        "name": "nori",
        "required_quantity": 5.0,
        "available_quantity": 0.0,
        "missing_quantity": 5.0,
        "unit": "sheet",
        "estimated_price": 3.75
      },
      {
        "name": "rice",
        "required_quantity": 2.0,
        "available_quantity": 0.7,
        "missing_quantity": 1.3,
        "unit": "bag",
        "estimated_price": 4.54
      },
      {
        "name": "cucumber",
        "required_quantity": 2.0,
        "available_quantity": 0.0,
        "missing_quantity": 2.0,
        "unit": "unit",
        "estimated_price": 2.58
      }
    ],
    "estimated_total": 20.86,
    "delivery_window": "tomorrow 4pm–6pm",
    "status": "approval_required"
  },
  "policy_decision": {
    "allowed": true,
    "approval_required": true,
    "reasons": [
      "Within budget: $20.86 ≤ $30.00",
      "Merchant 'Instacart' is on the allowed list",
      "No restricted items in cart",
      "Low-confidence inventory detected (1 item(s)) — approval enforced",
      "Method B: explicit user approval required before checkout"
    ],
    "violations": []
  },
  "reasoning_trace": [
    {"step": "intent_parsed",       "status": "info",    "message": "User intent parsed: 'Sushi' for 5 people on tomorrow night, budget $30.00."},
    {"step": "context_checked",     "status": "info",    "message": "Context loaded. Budget limit: $30.00. Event detected: 5 guests. Delivery: tomorrow 4pm–6pm."},
    {"step": "uncertainty_detected","status": "warning", "message": "rice inventory confidence is 61% — treating as uncertain, adding buffer."},
    {"step": "conflict_resolved",   "status": "info",    "message": "Substituted 'salmon' → 'shrimp': Salmon ($18.99/lb) exceeds budget..."},
    {"step": "inventory_assessed",  "status": "info",    "message": "Inventory diff complete. 4 item(s) need to be purchased."},
    {"step": "proposal_created",    "status": "success", "message": "Proposal created: 4 item(s) to purchase, estimated total $20.86."},
    {"step": "approval_requested",  "status": "info",    "message": "Policy evaluation complete. Proposal allowed. Awaiting approval."}
  ]
}
```

### POST /proposals/{id}/approve → 200

```json
{
  "proposal": {
    "id": "a1b2c3d4-...",
    "status": "checkout_created"
  },
  "checkout_session": {
    "checkout_session_id": "chk_f3a1b2c3",
    "proposal_id": "a1b2c3d4-...",
    "merchant": "Instacart",
    "checkout_url": "https://mock.instacart.local/checkout/a1b2c3d4-...",
    "status": "checkout_created",
    "estimated_total": 20.86
  },
  "reasoning_trace": [
    "...",
    {"step": "user_approved",    "status": "success", "message": "User explicitly approved the purchase proposal."},
    {"step": "checkout_created", "status": "success", "message": "Mock checkout session 'chk_f3a1b2c3' created with merchant 'Instacart'."}
  ]
}
```

---

## Proposal State Machine

```
DRAFT
  └─► APPROVAL_REQUIRED   ← policy gate passed, awaiting user
         ├─► APPROVED      ← user approves
         │      └─► CHECKOUT_CREATED  ← backend creates cart handoff
         │                └─► COMPLETED  (merchant confirms — future)
         └─► REJECTED      ← user declines, no checkout created
```

---

## Swapping in a Real Merchant (Instacart / other)

The mock checkout service is isolated in [app/services/checkout_service.py](app/services/checkout_service.py).
To replace it with a real integration:

1. **Instacart Connect API**: Replace `create_checkout_session()` with a call to
   `POST /fulfillment/orders` using the Instacart Connect API.
   Map each `MissingIngredient` to an Instacart `line_item` with `product_id` and `quantity`.

2. **Kroger / Walmart**: Similar pattern — create a cart via their respective cart APIs,
   receive a cart/checkout URL, return it as `checkout_url`.

3. **Auth**: Store API keys / OAuth tokens in environment variables (`INSTACART_API_KEY`, etc.).
   Load via `os.getenv()` or a settings model using `pydantic-settings`.

4. **Error handling**: Catch merchant API errors and raise `HTTPException(502)` so
   the proposal status does not advance to `checkout_created` on failure.

5. **Idempotency**: On retry, check `checkout_repo.get_by_proposal(proposal_id)` first
   and return the existing session rather than creating a duplicate.

---

## File Structure

```
autonomous-pantry/
  app/
    main.py                        ← FastAPI app + router registration
    models/
      common.py                    ← ProposalStatus, TraceStep enums
      inventory.py                 ← InventoryItem, InventorySnapshot, MissingIngredient
      intent.py                    ← UserIntent, ContextState
      proposal.py                  ← PurchaseProposal, ReasoningTraceEntry
      policy.py                    ← PolicyDecision
      checkout.py                  ← CheckoutSession
    services/
      repositories.py              ← In-memory stores
      trace_logger.py              ← Append trace entries to proposal
      inventory_diff.py            ← Compute missing ingredients
      proposal_builder.py          ← Orchestrate full proposal creation
      policy_engine.py             ← Evaluate hard rules, always require approval
      approval_service.py          ← State transitions: approve / reject / checkout
      checkout_service.py          ← Mock checkout session creation
    routes/
      health.py                    ← GET /health
      proposals.py                 ← POST/GET /proposals/*
    data/
      mock_data.py                 ← Seed data for demo narrative
  requirements.txt
  README.md
```
