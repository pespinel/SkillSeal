"""Description word-count percentiles, measured from a real corpus (#24).

Per #24: build the corpus measurement first, calibrate against it second — a
competitor's enumerated 170-verb blocklist zero-scored real skills purely
because "use" wasn't on the list. These numbers come from scanning 1,142 real
skills (see .corpus-benchmark/analysis-issue15-issue24.txt, gathered during
the #15/#24 investigation), not from guessing a plausible-looking scale.

Used only by `--explain-score` for descriptive context on a QUALITY-category
breakdown — it never feeds back into the score itself.
"""

from __future__ import annotations

# (percentile, word-count at or above which a description reaches it), n=1142
_WORD_COUNT_PERCENTILES: tuple[tuple[int, int], ...] = (
    (5, 7),
    (10, 11),
    (25, 19),
    (50, 37),
    (75, 55),
    (90, 80),
    (95, 105),
)


def word_count_percentile(word_count: int) -> int:
    """Roughly which percentile `word_count` falls at in the measured corpus.

    Returns 0 for anything below the corpus's own p5.
    """
    percentile = 0
    for p, threshold in _WORD_COUNT_PERCENTILES:
        if word_count < threshold:
            break
        percentile = p
    return percentile
