from skillseal.rules.base import build_registry


def test_all_rule_ids_are_unique() -> None:
    rules = build_registry()
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))
    assert len(rules) > 0
