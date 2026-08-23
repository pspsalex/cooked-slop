# SPDX-License-Identifier: MIT
"""
LLM-based recipe parser.

Sends the raw file content to an OpenAI-compatible API (e.g. Ollama) and asks
the model to extract structured recipe data as JSON.  Integrates with the
existing BaseRecipeParser / ParserRegistry infrastructure, but is NOT
auto-registered — it must be activated explicitly via --llm-config in
convert.py.

Sanity checks flag potential LLM hallucinations by inspecting the extracted
data for implausible values and prefixing recipe.description with a warning.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests
import yaml

from .base import BaseIngredientParser, BaseRecipeParser
from .generic_md import GenericMdParser, unroll_markdown_tables
from .models import Ingredient, Recipe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default sanity thresholds — overridden by the YAML config
# ---------------------------------------------------------------------------
_DEFAULT_SANITY = {
    "min_ingredients": 2,
    "max_ingredients": 50,
    "min_instructions": 1,
    "max_instructions": 80,
    "min_title_len": 3,
    "max_title_len": 120,
    "max_single_instruction_len": 2000,
}

_DEFAULT_SYSTEM = (
    "You are a recipe extraction assistant. Given raw recipe text, extract the "
    "recipe data and return ONLY a valid JSON object. No markdown, no extra text. "
    "Use this exact schema:\n"
    '{\n'
    '  "title": "string",\n'
    '  "categories": ["string"],\n'
    '  "yield_amount": "string",\n'
    '  "ingredients": ["string"],\n'
    '  "instructions": ["string"]\n'
    '}\n'
    "If a field cannot be determined, use an empty string or empty list."
)

_DEFAULT_MARKED_SYSTEM = (
    "You are a specialized recipe extraction assistant.\n"
    "Your job is to convert raw unstructured text strictly into standard marked Markdown recipe format.\n\n"
    "Guidelines:\n"
    "1. Place the title on line 1 as a level 1 heading: `# Recipe Title`.\n"
    "2. If mentioned, include metadata lines directly under title, e.g., `Yield: ...`, `Prep Time: ...`, `Categories: ...`.\n"
    "3. Create an ingredients section starting with header `## Ingredients`.\n"
    "   - List EVERY ingredient line starting with `- `.\n"
    "   - Use sub-headers like `### For the crust` to group ingredients if sub-sections exist.\n"
    "   - Do NOT omit, summarize, alter, or miss any ingredients.\n"
    "4. Create an instructions section starting with header `## Instructions`.\n"
    "   - List every instruction step line-by-line starting with step numbers `1. `, `2. ` or bullets `- `.\n"
    "   - Use sub-headers like `### Baking` to group steps if sub-sections exist.\n"
    "   - Do NOT omit, summarize, or skip any cooking steps.\n"
    "5. Return ONLY the marked Markdown content without code block backticks."
)


# ---------------------------------------------------------------------------
# Sanity checker
# ---------------------------------------------------------------------------
class RecipeSanityChecker:
    """
    Applies heuristic checks to an extracted recipe dict (pre-model-to-Recipe
    conversion) and returns a list of human-readable warning strings.  An empty
    list means the recipe looks plausible.
    """

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = {**_DEFAULT_SANITY, **cfg}

    def check(self, data: Dict[str, Any], json_ok: bool = True) -> List[str]:
        warnings: List[str] = []

        if not json_ok:
            warnings.append("JSON parse failed — data recovered via fallback")

        title = str(data.get("title", "")).strip()
        if not title:
            warnings.append("title is empty")
        elif len(title) < self.cfg["min_title_len"]:
            warnings.append(f"title suspiciously short ({len(title)} chars)")
        elif len(title) > self.cfg["max_title_len"]:
            warnings.append(f"title suspiciously long ({len(title)} chars)")

        ingredients = data.get("ingredients", [])
        if not isinstance(ingredients, list):
            warnings.append("ingredients field is not a list")
            ingredients = []
        elif len(ingredients) < self.cfg["min_ingredients"]:
            warnings.append(
                f"too few ingredients ({len(ingredients)} < {self.cfg['min_ingredients']})"
            )
        elif len(ingredients) > self.cfg["max_ingredients"]:
            warnings.append(
                f"too many ingredients ({len(ingredients)} > {self.cfg['max_ingredients']})"
            )

        instructions = data.get("instructions", [])
        if not isinstance(instructions, list):
            warnings.append("instructions field is not a list")
            instructions = []
        elif len(instructions) < self.cfg["min_instructions"]:
            warnings.append(
                f"too few instructions ({len(instructions)} < {self.cfg['min_instructions']})"
            )
        elif len(instructions) > self.cfg["max_instructions"]:
            warnings.append(
                f"too many instructions ({len(instructions)} > {self.cfg['max_instructions']})"
            )

        max_step = self.cfg["max_single_instruction_len"]
        for i, step in enumerate(instructions):
            if isinstance(step, str) and len(step) > max_step:
                warnings.append(
                    f"instruction step {i+1} is very long ({len(step)} chars) — possible padding"
                )
                break  # one warning is enough

        categories = data.get("categories", [])
        if isinstance(categories, list):
            for cat in categories:
                if isinstance(cat, (int, float)):
                    warnings.append(f"category looks like a number: {cat!r}")
                    break

        yield_amount = str(data.get("yield_amount", "")).strip()
        if yield_amount and not any(c.isdigit() for c in yield_amount):
            warnings.append(f"yield_amount has no digit: {yield_amount!r}")

        return warnings

    def check_recipe(self, recipe: Recipe) -> List[str]:
        """Applies sanity checks to a Recipe dataclass object."""
        data = {
            "title": recipe.title,
            "ingredients": [i.raw for i in recipe.ingredients],
            "instructions": recipe.instructions,
            "categories": recipe.categories,
            "yield_amount": recipe.yield_amount,
        }
        return self.check(data, json_ok=True)


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------
class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, cfg: Dict[str, Any]):
        self.base_url = cfg.get("base_url", "http://localhost:11434/v1").rstrip("/")
        self.model = cfg.get("model", "qwen2.5:7b-instruct")
        self.api_key = cfg.get("api_key", "") or "ollama"
        self.timeout = int(cfg.get("timeout_seconds", 120))
        self.temperature = float(cfg.get("temperature", 0.1))

    def chat(self, system: str, user: str) -> str:
        """Send a chat request and return the assistant reply as a string."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        base = self.base_url.rstrip("/")

        # Check for native Ollama API endpoints (/api or /api/chat)
        if base.endswith("/api/chat") or base.endswith("/api"):
            url = base if base.endswith("/chat") else f"{base}/chat"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": self.temperature},
            }
            logger.debug("LLM request (native Ollama) → %s (model=%s)", url, self.model)
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()["message"]["content"]
        else:
            # OpenAI-compatible endpoint
            if base.endswith("/chat/completions"):
                url = base
            elif base.endswith("/v1"):
                url = f"{base}/chat/completions"
            else:
                url = f"{base}/v1/chat/completions"

            payload = {
                "model": self.model,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            logger.debug("LLM request (OpenAI compat) → %s (model=%s)", url, self.model)
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                res_json = response.json()
                if "choices" in res_json and res_json["choices"]:
                    return res_json["choices"][0]["message"]["content"]
                elif "message" in res_json:
                    return res_json["message"]["content"]
                raise ValueError(f"Unexpected LLM response structure: {res_json}")
            except requests.HTTPError as err:
                if err.response is not None and err.response.status_code == 404:
                    fallback_url = f"{self.base_url.split('/v1')[0].rstrip('/')}/api/chat" if "/v1" in self.base_url else "http://localhost:11434/api/chat"
                    logger.warning(
                        "404 on %s — falling back to native Ollama API at %s", url, fallback_url
                    )
                    ollama_payload = {
                        "model": self.model,
                        "messages": payload["messages"],
                        "stream": False,
                        "options": {"temperature": self.temperature},
                    }
                    fb_res = requests.post(fallback_url, json=ollama_payload, headers=headers, timeout=self.timeout)
                    fb_res.raise_for_status()
                    return fb_res.json()["message"]["content"]
                raise


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> tuple[Optional[Dict], bool]:
    """
    Try several strategies to extract a JSON object from LLM output.
    Returns (parsed_dict_or_None, json_was_clean).
    json_was_clean is False when we had to use a fallback.
    """
    # 1. Direct parse
    try:
        return json.loads(text), True
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(stripped), False
    except json.JSONDecodeError:
        pass

    # 3. Find first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group()), False
        except json.JSONDecodeError:
            pass

    return None, False


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
class LLMRecipeParser(BaseRecipeParser):
    """
    Recipe parser that delegates extraction to an LLM.

    This parser is NOT registered with ParserRegistry automatically.
    It is injected by convert.py when --llm-config is provided.
    """

    def __init__(
        self,
        ingredient_parser: BaseIngredientParser,
        config_path: Optional[str] = None,
    ):
        super().__init__(ingredient_parser)
        self.source_format = "LLM"

        cfg = self._load_config(config_path)
        self._client = LLMClient(cfg.get("provider", {}))
        prompt_cfg = cfg.get("prompt", {})
        self._mode: str = prompt_cfg.get("mode", "marked").lower()
        if "system" in prompt_cfg:
            self._system_prompt = prompt_cfg["system"].strip()
        else:
            self._system_prompt = (
                _DEFAULT_SYSTEM if self._mode == "json" else _DEFAULT_MARKED_SYSTEM
            )
        self._max_input_chars: int = int(prompt_cfg.get("max_input_chars", 6000))
        self._sanity = RecipeSanityChecker(cfg.get("sanity", {}))

    # ------------------------------------------------------------------
    # BaseRecipeParser interface
    # ------------------------------------------------------------------

    @classmethod
    def format_id(cls) -> str:
        return "llm"

    @classmethod
    def aliases(cls) -> list[str]:
        return []

    @classmethod
    def priority(cls) -> int:
        return 99  # will not win auto-detection even if somehow registered

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        return 0.0  # never auto-detected

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        clean_content = unroll_markdown_tables(content)
        truncated = clean_content[: self._max_input_chars]
        if len(clean_content) > self._max_input_chars:
            logger.debug(
                "Input truncated from %d to %d chars for %s",
                len(clean_content),
                self._max_input_chars,
                filepath,
            )

        if self._mode == "json":
            user_msg = (
                f"Extract the recipe from the following text:\n\n```\n{truncated}\n```"
            )

            try:
                raw_reply = self._client.chat(self._system_prompt, user_msg)
            except requests.RequestException as exc:
                logger.error("LLM request failed for %s: %s", filepath, exc)
                return

            data, json_ok = _extract_json(raw_reply)
            if data is None:
                logger.error(
                    "Could not extract JSON from LLM reply for %s.\nReply was:\n%s",
                    filepath,
                    raw_reply[:500],
                )
                return

            warnings = self._sanity.check(data, json_ok=json_ok)

            recipe = self._build_recipe(data, filepath)

            if warnings:
                flag_msg = "⚠ HALLUCINATION_FLAG: " + "; ".join(warnings)
                logger.warning("Sanity issues in %s: %s", filepath, "; ".join(warnings))
                if recipe.description:
                    recipe.description = f"{flag_msg} | {recipe.description}"
                else:
                    recipe.description = flag_msg

            yield recipe
        else:
            user_msg = (
                f"Extract and format the recipe from the following raw text into marked Markdown:\n\n```\n{truncated}\n```"
            )

            try:
                raw_reply = self._client.chat(self._system_prompt, user_msg)
            except requests.RequestException as exc:
                logger.warning(
                    "LLM request failed for %s: %s — falling back to direct parser", filepath, exc
                )
                md_parser = GenericMdParser(self.ingredient_parser)
                for r in md_parser.parse_content(clean_content, filepath):
                    r.source_format = f"{self.source_format} (Fallback)"
                    yield r
                return

            clean_markdown = re.sub(
                r"^```(?:markdown|md)?\s*|\s*```$", "", raw_reply.strip(), flags=re.MULTILINE
            )

            md_parser = GenericMdParser(self.ingredient_parser)
            parsed_recipes = list(md_parser.parse_content(clean_markdown, filepath))

            if not parsed_recipes:
                logger.warning(
                    "Could not parse marked Markdown from LLM reply for %s — falling back to direct parser", filepath
                )
                for r in md_parser.parse_content(clean_content, filepath):
                    r.source_format = f"{self.source_format} (Fallback)"
                    yield r
                return

            for recipe in parsed_recipes:
                recipe.source_format = self.source_format
                warnings = self._sanity.check_recipe(recipe)
                if warnings:
                    flag_msg = "⚠ HALLUCINATION_FLAG: " + "; ".join(warnings)
                    logger.warning("Sanity issues in %s: %s", filepath, "; ".join(warnings))
                    if recipe.description:
                        recipe.description = f"{flag_msg} | {recipe.description}"
                    else:
                        recipe.description = flag_msg
                yield recipe

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: Optional[str]) -> Dict[str, Any]:
        if not config_path:
            logger.warning("No LLM config path provided — using built-in defaults")
            return {}
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"LLM config not found: {config_path}")
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _build_recipe(self, data: Dict[str, Any], filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        recipe.title = str(data.get("title", "")).strip()
        recipe.yield_amount = str(data.get("yield_amount", "")).strip()

        cats = data.get("categories", [])
        recipe.categories = [str(c).strip() for c in cats if str(c).strip()] if isinstance(cats, list) else []

        raw_ings = data.get("ingredients", [])
        if isinstance(raw_ings, list):
            for raw in raw_ings:
                raw_str = str(raw).strip()
                if raw_str:
                    recipe.ingredients.append(self.ingredient_parser.parse(raw_str))

        raw_steps = data.get("instructions", [])
        if isinstance(raw_steps, list):
            recipe.instructions = [str(s).strip() for s in raw_steps if str(s).strip()]
        elif isinstance(raw_steps, str) and raw_steps.strip():
            recipe.instructions = [raw_steps.strip()]

        return recipe
