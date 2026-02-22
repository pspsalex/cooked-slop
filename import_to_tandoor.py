#!/usr/bin/env python3
"""
Import schema.org JSON-LD recipes into Tandoor Recipes via the REST API.

Usage:
    python import_recipes.py --url https://tandoor.example.com --api-key YOUR_KEY [--recursive] path1 path2 ...
"""

import argparse
import json
import sys
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_json_files(paths: list[str], recursive: bool) -> list[Path]:
    """Collect all .json files from the given list of files/directories."""
    result = []
    for raw in paths:
        p = Path(raw)
        if p.is_file() and p.suffix.lower() == ".json":
            result.append(p)
        elif p.is_dir():
            pattern = "**/*.json" if recursive else "*.json"
            result.extend(sorted(p.glob(pattern)))
        else:
            print(f"[WARN] Skipping '{raw}': not a .json file or directory", file=sys.stderr)
    return result


def extract_recipes(data) -> list[dict]:
    """
    Return a flat list of schema.org Recipe objects from arbitrary JSON-LD input.
    Handles:
      - A single Recipe object  { "@type": "Recipe", ... }
      - A list of Recipe objects
      - A @graph wrapper        { "@graph": [...] }
      - Nested @graph inside a list
    """
    recipes = []

    def _collect(obj):
        if isinstance(obj, list):
            for item in obj:
                _collect(item)
        elif isinstance(obj, dict):
            if "@graph" in obj:
                _collect(obj["@graph"])
                return
            types = obj.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if any(t == "Recipe" or t.endswith("/Recipe") for t in types):
                recipes.append(obj)

    _collect(data)
    return recipes


# ---------------------------------------------------------------------------
# Schema.org -> Tandoor conversion
# ---------------------------------------------------------------------------

def to_list(val) -> list:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def parse_duration_to_minutes(iso: str | None) -> int | None:
    """Very simple ISO 8601 duration parser (PTxHxM only)."""
    if not iso:
        return None
    iso = iso.upper().lstrip("P")
    minutes = 0
    buf = ""
    for ch in iso:
        if ch.isdigit() or ch == ".":
            buf += ch
        elif ch == "T":
            pass
        elif ch == "H":
            minutes += int(float(buf) * 60)
            buf = ""
        elif ch == "M":
            minutes += int(float(buf))
            buf = ""
        elif ch == "S":
            buf = ""
    return minutes if minutes else None


def parse_ingredient(ing, order: int) -> dict:
    """
    Convert a schema.org ingredient into a structured Tandoor ingredient dict.

    Three cases:
      1. PropertyValue  -> structured: amount=value, unit=unitText, food=name
                          Fractions like "1/2" are evaluated to 0.5.
                          Non-numeric values go into note with no_amount=True.
      2. Plain string   -> no_amount=True, full string as food name
      3. Other dict     -> no_amount=True, name/text field as food name
    """
    base: dict = {"note": "", "order": order, "is_header": False}

    if isinstance(ing, dict):
        types = ing.get("@type", "")
        if isinstance(types, str):
            types = [types]
        is_pv = any(t == "PropertyValue" or t.endswith("/PropertyValue") for t in types)

        if is_pv:
            raw_value = ing.get("value", "")
            unit_text = str(ing.get("unitText", "") or "").strip()
            food_name = str(ing.get("name", "") or "").strip()

            amount = 0.0
            no_amount = False
            try:
                raw_str = str(raw_value).strip()
                if "/" in raw_str:
                    num, den = raw_str.split("/", 1)
                    amount = float(num.strip()) / float(den.strip())
                else:
                    amount = float(raw_str)
            except (ValueError, ZeroDivisionError):
                no_amount = True
                base["note"] = str(raw_value).strip()

            return {
                **base,
                "amount": amount,
                "unit": {"name": unit_text} if unit_text else None,
                "food": {"name": food_name or json.dumps(ing)},
                "no_amount": no_amount,
            }

        # HowToIngredient or other dict -- no structured split available
        food_name = (ing.get("name") or ing.get("text") or "").strip() or json.dumps(ing)
        return {**base, "amount": 0, "unit": None, "food": {"name": food_name}, "no_amount": True}

    # Plain string
    return {**base, "amount": 0, "unit": None, "food": {"name": str(ing).strip()}, "no_amount": True}


def step_text(step) -> str:
    if isinstance(step, str):
        return step.strip()
    if isinstance(step, dict):
        if step.get("@type") in ("HowToSection",):
            sub_steps = to_list(step.get("itemListElement", []))
            return "\n".join(step_text(s) for s in sub_steps)
        return (step.get("text") or step.get("name") or "").strip()
    return str(step)


def recipe_to_tandoor(rec: dict) -> dict:
    """Convert a schema.org Recipe dict into the Tandoor API payload format."""

    name = rec.get("name") or rec.get("headline") or "Untitled Recipe"
    description = rec.get("description", "")

    # Servings
    servings_raw = rec.get("recipeYield")
    servings = 1
    if servings_raw:
        if isinstance(servings_raw, list):
            servings_raw = servings_raw[0]
        try:
            servings = int(str(servings_raw).split()[0])
        except (ValueError, AttributeError):
            pass

    # Times (in minutes)
    prep_time = parse_duration_to_minutes(rec.get("prepTime"))
    cook_time = parse_duration_to_minutes(rec.get("cookTime"))
    total_time = parse_duration_to_minutes(rec.get("totalTime"))
    working_time = prep_time or 0
    waiting_time = cook_time or 0
    if total_time and not (prep_time or cook_time):
        working_time = total_time

    # Keywords / categories
    keywords = []
    for kw_field in ("keywords", "recipeCategory", "recipeCuisine"):
        raw = rec.get(kw_field)
        if not raw:
            continue
        if isinstance(raw, str):
            for k in raw.split(","):
                k = k.strip()
                if k:
                    keywords.append({"name": k})
        elif isinstance(raw, list):
            for k in raw:
                k = str(k).strip()
                if k:
                    keywords.append({"name": k})
    seen_kw: set[str] = set()
    unique_keywords = []
    for kw in keywords:
        n = kw["name"].lower()
        if n not in seen_kw:
            seen_kw.add(n)
            unique_keywords.append(kw)

    # Source URL
    source_url = rec.get("url") or rec.get("@id") or ""
    if source_url and not source_url.startswith("http"):
        source_url = ""

    # Ingredients -- preserve structured PropertyValue data where available;
    # plain strings are stored as no_amount food entries.
    ingredients_raw = to_list(rec.get("recipeIngredient", []))
    tandoor_ingredients = [
        parse_ingredient(i, order)
        for order, i in enumerate(ingredients_raw)
        if i
    ]

    # Steps / instructions -- all ingredients are attached to the first step
    instructions_raw = rec.get("recipeInstructions", [])
    if isinstance(instructions_raw, str):
        instruction_blocks = [instructions_raw.strip()]
    else:
        instruction_blocks = [step_text(s) for s in to_list(instructions_raw) if s]

    steps = []
    for idx, block in enumerate(instruction_blocks):
        steps.append({
            "name": "",
            "instruction": block,
            "ingredients": tandoor_ingredients if idx == 0 else [],
        })

    if not steps:
        steps.append({"name": "", "instruction": "", "ingredients": tandoor_ingredients})

    return {
        "name": name,
        "description": description,
        "servings": servings,
        "servings_text": "",
        "working_time": working_time,
        "waiting_time": waiting_time,
        "source_url": source_url,
        "keywords": unique_keywords,
        "steps": steps,
        "internal": True,
    }


# ---------------------------------------------------------------------------
# Tandoor API client
# ---------------------------------------------------------------------------

class TandoorClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def import_recipe(self, payload: dict) -> tuple[bool, str]:
        url = f"{self.base_url}/api/recipe/"
        try:
            resp = self.session.post(url, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                recipe_id = resp.json().get("id", "?")
                return True, f"Created recipe ID {recipe_id}"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            return False, f"Request error: {e}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import schema.org JSON-LD recipes into Tandoor Recipes."
    )
    parser.add_argument("--url", "-u", required=True,
                        help="Base URL of the Tandoor installation (e.g. https://tandoor.example.com)")
    parser.add_argument("--api-key", "-k", required=True,
                        help="Tandoor API key (Bearer token)")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Recursively search directories for JSON files")
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="JSON files or directories to import")
    args = parser.parse_args()

    client = TandoorClient(args.url, args.api_key)

    json_files = find_json_files(args.paths, args.recursive)
    if not json_files:
        print("No JSON files found.", file=sys.stderr)
        sys.exit(1)

    total_recipes = total_ok = total_fail = 0

    for jf in json_files:
        print(f"\n-- {jf}")
        try:
            with open(jf, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            print(f"   [ERROR] Could not read file: {e}", file=sys.stderr)
            continue

        recipes = extract_recipes(data)
        if not recipes:
            print("   [SKIP] No schema.org Recipe objects found.")
            continue

        for rec in recipes:
            recipe_name = rec.get("name") or "Untitled"
            total_recipes += 1
            payload = recipe_to_tandoor(rec)
            ok, msg = client.import_recipe(payload)
            print(f"   [{'OK' if ok else 'FAIL'}] {recipe_name!r} -- {msg}")
            if ok:
                total_ok += 1
            else:
                total_fail += 1

    print(f"\n{'='*50}")
    print(f"Done. {total_ok}/{total_recipes} recipes imported successfully."
          + (f" ({total_fail} failed)" if total_fail else ""))


if __name__ == "__main__":
    main()
