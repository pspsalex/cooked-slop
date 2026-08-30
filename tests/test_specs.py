# SPDX-License-Identifier: MIT
"""Automated validation of specification frontmatter and structure."""
from pathlib import Path
import pytest
import yaml

SPECS_DIR = Path(__file__).parent.parent / "specs"


def get_all_specs():
    """Discover all SPEC-*.md files in specs/ and specs/done/."""
    specs = sorted(list(SPECS_DIR.glob("SPEC-*.md")))
    specs.extend(sorted(list((SPECS_DIR / "done").glob("SPEC-*.md"))))
    return specs


@pytest.mark.parametrize("spec_path", get_all_specs(), ids=lambda p: p.name)
def test_spec_frontmatter_validity(spec_path: Path):
    """Validate that each spec has valid YAML frontmatter and required fields."""
    content = spec_path.read_text(encoding="utf-8")
    assert content.startswith("---"), f"{spec_path.name} must start with YAML frontmatter"

    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{spec_path.name} has malformed frontmatter delimiter"

    fm = yaml.safe_load(parts[1])
    assert isinstance(fm, dict), f"{spec_path.name} frontmatter is not a dictionary"

    required_keys = {"id", "title", "tier", "type", "priority", "status", "deliverables"}
    missing = required_keys - set(fm.keys())
    assert not missing, f"{spec_path.name} is missing frontmatter keys: {missing}"

    assert fm["status"] in {"active", "done", "blocked"}, f"Invalid status in {spec_path.name}"
    assert fm["priority"] in {"P0", "P1", "P2"}, f"Invalid priority in {spec_path.name}"
    assert isinstance(fm["deliverables"], list), f"{spec_path.name} deliverables must be a list"
