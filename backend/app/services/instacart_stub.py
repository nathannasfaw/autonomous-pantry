"""
Instacart stub: simulates placing a grocery order.
Computes subtotal, GA sales tax, and flat delivery fee.
"""

import random

GEORGIA_TAX_RATE = 0.04
DELIVERY_FEE = 4.99

PUBLIX_KEYWORDS = {"greenwise", "publix"}
KROGER_KEYWORDS = {"simple truth", "private selection", "kroger"}


def _detect_retailer(cart: list) -> str:
    """Pick the retailer that has the most store-specific items in the cart."""
    publix_count = 0
    kroger_count = 0

    for item in cart:
        store = item.get("store", "")
        brand = (item.get("brand") or "").lower()

        if store == "publix" or any(kw in brand for kw in PUBLIX_KEYWORDS):
            publix_count += 1
        elif store == "kroger" or any(kw in brand for kw in KROGER_KEYWORDS):
            kroger_count += 1

    if kroger_count > publix_count:
        return "Kroger"
    return "Publix"


def place_order(cart: list) -> dict:
    """Simulate placing an order through Instacart."""
    subtotal = round(sum(item.get("estimated_price", 0) for item in cart), 2)
    tax = round(subtotal * GEORGIA_TAX_RATE, 2)
    total = round(subtotal + tax + DELIVERY_FEE, 2)
    retailer = _detect_retailer(cart)

    return {
        "order_id": f"INST-{random.randint(10000, 99999)}",
        "status": "confirmed",
        "estimated_delivery": "45-60 minutes",
        "items": cart,
        "subtotal": subtotal,
        "tax": tax,
        "tax_label": "GA Sales Tax (4%)",
        "delivery_fee": DELIVERY_FEE,
        "total": total,
        "retailer": retailer,
    }
