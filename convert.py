#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Recipe format converter: Modular Architecture
Converts recipes from various formats into schema.org JSON-LD format.
"""

import argparse
import json
import re
import sys
import signal
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Union, Any, Type

# Optional dependencies
try:
    from ingredient_parser import parse_ingredient
    HAS_NLP_PARSER = True
except ImportError:
    HAS_NLP_PARSER = False

try:
    from recipe_scrapers import scrape_html
    HAS_RECIPE_SCRAPERS = True
except ImportError:
    HAS_RECIPE_SCRAPERS = False

# Global state for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    shutdown_requested = True
    print(f"\n\n{Colors.YELLOW}⚠️  Interrupt received! Finishing current recipe...{Colors.ENDC}")
    print(f"{Colors.DIM}Press Ctrl+C again to force quit (may lose data){Colors.ENDC}\n")
    # Set handler to default so second Ctrl+C kills immediately
    signal.signal(signal.SIGINT, signal.SIG_DFL)

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def print_progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '', 
                       length: int = 50, fill: str = '█'):
    """Print a colorful progress bar"""
    if total <= 0:
        return
    percent = 100 * (iteration / float(total))
    filled_length = int(length * iteration // total)
    bar_color = Colors.RED if percent < 33 else (Colors.YELLOW if percent < 66 else Colors.GREEN)
    bar = fill * filled_length + '░' * (length - filled_length)
    print(f'\r{Colors.CYAN}{prefix}{Colors.ENDC} |{bar_color}{bar}{Colors.ENDC}| '
          f'{Colors.BOLD}{percent:.1f}%{Colors.ENDC} {Colors.DIM}{suffix[:30]}{Colors.ENDC}\033[K', 
          end='', flush=True)
    if iteration >= total:
        print() 

from parsers import (
    Recipe, Ingredient, BaseIngredientParser, BaseRecipeParser,
    get_ingredient_parser, ParserFactory, GenericTextParser
)
from parsers.units import normalize_unit

# --- Output Conversion ---
class SchemaOrgConverter:
    """Converter to schema.org Recipe JSON-LD format"""
    
    def convert(self, recipe: Recipe, parse_ingredients: bool = True) -> dict:
        instructions = self._build_instructions(recipe.instructions)
        recipe_ingredients = []
        
        if parse_ingredients:
            for ing in recipe.ingredients:
                if ing.quantity or ing.unit:
                    prop_value = {
                        "@type": "PropertyValue",
                        "name": ing.name or ing.raw
                    }
                    if ing.quantity:
                        try:
                            prop_value["value"] = float(ing.quantity) if '/' not in ing.quantity and '.' in ing.quantity else int(ing.quantity)
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
            "name": recipe.title or 'Untitled Recipe',
            "recipeIngredient": recipe_ingredients,
            "recipeInstructions": instructions,
        }
        
        if recipe.yield_amount:
            schema_recipe['recipeYield'] = recipe.yield_amount
        
        if recipe.categories:
            schema_recipe['recipeCategory'] = recipe.categories[0]
            schema_recipe['keywords'] = ', '.join(recipe.categories)
        
        if recipe.source_file:
            schema_recipe['comment'] = f"Imported from {recipe.source_file}"
        
        schema_recipe['datePublished'] = datetime.now().isoformat()
        schema_recipe['description'] = f"Recipe converted from {recipe.source_format} format"
        
        return schema_recipe
    
    @staticmethod
    def _build_instructions(instructions: List[str]) -> List:
        if not instructions: return []
        if len(instructions) == 1: return [instructions[0]]
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
        return self.base_path.parent / f"{self.base_path.stem}_part{self.current_chunk_num:03d}{self.base_path.suffix}"

    def _open_new_file(self):
        dest = self._get_current_path()
        self.current_f = open(dest, 'w', encoding='utf-8')
        self.current_f.write("[\n")
        self.current_recipe_count = 0
        self.current_size_bytes = 2 # "[" and "\n"

    def _close_current_file(self):
        if self.current_f:
            self.current_f.write("\n]")
            self.current_f.close()
            self.current_f = None
            self.current_chunk_num += 1

    def write_recipe(self, recipe: dict):
        # Calculate size if needed for chunking
        recipe_json = json.dumps(recipe, indent=self.indent, ensure_ascii=False)
        recipe_size = len(recipe_json.encode('utf-8'))

        # Check if we need to rotate
        if self.chunk and self.current_f:
            if self.current_recipe_count >= self.max_recipes_per_chunk or \
               (self.current_recipe_count > 0 and self.current_size_bytes + recipe_size > self.max_chunk_size_bytes):
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
        description='Convert Recipes (MealMaster, MasterCook, PDF, HTML, CSV) to schema.org JSON-LD format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('input', type=Path, help='Input file or directory containing recipe files')
    parser.add_argument('-o', '--output', type=Path, default=Path('./converted_recipes'),
                        help='Output directory or file (default: ./converted_recipes)')
    parser.add_argument('-r', '--recursive', action='store_true', help='Scan directories recursively')
    parser.add_argument('--multiple-per-file', action='store_true', help='Save all recipes from a file into a single JSON file')
    parser.add_argument('--no-parse-ingredients', action='store_true', help='Keep ingredients as plain text')
    parser.add_argument('--no-nlp', action='store_true', help='Disable NLP ingredient parsing even if installed')
    parser.add_argument('--chunk', action='store_true', help='Split output into chunks')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show verbose output')
    return parser.parse_args()


def convert_recipe_file(
    input_path: Path, 
    output_dir: Path, 
    one_file_per_recipe: bool,
    verbose: bool,
    parse_ingredients: bool,
    ingredient_parser: BaseIngredientParser,
    stream_writer: Optional[JSONStreamWriter] = None
) -> int:
    parser = ParserFactory.get_parser(input_path, ingredient_parser)
    if not parser:
        if verbose: print(f"{Colors.RED}Unsupported file format: {input_path.suffix}{Colors.ENDC}")
        return 0
    
    try:
        recipes = parser.parse_file(str(input_path))
    except Exception as e:
        if verbose: print(f"{Colors.RED}Error parsing {input_path}: {e}{Colors.ENDC}")
        import traceback
        if verbose: traceback.print_exc()
        return 0
        
    if not recipes and input_path.suffix.lower() == '.txt':
        # Fallback to generic text parser
        fallback_parser = GenericTextParser(ingredient_parser)
        recipes = fallback_parser.parse_file(str(input_path))
        
    if not recipes:
        if verbose: print(f"{Colors.YELLOW}No recipes found in {input_path}{Colors.ENDC}")
        return 0
        
    converter = SchemaOrgConverter()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if stream_writer:
        for recipe in recipes:
            schema_recipe = converter.convert(recipe, parse_ingredients)
            stream_writer.write_recipe(schema_recipe)
            if verbose: print(f"  {Colors.GREEN}✓{Colors.ENDC} {schema_recipe.get('name')}")
    elif one_file_per_recipe:
        for recipe in recipes:
            schema_recipe = converter.convert(recipe, parse_ingredients)
            safe_name = re.sub(r'[^\w\s-]', '', schema_recipe.get('name', 'Untitled')).strip()
            safe_name = re.sub(r'[-\s]+', '_', safe_name)
            output_file = output_dir / f"{safe_name}.json"
            counter = 1
            while output_file.exists():
                output_file = output_dir / f"{safe_name}_{counter}.json"
                counter += 1
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(schema_recipe, f, indent=2, ensure_ascii=False)
            if verbose: print(f"  {Colors.GREEN}✓{Colors.ENDC} {schema_recipe.get('name')} → {output_file.name}")
    else:
        schema_recipes = [converter.convert(recipe, parse_ingredients) for recipe in recipes]
        output_file = output_dir / f"{input_path.stem}_recipes.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema_recipes, f, indent=2, ensure_ascii=False)
        if verbose: print(f"{Colors.GREEN}Converted {len(schema_recipes)} recipes to {output_file}{Colors.ENDC}")
            
    return input_path.stat().st_size

def process_directory(
    input_dir: Path, 
    output_dir: Path, 
    one_file_per_recipe: bool,
    verbose: bool,
    recursive: bool,
    parse_ingredients: bool,
    ingredient_parser: BaseIngredientParser,
    stream_writer: Optional[JSONStreamWriter] = None
) -> None:
    global shutdown_requested
    
    # Updated extensions to include stubs explicitly supported by ParserFactory.
    extensions = {'.mmf', '.mm', '.mxp', '.mx2', '.mz2', '.txt', '.html', '.htm', '.pdf', '.jpg', '.png', '.sqlite', '.db', '.csv', '.ccf'}
    extensions.update([e.upper() for e in extensions])
    
    recipe_files = []
    if recursive:
        for ext in extensions: recipe_files.extend(input_dir.rglob(f'*{ext}'))
    else:
        for ext in extensions: recipe_files.extend(input_dir.glob(f'*{ext}'))
        
    if not recipe_files:
        print(f"{Colors.RED}No recipe files found in {input_dir}{Colors.ENDC}")
        return
        
    total_bytes = sum(f.stat().st_size for f in recipe_files)
    processed_bytes = 0
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}🍳 Modular Recipe Converter{Colors.ENDC}")
    print(f"{Colors.DIM}Found {len(recipe_files)} file(s) ({total_bytes:,} bytes){Colors.ENDC}\n")
    
    for file_idx, recipe_file in enumerate(recipe_files, 1):
        if shutdown_requested:
            print(f"\n{Colors.YELLOW}Gracefully stopping after {file_idx-1}/{len(recipe_files)} files...{Colors.ENDC}")
            break
            
        if verbose:
            rel_path = recipe_file.relative_to(input_dir) if input_dir in recipe_file.parents else recipe_file
            print(f"\n{Colors.BOLD}[{file_idx}/{len(recipe_files)}]{Colors.ENDC} {Colors.CYAN}{rel_path}{Colors.ENDC}")
            
        bytes_processed = convert_recipe_file(recipe_file, output_dir, one_file_per_recipe, verbose, parse_ingredients, ingredient_parser, stream_writer)
        processed_bytes += recipe_file.stat().st_size if bytes_processed == 0 else bytes_processed
        
        if not verbose:
            print_progress_bar(processed_bytes, total_bytes, prefix='Converting', suffix=recipe_file.name)
            
    if not verbose: print()

def merge_all_recipes_to_file(temp_dir: Path, output_file: Path, chunk: bool = False) -> None:
    import shutil
    
    stream_writer = JSONStreamWriter(output_file, indent=2, chunk=chunk)
    json_files = sorted(temp_dir.glob('*.json'))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for recipe in data:
                        stream_writer.write_recipe(recipe)
                else:
                    stream_writer.write_recipe(data)
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not read {json_file.name}: {e}{Colors.ENDC}")
            
    stream_writer.close()
    
    if stream_writer.total_recipes > 0:
        if chunk:
            print(f"\n{Colors.YELLOW}📦 Split {stream_writer.total_recipes} recipes into multiple files.{Colors.ENDC}")
        else:
            print(f"\n{Colors.YELLOW}📦 Merged {stream_writer.total_recipes} recipes into one file{Colors.ENDC}")
    
    shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    global shutdown_requested
    signal.signal(signal.SIGINT, signal_handler)
    args = parse_arguments()
    
    print(f"\n{Colors.BOLD}{Colors.HEADER}╔══════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}║   🍳 Recipe Format Converter 🍳      ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}╚══════════════════════════════════════╝{Colors.ENDC}\n")
    
    parse_ingredients = not args.no_parse_ingredients
    ingredient_parser = get_ingredient_parser(use_nlp=(not args.no_nlp))
    if HAS_NLP_PARSER and not args.no_nlp:
        print(f"{Colors.GREEN}✓ Using NLP Ingredient Parser{Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}ℹ Using Regex Fallback Ingredient Parser{Colors.ENDC}")
    
    output_is_file = args.output.suffix != ''
    stream_writer = None
    if output_is_file:
        stream_writer = JSONStreamWriter(args.output, chunk=args.chunk)
        
    try:
        if args.input.is_file():
            if not args.verbose:
                print(f"{Colors.CYAN}Converting:{Colors.ENDC} {args.input.name}")
                print_progress_bar(0, args.input.stat().st_size, prefix='Processing', suffix=args.input.name)
            
            convert_recipe_file(args.input, args.output.parent if output_is_file else args.output, 
                               not args.multiple_per_file, args.verbose, parse_ingredients, 
                               ingredient_parser, stream_writer)
                
            if not args.verbose:
                print_progress_bar(args.input.stat().st_size, args.input.stat().st_size, prefix='Processing', suffix='Complete!')
                
        elif args.input.is_dir():
            process_directory(args.input, args.output.parent if output_is_file else args.output, 
                             not args.multiple_per_file, args.verbose, args.recursive, 
                             parse_ingredients, ingredient_parser, stream_writer)
        else:
            print(f"{Colors.RED}Error: {args.input} not found{Colors.ENDC}")
            return 1
            
        if stream_writer:
            stream_writer.close()
            
        if shutdown_requested:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Conversion interrupted (partial results saved){Colors.ENDC}")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✨ Conversion complete! ✨{Colors.ENDC}")
        print(f"{Colors.DIM}Output saved to: {args.output.absolute()}{Colors.ENDC}\n")
        return 0
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}Forced exit - data may be incomplete{Colors.ENDC}\n")
        return 1

if __name__ == '__main__':
    exit(main())
