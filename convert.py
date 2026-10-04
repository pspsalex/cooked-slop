#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import argparse
import concurrent.futures
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterator, List, Optional, Union

# Modular architecture imports (SPEC-015, SPEC-036)
from core.converter import SchemaOrgConverter
from core.writer import JSONStreamWriter
from core.shard import (
    get_tokens,
    minhash_bucket,
    get_recipe_sharded_path,
    _get_tokens,
    _minhash_bucket,
    _get_recipe_sharded_path,
)
from core.ui import Colors, print_progress_bar

# Import parsers
from parsers import Recipe, BaseIngredientParser, ParserRegistry, get_ingredient_parser
from parsers.llm_parser import LLMRecipeParser

# Backward compatibility re-exports
__all__ = [
    "SchemaOrgConverter",
    "JSONStreamWriter",
    "Colors",
    "print_progress_bar",
    "get_recipe_sharded_path",
    "get_tokens",
    "minhash_bucket",
    "_get_recipe_sharded_path",
    "_minhash_bucket",
    "_get_tokens",
    "parse_arguments",
    "configure_logging",
    "NLP_LOGGERS",
    "convert_recipe_file",
    "process_directory",
    "main",
]

# --- Logging setup ---
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kws)


logging.Logger.trace = trace
logger = logging.getLogger(__name__)

NLP_LOGGERS = ("ingredient-parser", "ingredient_parser", "nltk")


def configure_logging(
    verbose: int = 0, debug_sql: bool = False, debug_nlp: bool = False
) -> None:
    """Configure root and library logger levels according to verbosity flags."""
    if debug_sql:
        log_level = TRACE_LEVEL
    elif verbose >= 1:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    # NLP logging: only DEBUG if -vv (verbose >= 2) or --debug-nlp
    nlp_level = logging.DEBUG if (debug_nlp or verbose >= 2) else logging.INFO
    for logger_name in NLP_LOGGERS:
        logging.getLogger(logger_name).setLevel(nlp_level)


# --- CLI and Processing Logic ---
def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
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
        "-r",
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Scan directories recursively (default: True, use --no-recursive to disable)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of concurrent worker processes for directory conversion (default: auto)",
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
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity level: -v for conversion/app details, -vv for deep NLP debug traces",
    )
    parser.add_argument(
        "--debug-nlp",
        action="store_true",
        default=False,
        help="Explicitly enable detailed NLP ingredient parser debug logging",
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
    parser.add_argument(
        "--ext",
        nargs="+",
        default=None,
        help="Explicit list of file extensions to process (e.g. --ext .mmf .txt). Defaults to all registered parser extensions.",
    )
    return parser.parse_args(args)


def convert_recipe_file(
    input_path: Path,
    output_dir: Path,
    one_file_per_recipe: bool,
    verbose: Union[bool, int],
    parse_ingredients: bool,
    ingredient_parser: BaseIngredientParser,
    format_name: Optional[str] = None,
    stream_writer: Optional[JSONStreamWriter] = None,
    debug_sql: bool = False,
    llm_parser: Optional["LLMRecipeParser"] = None,
    shard: bool = False,
    add_date: bool = False,
    html_config: Optional[Path] = None,
    file_prefix: str = "",
    display_path: Optional[str] = None,
) -> int:
    if llm_parser is not None:
        parser = llm_parser
    else:
        parser = ParserRegistry.get_parser(
            input_path, ingredient_parser, format_name, debug=debug_sql
        )
        if parser is not None and hasattr(parser, "config_path") and html_config is not None:
            parser.config_path = str(html_config)

    path_display = display_path or input_path.name
    prefix_str = f"{Colors.BOLD}{file_prefix}{Colors.ENDC} " if file_prefix else ""
    if verbose:
        if parser:
            parser_info = parser.get_display_name(str(input_path))
            print(
                f"\n{prefix_str}{Colors.CYAN}{path_display}{Colors.ENDC}: {parser_info}"
            )
        else:
            print(
                f"\n{prefix_str}{Colors.CYAN}{path_display}{Colors.ENDC}: {Colors.RED}Unsupported file format: {input_path.suffix}{Colors.ENDC}"
            )

    if not parser:
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
                    get_recipe_sharded_path(url, title, base_dir=output_dir)
                    if shard
                    else output_dir
                )
                target_dir.mkdir(parents=True, exist_ok=True)

                safe_name = re.sub(
                    r"[^\w\s-]", "", title
                ).strip()
                safe_name = re.sub(r"[-\s]+", "_", safe_name)[:120].strip("_")
                if not safe_name:
                    safe_name = "recipe"
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


_ORIGINAL_CONVERT_RECIPE_FILE = convert_recipe_file

# Global worker state for ProcessPoolExecutor workers
_worker_ingredient_parser: Optional[BaseIngredientParser] = None
_worker_converter: Optional[SchemaOrgConverter] = None


def _worker_process_init(use_nlp: bool) -> None:
    """Initialize worker process with ingredient parser and schema converter once."""
    global _worker_ingredient_parser, _worker_converter
    _worker_ingredient_parser = get_ingredient_parser(use_nlp=use_nlp)
    _worker_converter = SchemaOrgConverter()


def _worker_convert_file(
    target_file: Path,
    output_dir: Path,
    one_file_per_recipe: bool,
    multiple_per_file: bool,
    parse_ingredients: bool,
    format_name: Optional[str],
    debug_sql: bool,
    shard: bool,
    add_date: bool,
    html_config: Optional[Path],
    stream_output: bool,
) -> tuple[str, list[dict], int, Optional[str]]:
    """Parse a single recipe file in worker process.

    Returns (filepath_str, list_of_schema_recipes, file_size_bytes, error_message).
    """
    global _worker_ingredient_parser, _worker_converter
    try:
        parser = ParserRegistry.get_parser(
            target_file, _worker_ingredient_parser, format_name, debug=debug_sql
        )
        if parser is not None and hasattr(parser, "config_path") and html_config is not None:
            parser.config_path = str(html_config)

        if not parser:
            return (str(target_file), [], 0, "Unsupported file format")

        file_size = target_file.stat().st_size
        collected: list[dict] = []

        for recipe in parser.parse_file(str(target_file)):
            schema_recipe = _worker_converter.convert(recipe, parse_ingredients, add_date)
            if stream_output:
                collected.append(schema_recipe)
            elif one_file_per_recipe:
                title = schema_recipe.get("name", "Untitled")
                url = schema_recipe.get("url", "")
                target_dir = (
                    get_recipe_sharded_path(url, title, base_dir=output_dir)
                    if shard
                    else output_dir
                )
                target_dir.mkdir(parents=True, exist_ok=True)

                safe_name = re.sub(r"[^\w\s-]", "", title).strip()
                safe_name = re.sub(r"[-\s]+", "_", safe_name)[:120].strip("_")
                if not safe_name:
                    safe_name = "recipe"
                out_file = target_dir / f"{safe_name}.json"
                counter = 1
                while out_file.exists():
                    out_file = target_dir / f"{safe_name}_{counter}.json"
                    counter += 1
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(schema_recipe, f, indent=2, ensure_ascii=False)
                collected.append(schema_recipe)
            else:
                collected.append(schema_recipe)

        if not stream_output and not one_file_per_recipe and collected:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = output_dir / f"{target_file.stem}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(collected, f, indent=2, ensure_ascii=False)

        return (str(target_file), collected, file_size, None)
    except Exception as e:
        return (str(target_file), [], 0, str(e))


def process_directory(
    input_dir: Path,
    output_dir: Path,
    one_file_per_recipe: bool,
    verbose: Union[bool, int],
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
    cli_extensions: Optional[List[str]] = None,
    workers: Optional[int] = None,
    multiple_per_file: bool = False,
) -> None:
    if cli_extensions:
        extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in cli_extensions
        }
    else:
        extensions = ParserRegistry.supported_extensions()
        if not extensions:
            extensions = {".txt", ".mmf", ".html", ".htm"}

    # Include uppercase variants
    extensions.update([e.upper() for e in extensions])

    recipe_files: list[Path] = []
    if recursive:
        for root_p, _, fnames in os.walk(input_dir):
            r_path = Path(root_p)
            for fname in fnames:
                if any(fname.endswith(ext) for ext in extensions):
                    recipe_files.append(r_path / fname)
    else:
        for p in input_dir.iterdir():
            if p.is_file() and any(p.name.endswith(ext) for ext in extensions):
                recipe_files.append(p)
        if not recipe_files:
            for root_p, _, fnames in os.walk(input_dir):
                r_path = Path(root_p)
                for fname in fnames:
                    if any(fname.endswith(ext) for ext in extensions):
                        recipe_files.append(r_path / fname)
            if recipe_files:
                print(
                    f"{Colors.YELLOW}ℹ No recipe files found at root level of {input_dir}, but found {len(recipe_files)} file(s) in subdirectories (auto-enabling recursive scan).{Colors.ENDC}"
                )

    recipe_files.sort()

    if not recipe_files:
        print(f"{Colors.RED}No recipe files found in {input_dir}{Colors.ENDC}")
        return

    total_bytes = sum(f.stat().st_size for f in recipe_files)
    processed_bytes = 0
    total_files = len(recipe_files)
    total_recipes = 0

    print(f"\n{Colors.BOLD}{Colors.CYAN}🍳 Modular Recipe Converter{Colors.ENDC}")
    print(
        f"{Colors.DIM}Found {total_files} file(s) ({total_bytes:,} bytes){Colors.ENDC}\n"
    )

    num_workers = workers if workers is not None else min(os.cpu_count() or 4, 8)
    is_monkeypatched = convert_recipe_file != _ORIGINAL_CONVERT_RECIPE_FILE

    if is_monkeypatched or llm_parser is not None or num_workers <= 1:
        for file_idx, recipe_file in enumerate(recipe_files, 1):
            target_file = recipe_file
            if target_file.is_absolute():
                try:
                    cwd = Path.cwd()
                    if target_file.is_relative_to(cwd):
                        target_file = target_file.relative_to(cwd)
                except (ValueError, TypeError):
                    pass

            try:
                rel_path = (
                    recipe_file.relative_to(input_dir)
                    if input_dir in recipe_file.parents
                    else target_file
                )
            except ValueError:
                rel_path = target_file

            bytes_processed = convert_recipe_file(
                target_file,
                output_dir,
                one_file_per_recipe,
                bool(verbose),
                parse_ingredients,
                ingredient_parser,
                format_name,
                stream_writer,
                debug_sql=debug_sql,
                llm_parser=llm_parser,
                shard=shard,
                add_date=add_date,
                html_config=html_config,
                file_prefix=f"[{file_idx}/{total_files}]",
                display_path=str(rel_path),
            )
            processed_bytes += (
                target_file.stat().st_size if bytes_processed == 0 else bytes_processed
            )

            if not verbose:
                print_progress_bar(
                    processed_bytes,
                    total_bytes,
                    prefix="Converting",
                    suffix=target_file.name,
                )
    else:
        stream_output = stream_writer is not None
        use_nlp = ingredient_parser.__class__.__name__ != "RegexIngredientParser"

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=num_workers,
            initializer=_worker_process_init,
            initargs=(use_nlp,),
        ) as executor:
            future_to_file = {
                executor.submit(
                    _worker_convert_file,
                    rf,
                    output_dir,
                    one_file_per_recipe,
                    multiple_per_file,
                    parse_ingredients,
                    format_name,
                    debug_sql,
                    shard,
                    add_date,
                    html_config,
                    stream_output,
                ): rf
                for rf in recipe_files
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                completed += 1
                file_path_str, recipes, file_size, err = future.result()
                processed_bytes += file_size

                if stream_writer:
                    for schema_recipe in recipes:
                        stream_writer.write_recipe(schema_recipe)
                total_recipes += len(recipes)

                if verbose:
                    if recipes:
                        status = f"{len(recipes)} recipe(s)"
                    elif err == "Unsupported file format":
                        status = "unsupported"
                    elif err:
                        status = f"error: {err}"
                    else:
                        status = "0 recipes"
                    prefix_str = f"{Colors.BOLD}[{completed}/{total_files}]{Colors.ENDC} "
                    print(
                        f"{prefix_str}{Colors.CYAN}{Path(file_path_str).name}{Colors.ENDC}: {status}"
                    )
                else:
                    print_progress_bar(
                        processed_bytes,
                        total_bytes,
                        prefix="Converting",
                        suffix=f"{total_recipes} recipes ({completed}/{total_files})",
                    )

    if not verbose:
        print()


def main(argv: Optional[List[str]] = None):
    args = parse_arguments(argv)

    # Configure logging based on flags
    configure_logging(
        verbose=args.verbose,
        debug_sql=args.debug_sql,
        debug_nlp=args.debug_nlp,
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

    # Choose ingredient parser: NLP only if installed AND not disabled via --no-nlp
    ingredient_parser = get_ingredient_parser(use_nlp=not args.no_nlp)

    # Initialize LLM parser if --llm-config is passed
    llm_parser = None
    if args.llm_config:
        if not args.llm_config.exists():
            print(
                f"{Colors.RED}LLM config file not found: {args.llm_config}{Colors.ENDC}"
            )
            return 1
        llm_parser = LLMRecipeParser.from_yaml(args.llm_config, ingredient_parser)
        print(
            f"  {Colors.CYAN}ℹ LLM Extraction Enabled: {llm_parser.model} via {llm_parser.base_url}{Colors.ENDC}"
        )
    elif ingredient_parser.__class__.__name__ == "RegexIngredientParser":
        print(f"  {Colors.DIM}ℹ Using Regex Fallback Ingredient Parser{Colors.ENDC}")
    else:
        print(f"  {Colors.CYAN}ℹ Using Spacy NLP Ingredient Parser{Colors.ENDC}")

    input_path = args.input
    if input_path.is_absolute():
        try:
            cwd = Path.cwd()
            if input_path.is_relative_to(cwd):
                input_path = input_path.relative_to(cwd)
        except (ValueError, TypeError):
            pass

    if not input_path.exists():
        print(f"{Colors.RED}Input path does not exist: {input_path}{Colors.ENDC}")
        return 1

    # Single-file output mode is active if:
    # 1) --multiple-per-file is explicitly passed (irrespective of output path format)
    # OR
    # 2) output path ends in .json and is not an existing directory
    write_to_single_file = args.multiple_per_file or (
        args.output.suffix.lower() == ".json" and not args.output.is_dir()
    )

    stream_writer = None
    if write_to_single_file:
        output_dir = args.output.parent
        stream_writer = JSONStreamWriter(args.output, chunk=args.chunk)
        one_file_per_recipe = False
    else:
        # No multiple-per-file and output string does not end in .json:
        # Create folder and do 1 recipe per file
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        one_file_per_recipe = True

    try:
        if input_path.is_dir():
            process_directory(
                input_path,
                output_dir,
                one_file_per_recipe,
                bool(args.verbose),
                args.recursive,
                not args.no_parse_ingredients,
                ingredient_parser,
                format_name=args.format,
                stream_writer=stream_writer,
                debug_sql=args.debug_sql,
                llm_parser=llm_parser,
                shard=args.shard,
                add_date=args.add_date,
                html_config=args.html_config,
                cli_extensions=args.ext,
                workers=args.workers,
                multiple_per_file=args.multiple_per_file,
            )
        else:
            if not args.verbose:
                print(f"  {Colors.CYAN}Converting:{Colors.ENDC} {input_path.name}")
            convert_recipe_file(
                input_path,
                output_dir,
                one_file_per_recipe,
                bool(args.verbose),
                not args.no_parse_ingredients,
                ingredient_parser,
                format_name=args.format,
                stream_writer=stream_writer,
                debug_sql=args.debug_sql,
                llm_parser=llm_parser,
                shard=args.shard,
                add_date=args.add_date,
                html_config=args.html_config,
                file_prefix="",
                display_path=input_path.name,
            )
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}Forced exit - data may be incomplete{Colors.ENDC}\n")
        return 1
    finally:
        if stream_writer:
            stream_writer.close()

    print(f"\n  {Colors.GREEN}{Colors.BOLD}✨ Conversion finished! ✨{Colors.ENDC}")
    print(f"  {Colors.DIM}Output saved to: {args.output}{Colors.ENDC}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
