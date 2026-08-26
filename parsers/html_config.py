# SPDX-License-Identifier: MIT
"""
HTML recipe configuration subsystem.

Supports extracting recipe fields from HTML pages using XPath expressions specified
in YAML configuration files.
"""

import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Any
import yaml

from .models import Recipe, Ingredient
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
    recipe_container: Optional[str] = None
    recipe_delimiter: Optional[str] = None
    multi_recipe: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HtmlRecipeSchema":
        name = data.get("name", "custom_html")
        description = data.get("description", "")
        version = str(data.get("version", "1.0"))
        recipe_delimiter = data.get("recipe_delimiter")

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
            recipe_container=data.get("recipe_container"),
            recipe_delimiter=data.get("recipe_delimiter") or recipe_delimiter,
            multi_recipe=data.get("multi_recipe", False),
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


def _parse_garvick_recipes(
    tree: Any,
    schema: HtmlRecipeSchema,
    ingredient_parser: BaseIngredientParser,
    filepath: Optional[str] = None,
) -> Iterator[Recipe]:
    """Extract multiple distinct recipes from Garvick-formatted HTML."""
    title_cfg = schema.fields.get("title")
    if not title_cfg:
        return

    title_nodes = tree.xpath(title_cfg.xpath)

    valid_titles = []
    for node in title_nodes:
        if isinstance(node, str):
            parent = getattr(node, "getparent", lambda: None)()
            if parent is None:
                continue
            text = " ".join(node.split())
        else:
            parent = node
            text = " ".join(node.text_content().split())

        if not text:
            continue

        t_lower = text.lower()
        if any(kw in t_lower for kw in [
            "tip:", "barbeque tip:", "links to", "click here", "recipes:",
            "site map", "privacy policy", "free recipes", "garvick home",
            "top 100", "for book lovers", "for chocolate lovers", "for candy lovers",
            "for movie buffs", "for cookie lovers", "for a child", "bath products", "your own creations",
            "recipe of the month", "chill dough overnight.", "try this recipe",
            "back to annual events", "annual events", "easter crafts", "easter games", "easter gifts", "easter recipes", "garnish:"
        ]):
            continue

        if parent.xpath("ancestor-or-self::a") or parent.xpath(".//a"):
            continue

        p_elem = parent.xpath("ancestor-or-self::p")
        if not p_elem:
            continue
        p = p_elem[0]
        valid_titles.append((p, text))

    seen = set()
    unique_titles = []
    for p, text in valid_titles:
        if p not in seen:
            seen.add(p)
            unique_titles.append((p, text))

    for idx, (p_elem, title_text) in enumerate(unique_titles):
        next_p = unique_titles[idx + 1][0] if idx + 1 < len(unique_titles) else None

        section_nodes = []
        curr = p_elem.getnext()
        while curr is not None:
            if curr == next_p:
                break
            if next_p is not None and next_p in curr.iterdescendants():
                break
            section_nodes.append(curr)
            curr = curr.getnext()

        ingredients = []
        instructions = []
        yield_amount = ""

        for elem in section_nodes:
            if elem.tag in ("script", "style", "table"):
                continue
            if elem.tag == "ul":
                for li in elem.xpath(".//li"):
                    raw = " ".join(li.text_content().split())
                    if raw:
                        ingredients.append(ingredient_parser.parse(raw))
            elif elem.tag == "p":
                if elem.xpath(".//a[contains(@href, 'index.html') or contains(@href, 'meal-master')]"):
                    break
                p_text = elem.text_content().strip()
                if not p_text:
                    continue
                elem_html = lxml.html.tostring(elem, encoding="unicode")
                raw_lines = [
                    re.sub(r"\s+", " ", html.unescape(l).replace("\xa0", " ")).strip()
                    for l in re.split(r"<br\s*/?>", elem_html, flags=re.IGNORECASE)
                ]
                raw_lines = [re.sub(r"<[^>]+>", "", l).strip() for l in raw_lines]
                raw_lines = [l for l in raw_lines if l]

                if len(raw_lines) > 1 and any(ingredient_parser.parse(l).quantity for l in raw_lines[:4]):
                    for line in raw_lines:
                        m_yield = re.match(r"^(?:serves|makes)\s+(.+)$", line, re.IGNORECASE)
                        if m_yield:
                            yield_amount = line
                            continue
                        if any(line.lower().startswith(x) for x in ["filling:", "glaze:", "frosting:", "marinade", "chocolate frosting:"]):
                            continue
                        if line.startswith("*") and ("cup" in line or "sugar" in line or "tb" in line):
                            instructions.append(line)
                            continue
                        parsed = ingredient_parser.parse(line)
                        if parsed.quantity or (parsed.unit and parsed.unit != line):
                            ingredients.append(parsed)
                        else:
                            instructions.append(line)
                else:
                    clean_text = " ".join(p_text.split())
                    m_yield = re.match(r"^(?:serves|makes)\s+(.+)$", clean_text, re.IGNORECASE)
                    if m_yield:
                        yield_amount = clean_text
                    elif clean_text.lower().startswith("filling:") or clean_text.lower().startswith("glaze:"):
                        pass
                    else:
                        instructions.append(clean_text)

        if ingredients:
            yield Recipe(
                title=title_text,
                yield_amount=yield_amount,
                ingredients=ingredients,
                instructions=instructions,
                source_file=filepath,
                source_format=f"HTML ({schema.name})",
            )


def _parse_single_chunk_with_schema(
    chunk: str,
    schema: HtmlRecipeSchema,
    ingredient_parser: BaseIngredientParser,
    filepath: Optional[str] = None,
) -> Recipe:
    """Parse a single HTML chunk into a Recipe model."""
    recipe = Recipe(source_file=filepath, source_format=f"HTML ({schema.name})")

    if schema.name == "macropolis":
        clean_chunk = re.sub(r'(?:<br\s*/?>\s*){2,}', '\n\n', chunk, flags=re.IGNORECASE)
        clean_chunk = re.sub(r'<br\s*/?>\s*\n?', '\n', clean_chunk, flags=re.IGNORECASE)
        try:
            tree = lxml.html.fromstring(f"<html><body>{clean_chunk}</body></html>")
        except Exception:
            tree = lxml.html.fromstring(f"<html><body>{chunk}</body></html>")
    else:
        tree = lxml.html.fromstring(f"<html><body>{chunk}</body></html>")

    text = tree.text_content()

    # Title
    title_cfg = schema.fields.get("title")
    if title_cfg:
        vals = extract_xpath_values(tree, title_cfg)
        if vals:
            raw_title = vals[0]
            recipe.title = re.sub(r'^Title:\s*', '', raw_title, flags=re.IGNORECASE).strip()
    if schema.name == "macropolis":
        if not recipe.title:
            m = re.search(
                r'Title:\s*([^<\r\n]+(?:\r?\n[^\r\n<]+)*?)(?=\s*(?:Categories:|Yield:|Ingredients:|\r?\n\r?\n|<|$))',
                text,
                re.IGNORECASE,
            )
            if m:
                recipe.title = " ".join(m.group(1).split()).strip()
        if recipe.title:
            recipe.title = html.unescape(recipe.title).strip()

    # Yield
    yield_cfg = schema.fields.get("yield_amount") or schema.fields.get("yield")
    if yield_cfg:
        vals = extract_xpath_values(tree, yield_cfg)
        if vals:
            m_y = re.search(r'Yield(?:\s*amount)?:\s*([^\r\n<]+)', text, re.IGNORECASE)
            if m_y:
                recipe.yield_amount = m_y.group(1).strip()
            else:
                raw_yield = vals[0]
                recipe.yield_amount = re.sub(
                    r'^Yield(?:\s*amount)?:\s*', '', raw_yield, flags=re.IGNORECASE
                ).strip()
    if schema.name == "macropolis":
        if not recipe.yield_amount:
            m = re.search(r'Yield(?:\s*amount)?:\s*([^\r\n<]+)', text, re.IGNORECASE)
            if m:
                recipe.yield_amount = m.group(1).strip()
        if recipe.yield_amount:
            recipe.yield_amount = html.unescape(recipe.yield_amount).strip()

    # Categories
    cat_cfg = schema.fields.get("categories") or schema.fields.get("category")
    if cat_cfg:
        vals = extract_xpath_values(tree, cat_cfg)
        if vals:
            m_c = re.search(
                r'Categories:\s*([^\r\n<]+)',
                text,
                re.IGNORECASE,
            )
            if m_c:
                cats_str = m_c.group(1).strip()
                delim = cat_cfg.split_delimiter or ","
                recipe.categories = [
                    html.unescape(c.strip())
                    for c in cats_str.split(delim)
                    if c.strip()
                ]
            else:
                cats = []
                for v in vals:
                    v_clean = re.sub(r'^Categories:\s*', '', v, flags=re.IGNORECASE).strip()
                    if cat_cfg.split_delimiter and cat_cfg.split_delimiter in v_clean:
                        cats.extend(
                            [
                                html.unescape(c.strip())
                                for c in v_clean.split(cat_cfg.split_delimiter)
                                if c.strip()
                            ]
                        )
                    else:
                        cats.append(html.unescape(v_clean))
                recipe.categories = cats
    if schema.name == "macropolis":
        if not recipe.categories:
            m = re.search(
                r'Categories:\s*([^<\r\n]+(?:\r?\n[^\r\n<]+)*?)(?=\s*(?:Yield:|Ingredients:|\r?\n\r?\n|<|$))',
                text,
                re.IGNORECASE,
            )
            if m:
                cats_str = " ".join(m.group(1).split()).strip()
                delim = (
                    cat_cfg.split_delimiter
                    if (cat_cfg and cat_cfg.split_delimiter)
                    else ","
                )
                recipe.categories = [
                    html.unescape(c.strip())
                    for c in cats_str.split(delim)
                    if c.strip()
                ]

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
            if ing_cfg.split_delimiter and ing_cfg.split_delimiter in raw:
                for line in raw.split(ing_cfg.split_delimiter):
                    if line.strip():
                        recipe.ingredients.append(
                            ingredient_parser.parse(html.unescape(line.strip()))
                        )
            else:
                recipe.ingredients.append(
                    ingredient_parser.parse(html.unescape(raw))
                )

    # Instructions
    inst_cfg = schema.fields.get("instructions")
    if inst_cfg:
        raw_insts = extract_xpath_values(tree, inst_cfg)
        recipe.instructions = [html.unescape(i) for i in raw_insts]

    # If neither ingredients nor instructions were extracted via XPath, parse from MealMaster body
    if schema.name == "macropolis" and not recipe.ingredients and not recipe.instructions:
        body_lines = [l.strip() for l in text.splitlines()]
        # Strip separator lines like +++++ or =====
        body_lines = [l if not re.match(r'^[+=-]{4,}$', l) else "" for l in body_lines]
        start_idx = 0
        while start_idx < len(body_lines):
            line = body_lines[start_idx]
            if (
                line.lower().startswith(('title:', 'categories:', 'yield:', 'category:'))
                or (recipe.title and (line == recipe.title or line in recipe.title))
            ):
                start_idx += 1
            elif not line:
                start_idx += 1
            else:
                break
        in_ingredients = True
        current_inst = []
        for line in body_lines[start_idx:]:
            if not line:
                if current_inst:
                    recipe.instructions.append(" ".join(current_inst))
                    current_inst = []
                continue
            is_header = bool(re.match(r'^[-=*]{2,}.*[-=*]{2,}$', line)) or bool(
                re.match(r'^[A-Z0-9 ,/-]{3,}--+$', line)
            )
            starts_qty = bool(
                re.match(r'^(\d|½|¼|¾|⅓|⅔|1/|2/|3/|4/|5/|6/|7/|8/|9/|\d+\s*\d+/\d+)', line)
            )
            if in_ingredients:
                if is_header or starts_qty:
                    recipe.ingredients.append(
                        ingredient_parser.parse(html.unescape(line))
                    )
                elif line.startswith("-") and len(line) < 40:
                    recipe.ingredients.append(
                        ingredient_parser.parse(html.unescape(line))
                    )
                elif len(recipe.ingredients) > 0 and (
                    len(line) > 80
                    or (
                        line[0].isupper()
                        and (
                            line.endswith(".")
                            or (
                                " " in line
                                and len(line.split()) > 7
                                and not any(
                                    w in line.lower()
                                    for w in [
                                        "tb", "ts", "tbsp", "tsp", "cup", "cups", "oz", "lb",
                                        "can", "clove", "cloves", "slice", "slices", "package",
                                        "pk", "c", "g", "kg", "ml", "md", "lg", "ea", "pn", "pinch"
                                    ]
                                )
                            )
                        )
                    )
                ):
                    in_ingredients = False
                    current_inst.append(html.unescape(line))
                else:
                    if len(recipe.ingredients) == 0 and len(line) < 40 and not line.endswith("."):
                        recipe.ingredients.append(
                            ingredient_parser.parse(html.unescape(line))
                        )
                    elif len(recipe.ingredients) > 0 and len(line) < 40 and not line.endswith("."):
                        recipe.ingredients.append(
                            ingredient_parser.parse(html.unescape(line))
                        )
                    else:
                        in_ingredients = False
                        current_inst.append(html.unescape(line))
            else:
                current_inst.append(html.unescape(line))
        if current_inst:
            recipe.instructions.append(" ".join(current_inst))

    return recipe


def parse_html_recipes_with_schema(
    content: str,
    schema: HtmlRecipeSchema,
    ingredient_parser: BaseIngredientParser,
    filepath: Optional[str] = None,
) -> Iterator[Recipe]:
    """Parse recipe HTML content into Recipe models using an HtmlRecipeSchema."""
    if not HAS_LXML:
        raise RuntimeError("lxml library is required for XPath HTML parsing.")

    if schema.name == "garvick":
        tree = lxml.html.fromstring(f"<html><body>{content}</body></html>")
        yield from _parse_garvick_recipes(tree, schema, ingredient_parser, filepath)
        return


    if schema.recipe_delimiter:
        delim = schema.recipe_delimiter
        if "title:" in delim.lower():
            pattern = r'(?i)(?=(?:<\s*b[^>]*>\s*|<\s*p[^>]*>\s*|<\s*font[^>]*>\s*)*Title:)'
        else:
            escaped = re.escape(delim)
            delim_pattern = re.sub(r'\\ ', r'\\s+', escaped)
            pattern = rf'(?i)(?={delim_pattern})'
        chunks = re.split(pattern, content)
        for chunk in chunks:
            if "title:" in delim.lower() and not re.search(r'Title:\s*', chunk, re.IGNORECASE):
                continue
            recipe = _parse_single_chunk_with_schema(
                chunk, schema, ingredient_parser, filepath
            )
            if recipe and (recipe.title or recipe.ingredients):
                yield recipe
    else:
        recipe = _parse_single_chunk_with_schema(
            content, schema, ingredient_parser, filepath
        )
        if recipe and (recipe.title or recipe.ingredients):
            yield recipe


def parse_html_with_schema(
    content: str,
    schema: HtmlRecipeSchema,
    ingredient_parser: BaseIngredientParser,
    filepath: Optional[str] = None,
) -> Recipe:
    """Parse recipe HTML content into Recipe model using an HtmlRecipeSchema (single recipe)."""
    return _parse_single_chunk_with_schema(
        content, schema, ingredient_parser, filepath
    )
