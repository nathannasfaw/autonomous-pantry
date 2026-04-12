"""
Session manager: stores all conversation sessions in memory.
"""

import re
import uuid
import copy
from app.data.seed_data import PANTRY, CALENDAR, PREFERENCES
from app.services import pantry_store

SESSIONS: dict = {}


def create_session(client_id: str | None = None) -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())
    resolved_client_id = client_id or session_id
    pantry_state = pantry_store.seed_if_empty(resolved_client_id, copy.deepcopy(PANTRY))

    # Load persisted preferences; fall back to seed defaults for new users
    saved_prefs = pantry_store.load_preferences(resolved_client_id)
    initial_prefs = saved_prefs if saved_prefs is not None else copy.deepcopy(PREFERENCES)
    # Merge on top of defaults so new preference keys added in future deploys are present
    if saved_prefs is not None:
        merged = copy.deepcopy(PREFERENCES)
        merged.update(saved_prefs)
        initial_prefs = merged

    SESSIONS[session_id] = {
        "conversation_id": session_id,
        "client_id": resolved_client_id,
        "messages": [],
        "stage": "idle",
        "recipe": None,
        "full_ingredient_list": [],
        "pantry_state": pantry_state,
        "ingredient_gaps": [],
        "current_cart": [],
        "nn_original_cart": [],
        "calendar_context": copy.deepcopy(CALENDAR),
        "preferences": initial_prefs,
        "confirmation_pending": False,
        # Option-selection state — populated when the LLM returns options_presented
        "presented_options": [],   # list of option dicts shown to the user on the current turn
        "selected_option": None,   # name of the option the user most recently chose
    }
    return session_id


def get_session(session_id: str) -> dict | None:
    """Retrieve a session by ID. Returns None if not found."""
    return SESSIONS.get(session_id)


def reset_cart(session: dict) -> None:
    """
    Reset recipe/cart/gaps/options/stage but preserve messages and preferences.
    Used when the user wants to switch to a completely different dish.
    """
    session["recipe"] = None
    session["full_ingredient_list"] = []
    session["ingredient_gaps"] = []
    session["current_cart"] = []
    session["nn_original_cart"] = []
    session["presented_options"] = []
    session["selected_option"] = None
    session["stage"] = "idle"
    session["confirmation_pending"] = False


def transition_to_options_presented(session: dict, options: list) -> None:
    """
    Move the session into the options_presented stage.
    Saves the option list and clears any stale single-recipe context so it
    cannot bleed into the option-selection turn.
    """
    session["recipe"] = None
    session["full_ingredient_list"] = []
    session["ingredient_gaps"] = []
    session["current_cart"] = []
    session["nn_original_cart"] = []
    session["presented_options"] = [dict(opt) for opt in (options or [])]
    session["selected_option"] = None
    session["stage"] = "options_presented"
    session["confirmation_pending"] = False


def resolve_selected_option(user_message: str, presented_options: list) -> dict | None:
    """
    Try to match the user's message against the currently presented options.
    Returns the matched option dict, or None if no match is found.

    Matching priority (case-insensitive):
      1. Exact option name
      2. Option name is a substring of the user message
      3. User message is a substring of the option name
      4. Significant word overlap (1+ shared word ≥ 5 chars, or 2+ shared words ≥ 4 chars)
    """
    if not presented_options:
        return None

    normalized_msg = user_message.lower().strip()

    # 1. Exact match
    for opt in presented_options:
        if opt.get("name", "").lower().strip() == normalized_msg:
            return opt

    # 2. Option name contained in the user message ("I'd like garlic bread please")
    for opt in presented_options:
        opt_name = opt.get("name", "").lower().strip()
        if opt_name and opt_name in normalized_msg:
            return opt

    # 3. User message contained in option name ("garlic" ⊆ "Garlic Bread")
    for opt in presented_options:
        opt_name = opt.get("name", "").lower().strip()
        if normalized_msg and normalized_msg in opt_name:
            return opt

    # 4. Significant word overlap
    msg_words = set(
        w for w in re.sub(r"[^a-z0-9\s]", "", normalized_msg).split() if len(w) >= 4
    )
    for opt in presented_options:
        opt_words = set(
            w for w in re.sub(r"[^a-z0-9\s]", "", opt.get("name", "").lower()).split()
            if len(w) >= 4
        )
        common = msg_words & opt_words
        if common and (any(len(w) >= 4 for w in common) or len(common) >= 2):
            return opt

    return None


def apply_cart_diff(session: dict, cart_diff: list) -> None:
    """
    Apply a list of diff operations to session["current_cart"].

    Supported operations:
    - swap:       replace one item with another
    - add:        add a new item
    - remove:     remove an item
    - update_qty: change the quantity of an existing item
    """
    cart = session["current_cart"]

    for op in cart_diff:
        action = op.get("action", "")

        if action == "swap":
            from_name = (op.get("from") or "").lower().strip()
            to_name = op.get("to", "")
            # Find and replace the item
            replaced = False
            for i, cart_item in enumerate(cart):
                if cart_item["item"].lower().strip() == from_name:
                    cart[i] = {
                        "item": to_name,
                        "quantity": op.get("quantity", cart_item.get("quantity", 1.0)),
                        "unit": op.get("unit", cart_item.get("unit", "")),
                        "estimated_price": op.get("estimated_price", cart_item.get("estimated_price", 5.00)),
                        "score": cart_item.get("score", 0.5),
                    }
                    replaced = True
                    break
            if not replaced:
                # If the from-item doesn't exist, just add the to-item
                cart.append({
                    "item": to_name,
                    "quantity": op.get("quantity", 1.0),
                    "unit": op.get("unit", ""),
                    "estimated_price": op.get("estimated_price", 5.00),
                    "score": 0.5,
                })

        elif action == "add":
            item_name = op.get("item", "")
            # Check if item already exists
            existing = next(
                (c for c in cart if c["item"].lower().strip() == item_name.lower().strip()),
                None
            )
            if existing:
                # Update quantity instead of duplicating
                existing["quantity"] = existing.get("quantity", 0) + op.get("quantity", 1.0)
            else:
                cart.append({
                    "item": item_name,
                    "quantity": op.get("quantity", 1.0),
                    "unit": op.get("unit", ""),
                    "estimated_price": op.get("estimated_price", 5.00),
                    "score": 0.5,
                })

        elif action == "remove":
            item_name = (op.get("item") or "").lower().strip()
            session["current_cart"] = [
                c for c in cart if c["item"].lower().strip() != item_name
            ]
            cart = session["current_cart"]

        elif action == "update_qty":
            item_name = (op.get("item") or "").lower().strip()
            new_qty = op.get("quantity", 1.0)
            for cart_item in cart:
                if cart_item["item"].lower().strip() == item_name:
                    cart_item["quantity"] = new_qty
                    break
