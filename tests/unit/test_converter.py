# SPDX-License-Identifier: MIT
"""Unit tests for SchemaOrgConverter."""
from datetime import datetime
import pytest
from converter import SchemaOrgConverter
from parsers.models import Recipe, Ingredient


def test_converter_empty_instructions():
    """Empty instructions list results in an empty array in JSON-LD."""
    converter = SchemaOrgConverter()
    recipe = Recipe(title="Test", instructions=[])
    result = converter.convert(recipe)
    assert result["recipeInstructions"] == []


def test_converter_single_instruction():
    """Single instruction results in a list of a single string."""
    converter = SchemaOrgConverter()
    recipe = Recipe(title="Test", instructions=["Mix all ingredients well."])
    result = converter.convert(recipe)
    assert result["recipeInstructions"] == ["Mix all ingredients well."]


def test_converter_multiple_instructions():
    """Multiple instructions produce a list of HowToStep objects."""
    converter = SchemaOrgConverter()
    instructions = ["Preheat oven to 350F.", "Mix dry ingredients.", "Bake for 30 minutes."]
    recipe = Recipe(title="Test", instructions=instructions)
    result = converter.convert(recipe)

    steps = result["recipeInstructions"]
    assert len(steps) == 3
    for i, step in enumerate(steps, 1):
        assert step["@type"] == "HowToStep"
        assert step["position"] == i
        assert step["text"] == instructions[i - 1]


def test_converter_ingredient_property_values():
    """Test ingredient PropertyValue conversion for int, float, fraction, unit, and comments."""
    converter = SchemaOrgConverter()
    recipe = Recipe(
        title="Test",
        ingredients=[
            Ingredient(raw="2 cups flour", quantity="2", unit="cup", name="flour"),
            Ingredient(raw="1.5 tsp salt", quantity="1.5", unit="teaspoon", name="salt"),
            Ingredient(raw="1/2 cup sugar", quantity="1/2", unit="cup", name="sugar"),
            Ingredient(
                raw="1 onion, finely chopped",
                quantity="1",
                unit="whole",
                name="onion",
                comment="finely chopped",
            ),
            Ingredient(raw="1 carrot", quantity="1", unit=None, name=None),
        ],
    )
    result = converter.convert(recipe, parse_ingredients=True)
    ingredients = result["recipeIngredient"]

    # Integer quantity
    assert ingredients[0] == {
        "@type": "PropertyValue",
        "name": "flour",
        "value": 2,
        "unitText": "cup",
    }
    assert isinstance(ingredients[0]["value"], int)

    # Float quantity
    assert ingredients[1] == {
        "@type": "PropertyValue",
        "name": "salt",
        "value": 1.5,
        "unitText": "teaspoon",
    }
    assert isinstance(ingredients[1]["value"], float)

    # Fraction quantity (retained as string)
    assert ingredients[2] == {
        "@type": "PropertyValue",
        "name": "sugar",
        "value": "1/2",
        "unitText": "cup",
    }
    assert isinstance(ingredients[2]["value"], str)

    # Comment mapped to description
    assert ingredients[3] == {
        "@type": "PropertyValue",
        "name": "onion",
        "value": 1,
        "unitText": "whole",
        "description": "finely chopped",
    }

    # Name fallback to raw when name is None
    assert ingredients[4] == {
        "@type": "PropertyValue",
        "name": "1 carrot",
        "value": 1,
    }


def test_converter_ingredient_plain_string_fallback():
    """Ingredient without quantity and unit falls back to raw string."""
    converter = SchemaOrgConverter()
    recipe = Recipe(
        title="Test",
        ingredients=[
            Ingredient(raw="salt and black pepper to taste", name="salt and black pepper to taste"),
        ],
    )
    result = converter.convert(recipe, parse_ingredients=True)
    assert result["recipeIngredient"] == ["salt and black pepper to taste"]


def test_converter_parse_ingredients_false():
    """When parse_ingredients=False, all ingredients remain raw strings."""
    converter = SchemaOrgConverter()
    recipe = Recipe(
        title="Test",
        ingredients=[
            Ingredient(raw="2 cups flour", quantity="2", unit="cup", name="flour"),
            Ingredient(raw="pinch of salt", name="salt"),
        ],
    )
    result = converter.convert(recipe, parse_ingredients=False)
    assert result["recipeIngredient"] == ["2 cups flour", "pinch of salt"]


def test_converter_categories_and_keywords():
    """First category becomes recipeCategory; all categories are joined into keywords."""
    converter = SchemaOrgConverter()
    recipe = Recipe(
        title="Pasta",
        categories=["Italian", "Main Course", "Pasta Dishes"],
    )
    result = converter.convert(recipe)
    assert result["recipeCategory"] == "Italian"
    assert result["keywords"] == "Italian, Main Course, Pasta Dishes"


def test_converter_empty_categories():
    """When categories list is empty, neither recipeCategory nor keywords are set."""
    converter = SchemaOrgConverter()
    recipe = Recipe(title="Pasta", categories=[])
    result = converter.convert(recipe)
    assert "recipeCategory" not in result
    assert "keywords" not in result


def test_converter_url_priority():
    """Test URL mapping: plain URL, SQLite anchor, and file path fallback."""
    converter = SchemaOrgConverter()

    # 1. Plain recipe.url takes precedence
    r_url = Recipe(
        title="Test",
        source_file="/tmp/recipes.txt",
        url="https://example.com/recipe/42",
    )
    assert converter.convert(r_url)["url"] == "https://example.com/recipe/42"
    assert converter.convert(r_url)["comment"] == "Imported from /tmp/recipes.txt"

    # 2. SQLite anchor when table and id exist
    r_sql = Recipe(
        title="Test",
        source_file="/data/recipes.db",
        sqlite_table="recipes",
        sqlite_id="123",
    )
    assert converter.convert(r_sql)["url"] == "file:///data/recipes.db#recipes,123"

    # 3. Fallback file:// path
    r_file = Recipe(
        title="Test",
        source_file="/home/user/recipes.mmf",
    )
    assert converter.convert(r_file)["url"] == "file:///home/user/recipes.mmf"

    # 4. No source_file -> no url or comment
    r_none = Recipe(title="Test")
    res_none = converter.convert(r_none)
    assert "url" not in res_none
    assert "comment" not in res_none


def test_converter_add_date():
    """Test add_date flag adds an ISO-8601 datePublished."""
    converter = SchemaOrgConverter()
    recipe = Recipe(title="Test")

    # Without add_date
    res_no_date = converter.convert(recipe, add_date=False)
    assert "datePublished" not in res_no_date

    # With add_date
    res_with_date = converter.convert(recipe, add_date=True)
    assert "datePublished" in res_with_date
    # Must parse as valid ISO timestamp
    parsed = datetime.fromisoformat(res_with_date["datePublished"])
    assert parsed is not None


def test_converter_metadata_fields():
    """Test name, recipeYield, and description formatting."""
    converter = SchemaOrgConverter()

    # Default name fallback
    r_empty_title = Recipe(title="")
    assert converter.convert(r_empty_title)["name"] == "Untitled Recipe"

    # Yield amount and source format description
    r_full = Recipe(
        title="Apple Pie",
        yield_amount="8 servings",
        source_format="MealMaster",
    )
    res = converter.convert(r_full)
    assert res["name"] == "Apple Pie"
    assert res["recipeYield"] == "8 servings"
    assert res["description"] == "Recipe converted from MealMaster format"
    assert res["@context"] == "https://schema.org"
    assert res["@type"] == "Recipe"
