from pathlib import Path

from skillseal.models import Skill
from skillseal.rules.base import extract_code_spans, frontmatter_key_line, offset_to_line


def _bare_skill(raw_text: str) -> Skill:
    """A Skill with no frontmatter block at all: raw_text == body."""
    return Skill(
        name="",
        description="",
        frontmatter={},
        body=raw_text,
        raw_text=raw_text,
        path=Path("SKILL.md"),
        dir=Path("."),
    )


def test_offset_to_line_with_no_frontmatter_prefix() -> None:
    skill = _bare_skill("line one\nline two\nline three\n")
    assert offset_to_line(skill, 0) == 1
    assert offset_to_line(skill, len("line one\n")) == 2
    assert offset_to_line(skill, len("line one\nline two\n")) == 3


def test_offset_to_line_accounts_for_frontmatter_prefix(make_skill) -> None:
    # default fixture body: 4-line frontmatter block, body starts at file line 5
    skill = make_skill(body="first\nsecond\nthird\n")
    assert offset_to_line(skill, 0) == 5
    assert offset_to_line(skill, len("first\n")) == 6
    assert offset_to_line(skill, len("first\nsecond\n")) == 7


def test_frontmatter_key_line_finds_key(make_skill) -> None:
    skill = make_skill(frontmatter={"name": "my-skill", "description": "desc"})
    assert frontmatter_key_line(skill, "name") == 2
    assert frontmatter_key_line(skill, "description") == 3


def test_frontmatter_key_line_falls_back_when_key_absent(make_skill) -> None:
    skill = make_skill(frontmatter={"description": "desc"})
    assert frontmatter_key_line(skill, "name") == 1


def test_frontmatter_key_line_falls_back_with_no_frontmatter_text() -> None:
    skill = _bare_skill("no frontmatter here\n")
    assert frontmatter_key_line(skill, "name") == 1


def test_extract_code_spans_finds_fence_at_column_zero() -> None:
    text = "text\n\n```bash\necho hi\n```\n\nmore\n"
    spans = extract_code_spans(text)
    assert ("echo hi", text.index("echo hi")) in spans


def test_extract_code_spans_finds_fence_nested_in_a_list_item() -> None:
    # a fence inside a numbered/bulleted step is indented by the list's own
    # content column, not column 0 — found via a real corpus where 22/42
    # skills used this pattern and every command inside was silently treated
    # as prose (#28-adjacent)
    text = "8. Run it:\n\n   ```bash\n   node script.mjs\n   ```\n\n   more.\n"
    spans = extract_code_spans(text)
    assert any("node script.mjs" in content for content, _offset in spans)
