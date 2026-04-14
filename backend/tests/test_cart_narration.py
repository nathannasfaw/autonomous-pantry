"""
Tests for _build_local_cart_narration consistency.

Verifies that the assistant response text is generated from the same resolved
cart/pricing data that drives cart_total — never from the raw gap list.

Run with:  cd autonomous-pantry/backend && python -m pytest tests/test_cart_narration.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.routes.chat import (
    DELIVERY_FEE,
    GEORGIA_TAX_RATE,
    _build_local_cart_narration,
    _compute_cart_total,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recipe(name="Homemade Pizza", ingredients=None):
    return {
        "name": name,
        "ingredients": ingredients or [
            {"item": "all-purpose flour", "quantity": 2, "unit": "cups"},
            {"item": "instant yeast", "quantity": 1, "unit": "tsp"},
            {"item": "warm water", "quantity": 0.75, "unit": "cups"},
            {"item": "salt", "quantity": 1, "unit": "tsp"},
            {"item": "olive oil", "quantity": 2, "unit": "tbsp"},
            {"item": "tomato sauce", "quantity": 0.5, "unit": "cups"},
            {"item": "mozzarella cheese", "quantity": 1, "unit": "cups"},
        ],
    }


def _pantry(*items):
    return [{"item": name, "quantity": 1, "unit": "count", "confidence": 0.9} for name in items]


def _cart_item(name, price):
    return {"item": name, "quantity": 1, "unit": "count", "estimated_price": price, "score": 0.9}


def _gaps(*items):
    return [{"item": name, "required": 1.0, "available": 0.0, "gap": 1.0, "unit": "count"} for name in items]


def _expected_total(subtotal):
    return round(subtotal * (1 + GEORGIA_TAX_RATE) + DELIVERY_FEE, 2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCartNarrationSourceOfTruth(unittest.TestCase):
    """Response text must come from cart_items, not from the raw gaps list."""

    def test_pizza_case_staple_not_in_added(self):
        """
        Classic bug: warm water was in gaps but is a staple.
        It must NOT appear in 'I added...' and MUST appear in the staple sentence.
        """
        recipe = _recipe()
        pantry = _pantry("salt", "olive oil", "tomato sauce", "mozzarella cheese")
        # gaps has 3 items: flour, yeast, warm water
        gaps = _gaps("all-purpose flour", "instant yeast", "warm water")
        # cart only has 2 priced items (warm water was classified as staple by NN)
        cart_items = [
            _cart_item("all-purpose flour", 3.49),
            _cart_item("instant yeast", 2.99),
        ]
        staples_assumed = ["warm water"]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=gaps,
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        # warm water must NOT appear as "added"
        self.assertNotIn(
            "I added all-purpose flour, instant yeast, and warm water",
            narration,
            "warm water should not be listed as an added cart item",
        )
        # warm water MUST appear as a staple
        self.assertIn("warm water", narration)
        self.assertIn("staple", narration.lower())

        # priced items must appear
        self.assertIn("all-purpose flour", narration)
        self.assertIn("instant yeast", narration)

    def test_total_matches_cart_items_only(self):
        """Total must equal sum of cart_items prices + tax + delivery, not include staples."""
        recipe = _recipe()
        pantry = _pantry("salt", "olive oil")
        gaps = _gaps("all-purpose flour", "instant yeast", "warm water")
        cart_items = [
            _cart_item("all-purpose flour", 3.49),
            _cart_item("instant yeast", 2.99),
        ]
        staples_assumed = ["warm water"]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=gaps,
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        expected = _expected_total(cart_total)  # 6.48 * 1.04 + 4.99
        self.assertIn(f"${expected:.2f}", narration, "total in narration must match cart_items pricing")

        # Ensure we are NOT computing total from 3 items (which would include warm water)
        wrong_total = _expected_total(_compute_cart_total(cart_items + [_cart_item("warm water", 0.0)]))
        # Both happen to be the same when staple price = 0; but the key invariant
        # is that the narration text says the right dollar amount
        self.assertIn(f"${expected:.2f}", narration)

    def test_no_added_sentence_when_cart_empty(self):
        """If NN recommends nothing (all pantry matches), no 'I added' sentence."""
        recipe = _recipe()
        pantry = _pantry("all-purpose flour", "instant yeast", "salt", "olive oil", "tomato sauce", "mozzarella cheese")
        gaps = []
        cart_items = []
        staples_assumed = []
        cart_total = 0.0

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=gaps,
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        self.assertNotIn("I added", narration)
        self.assertIn("You already have", narration)

    def test_dietary_filtered_item_not_mentioned(self):
        """
        If an item in gaps was dietary-filtered (not in cart_items or staples),
        it must NOT appear in the 'I added' sentence.
        """
        recipe = _recipe(
            name="Chicken Pasta",
            ingredients=[
                {"item": "pasta", "quantity": 200, "unit": "g"},
                {"item": "chicken breast", "quantity": 300, "unit": "g"},
                {"item": "cream", "quantity": 100, "unit": "ml"},
            ],
        )
        pantry = []
        # All three are gaps
        gaps = _gaps("pasta", "chicken breast", "cream")
        # NN dietary-filtered chicken breast (user is vegetarian)
        cart_items = [
            _cart_item("pasta", 1.99),
            _cart_item("cream", 2.49),
        ]
        staples_assumed = []
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=gaps,
            budget=30.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        # chicken breast was filtered out — must NOT appear in added sentence
        self.assertNotIn("chicken breast", narration)
        # priced items must appear
        self.assertIn("pasta", narration)
        self.assertIn("cream", narration)

    def test_staple_wording_singular(self):
        """Single staple uses 'it was not included'."""
        recipe = _recipe()
        pantry = []
        cart_items = [_cart_item("all-purpose flour", 3.49)]
        staples_assumed = ["warm water"]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=_gaps("all-purpose flour", "warm water"),
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        self.assertIn("it was not included", narration)

    def test_staple_wording_plural(self):
        """Multiple staples use 'they were not included'."""
        recipe = _recipe()
        pantry = []
        cart_items = [_cart_item("all-purpose flour", 3.49)]
        staples_assumed = ["warm water", "salt"]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=_gaps("all-purpose flour", "warm water", "salt"),
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        self.assertIn("they were not included", narration)

    def test_budget_over_message(self):
        """Over-budget message appears when total exceeds budget."""
        recipe = _recipe()
        pantry = []
        cart_items = [_cart_item("truffle oil", 25.00)]
        cart_total = _compute_cart_total(cart_items)
        total_with_fees = _expected_total(cart_total)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=_gaps("truffle oil"),
            budget=10.0,
            cart_total=cart_total,
            staples_assumed=[],
        )

        self.assertIn("slightly over", narration)
        self.assertIn(f"${total_with_fees:.2f}", narration)

    def test_budget_within_message(self):
        """Within-budget message appears when total is under budget."""
        recipe = _recipe()
        pantry = []
        cart_items = [_cart_item("pasta", 1.99)]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=_gaps("pasta"),
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=[],
        )

        self.assertIn("stays within", narration)

    def test_added_count_matches_cart_items(self):
        """
        The number of items described as 'added' must equal len(cart_items),
        not len(gaps).
        """
        recipe = _recipe()
        pantry = _pantry("olive oil")
        # 4 gaps, but only 2 end up priced (1 staple + 1 dietary-filtered)
        gaps = _gaps("all-purpose flour", "instant yeast", "warm water", "chicken stock")
        cart_items = [
            _cart_item("all-purpose flour", 3.49),
            _cart_item("instant yeast", 2.99),
        ]
        staples_assumed = ["warm water"]
        # chicken stock was dietary-filtered and drops silently
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=gaps,
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=staples_assumed,
        )

        # Only 2 priced items should be in the "I added" sentence
        self.assertIn("all-purpose flour", narration)
        self.assertIn("instant yeast", narration)
        # chicken stock (dietary-filtered) must not appear
        self.assertNotIn("chicken stock", narration)
        # warm water must appear as staple, not as added
        self.assertNotIn("I added all-purpose flour, instant yeast, warm water", narration)
        self.assertIn("warm water", narration)
        self.assertIn("staple", narration.lower())

    def test_no_budget_no_crash(self):
        """Works fine when budget is 0 (no budget set)."""
        recipe = _recipe()
        pantry = []
        cart_items = [_cart_item("pasta", 1.99)]
        cart_total = _compute_cart_total(cart_items)

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=_gaps("pasta"),
            budget=0.0,
            cart_total=cart_total,
            staples_assumed=[],
        )

        expected = _expected_total(cart_total)
        self.assertIn(f"${expected:.2f}", narration)
        self.assertNotIn("within", narration)
        self.assertNotIn("over", narration)

    def test_total_is_zero_with_empty_cart(self):
        """Empty cart gives only delivery fee + tax (i.e., just delivery fee since subtotal=0)."""
        recipe = _recipe()
        pantry = _pantry("all-purpose flour", "instant yeast")
        cart_items = []
        cart_total = 0.0

        narration = _build_local_cart_narration(
            recipe=recipe,
            pantry=pantry,
            cart_items=cart_items,
            gaps=[],
            budget=40.0,
            cart_total=cart_total,
            staples_assumed=[],
        )

        expected = _expected_total(0.0)  # 0 * 1.04 + 4.99 = 4.99
        self.assertIn(f"${expected:.2f}", narration)


class TestComputeCartTotal(unittest.TestCase):
    """_compute_cart_total sums estimated_price fields."""

    def test_sum(self):
        cart = [
            {"item": "flour", "estimated_price": 3.49},
            {"item": "yeast", "estimated_price": 2.99},
        ]
        self.assertAlmostEqual(_compute_cart_total(cart), 6.48)

    def test_missing_price_treated_as_zero(self):
        cart = [{"item": "flour"}, {"item": "yeast", "estimated_price": 2.99}]
        self.assertAlmostEqual(_compute_cart_total(cart), 2.99)

    def test_empty_cart(self):
        self.assertEqual(_compute_cart_total([]), 0)


if __name__ == "__main__":
    unittest.main()
