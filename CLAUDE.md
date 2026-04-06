# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repo contains two separate FastAPI backends and one React frontend, all under `autonomous-pantry/`.

| Directory | Purpose |
|-----------|---------|
| `app/` | **Method B** — approval-gated proposal API (no LLM, pure policy/state-machine) |
| `backend/` | **Chat backend** — conversational grocery assistant (Claude + PyTorch NN) |
| `frontend/` | React/Vite chat UI, connects to `backend/` on port 8000 |

---

## Running the services

### Method B API (`app/`)
```bash
cd autonomous-pantry
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Interactive docs: http://localhost:8000/docs
```

### Chat backend (`backend/`)
```bash
cd autonomous-pantry/backend
pip install -r requirements.txt
# Create .env from .env.example and set ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd autonomous-pantry/frontend
npm install
npm run dev      # dev server on http://localhost:5173
npm run build    # production build
npm run preview  # preview production build
```

---

## Architecture

### Method B (`app/`) — 6-layer pipeline

The proposal flow runs through six conceptual layers (all mock data in `app/data/mock_data.py`):

1. **Perception** → `InventorySnapshot` (CV confidence scores per item)
2. **Context** → `ContextState` (budget, guest count, delivery window)
3. **Intent** → `UserIntent` (parsed dish goal)
4. **Meta-Reasoning** → `policy_engine.py` + substitution logic in `proposal_builder.py`
5. **Optimization** → `inventory_diff.py` (gap calculation, buffering, pricing)
6. **Action** → `approval_service.py` + `checkout_service.py`

**Key invariant:** `checkout_service.py` is called only from `approval_service.approve_proposal()`. The LLM/agent path never touches checkout directly.

Proposal state machine: `DRAFT → APPROVAL_REQUIRED → APPROVED → CHECKOUT_CREATED` (or `REJECTED`).

All state is in-memory via `repositories.py` (no database). The mock checkout in `checkout_service.py` is the integration point for real merchant APIs (Instacart Connect, Kroger, etc.).

### Chat backend (`backend/`) — LLM + NN pipeline

`backend/app/routes/chat.py` drives a session state machine with these stages: `idle → cart_proposed → negotiating → confirmed/cancelled`.

**Idle stage** runs a 3-step pipeline:
1. `llm_service.call_llm_recipe()` — Claude with `web_search_20250305` tool; returns recipe or dish options
2. `gap_analysis.compute_gaps()` — diffs recipe ingredients against pantry state
3. `nn_service.recommend()` — feedforward MLP (`GroceryMLP`, 50→64→32→1) scores each gap item; items scoring ≥ 0.5 go into the cart
4. `llm_service.call_llm_cart_narration()` — Claude narrates the NN-generated cart

**Negotiating stage** uses `llm_service.call_llm_conversation()` to detect intent (`modify/confirm/cancel/reset/question`) and applies `cart_diff` operations via `session_manager.apply_cart_diff()`.

The NN (`GroceryMLP`) trains on synthetic data at startup if no `nn_weights.pth` file is present; otherwise loads saved weights. Model input features include gap ratio, guest count, day-of-week (one-hot), cuisine score, budget ratio, dietary conflict flag, and inventory confidence.

LLM calls use `claude-haiku-4-5-20251001` with an agentic loop in `_run_agentic_loop()` that handles `tool_use` stop reasons (web search is server-side, so no manual tool result injection is needed).

### Frontend (`frontend/`)

Single-page React app. `ChatWindow.jsx` manages session state, calls `POST /chat/start` then `POST /chat/message`. `useChat.js` is the primary data-fetching hook. `CartCard.jsx` and `RecipeCard.jsx` render the structured data returned alongside chat messages.

---

## Environment

`backend/.env.example`:
```
ANTHROPIC_API_KEY=your_key_here
```

The chat backend CORS allows only `http://localhost:5173`. To change the allowed origin, update `backend/main.py`.
