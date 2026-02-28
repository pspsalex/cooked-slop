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
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = f"{self.base_url}/chat/completions"
        logger.debug("LLM request → %s (model=%s)", url, self.model)
        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


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
        self._system_prompt: str = cfg.get("prompt", {}).get("system", _DEFAULT_SYSTEM).strip()
        self._max_input_chars: int = int(cfg.get("prompt", {}).get("max_input_chars", 6000))
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
        truncated = content[: self._max_input_chars]
        if len(content) > self._max_input_chars:
            logger.debug(
                "Input truncated from %d to %d chars for %s",
                len(content),
                self._max_input_chars,
                filepath,
            )

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
            # Preserve any description the recipe already has
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
