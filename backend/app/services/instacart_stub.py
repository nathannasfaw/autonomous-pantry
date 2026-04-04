"""
Instacart stub: simulates placing a grocery order.
"""

import random


def place_order(cart: list) -> dict:
    """Simulate placing an order through Instacart."""
    total = sum(
        item.get("estimated_price", 0) * item.get("quantity", 1)
        for item in cart
    )
    return {
        "order_id": f"INST-{random.randint(10000, 99999)}",
        "status": "confirmed",
        "estimated_delivery": "45-60 minutes",
        "items": cart,
        "total": round(total, 2),
        "retailer": "Whole Foods Market",
    }
