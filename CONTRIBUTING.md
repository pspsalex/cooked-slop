# Contributing to Recipe Format Converter

This project is primarily authored and maintained by AI agents.

## For AI Agents

**Read [`CLAUDE.md`](CLAUDE.md) first.** It contains all architecture, coding standards,
testing procedures, and known issues.

Key rules:
- All parsers must use `@ParserRegistry.register` and be imported in `parsers/__init__.py`
- Always use `./venv/bin/python3`, never bare `python3`
- Always use `--no-nlp` when generating expected test output
- Run `./venv/bin/python3 -m pytest tests/test_conversion.py` before submitting

## Bug Reports

Use the GitHub Issue tracker. Include:
- Description of the issue
- Steps to reproduce
- Sample input file(s) that cause the issue

## Pull Requests

- Create a new branch for each feature or bug fix
- Ensure all tests pass before submitting
- Write clear, descriptive commit messages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
