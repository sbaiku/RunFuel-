"""Meal ideas sized to a calorie burn.

Like ``calc``, this module imports nothing from the rest of the package, so the
matching logic is testable without a database, a request, or a template.

Only the dish name and its published per-serving nutrition are recorded here.
The recipes themselves belong to their authors and are not reproduced.
"""

from dataclasses import dataclass

MAX_SERVINGS = 3


@dataclass(frozen=True)
class Recipe:
    name: str
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    vegetarian: bool = False


@dataclass(frozen=True)
class Suggestion:
    """A recipe at a serving count that lands near the calories burned."""

    recipe: Recipe
    servings: int
    total_kcal: int
    total_protein_g: float


RECIPES: tuple[Recipe, ...] = (
    Recipe("Salmon and gnocchi hash", 641, 34.5, 58.9, 28.4),
    Recipe("Griddled chicken with pesto", 417, 40.5, 10.0, 23.0),
    Recipe("Salmon traybake with soy, chilli and lime", 553, 45.0, 11.5, 35.0),
    Recipe("Chicken egg-fried rice", 781, 57.8, 68.9, 29.4),
    Recipe("Vegetarian bolognese", 296, 13.0, 48.0, 4.0, vegetarian=True),
    Recipe("Chicken dhansak", 471, 45.0, 39.5, 13.0),
    Recipe("Chicken and ricotta meatballs with spaghetti", 531, 48.5, 40.1, 20.5),
    Recipe("Easy Mexican bean stew", 454, 26.6, 68.2, 3.8, vegetarian=True),
    Recipe("Nacho beef burritos", 581, 38.2, 42.3, 27.2),
    Recipe("Paneer jalfrezi", 258, 16.0, 13.0, 15.0, vegetarian=True),
)


def suggest(
    calories: float, recipes: tuple[Recipe, ...] = RECIPES
) -> Suggestion | None:
    """The recipe and whole serving count landing closest to ``calories``.

    Ties break toward fewer servings, then alphabetically by name, so the same
    burn always yields the same suggestion.
    """
    if not recipes:
        return None

    def distance(pairing: tuple[Recipe, int]) -> tuple[float, int, str]:
        recipe, servings = pairing
        return (
            abs(recipe.kcal * servings - calories),
            servings,
            recipe.name,
        )

    recipe, servings = min(
        (
            (recipe, servings)
            for recipe in recipes
            for servings in range(1, MAX_SERVINGS + 1)
        ),
        key=distance,
    )
    return Suggestion(
        recipe=recipe,
        servings=servings,
        total_kcal=recipe.kcal * servings,
        total_protein_g=recipe.protein_g * servings,
    )
