# 🍳 Recipe Format Converter

A modular, high-performance toolkit for converting recipes from various formats (MealMaster, MasterCook, CompuChef, HTML, etc.) into modern **Schema.org JSON-LD** format.

> [!IMPORTANT]
> **AI Authorship Disclosure**: This entire codebase, including all scripts, parsers, and documentation, was authored by an Artificial Intelligence (AI) agent.

## ✨ Features

- **High Performance Streaming**: Uses a custom `JSONStreamWriter` to handle thousands of recipes with minimal memory usage and no disk thrashing.
- **Mixed-Format Support**: Automatically detects and parses files containing multiple recipe types (e.g., a `.txt` file with both MasterCook and MealMaster recipes).
- **Modular Parser Architecture**:
  - **MealMaster (.mmf, .mm)**: Robust parsing with improved continuation handling.
  - **MasterCook (.mxp, .mx2)**: Enhanced support for versioned headers, multi-word categories, and multi-line ingredients.
  - **CompuChef (.ccf)**: Native support for legacy CompuChef exports.
  - **Ricette (Italian)**: Support for `:Ricette` separators and `-Field` markers.
  - **Generic Text & PDF Fallback**
  - **Web Scraping** (via `recipe-scrapers`)
- **NLP Ingredient Parsing**: Intelligent extraction of quantities, units, and ingredient names using `ingredient-parser-nlp`.
- **Dynamic Chunking**: Automatically split large recipe collections into manageable JSON parts based on file size or recipe count.

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Recipes/scripts
   ```

2. **Set up a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 📖 Usage

### Basic Conversion
Convert a single file to a merged JSON array:
```bash
./convert.py path/to/recipes.mxp -o output.json
```

### Directory Processing
Process an entire directory recursively:
```bash
./convert.py path/to/library/ -o output.json --recursive
```

### Chunked Output
Split a large collection into part-files (e.g., 50MB chunks):
```bash
./convert.py path/to/large_collection/ -o large_export.json --chunk
```

### Mixed-Format Detection
The converter intelligently identifies formats within a single file. For ambiguous files (like `.txt`), use:
```bash
./convert.py mixed_recipes.txt -o output.json
```

## 🧪 Testing

The project includes a regression testing suite to ensure parsing accuracy.

1. **Run all tests**:
   ```bash
   source venv/bin/activate
   pytest tests/test_conversion.py -v
   ```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
