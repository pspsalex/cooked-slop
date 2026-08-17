#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import argparse
import json
import logging
import os
import re
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Iterator, Union

# Import parsers
from parsers import Recipe, BaseIngredientParser, ParserRegistry, get_ingredient_parser
from parsers.llm_parser import LLMRecipeParser
from parsers.units import normalize_unit

# --- Sharding helpers ---
def _get_tokens(text: str) -> set[str]:
    """Extract lowercased word tokens (3+ chars) from text."""
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower().replace("_", " ")))


def _minhash_bucket(text: str, num_perm: int = 16) -> str:
    """
    Computes a short, fast MinHash signature prefix.
    Similar texts yield the same bucket string.
    """
    tokens = _get_tokens(text)
    if not tokens:
        tokens = {"default"}

    sig = []
    for i in range(num_perm):
        min_val = float('inf')
        for token in tokens:
            val = zlib.crc32(f"{i}:{token}".encode('utf-8'))
            if val < min_val:
                min_val = val
        sig.append(min_val)

    bucket_1 = f"{sig[0] % 256:02x}"
    bucket_2 = f"{sig[1] % 256:02x}"
    return f"{bucket_1}/{bucket_2}"


def _get_recipe_sharded_path(
    url: str,
    title: str,
    base_dir: Union[str, Path] = "recipes",
) -> Path:
    """Returns a MinHash-based sharded path for a recipe."""
    bucket_dir = _minhash_bucket(f"{title}")
    return Path(base_dir) / bucket_dir


# --- Logging setup ---
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kws)


logging.Logger.trace = trace
logger = logging.getLogger(__name__)


# --- UI Colors ---
class Colors:
    HEADER = "\001\033[95m\002"
    BLUE = "\001\033[94m\002"
    CYAN = "\001\033[96m\002"
    GREEN = "\001\033[92m\002"
    YELLOW = "\001\033[93m\002"
    RED = "\001\033[91m\002"
    ENDC = "\001\033[0m\002"
    BOLD = "\001\033[1m\002"
    DIM = "\001\033[2m\002"


def print_progress_bar(iteration, total, prefix="", suffix="", length=40, fill="█"):
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{Colors.CYAN}{prefix}{Colors.ENDC} |{bar}| {percent}% {suffix}", end="\r")
    if iteration == total:
        print()


# --- Output Conversion ---
class SchemaOrgConverter:
    """Converter to schema.org Recipe JSON-LD format"""

    def convert(self, recipe: Recipe, parse_ingredients: bool = True, add_date: bool = False) -> dict:
        instructions = self._build_instructions(recipe.instructions)
        recipe_ingredients = []

        if parse_ingredients:
            for ing in recipe.ingredients:
                if ing.quantity or ing.unit:
                    prop_value = {"@type": "PropertyValue", "name": ing.name or ing.raw}
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

        schema_recipe = {
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
    def _build_instructions(instructions: List[str]) -> List:
        if not instructions:
            return []
        if len(instructions) == 1:
            return [instructions[0]]
        return [
            {"@type": "HowToStep", "position": position, "text": instruction}
            for position, instruction in enumerate(instructions, 1)
        ]


class JSONStreamWriter:
    """Writes a JSON array to one or multiple files in a streaming fashion."""

    def __init__(self, base_output_path: Path, indent: int = 2, chunk: bool = False):
        self.base_path = base_output_path
        self.indent = indent
        self.chunk = chunk
        self.max_recipes_per_chunk = 35000
        self.max_chunk_size_bytes = 50 * 1024 * 1024

        self.current_f: Optional[Any] = None
        self.current_chunk_num = 1
        self.current_recipe_count = 0
        self.current_size_bytes = 0
        self.total_recipes = 0

        self.base_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_current_path(self) -> Path:
        if not self.chunk:
            return self.base_path
        return (
            self.base_path.parent
            / f"{self.base_path.stem}_part{self.current_chunk_num:03d}{self.base_path.suffix}"
        )

    def _open_new_file(self):
        dest = self._get_current_path()
        self.current_f = open(dest, "w", encoding="utf-8")
        self.current_f.write("[\n")
        self.current_recipe_count = 0
        self.current_size_bytes = 2  # "[" and "\n"

    def _close_current_file(self):
        if self.current_f:
            self.current_f.write("\n]")
            self.current_f.close()
            self.current_f = None
            self.current_chunk_num += 1

    def write_recipe(self, recipe: dict):
        # Calculate size if needed for chunking
        recipe_json = json.dumps(recipe, indent=self.indent, ensure_ascii=False)
        recipe_size = len(recipe_json.encode("utf-8"))

        # Check if we need to rotate
        if self.chunk and self.current_f:
            if self.current_recipe_count >= self.max_recipes_per_chunk or (
                self.current_recipe_count > 0
                and self.current_size_bytes + recipe_size > self.max_chunk_size_bytes
            ):
                self._close_current_file()

        if not self.current_f:
            self._open_new_file()
        elif self.current_recipe_count > 0:
            self.current_f.write(",\n")
            self.current_size_bytes += 2

        self.current_f.write(recipe_json)
        self.current_recipe_count += 1
        self.total_recipes += 1
        self.current_size_bytes += recipe_size

    def close(self):
        self._close_current_file()
        if self.total_recipes == 0 and not self.chunk:
            # Create an empty array file if no recipes were processed
            self._open_new_file()
            self._close_current_file()


# --- CLI and Processing Logic ---
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Recipes (MealMaster, MasterCook, PDF, HTML, CSV) to schema.org JSON-LD format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input", type=Path, help="Input file or directory containing recipe files"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("./converted_recipes"),
        help="Output directory or file (default: ./converted_recipes)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Scan directories recursively"
    )
    parser.add_argument(
        "--multiple-per-file",
        action="store_true",
        help="Save all recipes from a file into a single JSON file",
    )
    parser.add_argument(
        "--no-parse-ingredients",
        action="store_true",
        help="Keep ingredients as plain text",
    )
    parser.add_argument(
        "--no-nlp",
        action="store_true",
        help="Disable NLP ingredient parsing even if installed",
    )
    parser.add_argument("--chunk", action="store_true", help="Split output into chunks")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "--debug-sql",
        action="store_true",
        help="Show SQL queries at TRACE level (must be explicitly enabled, -v does not imply this)",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=ParserRegistry.all_format_names(),
        help="Override auto-detection and specify input format",
    )
    parser.add_argument(
        "--llm-config",
        type=Path,
        default=None,
        metavar="CONFIG",
        help="Path to LLM provider YAML config. When set, all files are parsed "
        "via the configured LLM instead of the auto-detected parser.",
    )
    parser.add_argument(
        "--html-config",
        type=Path,
        default=None,
        metavar="CONFIG",
        help="Path to HTML XPath layout YAML config.",
    )
    parser.add_argument(
        "--shard",
        action="store_true",
        help="Shard output into subdirectories based on recipe title MinHash bucket",
    )
    parser.add_argument(
        "--add-date",
        action="store_true",
        help="Output publishing dates in the resulting json."
    )
    return parser.parse_args()


def convert_recipe_file(
    input_path: Path,
    output_dir: Path,
    one_file_per_recipe: bool,
    verbose: bool,
    parse_ingredients: bool,
    ingredient_parser: BaseIngredientParser,
    format_name: Optional[str] = None,
    stream_writer: Optional[JSONStreamWriter] = None,
    debug_sql: bool = False,
    llm_parser: Optional["LLMRecipeParser"] = None,
    shard: bool = False,
    add_date: bool = False,
    html_config: Optional[Path] = None,
) -> int:
    if llm_parser is not None:
        parser = llm_parser
    else:
        parser = ParserRegistry.get_parser(
            input_path, ingredient_parser, format_name, debug=debug_sql
        )
        if parser is not None and hasattr(parser, "config_path") and html_config is not None:
            parser.config_path = str(html_config)

    if not parser:
        if verbose:
            print(
                f"{Colors.RED}Unsupported file format: {input_path.suffix}{Colors.ENDC}"
            )
        return 0

    try:
        recipe_count = 0
        converter = SchemaOrgConverter()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Collect recipes when writing multiple recipes per file (no stream_writer, not one_file_per_recipe)
        collected_recipes: List[dict] = []

        # Process recipes as they're yielded from the parser
        for recipe in parser.parse_file(str(input_path)):
            recipe_count += 1
            schema_recipe = converter.convert(recipe, parse_ingredients, add_date)

            if stream_writer:
                stream_writer.write_recipe(schema_recipe)
                if verbose:
                    print(f"  {Colors.GREEN}✓{Colors.ENDC} {schema_recipe.get('name')}")
            elif one_file_per_recipe:
                title = schema_recipe.get("name", "Untitled")
                url = schema_recipe.get("url", "")
                target_dir = (
                    _get_recipe_sharded_path(url, title, base_dir=output_dir)
                    if shard
                    else output_dir
                )
                target_dir.mkdir(parents=True, exist_ok=True)

                safe_name = re.sub(
                    r"[^\w\s-]", "", title
                ).strip()
                safe_name = re.sub(r"[-\s]+", "_", safe_name)
                output_file = target_dir / f"{safe_name}.json"
                counter = 1
                while output_file.exists():
                    output_file = target_dir / f"{safe_name}_{counter}.json"
                    counter += 1
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(schema_recipe, f, indent=2, ensure_ascii=False)
                if verbose:
                    print(
                        f"  {Colors.GREEN}✓{Colors.ENDC} {schema_recipe.get('name')} → {output_file}"
                    )
            else:
                collected_recipes.append(schema_recipe)
                if verbose:
                    print(f"  {Colors.GREEN}✓{Colors.ENDC} {schema_recipe.get('name')}")

        if recipe_count == 0:
            if verbose:
                print(f"{Colors.YELLOW}No recipes found in {input_path}{Colors.ENDC}")
            return 0

        # For multiple recipes per file mode, write all collected recipes to a single JSON file
        if collected_recipes:
            output_file = output_dir / f"{input_path.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(collected_recipes, f, indent=2, ensure_ascii=False)
            if verbose:
                print(
                    f"{Colors.GREEN}Converted {recipe_count} recipes → {output_file.name}{Colors.ENDC}"
                )

        return input_path.stat().st_size
    except Exception as e:
        if verbose:
            print(f"{Colors.RED}Error parsing {input_path}: {e}{Colors.ENDC}")
        import traceback

        if verbose:
            traceback.print_exc()
        return 0


def process_directory(
    input_dir: Path,
    output_dir: Path,
    one_file_per_recipe: bool,
    verbose: bool,
    recursive: bool,
    parse_ingredients: bool,
    ingredient_parser: BaseIngredientParser,
    format_name: Optional[str] = None,
    stream_writer: Optional[JSONStreamWriter] = None,
    debug_sql: bool = False,
    llm_parser: Optional["LLMRecipeParser"] = None,
    shard: bool = False,
    add_date: bool = False,
    html_config: Optional[Path] = None,
) -> None:
    # Updated extensions to include stubs explicitly supported by ParserFactory.
    extensions = {
        ".mca",
        ".mmf",
        ".mm",
        ".mxp",
        ".mx2",
        ".mz2",
        ".txt",
        ".html",
        ".htm",
        ".pdf",
        ".jpg",
        ".png",
        ".sqlite",
        ".db",
        ".csv",
        ".ccf",
        ".md",
    }
    extensions.update([e.upper() for e in extensions])

    recipe_files = []
    if recursive:
        for ext in extensions:
            recipe_files.extend(input_dir.rglob(f"*{ext}"))
    else:
        for ext in extensions:
            recipe_files.extend(input_dir.glob(f"*{ext}"))
        if not recipe_files:
            for ext in extensions:
                recipe_files.extend(input_dir.rglob(f"*{ext}"))
            if recipe_files:
                print(
                    f"{Colors.YELLOW}ℹ No recipe files found at root level of {input_dir}, but found {len(recipe_files)} file(s) in subdirectories (auto-enabling recursive scan).{Colors.ENDC}"
                )

    if not recipe_files:
        print(f"{Colors.RED}No recipe files found in {input_dir}{Colors.ENDC}")
        return

    total_bytes = sum(f.stat().st_size for f in recipe_files)
    processed_bytes = 0

    print(f"\n{Colors.BOLD}{Colors.CYAN}🍳 Modular Recipe Converter{Colors.ENDC}")
    print(
        f"{Colors.DIM}Found {len(recipe_files)} file(s) ({total_bytes:,} bytes){Colors.ENDC}\n"
    )

    for file_idx, recipe_file in enumerate(recipe_files, 1):
        if verbose:
            rel_path = (
                recipe_file.relative_to(input_dir)
                if input_dir in recipe_file.parents
                else recipe_file
            )
            print(
                f"\n{Colors.BOLD}[{file_idx}/{len(recipe_files)}]{Colors.ENDC} {Colors.CYAN}{rel_path}{Colors.ENDC}"
            )

        bytes_processed = convert_recipe_file(
            recipe_file,
            output_dir,
            one_file_per_recipe,
            verbose,
            parse_ingredients,
            ingredient_parser,
            format_name,
            stream_writer,
            debug_sql=debug_sql,
            llm_parser=llm_parser,
            shard=shard,
            add_date=add_date,
            html_config=html_config,
        )
        processed_bytes += (
            recipe_file.stat().st_size if bytes_processed == 0 else bytes_processed
        )

        if not verbose:
            print_progress_bar(
                processed_bytes,
                total_bytes,
                prefix="Converting",
                suffix=recipe_file.name,
            )

    if not verbose:
        print()


def main():
    args = parse_arguments()

    # Configure logging based on flags
    # -v/--verbose sets INFO level, but doesn't enable TRACE for SQL
    # --debug-sql explicitly enables TRACE level for SQL queries
    if args.debug_sql:
        log_level = TRACE_LEVEL
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level, format="%(name)s - %(levelname)s - %(message)s"
    )

    print("")
    print(
        f"{Colors.BOLD}{Colors.HEADER}╔══════════════════════════════════════╗{Colors.ENDC}"
    )
    print(
        f"{Colors.BOLD}{Colors.HEADER}║   🍳 Recipe Format Converter 🍳      ║{Colors.ENDC}"
    )
    print(
        f"{Colors.BOLD}{Colors.HEADER}╚══════════════════════════════════════╝{Colors.ENDC}\n"
    )

    parse_ingredients = not args.no_parse_ingredients
    use_nlp = not args.no_nlp
    ingredient_parser = get_ingredient_parser(use_nlp=use_nlp)

    from parsers.ingredients import HAS_NLP_PARSER

    if HAS_NLP_PARSER and use_nlp:
        print(f"{Colors.GREEN}✓ Using NLP Ingredient Parser{Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}ℹ Using Regex Fallback Ingredient Parser{Colors.ENDC}")

    # Build LLM parser if requested
    llm_parser = None
    if args.llm_config:
        if not args.llm_config.exists():
            print(
                f"{Colors.RED}Error: LLM config not found: {args.llm_config}{Colors.ENDC}"
            )
            return 1
        print(
            f"{Colors.CYAN}✓ LLM mode enabled — config: {args.llm_config}{Colors.ENDC}"
        )
        llm_parser = LLMRecipeParser(
            ingredient_parser, config_path=str(args.llm_config)
        )

    output_is_file = args.output.suffix != ""
    stream_writer = None
    if output_is_file:
        stream_writer = JSONStreamWriter(args.output, chunk=args.chunk)

    try:
        if args.input.is_file():
            if not args.verbose:
                print(f"{Colors.CYAN}Converting:{Colors.ENDC} {args.input.name}")
                print_progress_bar(
                    0,
                    args.input.stat().st_size,
                    prefix="Processing",
                    suffix=args.input.name,
                )

            convert_recipe_file(
                args.input,
                args.output.parent if output_is_file else args.output,
                not args.multiple_per_file,
                args.verbose,
                parse_ingredients,
                ingredient_parser,
                args.format,
                stream_writer,
                debug_sql=args.debug_sql,
                llm_parser=llm_parser,
                shard=args.shard,
                add_date=args.add_date,
                html_config=args.html_config,
            )

            if not args.verbose:
                print_progress_bar(
                    args.input.stat().st_size,
                    args.input.stat().st_size,
                    prefix="Processing",
                    suffix="Complete!",
                )

        elif args.input.is_dir():
            process_directory(
                args.input,
                args.output.parent if output_is_file else args.output,
                not args.multiple_per_file,
                args.verbose,
                args.recursive,
                parse_ingredients,
                ingredient_parser,
                args.format,
                stream_writer,
                debug_sql=args.debug_sql,
                llm_parser=llm_parser,
                shard=args.shard,
                add_date=args.add_date,
                html_config=args.html_config,
            )
        else:
            print(f"{Colors.RED}Error: {args.input} not found{Colors.ENDC}")
            return 1

        if stream_writer:
            stream_writer.close()

        print(f"\n{Colors.GREEN}{Colors.BOLD}✨ Conversion finished! ✨{Colors.ENDC}")
        print(f"{Colors.DIM}Output saved to: {args.output.absolute()}{Colors.ENDC}\n")
        return 0
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}Forced exit - data may be incomplete{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    exit(main())
