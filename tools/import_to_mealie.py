#!/usr/bin/env python3
"""
Import schema.org JSON-LD recipes into Mealie via the REST API.

Usage:
    python import_recipes_to_mealie.py <mealie_url> <api_key> [--recursive] <file_or_folder> [...]

Arguments:
    mealie_url      Base URL of your Mealie installation (e.g. https://mealie.example.com)
    api_key         Mealie API key (Settings → API Tokens)
    -r, --recursive Recursively search folders for JSON files
    paths           One or more JSON files or folders to import from
"""

import argparse
import json
import sys
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_json_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Expand a list of files/folders to a flat list of .json files."""
    result = []
    for p in paths:
        if p.is_file():
            if p.suffix.lower() == ".json":
                result.append(p)
            else:
                print(f"[SKIP] Not a JSON file: {p}")
        elif p.is_dir():
            pattern = "**/*.json" if recursive else "*.json"
            found = sorted(p.glob(pattern))
            if not found:
                print(f"[WARN] No JSON files found in: {p}")
            result.extend(found)
        else:
            print(f"[WARN] Path not found: {p}")
    return result


def extract_recipes(data: dict | list) -> list[dict]:
    """
    Return a list of schema.org Recipe objects from parsed JSON.

    Handles:
      - A single Recipe object              {"@type": "Recipe", ...}
      - A list of objects                   [{...}, {...}]
      - A @graph array                      {"@graph": [{...}, {...}]}
      - Nested inside a webpage/article     {"@type": "WebPage", "mainEntity": {...}}
    """
    recipes = []

    def _is_recipe(obj):
        if not isinstance(obj, dict):
            return False
        t = obj.get("@type", "")
        if isinstance(t, list):
            return "Recipe" in t
        return t == "Recipe"

    def _collect(obj):
        if isinstance(obj, list):
            for item in obj:
                _collect(item)
        elif isinstance(obj, dict):
            if _is_recipe(obj):
                recipes.append(obj)
            else:
                # Check @graph
                if "@graph" in obj:
                    _collect(obj["@graph"])
                # Check mainEntity / mainEntityOfPage
                for key in ("mainEntity", "mainEntityOfPage"):
                    if key in obj:
                        _collect(obj[key])

    _collect(data)
    return recipes


# ---------------------------------------------------------------------------
# Mealie API
# ---------------------------------------------------------------------------

class MealieClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def test_connection(self):
        resp = self.session.get(f"{self.base_url}/api/app/about", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def create_recipe(self, payload: dict) -> dict:
        """
        Create a recipe. Mealie supports POST /api/recipes with a full payload.
        Falls back to the two-step create-then-patch approach if needed.
        """
        print(f" >> URL: {payload.get('url')}")
        resp = self.session.post(
            f"{self.base_url}/api/recipes/create/html-or-json",
            json={
              "includeTags": True,
              "includeCategories": True,
              "data": json.dumps(payload),
              "url": payload.get('url'),
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import schema.org JSON-LD recipes into Mealie.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("mealie_url", help="Base URL of Mealie (e.g. https://mealie.example.com)")
    parser.add_argument("api_key", help="Mealie API key")
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively search folders for JSON files",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="FILE_OR_FOLDER",
        help="JSON files or folders containing JSON files",
    )
    args = parser.parse_args()

    client = MealieClient(args.mealie_url, args.api_key)

    # Verify connection
    print(f"Connecting to Mealie at {args.mealie_url} …")
    try:
        info = client.test_connection()
        version = info.get("version", "unknown")
        print(f"Connected  (Mealie {version})\n")
    except Exception as e:
        print(f"[ERROR] Could not connect to Mealie: {e}")
        sys.exit(1)

    # Collect files
    json_files = find_json_files([Path(p) for p in args.paths], args.recursive)
    if not json_files:
        print("No JSON files found. Exiting.")
        sys.exit(0)

    print(f"Found {len(json_files)} JSON file(s) to process.\n")

    total_imported = 0
    total_failed = 0

    for json_file in json_files:
        print(f"Processing: {json_file}")
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [ERROR] Could not read file: {e}")
            total_failed += 1
            continue

        recipes = extract_recipes(data)
        if not recipes:
            print("  [SKIP] No schema.org Recipe objects found in this file.")
            continue

        print(f"  Found {len(recipes)} recipe(s).")
        for recipe in recipes:
            name = recipe.get("name", "<unnamed>")
            try:
                result = client.create_recipe(recipe)
                slug = result.get("slug", "?") if isinstance(result, dict) else str(result)
                print(f"  [OK]    '{name}'  →  slug: {slug}")
                total_imported += 1
            except requests.HTTPError as e:
                body = ""
                try:
                    body = e.response.json()
                except Exception:
                    body = e.response.text[:200]
                print(f"  [FAIL]  '{name}'  →  HTTP {e.response.status_code}: {body}")
                total_failed += 1
            except Exception as e:
                print(f"  [FAIL]  '{name}'  →  {e}")
                total_failed += 1

    print(f"\nDone.  Imported: {total_imported}  |  Failed: {total_failed}")


if __name__ == "__main__":
    main()
