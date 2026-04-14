"""
Chat routes: /chat/start and /chat/message
"""

import logging
import re

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
    """Update user preferences for an existing session and persist them."""
    session = session_manager.get_session(request.conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session["preferences"].update(request.preferences)
    # Persist so preferences survive backend restarts and new sessions
    client_id = session.get("client_id")
    if client_id:
        from app.services import pantry_store
        pantry_store.save_preferences(client_id, session["preferences"])
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
    # OPTIONS_PRESENTED stage: resolve option selection
    # -----------------------------------------------------------------------
    elif stage == "options_presented":
        matched = session_manager.resolve_selected_option(
            user_message, session.get("presented_options", [])
        )

        if matched:
            # User selected a valid option — fetch its recipe via the idle pipeline
            option_name = matched["name"]
            session["selected_option"] = option_name
            logger.info("Option selected: %r from presented_options=%r", option_name,
                        [o.get("name") for o in session.get("presented_options", [])])

            agent_message, recipe_result = await _handle_idle(session, option_name)
            session["messages"].append({"role": "assistant", "content": agent_message})

            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                recipe=session.get("recipe"),
                cart=session["current_cart"] if session.get("current_cart") else None,
                stage=session["stage"],
            )

        elif llm_service.is_explicit_recipe_request(user_message):
            # User made a new recipe request while options were visible — start fresh
            session_manager.reset_cart(session)
            agent_message, recipe_result = await _handle_idle(session, user_message)
            session["messages"].append({"role": "assistant", "content": agent_message})

            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                recipe=session.get("recipe"),
                cart=session["current_cart"] if session.get("current_cart") else None,
                stage=session["stage"],
            )

        else:
            # Unrecognized input — prompt the user to choose from the current options
            options = session.get("presented_options", [])
            if options:
                names = ", ".join(f"**{o['name']}**" for o in options)
                agent_message = (
                    f"I didn't catch which one you'd like. "
                    f"Please choose from the options I suggested: {names}. "
                    f"Or ask for something completely different!"
                )
            else:
                agent_message = (
                    "Please tell me which dish you'd like to make, or ask for new suggestions!"
                )
            session["messages"].append({"role": "assistant", "content": agent_message})
            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                stage=session["stage"],
            )

    # -----------------------------------------------------------------------
    # CART_PROPOSED / NEGOTIATING stage: conversation loop
    # -----------------------------------------------------------------------
    elif stage in ("cart_proposed", "negotiating"):
        # Short-circuit: if the message clearly asks for alternatives, do not
        # send it to call_llm_conversation (which might misclassify it as
        # "question" and leave the old recipe active). Force a reset immediately.
        if llm_service.is_context_switch(user_message) or llm_service.is_explicit_recipe_request(user_message):
            session_manager.reset_cart(session)
            agent_message, _ = await _handle_idle(session, user_message)
            session["messages"].append({"role": "assistant", "content": agent_message})
            return ChatResponse(
                conversation_id=request.conversation_id,
                message=agent_message,
                recipe=session.get("recipe"),
                cart=session["current_cart"] if session.get("current_cart") else None,
                stage=session["stage"],
            )

        result = llm_service.call_llm_conversation(
            stage=session["stage"],
            current_cart=session["current_cart"],
            recipe=session["recipe"],
            preferences=session["preferences"],
            budget=llm_service.compute_effective_budget(session["preferences"]),
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

            # Budget validation
            cart_total = _compute_cart_total(session["current_cart"])
            budget = llm_service.compute_effective_budget(session["preferences"])
            if cart_total > budget:
                agent_message += f"\n\nHeads up: your cart total is ${cart_total:.2f}, which is over your ${budget:.2f} budget."

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

    # Options presented — save the list and move to options_presented stage
    if status == "options_presented":
        options = recipe_result.get("options") or []
        session_manager.transition_to_options_presented(session, options)
        agent_message = recipe_result.get("message", "Here are some options! Which would you like?")
        return agent_message, recipe_result

    if recipe_result.get("recipe") is None:
        session["stage"] = "idle"
        return recipe_result.get("message", "I had trouble finding a recipe. Please try again."), recipe_result

    recipe = recipe_result["recipe"]

    # ------------------------------------------------------------------
    # Post-generation dietary validation.
    # The LLM prompt already enforces dietary constraints, but we validate
    # at the code level as a safety net. Up to _MAX_DIETARY_RETRIES retries
    # are attempted; each retry passes an explicit violation note so Claude
    # knows exactly what it got wrong.
    # ------------------------------------------------------------------
    _MAX_DIETARY_RETRIES = 2
    dietary_flags = [f.lower() for f in session["preferences"].get("dietary_flags", [])]

    for _attempt in range(_MAX_DIETARY_RETRIES + 1):
        violations = nn_service.check_recipe_dietary_violations(recipe, dietary_flags)
        if not violations:
            break  # Recipe is clean — proceed

        logger.warning(
            "Dietary violation in recipe %r (attempt %d/%d): %r",
            recipe.get("name"), _attempt + 1, _MAX_DIETARY_RETRIES + 1, violations,
        )

        if _attempt < _MAX_DIETARY_RETRIES:
            violation_note = (
                f"The previous recipe '{recipe.get('name')}' violated dietary constraints "
                f"by including: {', '.join(violations)}. "
                "You MUST find a different recipe that completely excludes these ingredients."
            )
            retry_result = llm_service.call_llm_recipe(
                user_message=user_message,
                calendar=session["calendar_context"],
                preferences=session["preferences"],
                messages=session["messages"],
                pantry=session["pantry_state"],
                constraint_violation_note=violation_note,
            )
            if retry_result.get("recipe") is None:
                # LLM gave up — return the failure message it provided
                session["stage"] = "idle"
                return retry_result.get(
                    "message",
                    "I couldn't find a recipe that fits your dietary requirements. Try a different dish.",
                ), retry_result
            recipe = retry_result["recipe"]
        else:
            # All retries exhausted; refuse rather than serve a violating recipe
            logger.error(
                "Dietary retries exhausted for query %r — refusing recipe", normalized_query
            )
            diet_str = ", ".join(dietary_flags) or "your dietary restrictions"
            session["stage"] = "idle"
            return (
                f"I wasn't able to find a **{normalized_query}** recipe that fully respects "
                f"your dietary constraints ({diet_str}). Try asking for a different dish.",
                {"status": "recipe_lookup_failed", "recipe": None},
            )

    # ------------------------------------------------------------------
    # Post-generation time constraint validation.
    # Parse prep_time + cook_time strings and retry once if the total
    # exceeds the user's max_prep_time. If still over-limit after the
    # retry we warn and proceed — time is a soft preference, not safety.
    # ------------------------------------------------------------------
    max_prep_time = int(session["preferences"].get("max_prep_time", 0))
    if 0 < max_prep_time < 120:  # 0 or >= 120 means "no limit"
        _MAX_TIME_RETRIES = 1
        for _time_attempt in range(_MAX_TIME_RETRIES + 1):
            total_time = (
                _parse_time_minutes(recipe.get("prep_time", ""))
                + _parse_time_minutes(recipe.get("cook_time", ""))
            )
            if total_time == 0 or total_time <= max_prep_time:
                break  # within limit or time unknown — give benefit of the doubt
            logger.warning(
                "Recipe %r total time %d min exceeds limit %d min (attempt %d/%d)",
                recipe.get("name"), total_time, max_prep_time,
                _time_attempt + 1, _MAX_TIME_RETRIES + 1,
            )
            if _time_attempt < _MAX_TIME_RETRIES:
                time_note = (
                    f"The previous recipe '{recipe.get('name')}' takes ~{total_time} minutes total "
                    f"(prep + cook), which exceeds the user's {max_prep_time}-minute limit. "
                    f"Find a different recipe that can be fully prepared and cooked in "
                    f"{max_prep_time} minutes or less."
                )
                retry_result = llm_service.call_llm_recipe(
                    user_message=user_message,
                    calendar=session["calendar_context"],
                    preferences=session["preferences"],
                    messages=session["messages"],
                    pantry=session["pantry_state"],
                    constraint_violation_note=time_note,
                )
                if retry_result.get("recipe") is None:
                    session["stage"] = "idle"
                    return (
                        retry_result.get(
                            "message",
                            f"I couldn't find a recipe within your {max_prep_time}-minute limit. "
                            "Try asking for a quick dish!",
                        ),
                        retry_result,
                    )
                recipe = retry_result["recipe"]
            # else: retry exhausted — warn and continue with over-limit recipe

    recipe = recipe_image_service.populate_recipe_image(recipe)
    session["recipe"] = recipe
    session["full_ingredient_list"] = recipe.get("ingredients", [])
    logger.info(
        "Recipe selected: normalized=%r name=%r cuisine=%r ingredients=%d image=%r",
        normalized_query,
        recipe.get("name"),
        recipe.get("cuisine", ""),
        len(session["full_ingredient_list"]),
        recipe.get("image_url", ""),
    )

    # Compute ingredient gaps
    gaps = gap_analysis.compute_gaps(
        recipe_ingredients=session["full_ingredient_list"],
        pantry=session["pantry_state"],
        recipe_name=recipe.get("name"),
    )
    session["ingredient_gaps"] = gaps
    logger.info(
        "Gap analysis complete: normalized=%r gaps=%d matched_pantry=%d",
        normalized_query,
        len(gaps),
        max(0, len(session["full_ingredient_list"]) - len(gaps)),
    )

    # Run NN recommendations — pass the recipe's cuisine so the user's
    # cuisine_weights[cuisine] is used directly rather than averaged.
    nn_recs, staples_assumed = nn_service.recommend(
        ingredient_gaps=gaps,
        calendar=session["calendar_context"],
        preferences=session["preferences"],
        recipe_cuisine=recipe.get("cuisine"),
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

    cart_total = _compute_cart_total(nn_recs)
    agent_message = _build_local_cart_narration(
        recipe=recipe,
        pantry=session["pantry_state"],
        cart_items=nn_recs,
        gaps=gaps,
        budget=llm_service.compute_effective_budget(session["preferences"]),
        cart_total=cart_total,
        staples_assumed=staples_assumed,
    )

    session["stage"] = "cart_proposed"
    return agent_message, recipe_result


GEORGIA_TAX_RATE = 0.04
DELIVERY_FEE = 4.99


def _compute_cart_subtotal(cart: list) -> float:
    """Sum of item prices only (no tax/delivery)."""
    return round(sum(item.get("estimated_price", 0) for item in cart), 2)


def _compute_cart_total(cart: list) -> float:
    """Compute the total estimated cost of the current cart.
    estimated_price already accounts for quantity (set by the pricing engine)."""
    return sum(item.get("estimated_price", 0) for item in cart)


def _normalize_item_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _format_name_list(items: list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _get_pantry_matches(recipe_ingredients: list, pantry: list) -> list[str]:
    pantry_items = {str(item.get("item", "")).strip(): _normalize_item_name(item.get("item", "")) for item in pantry}
    pantry_norms = set(pantry_items.values())
    matches: list[str] = []
    for ingredient in recipe_ingredients or []:
        ingredient_name = str(ingredient.get("item", "")).strip()
        if not ingredient_name:
            continue
        if _normalize_item_name(ingredient_name) in pantry_norms and ingredient_name not in matches:
            matches.append(ingredient_name)
    return matches


def _build_local_cart_narration(
    recipe: dict,
    pantry: list,
    cart_items: list,
    gaps: list,
    budget: float,
    cart_total: float,
    staples_assumed: list | None = None,
) -> str:
    """
    Build the assistant response from the **resolved cart** as the single source of truth.

    Categories (mutually exclusive, covering all gap items):
      - already_in_pantry  : matched from pantry; not in gaps at all
      - priced_cart_item   : in cart_items (nn_recs); these are what drive cart_total
      - assumed_staple     : in staples_assumed; zero-cost, excluded from total
      - unresolved         : in gaps but absent from both cart_items and staples (e.g.
                             dietary-filtered); logged as a warning, not mentioned to user

    The response text mentions only items that are in one of the first three categories,
    and the total is always computed from cart_items — never from gaps.
    """
    try:
        budget_value = float(budget)
    except (TypeError, ValueError):
        budget_value = 0.0

    # --- Resolve categories ------------------------------------------------
    pantry_matches = _get_pantry_matches(recipe.get("ingredients", []), pantry)

    # priced_cart_item: derive names from the actual resolved/priced cart
    priced_items: list[str] = []
    for item in cart_items or []:
        name = str(item.get("item", "")).strip()
        if name and name not in priced_items:
            priced_items.append(name)

    staple_names: list[str] = list(staples_assumed or [])

    # Safeguard: find gap items that ended up in neither cart nor staples
    accounted_norms = {_normalize_item_name(n) for n in priced_items + staple_names}
    unresolved: list[str] = []
    for gap in gaps or []:
        name = str(gap.get("item", "")).strip()
        if name and _normalize_item_name(name) not in accounted_norms:
            unresolved.append(name)

    # Log the resolved breakdown for every request
    logger.debug(
        "Cart narration breakdown | recipe=%r | pantry_matches=%r | priced_cart=%r "
        "| staples=%r | unresolved=%r | cart_total=%.2f",
        recipe.get("name"),
        pantry_matches,
        priced_items,
        staple_names,
        unresolved,
        cart_total,
    )
    if unresolved:
        logger.warning(
            "Unresolved gap items (not in cart or staples, likely dietary-filtered) "
            "for recipe %r: %r",
            recipe.get("name"),
            unresolved,
        )

    # Consistency check: the text mentions exactly what was priced
    # (priced_items + staple_names exhausts what we tell the user about)
    described_count = len(priced_items) + len(staple_names)
    gap_count = len(gaps or [])
    if described_count != gap_count:
        logger.debug(
            "Gap count mismatch: gaps=%d described=%d (priced=%d staples=%d unresolved=%d) "
            "for recipe %r — unresolved items are dietary-filtered or otherwise excluded",
            gap_count, described_count, len(priced_items), len(staple_names),
            len(unresolved), recipe.get("name"),
        )

    # --- Build the response text from resolved categories ------------------
    parts: list[str] = []

    if pantry_matches:
        parts.append(f"You already have {_format_name_list(pantry_matches)} in your pantry.")

    if priced_items:
        parts.append(
            f"I added {_format_name_list(priced_items)} to your cart for "
            f"{recipe.get('name', 'this recipe')}."
        )

    if staple_names:
        parts.append(
            f"I treated {_format_name_list(staple_names)} as a pantry staple, "
            f"so {'it was' if len(staple_names) == 1 else 'they were'} not included in the price."
        )

    total_with_fees = round(cart_total * (1 + GEORGIA_TAX_RATE) + DELIVERY_FEE, 2)
    if budget_value > 0 and total_with_fees <= budget_value:
        parts.append(
            f"Your total is ${total_with_fees:.2f} including GA tax and delivery, "
            f"which stays within your ${budget_value:.2f} budget."
        )
    elif budget_value > 0:
        parts.append(
            f"Your total is ${total_with_fees:.2f} including GA tax and delivery, "
            f"which is slightly over your ${budget_value:.2f} budget."
        )
    else:
        parts.append(f"Your total is ${total_with_fees:.2f} including GA tax and delivery.")

    return " ".join(parts).strip()


def _parse_time_minutes(time_str: str) -> int:
    """
    Parse a recipe time string into total minutes.
    Handles formats like '20 min', '1 hr 30 min', '1.5 hours', '45 minutes'.
    Returns 0 when the string is empty or unparseable.
    """
    import re as _re
    if not time_str:
        return 0
    s = str(time_str)
    total = 0
    m = _re.search(r"(\d+(?:\.\d+)?)\s*(?:hr|hour|h)\b", s, _re.IGNORECASE)
    if m:
        total += int(float(m.group(1)) * 60)
    m = _re.search(r"(\d+)\s*(?:min|minute|m)\b", s, _re.IGNORECASE)
    if m:
        total += int(m.group(1))
    return total
