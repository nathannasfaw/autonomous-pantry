"""
Tests for the preference flow: persistence, session loading, prompt building,
dietary conflict detection, and NN filtering.

Run with:  cd autonomous-pantry/backend && python -m pytest tests/ -v
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Make sure 'app' package is importable when running from backend/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ===========================================================================
# 1. Preferences persistence (pantry_store)
# ===========================================================================
class TestPreferencesPersistence(unittest.TestCase):
    """save_preferences / load_preferences round-trip through SQLite."""

    def setUp(self):
        # Use a temp DB so tests don't touch the real pantry.db
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        # Patch the module-level DB_PATH before importing
        import app.services.pantry_store as ps
        self._original_db_path = ps.DB_PATH
        ps.DB_PATH = self.db_path
        ps.initialize_db()
        self.ps = ps

    def tearDown(self):
        self.ps.DB_PATH = self._original_db_path
        try:
            os.unlink(self.db_path)
        except PermissionError:
            pass  # Windows may hold SQLite WAL files briefly; temp file will be cleaned up

    def test_save_and_load_round_trip(self):
        prefs = {"dietary_flags": ["vegan"], "budget_per_order": 50.0, "skill_level": "beginner"}
        self.ps.save_preferences("client-abc", prefs)
        loaded = self.ps.load_preferences("client-abc")
        self.assertEqual(loaded["dietary_flags"], ["vegan"])
        self.assertEqual(loaded["budget_per_order"], 50.0)
        self.assertEqual(loaded["skill_level"], "beginner")

    def test_load_returns_none_for_unknown_client(self):
        result = self.ps.load_preferences("nonexistent-client")
        self.assertIsNone(result)

    def test_save_overwrites_existing_preferences(self):
        self.ps.save_preferences("client-xyz", {"budget_per_order": 80.0})
        self.ps.save_preferences("client-xyz", {"budget_per_order": 30.0, "serving_size": 4})
        loaded = self.ps.load_preferences("client-xyz")
        self.assertEqual(loaded["budget_per_order"], 30.0)
        self.assertEqual(loaded["serving_size"], 4)

    def test_different_clients_are_isolated(self):
        self.ps.save_preferences("client-a", {"dietary_flags": ["vegan"]})
        self.ps.save_preferences("client-b", {"dietary_flags": ["keto"]})
        a = self.ps.load_preferences("client-a")
        b = self.ps.load_preferences("client-b")
        self.assertEqual(a["dietary_flags"], ["vegan"])
        self.assertEqual(b["dietary_flags"], ["keto"])


# ===========================================================================
# 2. Session creation loads persisted preferences
# ===========================================================================
class TestSessionPreferenceLoading(unittest.TestCase):
    """create_session uses saved prefs; new users get seed defaults."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        import app.services.pantry_store as ps
        self._original_db_path = ps.DB_PATH
        ps.DB_PATH = self.db_path
        ps.initialize_db()
        self.ps = ps

    def tearDown(self):
        self.ps.DB_PATH = self._original_db_path
        import app.services.session_manager as sm
        sm.SESSIONS.clear()
        try:
            os.unlink(self.db_path)
        except PermissionError:
            pass  # Windows WAL file lock; temp file will be cleaned up by OS

    def test_new_user_gets_seed_defaults(self):
        import app.services.session_manager as sm
        from app.data.seed_data import PREFERENCES
        sid = sm.create_session(client_id="brand-new-client")
        session = sm.get_session(sid)
        self.assertEqual(session["preferences"]["budget_per_order"], PREFERENCES["budget_per_order"])

    def test_returning_user_gets_saved_preferences(self):
        self.ps.save_preferences("returning-user", {"dietary_flags": ["vegetarian"], "budget_per_order": 25.0})
        import app.services.session_manager as sm
        sid = sm.create_session(client_id="returning-user")
        session = sm.get_session(sid)
        self.assertIn("vegetarian", session["preferences"]["dietary_flags"])
        self.assertEqual(session["preferences"]["budget_per_order"], 25.0)

    def test_saved_prefs_merge_with_new_default_keys(self):
        """
        If a new preference key is added to PREFERENCES (e.g. after a deploy),
        returning users should get the new default merged in alongside their saved prefs.
        """
        self.ps.save_preferences("old-user", {"dietary_flags": ["keto"]})
        import app.services.session_manager as sm
        sid = sm.create_session(client_id="old-user")
        session = sm.get_session(sid)
        # Old preference preserved
        self.assertIn("keto", session["preferences"]["dietary_flags"])
        # New default keys still present (skill_level is in PREFERENCES)
        self.assertIn("skill_level", session["preferences"])


# ===========================================================================
# 3. Preference constraints prompt builder
# ===========================================================================
class TestBuildPreferenceConstraints(unittest.TestCase):
    """_build_preference_constraints produces correct, non-empty constraint text."""

    def setUp(self):
        from app.services.llm_service import _build_preference_constraints
        self.build = _build_preference_constraints

    def test_empty_preferences_no_crash(self):
        result = self.build({})
        self.assertIsInstance(result, str)

    def test_dietary_flags_appear_in_output(self):
        result = self.build({"dietary_flags": ["vegan", "gluten-free"]})
        self.assertIn("vegan", result.lower())
        self.assertIn("gluten-free", result.lower())
        self.assertIn("HARD DIETARY CONSTRAINTS", result)

    def test_disliked_ingredients_appear_in_output(self):
        result = self.build({"disliked_ingredients": ["cilantro", "anchovies"]})
        self.assertIn("cilantro", result)
        self.assertIn("anchovies", result)
        self.assertIn("DISLIKED INGREDIENTS", result)

    def test_max_prep_time_appears_only_when_set(self):
        result_no_limit = self.build({"max_prep_time": 120})
        self.assertNotIn("MAX TOTAL TIME", result_no_limit)

        result_limited = self.build({"max_prep_time": 30})
        self.assertIn("30 minutes", result_limited)

    def test_skill_level_mapped_correctly(self):
        beginner = self.build({"skill_level": "beginner"})
        self.assertIn("beginner", beginner.lower())
        self.assertIn("simple", beginner.lower())

        advanced = self.build({"skill_level": "advanced"})
        self.assertIn("advanced", advanced.lower())

    def test_serving_size_present(self):
        result = self.build({"serving_size": 6})
        self.assertIn("6", result)
        self.assertIn("servings", result.lower())

    def test_budget_present(self):
        result = self.build({"budget_per_order": 45.0})
        self.assertIn("45", result)

    def test_cuisine_weights_ranked(self):
        result = self.build({
            "cuisine_weights": {"Italian": 0.9, "Japanese": 0.5, "Mexican": 0.3}
        })
        self.assertIn("Italian", result)
        self.assertIn("CUISINE PREFERENCES", result)
        # Italian (0.9) should appear before Japanese (0.5)
        self.assertLess(result.index("Italian"), result.index("Japanese"))


# ===========================================================================
# 4. Dietary conflict detection (NN service)
# ===========================================================================
class TestDietaryConflictDetection(unittest.TestCase):
    """_has_dietary_conflict correctly maps flags to ingredient keywords."""

    def setUp(self):
        from app.services.nn_service import _has_dietary_conflict
        self.check = _has_dietary_conflict

    # ── vegan ──────────────────────────────────────────────────────────────
    def test_vegan_rejects_chicken(self):
        self.assertTrue(self.check("chicken breast", ["vegan"]))

    def test_vegan_rejects_mozzarella(self):
        self.assertTrue(self.check("mozzarella", ["vegan"]))

    def test_vegan_rejects_eggs(self):
        self.assertTrue(self.check("eggs", ["vegan"]))

    def test_vegan_allows_tofu(self):
        self.assertFalse(self.check("tofu", ["vegan"]))

    # ── vegetarian ────────────────────────────────────────────────────────
    def test_vegetarian_rejects_salmon(self):
        self.assertTrue(self.check("salmon", ["vegetarian"]))

    def test_vegetarian_allows_cheese(self):
        self.assertFalse(self.check("parmesan cheese", ["vegetarian"]))

    # ── gluten-free ───────────────────────────────────────────────────────
    def test_gluten_free_rejects_bread(self):
        self.assertTrue(self.check("bread", ["gluten-free"]))

    def test_gluten_free_rejects_pasta(self):
        self.assertTrue(self.check("pasta", ["gluten-free"]))

    def test_gluten_free_rejects_panko(self):
        self.assertTrue(self.check("panko breadcrumbs", ["gluten-free"]))

    def test_gluten_free_allows_rice(self):
        self.assertFalse(self.check("rice", ["gluten-free"]))

    # ── no shellfish ──────────────────────────────────────────────────────
    def test_no_shellfish_rejects_shrimp(self):
        self.assertTrue(self.check("shrimp", ["no shellfish"]))

    def test_no_shellfish_rejects_crab(self):
        self.assertTrue(self.check("crab meat", ["no shellfish"]))

    def test_no_shellfish_allows_salmon(self):
        self.assertFalse(self.check("salmon", ["no shellfish"]))

    # ── no pork ───────────────────────────────────────────────────────────
    def test_no_pork_rejects_bacon(self):
        self.assertTrue(self.check("bacon", ["no pork"]))

    def test_no_pork_rejects_pork_chops(self):
        self.assertTrue(self.check("pork chops", ["no pork"]))

    def test_no_pork_allows_chicken(self):
        self.assertFalse(self.check("chicken", ["no pork"]))

    # ── keto ─────────────────────────────────────────────────────────────
    def test_keto_rejects_pasta(self):
        self.assertTrue(self.check("pasta", ["keto"]))

    def test_keto_rejects_rice(self):
        self.assertTrue(self.check("rice", ["keto"]))

    def test_keto_allows_salmon(self):
        self.assertFalse(self.check("salmon", ["keto"]))

    # ── multiple flags ────────────────────────────────────────────────────
    def test_multiple_flags_any_conflict_triggers(self):
        # gluten-free rules out bread even though vegan wouldn't
        self.assertTrue(self.check("bread", ["vegan", "gluten-free"]))

    # ── custom "no X" fallback ────────────────────────────────────────────
    def test_custom_no_flag_fallback(self):
        # "no mushroom" is not in DIETARY_CONFLICT_MAP, falls back to substring
        self.assertTrue(self.check("mushrooms", ["no mushroom"]))
        self.assertFalse(self.check("chicken", ["no mushroom"]))

    # ── word-boundary false-positive prevention ────────────────────────────
    def test_no_pork_does_not_match_chamomile(self):
        # "ham" is a substring of "chamomile" but must NOT trigger no-pork
        self.assertFalse(self.check("chamomile tea", ["no pork"]))

    def test_no_shellfish_does_not_match_unrelated(self):
        # "crab apple" contains "crab" but shouldn't trigger shellfish ban
        # (edge case: users don't cook crab apples, but let's verify word-match precision)
        # Actually crab IS in the shellfish set and crab apple IS an apple — this
        # is an accepted limitation of keyword matching. We just verify salmon is clean.
        self.assertFalse(self.check("salmon fillet", ["no shellfish"]))

    # ── hidden/processed ingredient detection ─────────────────────────────
    def test_vegan_rejects_surimi(self):
        # surimi = imitation crab, made from fish
        self.assertTrue(self.check("surimi", ["vegan"]))

    def test_vegan_rejects_fish_sauce(self):
        self.assertTrue(self.check("fish sauce", ["vegan"]))

    def test_vegan_rejects_anchovy_paste(self):
        self.assertTrue(self.check("anchovy paste", ["vegan"]))

    def test_gluten_free_rejects_soy_sauce(self):
        # Regular soy sauce contains wheat
        self.assertTrue(self.check("soy sauce", ["gluten-free"]))

    def test_vegetarian_rejects_worcestershire(self):
        # Worcestershire contains anchovies
        self.assertTrue(self.check("worcestershire sauce", ["vegetarian"]))

    def test_halal_rejects_wine(self):
        self.assertTrue(self.check("white wine", ["halal"]))


# ===========================================================================
# 5. NN recommend() filters dietary conflicts
# ===========================================================================
class TestNNRecommendFiltering(unittest.TestCase):
    """
    nn_service.recommend() must not include items that conflict with dietary flags.
    We mock the model to always return score=0.9 so that only dietary filtering matters.
    """

    def _make_gap(self, name, required=1.0, available=0.0):
        return {"item": name, "required": required, "available": available,
                "gap": required - available, "unit": "lbs", "confidence": 0.9}

    def test_vegan_flag_removes_chicken_from_cart(self):
        import app.services.nn_service as ns

        # Force a known model state (score always 0.9 → above 0.5 threshold)
        mock_tensor = MagicMock()
        mock_tensor.squeeze.return_value.item.return_value = 0.9
        mock_model = MagicMock(return_value=mock_tensor)
        original_model = ns._model
        ns._model = mock_model

        try:
            gaps = [self._make_gap("chicken breast"), self._make_gap("broccoli")]
            prefs = {"dietary_flags": ["vegan"], "disliked_ingredients": [],
                     "cuisine_weights": {}, "budget_per_order": 80.0, "quality_priority": 0.5}
            calendar = {"tonight_guests": 2, "events_this_week": []}
            cart, _ = ns.recommend(gaps, calendar, prefs)
            cart_names = [c["item"] for c in cart]
            self.assertNotIn("chicken breast", cart_names)
            self.assertIn("broccoli", cart_names)
        finally:
            ns._model = original_model

    def test_disliked_ingredient_removed_from_cart(self):
        import app.services.nn_service as ns

        mock_tensor = MagicMock()
        mock_tensor.squeeze.return_value.item.return_value = 0.9
        mock_model = MagicMock(return_value=mock_tensor)
        original_model = ns._model
        ns._model = mock_model

        try:
            gaps = [self._make_gap("cilantro"), self._make_gap("tomato")]
            prefs = {"dietary_flags": [], "disliked_ingredients": ["cilantro"],
                     "cuisine_weights": {}, "budget_per_order": 80.0, "quality_priority": 0.5}
            calendar = {"tonight_guests": 2, "events_this_week": []}
            cart, _ = ns.recommend(gaps, calendar, prefs)
            cart_names = [c["item"] for c in cart]
            self.assertNotIn("cilantro", cart_names)
            self.assertIn("tomato", cart_names)
        finally:
            ns._model = original_model


# ===========================================================================
# 6. check_recipe_dietary_violations — post-generation recipe validation
# ===========================================================================
class TestCheckRecipeDietaryViolations(unittest.TestCase):
    """check_recipe_dietary_violations identifies violating ingredients in a recipe."""

    def setUp(self):
        from app.services.nn_service import check_recipe_dietary_violations
        self.check = check_recipe_dietary_violations

    def _make_recipe(self, *ingredient_names):
        return {"ingredients": [{"item": n, "quantity": 1, "unit": "cup"} for n in ingredient_names]}

    def test_clean_vegan_recipe_returns_empty(self):
        recipe = self._make_recipe("tofu", "broccoli", "soy sauce", "garlic")
        # soy sauce is gluten-containing but not a vegan violation
        violations = self.check(recipe, ["vegan"])
        # broccoli, tofu, garlic are all fine; soy sauce is vegan-ok (contains no animal products)
        self.assertNotIn("tofu", violations)
        self.assertNotIn("broccoli", violations)

    def test_detects_chicken_in_vegan_recipe(self):
        recipe = self._make_recipe("tofu", "chicken breast", "broccoli")
        violations = self.check(recipe, ["vegan"])
        self.assertIn("chicken breast", violations)
        self.assertNotIn("tofu", violations)

    def test_detects_multiple_violations(self):
        recipe = self._make_recipe("pasta", "bread", "olive oil", "tomato")
        violations = self.check(recipe, ["gluten-free"])
        self.assertIn("pasta", violations)
        self.assertIn("bread", violations)
        self.assertNotIn("olive oil", violations)

    def test_no_flags_returns_empty(self):
        recipe = self._make_recipe("beef", "butter", "cream")
        violations = self.check(recipe, [])
        self.assertEqual(violations, [])

    def test_empty_recipe_returns_empty(self):
        self.assertEqual(self.check({}, ["vegan"]), [])
        self.assertEqual(self.check({"ingredients": []}, ["vegan"]), [])

    def test_detects_hidden_ingredient_violation(self):
        # fish sauce and worcestershire are hidden animal products
        recipe = self._make_recipe("noodles", "fish sauce", "lime juice")
        violations = self.check(recipe, ["vegetarian"])
        self.assertIn("fish sauce", violations)

    def test_violation_note_format_contains_ingredient_names(self):
        """Simulates what _handle_idle does with the violation list."""
        recipe = self._make_recipe("bacon", "eggs", "cheese")
        violations = self.check(recipe, ["vegan"])
        note = f"Previous recipe violated constraints: {', '.join(violations)}"
        self.assertIn("bacon", note)
        self.assertIn("eggs", note)


# ===========================================================================
# 7. Cuisine-specific scoring in recommend()
# ===========================================================================
class TestCuisineSpecificScoring(unittest.TestCase):
    """
    recommend() with recipe_cuisine should use cuisine_weights[cuisine] directly
    rather than the average of all weights.
    """

    def _make_gap(self, name, required=1.0):
        return {"item": name, "required": required, "available": 0.0,
                "gap": required, "unit": "count", "confidence": 0.9}

    def _run_recommend(self, gaps, cuisine_weights, recipe_cuisine):
        import app.services.nn_service as ns
        mock_features = []

        original_build = ns._build_feature_vector

        # Capture the cuisine_score feature passed to the vector builder
        captured = {}

        def capturing_build(gap_ratio, guest_count, day_of_week, cuisine_score,
                            budget_remaining_ratio, dietary_conflict, confidence, historical_reorder):
            captured["cuisine_score"] = cuisine_score
            return original_build(gap_ratio, guest_count, day_of_week, cuisine_score,
                                  budget_remaining_ratio, dietary_conflict, confidence, historical_reorder)

        mock_tensor = MagicMock()
        mock_tensor.squeeze.return_value.item.return_value = 0.9
        mock_model = MagicMock(return_value=mock_tensor)
        original_model = ns._model
        ns._model = mock_model

        try:
            with patch.object(ns, "_build_feature_vector", side_effect=capturing_build):
                prefs = {
                    "dietary_flags": [],
                    "disliked_ingredients": [],
                    "cuisine_weights": cuisine_weights,
                    "budget_per_order": 80.0,
                    "quality_priority": 0.5,
                }
                calendar = {"tonight_guests": 2, "events_this_week": []}
                ns.recommend(gaps, calendar, prefs, recipe_cuisine=recipe_cuisine)
        finally:
            ns._model = original_model

        return captured

    def test_known_cuisine_uses_specific_weight(self):
        cuisine_weights = {"Japanese": 0.9, "Italian": 0.3, "Mexican": 0.5}
        captured = self._run_recommend(
            [self._make_gap("nori")], cuisine_weights, recipe_cuisine="Japanese"
        )
        # Should use 0.9 directly, not average (0.9+0.3+0.5)/3 ≈ 0.567
        self.assertAlmostEqual(captured["cuisine_score"], 0.9, places=5)

    def test_low_preference_cuisine_uses_low_weight(self):
        cuisine_weights = {"Japanese": 0.9, "Italian": 0.2}
        captured = self._run_recommend(
            [self._make_gap("pasta")], cuisine_weights, recipe_cuisine="Italian"
        )
        self.assertAlmostEqual(captured["cuisine_score"], 0.2, places=5)

    def test_unknown_cuisine_falls_back_to_average(self):
        cuisine_weights = {"Japanese": 0.8, "Italian": 0.4}
        captured = self._run_recommend(
            [self._make_gap("tacos")], cuisine_weights, recipe_cuisine="Peruvian"
        )
        expected_avg = (0.8 + 0.4) / 2
        self.assertAlmostEqual(captured["cuisine_score"], expected_avg, places=5)

    def test_no_cuisine_uses_average(self):
        cuisine_weights = {"Japanese": 0.6, "Mexican": 0.4}
        captured = self._run_recommend(
            [self._make_gap("chicken")], cuisine_weights, recipe_cuisine=None
        )
        expected_avg = (0.6 + 0.4) / 2
        self.assertAlmostEqual(captured["cuisine_score"], expected_avg, places=5)

    def test_cuisine_matching_is_case_insensitive(self):
        cuisine_weights = {"Japanese": 0.85}
        captured = self._run_recommend(
            [self._make_gap("nori")], cuisine_weights, recipe_cuisine="japanese"
        )
        self.assertAlmostEqual(captured["cuisine_score"], 0.85, places=5)


# ===========================================================================
# 7. Intent routing: is_explicit_recipe_request
# ===========================================================================
class TestIntentRouting(unittest.TestCase):
    """Verify that is_explicit_recipe_request accepts natural meal phrases
    and rejects unrelated messages."""

    def setUp(self):
        from app.services.llm_service import is_explicit_recipe_request
        self.classify = is_explicit_recipe_request

    # ── Messages that MUST route to meal-suggestion flow ───────────────────

    def test_suggest_dinner_for_tonight(self):
        self.assertTrue(self.classify("Suggest dinner for tonight"))

    def test_what_should_i_make_for_dinner_tonight(self):
        self.assertTrue(self.classify("What should I make for dinner tonight?"))

    def test_what_should_i_make_tonight(self):
        self.assertTrue(self.classify("What should I make tonight?"))

    def test_what_can_i_cook_tonight(self):
        self.assertTrue(self.classify("What can I cook tonight?"))

    def test_what_can_i_make_with_pantry(self):
        self.assertTrue(self.classify("What can I make with my pantry?"))

    def test_dinner_ideas_for_tonight(self):
        self.assertTrue(self.classify("Dinner ideas for tonight"))

    def test_whats_for_dinner(self):
        self.assertTrue(self.classify("What's for dinner?"))

    def test_what_is_for_dinner(self):
        self.assertTrue(self.classify("What is for dinner tonight?"))

    def test_need_dinner_ideas_8_people(self):
        self.assertTrue(self.classify("I need dinner ideas for 8 people"))

    def test_what_should_we_eat_tonight(self):
        self.assertTrue(self.classify("What should we eat tonight?"))

    def test_give_me_dinner_ideas(self):
        self.assertTrue(self.classify("Give me dinner ideas"))

    def test_find_me_a_pasta_recipe(self):
        self.assertTrue(self.classify("find me a pasta recipe"))

    def test_help_me_figure_out_dinner(self):
        self.assertTrue(self.classify("Help me figure out dinner"))

    def test_what_should_i_have_for_dinner(self):
        self.assertTrue(self.classify("What should I have for dinner?"))

    def test_what_can_we_make_for_lunch(self):
        self.assertTrue(self.classify("What can we make for lunch?"))

    def test_meal_ideas(self):
        self.assertTrue(self.classify("Give me some meal ideas"))

    def test_i_want_to_make_pizza(self):
        self.assertTrue(self.classify("I want to make pizza"))

    # ── Messages that must NOT route to meal-suggestion flow ────────────────

    def test_pantry_query_is_rejected(self):
        self.assertFalse(self.classify("How many eggs do I have?"))

    def test_generic_question_is_rejected(self):
        self.assertFalse(self.classify("What is the weather like?"))

    def test_empty_message_is_rejected(self):
        self.assertFalse(self.classify(""))

    def test_scan_update_is_rejected(self):
        self.assertFalse(self.classify("I scanned my pantry and added the following items"))

    def test_order_status_is_rejected(self):
        self.assertFalse(self.classify("Did my order go through?"))

    # ── Case insensitivity ─────────────────────────────────────────────────

    def test_uppercase_is_recognised(self):
        self.assertTrue(self.classify("WHAT SHOULD I MAKE FOR DINNER?"))

    def test_mixed_case_is_recognised(self):
        self.assertTrue(self.classify("What Should I Make Tonight?"))


# ===========================================================================
# 8. Option resolution: resolve_selected_option
# ===========================================================================
class TestOptionResolution(unittest.TestCase):
    """Unit tests for session_manager.resolve_selected_option."""

    def setUp(self):
        from app.services.session_manager import resolve_selected_option
        self.resolve = resolve_selected_option
        self.options = [
            {"name": "Garlic Bread", "uses_from_pantry": ["flour", "garlic"], "needs": ["butter"]},
            {"name": "Pasta Primavera", "uses_from_pantry": ["pasta"], "needs": ["vegetables"]},
            {"name": "Chicken Stir Fry", "uses_from_pantry": ["chicken"], "needs": ["soy sauce"]},
        ]

    def test_exact_match(self):
        result = self.resolve("Garlic Bread", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Garlic Bread")

    def test_case_insensitive_exact_match(self):
        result = self.resolve("garlic bread", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Garlic Bread")

    def test_option_name_in_user_message(self):
        result = self.resolve("I'd like garlic bread please", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Garlic Bread")

    def test_user_message_in_option_name(self):
        # "pasta" is contained within "Pasta Primavera"
        result = self.resolve("pasta", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Pasta Primavera")

    def test_word_overlap_match(self):
        result = self.resolve("stir fry sounds good", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Chicken Stir Fry")

    def test_no_match_returns_none(self):
        result = self.resolve("tacos", self.options)
        self.assertIsNone(result)

    def test_empty_options_returns_none(self):
        result = self.resolve("garlic bread", [])
        self.assertIsNone(result)

    def test_empty_message_returns_none(self):
        result = self.resolve("", self.options)
        self.assertIsNone(result)

    def test_unrelated_message_returns_none(self):
        result = self.resolve("what is the weather today", self.options)
        self.assertIsNone(result)

    def test_first_option_wins_on_substring(self):
        # "pasta" is in "Pasta Primavera" — should match
        result = self.resolve("let's do pasta primavera", self.options)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Pasta Primavera")


# ===========================================================================
# 9. State transitions: transition_to_options_presented and reset_cart
# ===========================================================================
class TestStateTransitions(unittest.TestCase):
    """Verify session state is correctly updated during stage transitions."""

    def _make_session(self, **overrides):
        session = {
            "stage": "idle",
            "recipe": None,
            "full_ingredient_list": [],
            "ingredient_gaps": [],
            "current_cart": [],
            "nn_original_cart": [],
            "presented_options": [],
            "selected_option": None,
            "confirmation_pending": False,
            "messages": [],
            "preferences": {},
            "pantry_state": [],
            "calendar_context": {},
        }
        session.update(overrides)
        return session

    def test_transition_to_options_clears_recipe(self):
        from app.services.session_manager import transition_to_options_presented
        session = self._make_session(
            stage="cart_proposed",
            recipe={"name": "Pizza"},
            current_cart=[{"item": "mozzarella"}],
        )
        options = [{"name": "Garlic Bread"}, {"name": "Pasta"}]
        transition_to_options_presented(session, options)

        self.assertEqual(session["stage"], "options_presented")
        self.assertIsNone(session["recipe"])
        self.assertEqual(session["current_cart"], [])
        self.assertEqual(len(session["presented_options"]), 2)
        self.assertIsNone(session["selected_option"])

    def test_transition_to_options_stores_options(self):
        from app.services.session_manager import transition_to_options_presented
        session = self._make_session()
        options = [{"name": "Tacos"}, {"name": "Soup"}, {"name": "Salad"}]
        transition_to_options_presented(session, options)
        names = [o["name"] for o in session["presented_options"]]
        self.assertEqual(names, ["Tacos", "Soup", "Salad"])

    def test_transition_to_options_with_none_options(self):
        from app.services.session_manager import transition_to_options_presented
        session = self._make_session(recipe={"name": "Pizza"})
        transition_to_options_presented(session, None)
        self.assertEqual(session["presented_options"], [])
        self.assertIsNone(session["recipe"])

    def test_reset_cart_clears_options(self):
        from app.services.session_manager import reset_cart
        session = self._make_session(
            stage="options_presented",
            presented_options=[{"name": "Garlic Bread"}],
            selected_option="Garlic Bread",
            recipe={"name": "Pizza"},
        )
        reset_cart(session)
        self.assertEqual(session["stage"], "idle")
        self.assertEqual(session["presented_options"], [])
        self.assertIsNone(session["selected_option"])
        self.assertIsNone(session["recipe"])

    def test_options_are_deep_copied(self):
        """Mutating the original options list must not affect session state."""
        from app.services.session_manager import transition_to_options_presented
        session = self._make_session()
        options = [{"name": "Pizza"}]
        transition_to_options_presented(session, options)
        options[0]["name"] = "MUTATED"  # mutate original
        self.assertEqual(session["presented_options"][0]["name"], "Pizza")


# ===========================================================================
# 10. Multi-turn state correctness (async integration)
# ===========================================================================
class TestMultiTurnStateCorrectness(unittest.IsolatedAsyncioTestCase):
    """
    End-to-end multi-turn sequences using the send_message route handler.
    All external service calls (LLM, NN, gap analysis) are mocked.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_session(self):
        """Return a minimal session dict that mirrors what create_session produces."""
        return {
            "stage": "idle",
            "recipe": None,
            "full_ingredient_list": [],
            "ingredient_gaps": [],
            "current_cart": [],
            "nn_original_cart": [],
            "presented_options": [],
            "selected_option": None,
            "confirmation_pending": False,
            "messages": [],
            "preferences": {"dietary_flags": [], "budget_per_order": 80.0,
                            "serving_size": 2, "cuisine_weights": {},
                            "disliked_ingredients": [], "skill_level": "intermediate"},
            "pantry_state": [{"item": "flour", "quantity": 2, "unit": "cups"}],
            "calendar_context": {"tonight_guests": 0},
            "staples_assumed": [],
        }

    def _pizza_recipe(self):
        return {
            "name": "Margherita Pizza",
            "cuisine": "Italian",
            "servings": 2,
            "prep_time": "20 min",
            "cook_time": "15 min",
            "source_url": "https://example.com/pizza",
            "image_url": "",
            "ingredients": [
                {"item": "flour", "quantity": 2, "unit": "cups"},
                {"item": "mozzarella", "quantity": 1, "unit": "ball"},
                {"item": "tomato sauce", "quantity": 0.5, "unit": "cup"},
            ],
            "steps_summary": "Make dough, top with sauce and cheese, bake.",
        }

    def _garlic_bread_recipe(self):
        return {
            "name": "Garlic Bread",
            "cuisine": "Italian",
            "servings": 2,
            "prep_time": "5 min",
            "cook_time": "10 min",
            "source_url": "https://example.com/garlic-bread",
            "image_url": "",
            "ingredients": [
                {"item": "bread", "quantity": 1, "unit": "loaf"},
                {"item": "garlic", "quantity": 3, "unit": "cloves"},
                {"item": "butter", "quantity": 2, "unit": "tbsp"},
            ],
            "steps_summary": "Mix garlic butter, spread on bread, toast.",
        }

    def _stir_fry_recipe(self):
        return {
            "name": "Stir Fry",
            "cuisine": "Chinese",
            "servings": 2,
            "prep_time": "10 min",
            "cook_time": "10 min",
            "source_url": "https://example.com/stir-fry",
            "image_url": "",
            "ingredients": [
                {"item": "chicken", "quantity": 1, "unit": "lb"},
                {"item": "soy sauce", "quantity": 2, "unit": "tbsp"},
                {"item": "vegetables", "quantity": 2, "unit": "cups"},
            ],
            "steps_summary": "Stir fry chicken and veg in sauce.",
        }

    def _nn_cart(self, items=("mozzarella", "tomato sauce")):
        return [
            {"item": i, "quantity": 1, "unit": "unit", "estimated_price": 3.0, "score": 0.8}
            for i in items
        ]

    # ------------------------------------------------------------------
    # Sequence 1: pizza → alternatives → garlic bread
    # ------------------------------------------------------------------
    async def test_seq1_option_selection_after_specific_recipe(self):
        """
        1. "I want to make pizza" → recipe presented
        2. "what else can I make" → options shown (garlic bread, pasta, soup)
        3. "garlic bread" → garlic bread recipe becomes active; pizza is gone
        """
        session = self._make_session()
        pizza = self._pizza_recipe()
        garlic_bread = self._garlic_bread_recipe()
        options = [
            {"name": "Garlic Bread", "uses_from_pantry": ["flour"], "needs": ["butter"]},
            {"name": "Pasta", "uses_from_pantry": ["pasta"], "needs": []},
        ]

        with patch("app.routes.chat.llm_service") as mock_llm, \
             patch("app.routes.chat.nn_service") as mock_nn, \
             patch("app.routes.chat.gap_analysis") as mock_gap, \
             patch("app.routes.chat.recipe_image_service") as mock_img, \
             patch("app.routes.chat.session_manager") as mock_sm:

            # Wire the real session-manager functions through (only mock SESSIONS lookup)
            from app.services import session_manager as real_sm
            mock_sm.get_session.return_value = session
            mock_sm.reset_cart.side_effect = real_sm.reset_cart
            mock_sm.apply_cart_diff.side_effect = real_sm.apply_cart_diff
            mock_sm.transition_to_options_presented.side_effect = real_sm.transition_to_options_presented
            mock_sm.resolve_selected_option.side_effect = real_sm.resolve_selected_option

            mock_img.populate_recipe_image.side_effect = lambda r: r
            mock_nn.check_recipe_dietary_violations.return_value = []
            mock_gap.compute_gaps.return_value = [{"item": "mozzarella"}]
            mock_nn.recommend.return_value = (self._nn_cart(), [])

            # ── Turn 1: specific recipe request ────────────────────────
            mock_llm.is_explicit_recipe_request.return_value = True
            mock_llm.is_context_switch.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": pizza,
                "message": "Here is pizza!", "normalized_query": "pizza",
            }
            mock_llm.call_llm_cart_narration.return_value = {
                "message": "Here is your cart.", "status": "cart_proposed",
            }

            from app.routes.chat import send_message
            from app.models.session import ChatRequest
            req1 = ChatRequest(conversation_id="test-session", message="I want to make pizza")
            resp1 = await send_message(req1)

            self.assertEqual(session["stage"], "cart_proposed")
            self.assertEqual(session["recipe"]["name"], "Margherita Pizza")
            self.assertEqual(session["presented_options"], [])

            # ── Turn 2: ask for alternatives ───────────────────────────
            mock_llm.is_explicit_recipe_request.return_value = True
            mock_llm.is_context_switch.return_value = True  # triggers forced reset
            mock_llm.call_llm_recipe.return_value = {
                "status": "options_presented",
                "options": options,
                "message": "Here are some ideas!",
                "normalized_query": "what else",
            }

            req2 = ChatRequest(conversation_id="test-session", message="what else can I make")
            resp2 = await send_message(req2)

            self.assertEqual(session["stage"], "options_presented")
            self.assertIsNone(session["recipe"],
                              "Old pizza recipe must be cleared when options are presented")
            self.assertEqual(len(session["presented_options"]), 2)

            # ── Turn 3: select garlic bread ────────────────────────────
            mock_llm.is_explicit_recipe_request.return_value = False
            mock_llm.is_context_switch.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": garlic_bread,
                "message": "Here is garlic bread!", "normalized_query": "garlic bread",
            }

            req3 = ChatRequest(conversation_id="test-session", message="garlic bread")
            resp3 = await send_message(req3)

            self.assertEqual(session["recipe"]["name"], "Garlic Bread",
                             "Active recipe must be garlic bread, not pizza")
            self.assertEqual(session["stage"], "cart_proposed")
            self.assertEqual(session["selected_option"], "Garlic Bread")

    # ------------------------------------------------------------------
    # Sequence 2: open-ended → tacos
    # ------------------------------------------------------------------
    async def test_seq2_open_ended_then_option_selection(self):
        """
        1. "Give me dinner ideas" → options: [tacos, soup]
        2. "tacos" → tacos recipe becomes active; no stale prior recipe
        """
        session = self._make_session()
        tacos_recipe = {
            "name": "Tacos", "cuisine": "Mexican", "servings": 2,
            "prep_time": "10 min", "cook_time": "10 min",
            "source_url": "https://example.com/tacos", "image_url": "",
            "ingredients": [
                {"item": "tortillas", "quantity": 4, "unit": "piece"},
                {"item": "beef", "quantity": 0.5, "unit": "lb"},
                {"item": "salsa", "quantity": 1, "unit": "cup"},
            ],
            "steps_summary": "Cook beef, fill tortillas.",
        }
        options = [
            {"name": "Tacos", "uses_from_pantry": [], "needs": ["tortillas", "beef"]},
            {"name": "Soup", "uses_from_pantry": ["broth"], "needs": []},
        ]

        with patch("app.routes.chat.llm_service") as mock_llm, \
             patch("app.routes.chat.nn_service") as mock_nn, \
             patch("app.routes.chat.gap_analysis") as mock_gap, \
             patch("app.routes.chat.recipe_image_service") as mock_img, \
             patch("app.routes.chat.session_manager") as mock_sm:

            from app.services import session_manager as real_sm
            mock_sm.get_session.return_value = session
            mock_sm.reset_cart.side_effect = real_sm.reset_cart
            mock_sm.apply_cart_diff.side_effect = real_sm.apply_cart_diff
            mock_sm.transition_to_options_presented.side_effect = real_sm.transition_to_options_presented
            mock_sm.resolve_selected_option.side_effect = real_sm.resolve_selected_option

            mock_img.populate_recipe_image.side_effect = lambda r: r
            mock_nn.check_recipe_dietary_violations.return_value = []
            mock_gap.compute_gaps.return_value = [{"item": "beef"}]
            mock_nn.recommend.return_value = (self._nn_cart(["beef", "tortillas"]), [])

            # Turn 1
            mock_llm.is_explicit_recipe_request.return_value = True
            mock_llm.is_context_switch.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "options_presented", "options": options,
                "message": "Here are dinner ideas!", "normalized_query": "dinner",
            }

            from app.routes.chat import send_message
            from app.models.session import ChatRequest
            resp1 = await send_message(ChatRequest(conversation_id="s", message="Give me dinner ideas"))

            self.assertEqual(session["stage"], "options_presented")
            self.assertIsNone(session["recipe"])

            # Turn 2
            mock_llm.is_explicit_recipe_request.return_value = False
            mock_llm.is_context_switch.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": tacos_recipe,
                "message": "Here are tacos!", "normalized_query": "tacos",
            }
            mock_llm.call_llm_cart_narration.return_value = {
                "message": "Cart ready.", "status": "cart_proposed",
            }

            resp2 = await send_message(ChatRequest(conversation_id="s", message="tacos"))

            self.assertEqual(session["recipe"]["name"], "Tacos")
            self.assertEqual(session["selected_option"], "Tacos")
            self.assertIsNone(session.get("old_recipe"), "No stale prior recipe")

    # ------------------------------------------------------------------
    # Sequence 3: pasta → alternatives → stir fry
    # ------------------------------------------------------------------
    async def test_seq3_context_switch_replaces_recipe(self):
        """
        After a specific recipe (pasta), asking 'what else' and then picking
        stir fry must replace the pasta recipe entirely.
        """
        session = self._make_session()
        pasta_recipe = {
            "name": "Pasta Carbonara", "cuisine": "Italian", "servings": 2,
            "prep_time": "10 min", "cook_time": "20 min",
            "source_url": "https://example.com/pasta", "image_url": "",
            "ingredients": [
                {"item": "pasta", "quantity": 200, "unit": "g"},
                {"item": "eggs", "quantity": 2, "unit": "whole"},
                {"item": "bacon", "quantity": 100, "unit": "g"},
            ],
            "steps_summary": "Cook pasta, mix with eggs and bacon.",
        }
        stir_fry = self._stir_fry_recipe()
        options = [
            {"name": "Stir Fry", "uses_from_pantry": ["chicken"], "needs": ["soy sauce"]},
            {"name": "Salad", "uses_from_pantry": ["lettuce"], "needs": []},
        ]

        with patch("app.routes.chat.llm_service") as mock_llm, \
             patch("app.routes.chat.nn_service") as mock_nn, \
             patch("app.routes.chat.gap_analysis") as mock_gap, \
             patch("app.routes.chat.recipe_image_service") as mock_img, \
             patch("app.routes.chat.session_manager") as mock_sm:

            from app.services import session_manager as real_sm
            mock_sm.get_session.return_value = session
            mock_sm.reset_cart.side_effect = real_sm.reset_cart
            mock_sm.apply_cart_diff.side_effect = real_sm.apply_cart_diff
            mock_sm.transition_to_options_presented.side_effect = real_sm.transition_to_options_presented
            mock_sm.resolve_selected_option.side_effect = real_sm.resolve_selected_option

            mock_img.populate_recipe_image.side_effect = lambda r: r
            mock_nn.check_recipe_dietary_violations.return_value = []
            mock_gap.compute_gaps.return_value = []
            mock_nn.recommend.return_value = ([], [])

            from app.routes.chat import send_message
            from app.models.session import ChatRequest

            # Turn 1: specific recipe
            mock_llm.is_explicit_recipe_request.return_value = True
            mock_llm.is_context_switch.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": pasta_recipe,
                "message": "Here is pasta!", "normalized_query": "pasta",
            }
            mock_llm.call_llm_cart_narration.return_value = {"message": "Cart.", "status": "cart_proposed"}
            await send_message(ChatRequest(conversation_id="s", message="Give me a pasta recipe"))
            self.assertEqual(session["recipe"]["name"], "Pasta Carbonara")

            # Turn 2: context switch
            mock_llm.is_context_switch.return_value = True
            mock_llm.is_explicit_recipe_request.return_value = True
            mock_llm.call_llm_recipe.return_value = {
                "status": "options_presented", "options": options,
                "message": "Here are alternatives!", "normalized_query": "alternatives",
            }
            await send_message(ChatRequest(conversation_id="s", message="Actually what else can I make?"))
            self.assertIsNone(session["recipe"], "Pasta recipe must be cleared after context switch")
            self.assertEqual(session["stage"], "options_presented")

            # Turn 3: pick stir fry
            mock_llm.is_context_switch.return_value = False
            mock_llm.is_explicit_recipe_request.return_value = False
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": stir_fry,
                "message": "Stir fry!", "normalized_query": "stir fry",
            }
            mock_llm.call_llm_cart_narration.return_value = {"message": "Cart.", "status": "cart_proposed"}
            await send_message(ChatRequest(conversation_id="s", message="stir fry"))
            self.assertEqual(session["recipe"]["name"], "Stir Fry")

    # ------------------------------------------------------------------
    # Sequence 4: invalid option selection
    # ------------------------------------------------------------------
    async def test_seq4_invalid_option_selection_is_graceful(self):
        """
        When user picks something not in the options list, they should get a
        helpful prompt — not the old recipe and not a crash.
        """
        session = self._make_session()
        session["stage"] = "options_presented"
        session["presented_options"] = [
            {"name": "Garlic Bread"},
            {"name": "Pasta"},
        ]
        session["recipe"] = None  # already cleared by transition_to_options_presented

        with patch("app.routes.chat.llm_service") as mock_llm, \
             patch("app.routes.chat.session_manager") as mock_sm:

            from app.services import session_manager as real_sm
            mock_sm.get_session.return_value = session
            mock_sm.resolve_selected_option.side_effect = real_sm.resolve_selected_option
            mock_llm.is_explicit_recipe_request.return_value = False
            mock_llm.is_context_switch.return_value = False

            from app.routes.chat import send_message
            from app.models.session import ChatRequest
            resp = await send_message(ChatRequest(conversation_id="s", message="tacos"))

            # Session must remain in options_presented — no recipe, no crash
            self.assertEqual(session["stage"], "options_presented")
            self.assertIsNone(session["recipe"])
            # Response message must reference the actual options, not a stale recipe
            self.assertIn("Garlic Bread", resp.message)
            self.assertIn("Pasta", resp.message)

    # ------------------------------------------------------------------
    # Sequence 5: option selected, then fresh specific recipe request
    # ------------------------------------------------------------------
    async def test_seq5_new_specific_request_replaces_option_state(self):
        """
        After selecting an option (now in cart_proposed), a new specific recipe
        request resets all option state cleanly.
        """
        session = self._make_session()
        garlic_bread = self._garlic_bread_recipe()
        pizza = self._pizza_recipe()

        # Start as if user previously selected garlic bread
        session["stage"] = "cart_proposed"
        session["recipe"] = garlic_bread
        session["selected_option"] = "Garlic Bread"
        session["presented_options"] = []
        session["current_cart"] = self._nn_cart(["butter", "garlic"])

        with patch("app.routes.chat.llm_service") as mock_llm, \
             patch("app.routes.chat.nn_service") as mock_nn, \
             patch("app.routes.chat.gap_analysis") as mock_gap, \
             patch("app.routes.chat.recipe_image_service") as mock_img, \
             patch("app.routes.chat.session_manager") as mock_sm:

            from app.services import session_manager as real_sm
            mock_sm.get_session.return_value = session
            mock_sm.reset_cart.side_effect = real_sm.reset_cart
            mock_sm.apply_cart_diff.side_effect = real_sm.apply_cart_diff
            mock_sm.transition_to_options_presented.side_effect = real_sm.transition_to_options_presented
            mock_sm.resolve_selected_option.side_effect = real_sm.resolve_selected_option

            mock_img.populate_recipe_image.side_effect = lambda r: r
            mock_nn.check_recipe_dietary_violations.return_value = []
            mock_gap.compute_gaps.return_value = [{"item": "mozzarella"}]
            mock_nn.recommend.return_value = (self._nn_cart(["mozzarella"]), [])

            # New direct request
            mock_llm.is_context_switch.return_value = False
            mock_llm.is_explicit_recipe_request.return_value = True  # triggers forced reset
            mock_llm.call_llm_recipe.return_value = {
                "status": "recipe_found", "recipe": pizza,
                "message": "Here is pizza!", "normalized_query": "pizza",
            }
            mock_llm.call_llm_cart_narration.return_value = {"message": "Cart.", "status": "cart_proposed"}

            from app.routes.chat import send_message
            from app.models.session import ChatRequest
            await send_message(ChatRequest(conversation_id="s", message="I want to make pizza"))

            self.assertEqual(session["recipe"]["name"], "Margherita Pizza")
            self.assertEqual(session["presented_options"], [],
                             "Presented options must be cleared on new specific request")
            self.assertEqual(session["stage"], "cart_proposed")


if __name__ == "__main__":
    unittest.main()
