"""v2 harness — small-LLM-first form-filling, teacher-distillation design.

See docs/doc-18-harness-redesign.md (architecture) and
docs/doc-18.1-turn-logic.html (the per-turn contract this implements).

The deterministic core (schema, state, prestep, validator, composer) is pure
stdlib and needs no model. The two learned calls (extractor, responder) and the
teacher LM live in program.py / claude_lm.py (added in M1 chunk 3).
"""
