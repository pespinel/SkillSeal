from skillseal.routing.evaluator import HeuristicRoutingEvaluator


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


def test_single_word_prompt_does_not_automatically_trigger(make_skill) -> None:
    # a one-content-word prompt matching a single stem used to reach recall
    # 1.0 and trigger with full confidence — every short should_not_trigger
    # sharing that stem became an automatic false positive (#15a)
    skill = make_skill(
        description="Use this skill when the user asks to audit financial transactions."
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "audit")
    assert result.triggered is False


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


def test_single_word_keyword_does_not_force_trigger(make_skill) -> None:
    # a lone common word in `keywords:` used to short-circuit unconditionally,
    # making should_not_trigger unsatisfiable for that skill (#15b) — it
    # still counts toward ordinary recall, but can no longer force a match
    # on its own
    description = "A skill about something else entirely, completely unrelated in wording."
    skill = make_skill(
        description=description,
        frontmatter={"name": "my-skill", "description": description, "keywords": ["kubernetes"]},
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Help me debug a kubernetes deployment")
    assert result.triggered is False


def test_multiword_keyword_phrase_triggers_regardless_of_recall(make_skill) -> None:
    description = "A skill about something else entirely, completely unrelated in wording."
    skill = make_skill(
        description=description,
        frontmatter={
            "name": "my-skill",
            "description": description,
            "keywords": ["kubernetes deployment"],
        },
    )
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Help me debug a kubernetes deployment")
    assert result.triggered is True


def test_empty_description_never_triggers(make_skill) -> None:
    skill = make_skill(description="", frontmatter={"name": "my-skill", "description": ""})
    evaluator = HeuristicRoutingEvaluator()
    result = evaluator.evaluate(skill, "Anything at all")
    assert result.triggered is False


def test_threshold_is_constructor_configurable(make_skill) -> None:
    # a prompt with exactly one overlapping term out of several: low recall,
    # below the default 0.3 cutoff but above a looser one
    skill = make_skill(description="Use this skill when reviewing payment code.")
    prompt = "Please look at this payment thing among many unrelated other words here"
    default_result = HeuristicRoutingEvaluator().evaluate(skill, prompt)
    loose_result = HeuristicRoutingEvaluator(threshold=0.05).evaluate(skill, prompt)
    assert default_result.triggered is False
    assert loose_result.triggered is True
