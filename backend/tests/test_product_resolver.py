"""
Tests for the product resolver, product cache, and package-based pricing.

All tests that touch the database use a temp file via the db_path parameter
so they are fully isolated — no patching of module-level globals needed.

Tests that exercise OFF behaviour mock off_client so no real HTTP calls are made.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.services import product_cache, product_resolver as pr
from app.data.seed_products import SEED_CATALOGUE, seed_common_ingredients
from app.models.cart import Cart, CartItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_db():
    """Create a temporary SQLite file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _seed(db):
    seed_common_ingredients(db_path=db)


# ---------------------------------------------------------------------------
# 1. product_cache CRUD
# ---------------------------------------------------------------------------

class TestProductCacheCRUD(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()

    def tearDown(self):
        os.unlink(self.db)

    def test_get_returns_none_for_missing_key(self):
        self.assertIsNone(product_cache.get("nonexistent", self.db))

    def test_put_and_get_roundtrip(self):
        record = {
            "ingredient_key": "test_flour",
            "product_name": "Test Flour",
            "brand": "TestBrand",
            "package_amount": 5.0,
            "package_unit": "lb",
            "estimated_price": 4.49,
            "source": "seeded",
            "confidence": 1.0,
        }
        product_cache.put(record, self.db)
        result = product_cache.get("test_flour", self.db)
        self.assertIsNotNone(result)
        self.assertEqual(result["product_name"], "Test Flour")
        self.assertAlmostEqual(result["estimated_price"], 4.49)

    def test_put_miss_stores_off_miss_record(self):
        product_cache.put_miss("weird_ingredient", self.db)
        result = product_cache.get("weird_ingredient", self.db)
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "off_miss")
        self.assertAlmostEqual(result["confidence"], 0.0)

    def test_bulk_put_skips_existing(self):
        records = [
            {"ingredient_key": "a", "product_name": "A", "estimated_price": 1.0,
             "source": "seeded", "confidence": 1.0, "package_amount": 1.0, "package_unit": "oz"},
        ]
        inserted_first = product_cache.bulk_put(records, self.db)
        inserted_second = product_cache.bulk_put(records, self.db)
        self.assertEqual(inserted_first, 1)
        self.assertEqual(inserted_second, 0)  # already exists — skipped

    def test_bulk_put_replaces_off_miss_with_seeded_record(self):
        product_cache.put_miss("pizza sauce", self.db)
        records = [
            {"ingredient_key": "pizza sauce", "product_name": "Pizza Sauce", "brand": "Hunts",
             "estimated_price": 1.79, "source": "seeded", "confidence": 1.0,
             "package_amount": 14.0, "package_unit": "oz"},
        ]
        inserted = product_cache.bulk_put(records, self.db)
        result = product_cache.get("pizza sauce", self.db)
        self.assertEqual(inserted, 1)
        self.assertEqual(result["source"], "seeded")
        self.assertEqual(result["product_name"], "Pizza Sauce")


# ---------------------------------------------------------------------------
# 2. Seeding
# ---------------------------------------------------------------------------

class TestSeeding(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()

    def tearDown(self):
        os.unlink(self.db)

    def test_seed_inserts_records(self):
        inserted = seed_common_ingredients(db_path=self.db)
        self.assertGreater(inserted, 50)

    def test_seed_is_idempotent(self):
        first = seed_common_ingredients(db_path=self.db)
        second = seed_common_ingredients(db_path=self.db)
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)

    def test_yeast_is_seeded(self):
        seed_common_ingredients(db_path=self.db)
        record = product_cache.get("yeast", self.db)
        self.assertIsNotNone(record)
        self.assertEqual(record["source"], "seeded")
        self.assertAlmostEqual(record["package_amount"], 2.25)
        self.assertEqual(record["package_unit"], "tsp")

    def test_common_ingredients_all_seeded(self):
        seed_common_ingredients(db_path=self.db)
        for key in ("flour", "eggs", "milk", "butter", "olive oil",
                    "tomato sauce", "pasta", "rice", "garlic", "onion"):
            with self.subTest(key=key):
                self.assertIsNotNone(product_cache.get(key, self.db))


# ---------------------------------------------------------------------------
# 3. Cache hit skips OFF
# ---------------------------------------------------------------------------

class TestCacheHitSkipsOFF(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()
        _seed(self.db)

    def tearDown(self):
        os.unlink(self.db)

    @patch("app.services.off_client.search_product")
    def test_seeded_ingredient_never_calls_off(self, mock_search):
        result = pr.get_product("yeast", db_path=self.db)
        mock_search.assert_not_called()
        self.assertIsNotNone(result)

    @patch("app.services.off_client.search_product")
    def test_flour_never_calls_off(self, mock_search):
        pr.get_product("flour", db_path=self.db)
        mock_search.assert_not_called()

    @patch("app.services.off_client.search_product")
    def test_eggs_never_calls_off(self, mock_search):
        pr.get_product("eggs", db_path=self.db)
        mock_search.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Cache miss calls OFF once and stores result
# ---------------------------------------------------------------------------

class TestCacheMissCallsOFF(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()
        # Do NOT seed so every lookup is a cache miss

    def tearDown(self):
        os.unlink(self.db)

    @patch("app.services.off_client.pick_best_candidate")
    @patch("app.services.off_client.search_product")
    def test_cache_miss_calls_off_once(self, mock_search, mock_pick):
        mock_search.return_value = [{"product_name": "Fancy Spice", "brands": "SpiceCo",
                                     "quantity": "50 g", "_id": "123"}]
        mock_pick.return_value = {"product_name": "Fancy Spice", "brands": "SpiceCo",
                                  "quantity": "50 g", "_id": "123"}
        pr.get_product("fancy spice", db_path=self.db)
        mock_search.assert_called_once_with("fancy spice")

    @patch("app.services.off_client.pick_best_candidate")
    @patch("app.services.off_client.search_product")
    def test_result_stored_after_off_call(self, mock_search, mock_pick):
        mock_search.return_value = [{"product_name": "Fancy Spice", "brands": "SpiceCo",
                                     "quantity": "50 g", "_id": "123"}]
        mock_pick.return_value = {"product_name": "Fancy Spice", "brands": "SpiceCo",
                                  "quantity": "50 g", "_id": "123"}
        pr.get_product("fancy spice", db_path=self.db)
        cached = product_cache.get("fancy spice", self.db)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["source"], "off_search")

    @patch("app.services.off_client.pick_best_candidate")
    @patch("app.services.off_client.search_product")
    def test_repeated_request_reuses_cache(self, mock_search, mock_pick):
        mock_search.return_value = [{"product_name": "Fancy Spice", "brands": "SpiceCo",
                                     "quantity": "50 g", "_id": "123"}]
        mock_pick.return_value = {"product_name": "Fancy Spice", "brands": "SpiceCo",
                                  "quantity": "50 g", "_id": "123"}
        pr.get_product("fancy spice", db_path=self.db)
        pr.get_product("fancy spice", db_path=self.db)
        pr.get_product("fancy spice", db_path=self.db)
        # OFF should only have been called once
        self.assertEqual(mock_search.call_count, 1)


# ---------------------------------------------------------------------------
# 5. OFF miss is persisted and not retried
# ---------------------------------------------------------------------------

class TestOFFMissPersisted(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()

    def tearDown(self):
        os.unlink(self.db)

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_off_miss_stored_as_off_miss(self, mock_search, mock_pick):
        pr.get_product("unicorn powder", db_path=self.db)
        cached = product_cache.get("unicorn powder", self.db)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["source"], "off_miss")

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_off_miss_not_retried(self, mock_search, mock_pick):
        pr.get_product("unicorn powder", db_path=self.db)
        pr.get_product("unicorn powder", db_path=self.db)
        pr.get_product("unicorn powder", db_path=self.db)
        self.assertEqual(mock_search.call_count, 1)

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_off_miss_returns_none(self, mock_search, mock_pick):
        result = pr.get_product("unicorn powder", db_path=self.db)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 6. Quantity parsing
# ---------------------------------------------------------------------------

class TestParsePackageQuantity(unittest.TestCase):
    def _parse(self, s):
        return pr.parse_package_quantity(s)

    def test_simple_grams(self):
        self.assertEqual(self._parse("21 g"), (21.0, "g"))

    def test_simple_oz(self):
        self.assertEqual(self._parse("8 oz"), (8.0, "oz"))

    def test_simple_ml(self):
        self.assertEqual(self._parse("500 ml"), (500.0, "ml"))

    def test_no_space_grams(self):
        self.assertEqual(self._parse("250g"), (250.0, "g"))

    def test_multipack_grams(self):
        amt, unit = self._parse("2 x 10 g")
        self.assertAlmostEqual(amt, 20.0)
        self.assertEqual(unit, "g")

    def test_multipack_ml(self):
        amt, unit = self._parse("6 x 29.5 ml")
        self.assertAlmostEqual(amt, 177.0)
        self.assertEqual(unit, "ml")

    def test_count_unit(self):
        result = self._parse("12 eggs")
        self.assertIsNotNone(result)
        amt, unit = result
        self.assertAlmostEqual(amt, 12.0)
        self.assertEqual(unit, "count")

    def test_empty_returns_none(self):
        self.assertIsNone(self._parse(""))

    def test_none_returns_none(self):
        self.assertIsNone(self._parse(None))

    def test_decimal_amount(self):
        amt, unit = self._parse("2.25 tsp")
        self.assertAlmostEqual(amt, 2.25)
        self.assertEqual(unit, "tsp")


# ---------------------------------------------------------------------------
# 7. Unit conversion
# ---------------------------------------------------------------------------

class TestUnitConversion(unittest.TestCase):
    def test_same_unit_volume(self):
        r, p = pr.convert_recipe_to_package_units(1.0, "cup", 236.588, "ml")
        self.assertAlmostEqual(r, 236.588, places=1)
        self.assertAlmostEqual(p, 236.588, places=1)

    def test_tsp_to_tsp(self):
        r, p = pr.convert_recipe_to_package_units(2.25, "tsp", 2.25, "tsp")
        self.assertAlmostEqual(r, p)

    def test_dry_volume_can_convert_to_mass_for_packaged_goods(self):
        r, p = pr.convert_recipe_to_package_units(1.0, "cup", 100.0, "g")
        self.assertAlmostEqual(r, 201.6, places=1)
        self.assertAlmostEqual(p, 100.0, places=1)

    def test_count_to_count(self):
        r, p = pr.convert_recipe_to_package_units(3.0, "count", 12.0, "count")
        self.assertAlmostEqual(r, 3.0)
        self.assertAlmostEqual(p, 12.0)

    def test_oz_to_oz_mass(self):
        r, p = pr.convert_recipe_to_package_units(8.0, "oz", 16.0, "oz")
        self.assertAlmostEqual(r / p, 0.5)


# ---------------------------------------------------------------------------
# 8. Package-based pricing
# ---------------------------------------------------------------------------

class TestPackagePricing(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()
        _seed(self.db)

    def tearDown(self):
        os.unlink(self.db)

    def test_yeast_one_packet(self):
        # 2.25 tsp = exactly 1 packet of yeast @ $0.75
        price = pr.get_basket_price("yeast", 2.25, "tsp", db_path=self.db)
        self.assertAlmostEqual(price, 0.75, places=2)

    def test_yeast_costs_more_than_cents(self):
        # Old heuristic gave ~$0.23 — package pricing should give $0.75+
        price = pr.get_basket_price("yeast", 2.25, "tsp", db_path=self.db)
        self.assertGreater(price, 0.50)

    def test_yeast_two_packets_needed(self):
        # 3 tsp > 2.25 tsp per packet → need 2 packets → $1.50
        price = pr.get_basket_price("yeast", 3.0, "tsp", db_path=self.db)
        self.assertAlmostEqual(price, 1.50, places=2)

    def test_eggs_whole_dozen(self):
        # Recipe needs 6 eggs; package is 12 → 1 package @ $4.49
        price = pr.get_basket_price("eggs", 6.0, "count", db_path=self.db)
        self.assertAlmostEqual(price, 4.49, places=2)

    def test_eggs_more_than_one_dozen(self):
        # 13 eggs → need 2 dozens → $8.98
        price = pr.get_basket_price("eggs", 13.0, "count", db_path=self.db)
        self.assertAlmostEqual(price, 8.98, places=2)

    def test_minimum_one_package(self):
        # Even if recipe needs a tiny amount, you still buy at least 1 package
        price = pr.get_basket_price("yeast", 0.5, "tsp", db_path=self.db)
        self.assertAlmostEqual(price, 0.75, places=2)

    def test_flour_package_pricing(self):
        # Flour: 5 lb bag @ $4.49. Recipe needs 2 cups ≈ 403g ≈ 0.89 lb → 1 bag
        price = pr.get_basket_price("flour", 2.0, "cup", db_path=self.db)
        self.assertGreater(price, 0)
        # Should cost at most 2 bags
        self.assertLessEqual(price, 8.98)

    def test_package_pricing_metadata_is_explicit(self):
        result = pr.resolve_basket_pricing("flour", 2.0, "cup", db_path=self.db)
        self.assertEqual(result["pricing_source"], "package_pricing")
        self.assertIsNone(result["fallback_reason"])
        self.assertAlmostEqual(result["estimated_price"], 4.49, places=2)
        self.assertAlmostEqual(result["package_amount"], 5.0, places=2)
        self.assertEqual(result["package_unit"], "lb")
        self.assertAlmostEqual(result["required_amount"], 2.0, places=2)
        self.assertEqual(result["required_unit"], "cup")

    def test_seeded_common_items_use_package_pricing(self):
        for item_name, qty, unit in (
            ("yeast", 2.25, "tsp"),
            ("flour", 2.0, "cup"),
            ("eggs", 6.0, "count"),
            ("olive oil", 2.0, "tbsp"),
            ("mozzarella", 8.0, "oz"),
        ):
            with self.subTest(item=item_name):
                result = pr.resolve_basket_pricing(item_name, qty, unit, db_path=self.db)
                self.assertEqual(result["pricing_source"], "package_pricing")
                self.assertIsNone(result["fallback_reason"])

    def test_common_alias_resolves_to_seeded_product(self):
        result = pr.resolve_basket_pricing("all purpose flour", 2.0, "cup", db_path=self.db)
        self.assertEqual(result["pricing_source"], "package_pricing")
        self.assertAlmostEqual(result["estimated_price"], 4.49, places=2)

    def test_salt_and_sugar_variants_use_package_pricing(self):
        cases = (
            ("kosher salt", 1.0, "tsp"),
            ("sea salt", 1.0, "tsp"),
            ("granulated sugar", 0.5, "cup"),
            ("white sugar", 2.0, "tbsp"),
            ("caster sugar", 0.25, "cup"),
        )
        for item_name, qty, unit in cases:
            with self.subTest(item=item_name):
                result = pr.resolve_basket_pricing(item_name, qty, unit, db_path=self.db)
                self.assertEqual(result["pricing_source"], "package_pricing")
                self.assertIsNone(result["fallback_reason"])
                self.assertGreater(result["estimated_price"], 1.00)

    def test_pizza_sauce_uses_seeded_package_pricing(self):
        result = pr.resolve_basket_pricing("pizza sauce", 0.5, "cup", db_path=self.db)
        self.assertEqual(result["pricing_source"], "package_pricing")
        self.assertIsNone(result["fallback_reason"])
        self.assertEqual(result["brand"], "Hunts")
        self.assertEqual(result["product_name"], "Pizza Sauce")
        self.assertAlmostEqual(result["estimated_price"], 1.79, places=2)

    def test_pizza_sauce_alias_works_even_if_primary_key_was_cached_miss(self):
        db = _tmp_db()
        try:
            product_cache.put_miss("pizza sauce", db)
            _seed(db)
            result = pr.resolve_basket_pricing("pizza sauce", 0.5, "cup", db_path=db)
            self.assertEqual(result["pricing_source"], "package_pricing")
            self.assertEqual(result["product_name"], "Pizza Sauce")
        finally:
            os.unlink(db)


# ---------------------------------------------------------------------------
# 9. Fallback when no product data available
# ---------------------------------------------------------------------------

class TestFallback(unittest.TestCase):
    def setUp(self):
        self.db = _tmp_db()
        # Empty cache — no seeds

    def tearDown(self):
        os.unlink(self.db)

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_fallback_returns_nonzero_price(self, _s, _p):
        # Should fall back to heuristic and return something sensible
        price = pr.get_basket_price("chicken breast", 1.0, "lb", db_path=self.db)
        self.assertGreater(price, 0.0)

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_fallback_pricing_source_and_reason_are_exposed(self, _s, _p):
        result = pr.resolve_basket_pricing("completely unknown ingredient xyz", 1.0, "", db_path=self.db)
        self.assertEqual(result["pricing_source"], "fallback_fractional_pricing")
        self.assertEqual(result["fallback_reason"], "no_product_match")
        self.assertEqual(result["required_amount"], 1.0)
        self.assertEqual(result["required_unit"], "")

    def test_unit_conversion_failure_is_visible(self):
        _seed(self.db)
        result = pr.resolve_basket_pricing("flour", 1.0, "count", db_path=self.db)
        self.assertEqual(result["pricing_source"], "fallback_fractional_pricing")
        self.assertEqual(result["fallback_reason"], "unit_conversion_failed")
        self.assertAlmostEqual(result["package_amount"], 5.0, places=2)
        self.assertEqual(result["package_unit"], "lb")

    @patch("app.services.off_client.pick_best_candidate", return_value=None)
    @patch("app.services.off_client.search_product", return_value=[])
    def test_fallback_does_not_raise(self, _s, _p):
        # Should never raise regardless of input
        try:
            pr.get_basket_price("completely unknown ingredient xyz", 1.0, "", db_path=self.db)
        except Exception as e:
            self.fail(f"get_basket_price raised unexpectedly: {e}")


# ---------------------------------------------------------------------------
# 10. Ingredient key normalisation
# ---------------------------------------------------------------------------

class TestNormalizeKey(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(pr.normalize_ingredient_key("FLOUR"), "flour")

    def test_strips_whitespace(self):
        self.assertEqual(pr.normalize_ingredient_key("  eggs  "), "eggs")

    def test_collapses_internal_spaces(self):
        self.assertEqual(pr.normalize_ingredient_key("olive  oil"), "olive oil")

    def test_mixed(self):
        self.assertEqual(pr.normalize_ingredient_key("  Bread  Flour  "), "bread flour")


class TestCartTotals(unittest.TestCase):
    def test_cart_total_sums_package_prices_without_quantity_multiplier(self):
        cart = Cart(items=[
            CartItem(item="flour", quantity=2.0, unit="cup", estimated_price=4.49),
            CartItem(item="eggs", quantity=6.0, unit="count", estimated_price=4.49),
        ])
        self.assertAlmostEqual(cart.total, 8.98, places=2)


if __name__ == "__main__":
    unittest.main()
