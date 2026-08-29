from skillseal.description_corpus import word_count_percentile


def test_below_p5_returns_zero() -> None:
    assert word_count_percentile(0) == 0
    assert word_count_percentile(6) == 0


def test_exact_thresholds() -> None:
    assert word_count_percentile(7) == 5
    assert word_count_percentile(37) == 50
    assert word_count_percentile(105) == 95


def test_above_p95_stays_at_95() -> None:
    assert word_count_percentile(500) == 95


def test_between_thresholds_rounds_down() -> None:
    assert word_count_percentile(15) == 10  # between p10=11 and p25=19
