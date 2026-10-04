# SPDX-License-Identifier: MIT
"""Audit and inspect converted recipes JSON for anomalies and quality issues."""

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit converted recipe JSON for missing steps, empty ingredients, anomalies, and formatting bugs."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="all_recipes.json",
        help="Path to JSON file containing recipes array (default: all_recipes.json)",
    )
    parser.add_argument(
        "--random",
        type=int,
        default=0,
        metavar="N",
        help="Pick N random recipes to inspect in detail",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic inspection (default: 42)",
    )
    parser.add_argument(
        "--show",
        choices=["empty", "no-steps", "no-ings", "few-ings", "long-ings", "monsters", "bad-titles", "encoding"],
        help="Display detailed list of examples for a specific issue category",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max number of items to show when using --show (default: 10)",
    )
    return parser.parse_args()


def extract_format(recipe: Dict[str, Any]) -> str:
    desc = recipe.get("description") or ""
    m = re.search(r"converted from ([^)]+) format", desc)
    if m:
        return m.group(1)
    if "sqlite" in (recipe.get("comment") or "").lower():
        return "SQLite"
    return "Unknown / Not Set"


def extract_ingredient_text(ing: Any) -> str:
    if isinstance(ing, dict):
        return ing.get("name") or ing.get("description") or ing.get("value") or ""
    return str(ing)


def extract_instruction_text(inst: Any) -> str:
    if isinstance(inst, dict):
        return inst.get("text") or inst.get("name") or ""
    return str(inst)


def is_suspicious_title(name: str) -> bool:
    if not name or not name.strip():
        return True
    s = name.strip()
    if s.lower() in {"untitled", "unknown", "recipe", "no title", "recipe by :", "ingredients"}:
        return True
    # Email headers as title
    if re.match(r"^(From|Date|Subject|To|Message-ID|Re):\s*", s, re.IGNORECASE):
        return True
    # Digest filenames as title
    if re.match(r"^v\d{3}n\d{3}", s, re.IGNORECASE):
        return True
    # Nutrition lines as title
    if re.search(r"calories from fat|dietary fiber|total fat", s, re.IGNORECASE):
        return True
    # QTitle or prefix remnants
    if re.match(r"^QTitle:\s*", s, re.IGNORECASE):
        return True
    # Pandoc underline/bold formatting artifacts
    if re.search(r"\[.+\]\{.*\}", s):
        return True
    return False


def print_recipe_card(idx: int, r: Dict[str, Any], show_full: bool = False) -> None:
    name = r.get("name") or "<NO TITLE>"
    fmt = extract_format(r)
    comment = r.get("comment") or "<No source comment>"
    yield_amt = r.get("recipeYield")
    category = r.get("recipeCategory")
    ings = r.get("recipeIngredient") or []
    insts = r.get("recipeInstructions") or []
    if isinstance(insts, str):
        insts = [insts]

    print(f"\n--- [Recipe #{idx}] {name} ---")
    print(f"  Format:   {fmt}")
    print(f"  Source:   {comment}")
    if yield_amt:
        print(f"  Yield:    {yield_amt}")
    if category:
        print(f"  Category: {category}")
    print(f"  Ingredients ({len(ings)}):")
    limit_ings = len(ings) if show_full else min(len(ings), 4)
    for i, ing in enumerate(ings[:limit_ings]):
        if isinstance(ing, dict):
            val = ing.get("value", "")
            unit = ing.get("unitText", "")
            iname = ing.get("name", "")
            qty_str = f"{val} {unit}".strip()
            print(f"    {i+1}. {iname}" + (f" [{qty_str}]" if qty_str else ""))
        else:
            print(f"    {i+1}. {ing}")
    if len(ings) > limit_ings:
        print(f"    ... and {len(ings) - limit_ings} more ingredients")

    print(f"  Instructions ({len(insts)}):")
    limit_insts = len(insts) if show_full else min(len(insts), 3)
    for i, step in enumerate(insts[:limit_insts]):
        text = extract_instruction_text(step).replace("\n", " ").strip()
        if len(text) > 120 and not show_full:
            text = text[:117] + "..."
        print(f"    Step {i+1}: {text}")
    if len(insts) > limit_insts:
        print(f"    ... and {len(insts) - limit_insts} more steps")


def main() -> None:
    args = parse_args()
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading '{filepath}'...")
    with open(filepath, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    total = len(recipes)
    print(f"Loaded {total:,} recipes.")

    # Categorize issues
    format_counts = Counter()
    empty_both = []
    zero_ing = []
    zero_inst = []
    few_ing = []
    long_ing = []
    monsters = []
    bad_titles = []
    encoding_issues = []

    for idx, r in enumerate(recipes):
        fmt = extract_format(r)
        format_counts[fmt] += 1

        name = r.get("name") or ""
        ings = r.get("recipeIngredient") or []
        insts = r.get("recipeInstructions") or []
        if isinstance(insts, str):
            insts = [insts]

        num_ing = len(ings)
        num_inst = len(insts)

        # 1. Empty both
        if num_ing == 0 and num_inst == 0:
            empty_both.append(idx)
        elif num_ing == 0:
            zero_ing.append(idx)
        elif num_inst == 0:
            zero_inst.append(idx)
        elif num_ing <= 2:
            few_ing.append(idx)

        # 2. Giant recipes / un-split books
        if num_ing > 50 or num_inst > 50:
            monsters.append(idx)

        # 3. Long ingredients
        for ing in ings:
            txt = extract_ingredient_text(ing)
            if len(txt) > 120:
                long_ing.append(idx)
                break

        # 4. Bad / suspicious titles
        if is_suspicious_title(name):
            bad_titles.append(idx)

        # 5. Encoding issues / unescaped entities
        full_text = f"{name} {extract_format(r)} " + " ".join(extract_ingredient_text(i) for i in ings[:10])
        if "\ufffd" in full_text or "â€" in full_text or "Cafe«" in full_text or "&amp;" in full_text:
            encoding_issues.append(idx)

    # Print summary
    print("\n" + "=" * 65)
    print("                RECIPE AUDIT SUMMARY")
    print("=" * 65)
    print(f"Total recipes: {total:,}\n")

    print("Format Breakdown:")
    for fmt, count in format_counts.most_common():
        pct = (count / total) * 100
        print(f"  - {fmt:30s}: {count:6,d} ({pct:5.1f}%)")

    print("\nDetected Problem Categories:")
    issues = [
        ("Empty both (0 ingredients & 0 steps)", len(empty_both), "empty"),
        ("Missing ingredients (0 ing, has steps)", len(zero_ing), "no-ings"),
        ("Missing instructions (has ing, 0 steps)", len(zero_inst), "no-steps"),
        ("Suspiciously few ingredients (1-2 ing)", len(few_ing), "few-ings"),
        ("Excessively long ingredients (>120 chars)", len(long_ing), "long-ings"),
        ("Giant multi-recipe files (>50 items)", len(monsters), "monsters"),
        ("Suspicious / malformed titles", len(bad_titles), "bad-titles"),
        ("Encoding glitches / entities", len(encoding_issues), "encoding"),
    ]

    for label, count, key in issues:
        pct = (count / total) * 100
        flag_hint = f"--show {key}"
        print(f"  - {label:42s}: {count:6,d} ({pct:5.1f}%) -> {flag_hint}")

    if args.show:
        mapping = {
            "empty": empty_both,
            "no-ings": zero_ing,
            "no-steps": zero_inst,
            "few-ings": few_ing,
            "long-ings": long_ing,
            "monsters": monsters,
            "bad-titles": bad_titles,
            "encoding": encoding_issues,
        }
        target_list = mapping[args.show]
        print("\n" + "=" * 65)
        print(f"  SHOWING UP TO {args.limit} EXAMPLES FOR: {args.show.upper()}")
        print("=" * 65)
        for idx in target_list[:args.limit]:
            print_recipe_card(idx, recipes[idx])

    if args.random > 0:
        print("\n" + "=" * 65)
        print(f"        {args.random} RANDOM RECIPES INSPECTION (Seed: {args.seed})")
        print("=" * 65)
        random.seed(args.seed)
        chosen = random.sample(range(total), args.random)
        for i, idx in enumerate(chosen, 1):
            print(f"\n[Random Sample {i} of {args.random}]")
            print_recipe_card(idx, recipes[idx], show_full=False)


if __name__ == "__main__":
    main()
