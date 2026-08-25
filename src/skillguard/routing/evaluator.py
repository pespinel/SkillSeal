"""RoutingEvaluator implementations: deterministic heuristic and optional LLM-backed."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from skillguard.models import RoutingResult, Skill

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*")
_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "as",
    "at",
    "by",
    "from",
    "your",
    "you",
    "i",
    "we",
    "they",
    "he",
    "she",
    "them",
    "his",
    "her",
    "their",
    "our",
    "my",
    "me",
    "us",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "shall",
    "may",
    "might",
    "must",
    "not",
    "no",
    "yes",
    "so",
    "than",
    "then",
    "there",
    "here",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "why",
    "when",
    "where",
    "about",
    "into",
    "over",
    "under",
    "again",
    "once",
    "just",
    "also",
    "please",
    "up",
    "out",
    "all",
    "any",
    "some",
    "whether",
    "whatever",
}


def _stem(word: str) -> str:
    """Naive deterministic stemmer (suffix stripping only, no real morphology)."""
    if len(word) > 6 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 5 and word.endswith("edly"):
        return word[:-4]
    if len(word) > 5 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _terms(text: str) -> set[str]:
    words = (w.lower() for w in _WORD_RE.findall(text))
    return {_stem(w) for w in words if len(w) >= 2 and w not in _STOPWORDS}


class RoutingEvaluator(Protocol):
    def evaluate(self, skill: Skill, prompt: str) -> RoutingResult: ...


@dataclass
class HeuristicRoutingEvaluator:
    """Fully offline: scores how much of the *prompt's* distinctive vocabulary
    is covered by the skill's own vocabulary (name + description + keywords).

    Recall is computed against the prompt's term count, not the description's:
    a short prompt against a long, thorough description should still be able
    to match cleanly, rather than being structurally penalized by the
    description's length. A hit on any declared `keywords:` term also
    triggers directly, since those are an explicit author signal.
    """

    threshold: float = 0.3

    def evaluate(self, skill: Skill, prompt: str) -> RoutingResult:
        prompt_terms = _terms(prompt)
        desc_terms = _terms(f"{skill.name.replace('-', ' ')} {skill.description}")

        keyword_terms: set[str] = set()
        raw_keywords = skill.frontmatter.get("keywords")
        if isinstance(raw_keywords, list):
            for kw in raw_keywords:
                keyword_terms |= _terms(str(kw))

        reference_terms = desc_terms | keyword_terms
        if not reference_terms or not prompt_terms:
            return RoutingResult(
                triggered=False,
                confidence=0.0,
                reason="Skill has no usable description/keyword terms.",
            )

        overlap = reference_terms & prompt_terms
        recall = len(overlap) / len(prompt_terms)
        keyword_hit = bool(keyword_terms & prompt_terms)
        triggered = recall >= self.threshold or keyword_hit

        if triggered:
            matched = sorted(overlap) or sorted(keyword_terms & prompt_terms)
            reason = f"Matched terms: {', '.join(matched[:6])}"
        elif recall == 0:
            reason = "No meaningful overlap between prompt and skill description."
        else:
            reason = f"Description overlap too low ({recall:.0%} of prompt terms matched)."

        return RoutingResult(triggered=triggered, confidence=round(recall, 3), reason=reason)


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...


_LLM_PROMPT_TEMPLATE = """You are deciding whether an AI agent skill should trigger for a prompt.

Skill name: {name}
Skill description: {description}

User prompt: "{prompt}"

Should this skill be triggered for this prompt? Respond with exactly two lines:
TRIGGER: yes or no
REASON: one short sentence
"""

_TRIGGER_RE = re.compile(r"TRIGGER:\s*(yes|no)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASON:\s*(.+)")


@dataclass
class LLMRoutingEvaluator:
    """Delegates the trigger/no-trigger decision to an LLMProvider."""

    provider: LLMProvider

    def evaluate(self, skill: Skill, prompt: str) -> RoutingResult:
        completion = self.provider.complete(
            _LLM_PROMPT_TEMPLATE.format(
                name=skill.name, description=skill.description, prompt=prompt
            )
        )
        trigger_match = _TRIGGER_RE.search(completion)
        reason_match = _REASON_RE.search(completion)
        if trigger_match is None:
            return RoutingResult(
                triggered=False, confidence=0.0, reason="Could not parse model response."
            )
        triggered = trigger_match.group(1).lower() == "yes"
        reason = reason_match.group(1).strip() if reason_match else completion.strip()[:200]
        return RoutingResult(triggered=triggered, confidence=1.0, reason=reason)


class OpenAICompatibleProvider:
    """LLMProvider backed by any OpenAI-compatible /chat/completions endpoint.

    Configured via SKILLGUARD_BASE_URL, SKILLGUARD_API_KEY, SKILLGUARD_MODEL.
    """

    def __init__(
        self, base_url: str | None = None, api_key: str | None = None, model: str | None = None
    ) -> None:
        base_url = base_url or os.environ.get("SKILLGUARD_BASE_URL")
        model = model or os.environ.get("SKILLGUARD_MODEL")
        if not base_url or not model:
            raise RuntimeError(
                "SKILLGUARD_BASE_URL and SKILLGUARD_MODEL must be set to use the LLM evaluator."
            )
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("SKILLGUARD_API_KEY")
        self.model = model

    def complete(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to reach {self.base_url}: {exc}") from exc
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected response shape from LLM provider.") from exc
