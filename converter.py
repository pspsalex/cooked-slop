# SPDX-License-Identifier: MIT
"""Schema.org JSON-LD recipe converter."""
from datetime import datetime
from typing import Any, Dict, List
from parsers.models import Recipe


class SchemaOrgConverter:
    """Converter to schema.org Recipe JSON-LD format."""

    def convert(
        self,
        recipe: Recipe,
        parse_ingredients: bool = True,
        add_date: bool = False,
    ) -> Dict[str, Any]:
        """Convert an internal Recipe dataclass instance into a Schema.org dict.

        Args:
            recipe: Recipe dataclass instance to convert.
            parse_ingredients: Whether to parse ingredients into structured PropertyValue objects.
            add_date: Whether to add datePublished timestamp.

        Returns:
            Dictionary representing Schema.org Recipe JSON-LD.
        """
        instructions = self._build_instructions(recipe.instructions)
        recipe_ingredients = []

        if parse_ingredients:
            for ing in recipe.ingredients:
                if ing.quantity or ing.unit:
                    prop_value: Dict[str, Any] = {
                        "@type": "PropertyValue",
                        "name": ing.name or ing.raw,
                    }
                    if ing.quantity:
                        try:
                            prop_value["value"] = (
                                float(ing.quantity)
                                if "/" not in ing.quantity and "." in ing.quantity
                                else int(ing.quantity)
                            )
                        except ValueError:
                            prop_value["value"] = ing.quantity
                    if ing.unit:
                        prop_value["unitText"] = ing.unit
                    if ing.comment:
                        prop_value["description"] = ing.comment

                    recipe_ingredients.append(prop_value)
                else:
                    recipe_ingredients.append(ing.raw)
        else:
            recipe_ingredients = [ing.raw for ing in recipe.ingredients]

        schema_recipe: Dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": recipe.title or "Untitled Recipe",
            "recipeIngredient": recipe_ingredients,
            "recipeInstructions": instructions,
        }

        if recipe.yield_amount:
            schema_recipe["recipeYield"] = recipe.yield_amount

        if recipe.categories:
            schema_recipe["recipeCategory"] = recipe.categories[0]
            schema_recipe["keywords"] = ", ".join(recipe.categories)

        if recipe.source_file:
            schema_recipe["comment"] = f"Imported from {recipe.source_file}"
            if recipe.url:
                schema_recipe["url"] = recipe.url
            elif recipe.sqlite_table and recipe.sqlite_id:
                schema_recipe["url"] = (
                    f"file://{recipe.source_file}#{recipe.sqlite_table},{recipe.sqlite_id}"
                )
            else:
                schema_recipe["url"] = f"file://{recipe.source_file}"

        if add_date:
            schema_recipe["datePublished"] = datetime.now().isoformat()

        schema_recipe["description"] = (
            f"Recipe converted from {recipe.source_format} format"
        )

        return schema_recipe

    @staticmethod
    def _build_instructions(instructions: List[str]) -> List[Any]:
        """Build schema.org recipeInstructions structure from a list of strings.

        Args:
            instructions: List of instruction strings.

        Returns:
            List of instruction strings or HowToStep dicts.
        """
        if not instructions:
            return []
        if len(instructions) == 1:
            return [instructions[0]]
        return [
            {"@type": "HowToStep", "position": position, "text": instruction}
            for position, instruction in enumerate(instructions, 1)
        ]
