# Contributing to Recipe Format Converter

Welcome! This project is a modular toolkit for converting recipes into Schema.org JSON-LD format.

## 🤖 Guidelines for AI Agents

This codebase is primarily authored and maintained by AI agents. To maintain consistency, all AI agents MUST follow these rules:

### 1. Registry Architecture
- All parsers MUST be registered using the `@ParserRegistry.register` decorator.
- Parsers MUST inherit from `BaseRecipeParser` and implement `detect` and `parse_content`.
- Avoid modifying `ParserRegistry` or `BaseRecipeParser` unless absolutely necessary.

### 2. Testing Framework
- **Regression Testing**: We use a regression-based test suite in `tests/test_conversion.py`.
- **Samples**: Add new test cases to `tests/samples/`.
- **Expected Output**: Generate expected JSON output in `tests/expected/` using the `--no-nlp` flag to ensure deterministic results.
- **Execution**: ALWAYS run tests within the project's virtual environment:
  ```bash
  ./venv/bin/python3 -m pytest tests/test_conversion.py
  ```

### 3. Models and Schema
- Use the `Recipe` and `Ingredient` dataclasses in `parsers/models.py`.
- Ensure the output strictly adheres to the Schema.org `Recipe` JSON-LD specification.

### 4. Coding Standards
- **Python Version**: 3.10+
- **Type Hints**: Mandatory for all function signatures.
- **Docstrings**: Use Google-style docstrings.
- **Dependencies**: Minimize new dependencies. Prefer standard library or existing requirements.

## 🛠 General Contribution Guidelines

### Reporting Bugs
Please use the GitHub Issue tracker to report bugs. Include:
- A description of the issue.
- Steps to reproduce.
- Sample input file(s) that cause the issue.

### Pull Requests
- Create a new branch for each feature or bug fix.
- Ensure all tests pass (`./venv/bin/python3 -m pytest tests/test_conversion.py`) before submitting.
- Write clear, descriptive commit messages.

## 📄 License
By contributing, you agree that your contributions will be licensed under the MIT License.
