# Limitations

- Rules are regex/heuristic-based, not a real parser or NLP model — they will
  have false positives and false negatives. Findings are phrased as
  *potential* risk, never certainty.
- The heuristic routing evaluator uses simple tokenization and suffix
  stripping, not real stemming or embeddings; words like "secure" and
  "security" won't match each other.
- Token counts are a rough `len(text) // 4` estimate, not a real tokenizer.
- No sandboxing or dynamic execution — nothing in a skill is ever run.
- No compatibility testing against real agents (Claude Code, Codex, Gemini, etc.).

Planned work is tracked in [Issues](https://github.com/pespinel/skillseal/issues),
not here.
