import pytest

from runfuel import recipes


class TestRecipeData:
    def test_carries_the_full_set(self):
        assert len(recipes.RECIPES) == 10

    def test_every_recipe_has_positive_nutrition(self):
        for recipe in recipes.RECIPES:
            assert recipe.kcal > 0, recipe.name
            assert recipe.protein_g > 0, recipe.name

    def test_names_are_unique(self):
        names = [recipe.name for recipe in recipes.RECIPES]
        assert len(set(names)) == len(names)

    def test_a_known_recipe_keeps_its_figures(self):
        hash_ = next(r for r in recipes.RECIPES if r.name == "Salmon and gnocchi hash")

        assert hash_.kcal == 641
        assert hash_.protein_g == 34.5

    def test_vegetarian_dishes_are_flagged(self):
        vegetarian = {r.name for r in recipes.RECIPES if r.vegetarian}

        assert vegetarian == {
            "Vegetarian bolognese",
            "Easy Mexican bean stew",
            "Paneer jalfrezi",
        }


class TestSuggest:
    def test_a_single_serving_that_nearly_matches_wins(self):
        # 643 kcal burned; one serving of the 641 kcal hash is 2 kcal away.
        suggestion = recipes.suggest(643)

        assert suggestion.recipe.name == "Salmon and gnocchi hash"
        assert suggestion.servings == 1
        assert suggestion.total_kcal == 641

    def test_more_servings_of_a_smaller_dish_can_beat_one_big_dish(self):
        # 900 kcal. The nearest single recipe is egg-fried rice at 781 (119 away),
        # but two servings of the 454 kcal bean stew land on 908 -- only 8 away.
        suggestion = recipes.suggest(900)

        assert suggestion.recipe.name == "Easy Mexican bean stew"
        assert suggestion.servings == 2
        assert suggestion.total_kcal == 908

    def test_a_burn_smaller_than_every_recipe_still_suggests_the_smallest(self):
        suggestion = recipes.suggest(200)

        assert suggestion.recipe.name == "Paneer jalfrezi"
        assert suggestion.servings == 1

    def test_a_very_large_burn_uses_the_serving_cap(self):
        suggestion = recipes.suggest(2400)

        assert suggestion.recipe.name == "Chicken egg-fried rice"
        assert suggestion.servings == 3
        assert suggestion.total_kcal == 2343

    def test_a_tie_prefers_fewer_servings(self):
        # 707.5 sits exactly between one serving of the 641 kcal hash and three
        # servings of the 258 kcal paneer (774) -- both 66.5 away, and the next
        # nearest total (781) is 73.5 away, so this really is a two-way tie.
        suggestion = recipes.suggest(707.5)

        assert suggestion.recipe.name == "Salmon and gnocchi hash"
        assert suggestion.servings == 1

    def test_a_tie_at_equal_servings_breaks_alphabetically(self):
        # 277 sits exactly between one serving of paneer (258) and of bolognese (296).
        suggestion = recipes.suggest(277)

        assert suggestion.recipe.name == "Paneer jalfrezi"

    @pytest.mark.parametrize("calories", [1, 250, 640, 1500, 5000])
    def test_servings_are_always_a_whole_number_from_one_to_three(self, calories):
        suggestion = recipes.suggest(calories)

        assert suggestion.servings in (1, 2, 3)

    def test_protein_scales_with_the_serving_count(self):
        suggestion = recipes.suggest(900)

        assert suggestion.total_protein_g == pytest.approx(2 * 26.6)

    def test_no_recipes_means_no_suggestion(self):
        assert recipes.suggest(600, recipes=()) is None
