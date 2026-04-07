"""
Session manager: stores all conversation sessions in memory.
"""

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
        "preferences": copy.deepcopy(PREFERENCES),
        "confirmation_pending": False,
    }
    return session_id


def get_session(session_id: str) -> dict | None:
    """Retrieve a session by ID. Returns None if not found."""
    return SESSIONS.get(session_id)


def reset_cart(session: dict) -> None:
    """
    Reset recipe/cart/gaps/stage but preserve messages and preferences.
    Used when the user wants to switch to a completely different dish.
    """
    session["recipe"] = None
    session["full_ingredient_list"] = []
    session["ingredient_gaps"] = []
    session["current_cart"] = []
    session["nn_original_cart"] = []
    session["stage"] = "idle"
    session["confirmation_pending"] = False


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
