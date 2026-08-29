from skillseal.routing.evaluator import LLMRoutingEvaluator


class _FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, prompt: str) -> str:
        return self.response


def test_confidence_is_none_not_a_fabricated_number(make_skill) -> None:
    # the model gives a yes/no, not a calibrated certainty - 1.0 would be a
    # fabricated confidence score, not a real one (see #15 discussion)
    skill = make_skill()
    evaluator = LLMRoutingEvaluator(provider=_FakeProvider("TRIGGER: yes\nREASON: matches.\n"))

    result = evaluator.evaluate(skill, "some prompt")

    assert result.triggered is True
    assert result.confidence is None


def test_unparseable_response_confidence_is_none(make_skill) -> None:
    skill = make_skill()
    evaluator = LLMRoutingEvaluator(provider=_FakeProvider("garbage, no TRIGGER line here"))

    result = evaluator.evaluate(skill, "some prompt")

    assert result.triggered is False
    assert result.confidence is None
    assert result.reason == "Could not parse model response."
