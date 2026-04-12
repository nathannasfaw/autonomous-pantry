"""
Chat routes: /chat/start and /chat/message
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.session import (
    ChatRequest,
    ChatResponse,
    PreferencesUpdate,
    StartSessionRequest,
    StartSessionResponse,
)
from app.services import (
    gap_analysis,
    instacart_stub,
    llm_service,
    nn_service,
    recipe_image_service,
    session_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=StartSessionResponse)
async def start_chat(request: StartSessionRequest | None = None):
    """Create a new conversation session."""
    client_id = request.client_id if request else None
    session_id = session_manager.create_session(client_id=client_id)
    return StartSessionResponse(conversation_id=session_id)


@router.post("/preferences")
async def update_preferences(request: PreferencesUpdate):
    """Update user preferences for an existing session."""
    session = session_manager.get_session(request.conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session["preferences"].update(request.preferences)
    return {"status": "ok", "preferences": session["preferences"]}


@router.get("/preferences/{conversation_id}")
async def get_preferences(conversation_id: str):
    """Get current preferences for a session."""
    session = session_manager.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["preferences"]


class SummarizeRequest(BaseModel):
    messages: list[dict]


@router.post("/summarize-title")
async def summarize_title(request: SummarizeRequest):
    """Generate a short conversation title from message history."""
    # Build a compact transcript from the first few messages
    transcript = ""
    for msg in request.messages[:6]:  # Only use first 6 messages max
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if text:
            transcript += f"{role}: {text[:200]}\n"

    if not transcript.strip():
        return {"title": "New Chat"}

    try:
        title = llm_service.generate_title(transcript)
        return {"title": title}
    except Exception as e:
        logger.warning("Title generation failed: %s", e)
        # Fallback to first user message
        first_user = next((m.get("text", "") for m in request.messages if m.get("role") == "user"), "New Chat")
        return {"title": first_user[:40] + ("…" if len(first_user) > 40 else "")}


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Process a user message within an existing session."""
    session = session_manager.get_session(request.conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    user_message = request.message.strip()

    # Append user message to history
    session["messages"].append({"role": "user", "content": user_message})

    stage = session["stage"]
    order_confirmed = False
    order_details = None
    agent_message = ""

    # -----------------------------------------------------------------------
    # IDLE stage: find a recipe, compute gaps, run NN, narrate cart
    # -----------------------------------------------------------------------
    if stage == "idle":
        if not llm_service.is_explicit_recipe_request(user_message):
            agent_message = (
                "I can help with pantry questions, or suggest meals when you ask for a "
                "recipe or meal idea. Try `what can I make with my pantry?` or "
                "`find me a pasta recipe`."
            )
            session["messages"].append({"role": "assistant", "content": agent_message})
            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                recipe=None,
                cart=None,
                stage=session["stage"],
            )

        agent_message, recipe_result = await _handle_idle(session, user_message)

        session["messages"].append({"role": "assistant", "content": agent_message})

        # Options presented or error — no recipe/cart yet, stay idle
        if recipe_result.get("status") in ("error", "options_presented") or session["recipe"] is None:
            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                recipe=None,
                cart=None,
                stage=session["stage"],
            )

        return ChatResponse(
            conversation_id=request.conversation_id,
            message=agent_message,
            recipe=session["recipe"],
            cart=session["current_cart"],
            stage=session["stage"],
        )

    # -----------------------------------------------------------------------
    # CART_PROPOSED / NEGOTIATING stage: conversation loop
    # -----------------------------------------------------------------------
    elif stage in ("cart_proposed", "negotiating"):
        result = llm_service.call_llm_conversation(
            stage=session["stage"],
            current_cart=session["current_cart"],
            recipe=session["recipe"],
            preferences=session["preferences"],
            budget=session["preferences"].get("budget_per_order", 80.0),
            messages=session["messages"],
        )

        intent = result.get("intent", "unclear")
        agent_message = result.get("message", "")

        if intent == "reset":
            new_intent = result.get("new_intent", "")
            session_manager.reset_cart(session)

            # Re-run idle flow with new intent
            reset_message = new_intent if new_intent else user_message
            # Replace last user message with new intent
            session["messages"].append({"role": "user", "content": reset_message})
            agent_message, _ = await _handle_idle(session, reset_message)

        elif intent == "modify":
            cart_diff = result.get("cart_diff", [])
            session_manager.apply_cart_diff(session, cart_diff)

            # Budget validation (check subtotal against budget, not tax/delivery)
            cart_subtotal = _compute_cart_subtotal(session["current_cart"])
            budget = session["preferences"].get("budget_per_order", 80.0)
            if cart_subtotal > budget:
                agent_message += f"\n\nHeads up: your item subtotal is ${cart_subtotal:.2f}, which is over your ${budget:.2f} budget."

            session["stage"] = "negotiating"

        elif intent == "confirm":
            order_details = instacart_stub.place_order(session["current_cart"])
            session["stage"] = "confirmed"
            order_confirmed = True

        elif intent == "cancel":
            session["stage"] = "cancelled"

        elif intent in ("question", "unclear"):
            # No cart changes, keep current stage
            pass

        session["messages"].append({"role": "assistant", "content": agent_message})
        return ChatResponse(
            conversation_id=request.conversation_id,
            message=agent_message,
            recipe=session.get("recipe"),
            cart=session["current_cart"] if session["current_cart"] else None,
            stage=session["stage"],
            order_confirmed=order_confirmed,
            order_details=order_details,
        )

    # -----------------------------------------------------------------------
    # CONFIRMED / CANCELLED: terminal stages
    # -----------------------------------------------------------------------
    elif stage == "confirmed":
        agent_message = "Your order has already been confirmed! Start a new conversation to order again."
        session["messages"].append({"role": "assistant", "content": agent_message})
        return ChatResponse(
            conversation_id=request.conversation_id,
            message=agent_message,
            recipe=session.get("recipe"),
            cart=session["current_cart"] if session["current_cart"] else None,
            stage=session["stage"],
            order_confirmed=True,
        )

    elif stage == "cancelled":
        agent_message = "Your order was cancelled. Start a new conversation to try again."
        session["messages"].append({"role": "assistant", "content": agent_message})
        return ChatResponse(
            conversation_id=request.conversation_id,
            message=agent_message,
            stage=session["stage"],
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown session stage: {stage}")


async def _handle_idle(session: dict, user_message: str) -> tuple[str, dict]:
    """
    Handle idle stage: LLM Call 1 → gap analysis → NN → LLM Call 2.
    Returns (agent_message, recipe_result_dict).
    Mutates session in place.
    """
    # LLM Call 1: recipe discovery (may return options or a full recipe)
    recipe_result = llm_service.call_llm_recipe(
        user_message=user_message,
        calendar=session["calendar_context"],
        preferences=session["preferences"],
        messages=session["messages"],
        pantry=session["pantry_state"],
    )

    status = recipe_result.get("status")
    normalized_query = recipe_result.get("normalized_query", user_message.strip())
    logger.info(
        "Idle recipe flow: normalized=%r status=%s pantry_items=%d",
        normalized_query,
        status,
        len(session["pantry_state"]),
    )

    if status in ("error", "recipe_lookup_failed", "not_recipe_request"):
        session["stage"] = "idle"
        return recipe_result.get("message", "I had trouble with that. Please try again."), recipe_result

    # Options presented — stay idle so next message picks a specific dish
    if status == "options_presented":
        agent_message = recipe_result.get("message", "Here are some options! Which would you like?")
        return agent_message, recipe_result

    if recipe_result.get("recipe") is None:
        session["stage"] = "idle"
        return recipe_result.get("message", "I had trouble finding a recipe. Please try again."), recipe_result

    recipe = recipe_result["recipe"]
    recipe = recipe_image_service.populate_recipe_image(recipe)
    session["recipe"] = recipe
    session["full_ingredient_list"] = recipe.get("ingredients", [])
    logger.info(
        "Recipe selected: normalized=%r name=%r ingredients=%d image=%r",
        normalized_query,
        recipe.get("name"),
        len(session["full_ingredient_list"]),
        recipe.get("image_url", ""),
    )

    # Compute ingredient gaps
    gaps = gap_analysis.compute_gaps(
        recipe_ingredients=session["full_ingredient_list"],
        pantry=session["pantry_state"],
    )
    session["ingredient_gaps"] = gaps
    logger.info(
        "Gap analysis complete: normalized=%r gaps=%d matched_pantry=%d",
        normalized_query,
        len(gaps),
        max(0, len(session["full_ingredient_list"]) - len(gaps)),
    )

    # Run NN recommendations
    nn_recs, staples_assumed = nn_service.recommend(
        ingredient_gaps=gaps,
        calendar=session["calendar_context"],
        preferences=session["preferences"],
    )

    session["nn_original_cart"] = list(nn_recs)  # immutable reference
    session["current_cart"] = [dict(item) for item in nn_recs]  # mutable working copy
    session["staples_assumed"] = staples_assumed
    logger.info(
        "NN recommendation result: normalized=%r cart_items=%d staples=%d",
        normalized_query,
        len(nn_recs),
        len(staples_assumed),
    )

    # LLM Call 2: narrate cart
    cart_total = _compute_cart_total(nn_recs)
    narration = llm_service.call_llm_cart_narration(
        recipe=recipe,
        pantry=session["pantry_state"],
        gaps=gaps,
        nn_recommendations=nn_recs,
        preferences=session["preferences"],
        budget=session["preferences"].get("budget_per_order", 80.0),
        cart_total=cart_total,
        staples_assumed=staples_assumed,
    )

    session["stage"] = "cart_proposed"
    agent_message = narration.get("message", recipe_result.get("message", "Here's what I found!"))
    return agent_message, recipe_result


GEORGIA_TAX_RATE = 0.04
DELIVERY_FEE = 4.99


def _compute_cart_subtotal(cart: list) -> float:
    """Sum of item prices only (no tax/delivery)."""
    return round(sum(item.get("estimated_price", 0) for item in cart), 2)


def _compute_cart_total(cart: list) -> float:
    """All-in total: subtotal + GA tax + delivery fee."""
    subtotal = _compute_cart_subtotal(cart)
    tax = round(subtotal * GEORGIA_TAX_RATE, 2)
    return round(subtotal + tax + DELIVERY_FEE, 2)
