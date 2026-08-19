# GitHub Copilot Instructions

**All project standards, architecture, and coding guidelines are in [`AGENTS.md`](../AGENTS.md).**
Read it before making any changes.

Key points summarized:
- All parsers use `@ParserRegistry.register` — see AGENTS.md for required methods
- Always use `./venv/bin/python3`, never bare `python3`
- Always use `--no-nlp` when generating expected test output
- Reference parser to copy from: `parsers/cookware.py`

---

## Documentation Policy

- DO NOT create README files, guide files, or explanatory markdown documents
- DO NOT create tutorial files, how-to guides, SUMMARY files, or overview documents
- DO NOT create ARCHITECTURE files, CHECKLIST files, or design/verification documents
- DO create documentation only when the user explicitly requests it

### Exception Cases
- User explicitly asks for documentation
- Documentation is part of the codebase's required structure
- Comments in code itself

---

**Remember**: Code first, documentation only when asked. See [`AGENTS.md`](../AGENTS.md) for full details.
