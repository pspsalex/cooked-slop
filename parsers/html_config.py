# SPDX-License-Identifier: MIT
"""
HTML recipe configuration subsystem.

Supports extracting recipe fields from HTML pages using XPath expressions specified
in YAML configuration files.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from .models import Recipe
from .base import BaseIngredientParser

logger = logging.getLogger(__name__)

try:
    import lxml.html
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


@dataclass
class FieldConfig:
    """Configuration for extracting a specific field via XPath."""
    xpath: str
    attribute: Optional[str] = None
    join_delimiter: Optional[str] = " "
    split_delimiter: Optional[str] = None


@dataclass
class HtmlDetectionConfig:
    """Rules for matching an HTML layout configuration."""
    path_pattern: Optional[str] = None
    content_patterns: List[str] = field(default_factory=list)


@dataclass
class HtmlRecipeSchema:
    """Complete layout schema for extracting recipes from HTML via XPath."""
    name: str
    description: str = ""
    version: str = "1.0"
    detection: HtmlDetectionConfig = field(default_factory=HtmlDetectionConfig)
    fields: Dict[str, FieldConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HtmlRecipeSchema":
        name = data.get("name", "custom_html")
        description = data.get("description", "")
        version = str(data.get("version", "1.0"))

        det_data = data.get("detection", {})
        detection = HtmlDetectionConfig(
            path_pattern=det_data.get("path_pattern"),
            content_patterns=det_data.get("content_patterns", []),
        )

        fields_data = data.get("fields", {})
        fields = {}
        for key, val in fields_data.items():
            if isinstance(val, str):
                fields[key] = FieldConfig(xpath=val)
            elif isinstance(val, dict):
                fields[key] = FieldConfig(
                    xpath=val.get("xpath", ""),
                    attribute=val.get("attribute"),
                    join_delimiter=val.get("join_delimiter", " "),
                    split_delimiter=val.get("split_delimiter"),
                )

        return cls(
            name=name,
            description=description,
            version=version,
            detection=detection,
            fields=fields,
        )


class HtmlConfigRegistry:
    """Registry for managing HTML YAML XPath schemas."""

    def __init__(self):
        self._schemas: Dict[str, HtmlRecipeSchema] = {}

    def register_schema(self, schema: HtmlRecipeSchema):
        """Register an HTML schema configuration."""
        self._schemas[schema.name] = schema

    def load_schema_from_file(self, file_path: Path) -> Optional[HtmlRecipeSchema]:
        """Load a single schema from a YAML file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    schema = HtmlRecipeSchema.from_dict(data)
                    self.register_schema(schema)
                    return schema
        except Exception as e:
            logger.warning("Failed to load HTML schema from %s: %s", file_path, e)
        return None

    def load_schemas_from_yaml(self, config_dir: Path):
        """Load all YAML HTML schemas from directory."""
        if not config_dir.exists():
            return
        for yaml_file in config_dir.glob("*.y[am]*l"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict) and "fields" in data:
                        schema = HtmlRecipeSchema.from_dict(data)
                        self._schemas[schema.name] = schema
            except Exception as e:
                logger.warning("Failed to load HTML schema from %s: %s", yaml_file, e)

    def detect_schema(self, content_sample: str, filepath: str) -> Optional[HtmlRecipeSchema]:
        """Find the best matching HTML schema for a given content/file."""
        best_schema = None
        best_score = 0.0

        for schema in self._schemas.values():
            score = self.score_schema(schema, content_sample, filepath)
            if score > best_score and score >= 0.5:
                best_score = score
                best_schema = schema

        return best_schema

    def score_schema(self, schema: HtmlRecipeSchema, content_sample: str, filepath: str) -> float:
        """Calculate confidence score (0.0 to 1.0) for a schema match."""
        score = 0.0
        checks = 0

        if schema.detection.path_pattern:
            checks += 1
            if re.search(schema.detection.path_pattern, filepath, re.IGNORECASE):
                score += 1.0

        if schema.detection.content_patterns:
            checks += len(schema.detection.content_patterns)
            for pattern in schema.detection.content_patterns:
                if pattern.lower() in content_sample.lower():
                    score += 1.0

        if checks == 0:
            return 0.1

        return score / checks

    def get_schema(self, name: str) -> Optional[HtmlRecipeSchema]:
        """Get schema by name."""
        return self._schemas.get(name)


_global_html_registry: Optional[HtmlConfigRegistry] = None


def get_html_schema_registry() -> HtmlConfigRegistry:
    """Get global HTML schema registry and auto-load YAML configs."""
    global _global_html_registry
    if _global_html_registry is None:
        _global_html_registry = HtmlConfigRegistry()

        config_paths = [
            Path(__file__).parent.parent / "configs",
            Path.cwd() / "configs",
        ]

        for config_dir in config_paths:
            if config_dir.exists():
                _global_html_registry.load_schemas_from_yaml(config_dir)

    return _global_html_registry


def extract_xpath_values(tree: Any, cfg: FieldConfig) -> List[str]:
    """Evaluate XPath expression on lxml element tree and return cleaned strings."""
    if not HAS_LXML or not cfg.xpath:
        return []
    try:
        results = tree.xpath(cfg.xpath)
    except Exception as e:
        logger.warning("XPath evaluation error for pattern '%s': %s", cfg.xpath, e)
        return []

    values = []
    if not isinstance(results, list):
        results = [results]

    for item in results:
        if isinstance(item, str):
            val = item.strip()
        elif hasattr(item, "text_content"):
            val = item.text_content().strip()
        else:
            val = str(item).strip()

        # Clean whitespace (normalize newlines/tabs/multiple spaces)
        val = " ".join(val.split())
        if val:
            values.append(val)

    return values


def parse_html_with_schema(
    content: str,
    schema: HtmlRecipeSchema,
    ingredient_parser: BaseIngredientParser,
    filepath: Optional[str] = None,
) -> Recipe:
    """Parse recipe HTML content into Recipe model using an HtmlRecipeSchema."""
    if not HAS_LXML:
        raise RuntimeError("lxml library is required for XPath HTML parsing.")

    tree = lxml.html.fromstring(f"<html><body>{content}</body></html>")
    recipe = Recipe(source_file=filepath, source_format=f"HTML ({schema.name})")

    # Title
    title_cfg = schema.fields.get("title")
    if title_cfg:
        vals = extract_xpath_values(tree, title_cfg)
        if vals:
            recipe.title = vals[0]

    # Yield
    yield_cfg = schema.fields.get("yield_amount") or schema.fields.get("yield")
    if yield_cfg:
        vals = extract_xpath_values(tree, yield_cfg)
        if vals:
            recipe.yield_amount = vals[0]

    # Categories
    cat_cfg = schema.fields.get("categories") or schema.fields.get("category")
    if cat_cfg:
        vals = extract_xpath_values(tree, cat_cfg)
        if vals:
            cats = []
            for v in vals:
                if cat_cfg.split_delimiter and cat_cfg.split_delimiter in v:
                    cats.extend([c.strip() for c in v.split(cat_cfg.split_delimiter) if c.strip()])
                else:
                    cats.append(v)
            recipe.categories = cats

    # Description
    desc_cfg = schema.fields.get("description")
    if desc_cfg:
        vals = extract_xpath_values(tree, desc_cfg)
        if vals:
            recipe.description = " ".join(vals)

    # URL
    url_cfg = schema.fields.get("url")
    if url_cfg:
        vals = extract_xpath_values(tree, url_cfg)
        if vals:
            recipe.url = vals[0]

    # Ingredients
    ing_cfg = schema.fields.get("ingredients")
    if ing_cfg:
        raw_ings = extract_xpath_values(tree, ing_cfg)
        for raw in raw_ings:
            recipe.ingredients.append(ingredient_parser.parse(raw))

    # Instructions
    inst_cfg = schema.fields.get("instructions")
    if inst_cfg:
        raw_insts = extract_xpath_values(tree, inst_cfg)
        recipe.instructions = raw_insts

    return recipe
