from skillguard.routing.evaluator import HeuristicRoutingEvaluator


def test_matching_prompt_triggers(make_skill) -> None:
    skill = make_skill(
        description="Use this skill when reviewing payment and checkout code for security issues."
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(
        skill, "Please review this payment integration for security problems"
    )
    assert result.triggered is True
    assert result.confidence > 0


def test_unrelated_prompt_does_not_trigger(make_skill) -> None:
    skill = make_skill(
        description="Use this skill when reviewing payment and checkout code for security issues."
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Explain how photosynthesis works in plants")
    assert result.triggered is False


def test_short_prompt_not_structurally_penalized_by_long_description(make_skill) -> None:
    long_description = (
        "Use this skill when reviewing, checking, or auditing a payment or checkout "
        "integration for correctness and security issues, such as amount handling, "
        "webhook verification, refund logic, and idempotency across many providers."
    )
    skill = make_skill(description=long_description)
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Review this payment code")
    assert result.triggered is True


def test_keyword_hit_triggers_regardless_of_recall(make_skill) -> None:
    description = "A skill about something else entirely, completely unrelated in wording."
    skill = make_skill(
        description=description,
        frontmatter={"name": "my-skill", "description": description, "keywords": ["kubernetes"]},
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Help me debug a kubernetes deployment")
    assert result.triggered is True


def test_empty_description_never_triggers(make_skill) -> None:
    skill = make_skill(description="", frontmatter={"name": "my-skill", "description": ""})
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Anything at all")
    assert result.triggered is False
