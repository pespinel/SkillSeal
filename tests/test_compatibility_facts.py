from datetime import date, timedelta

from skillseal import compatibility_facts as facts

_ALL_FACTS = [
    facts.NAME_DIRECTORY_MISMATCH,
    facts.NON_SPEC_KEYS,
    facts.ALLOWED_TOOLS_EXPERIMENTAL,
    facts.DESCRIPTION_BLOCK_SCALAR,
]


def test_facts_are_not_stale() -> None:
    # a fact unverified for a year is a claim, not documentation — re-check
    # the vendor doc and bump `checked` before it goes further out of date
    cutoff = date.today() - timedelta(days=facts.STALE_AFTER_MONTHS * 30)
    for fact in _ALL_FACTS:
        checked = date.fromisoformat(fact.checked)
        assert checked >= cutoff, (
            f"{fact.source} last verified {fact.checked}, re-check the vendor doc"
        )


def test_facts_cite_a_source_url() -> None:
    for fact in _ALL_FACTS:
        assert fact.source.startswith("https://")
