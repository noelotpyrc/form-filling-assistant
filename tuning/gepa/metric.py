"""Hybrid metric for GEPA optimization of FormAssistant.

Score = renormalized weighted sum across ACTIVE modules per case.
A module is "active" iff its corresponding gold flag fires (action_router and
text_responder are always active). Inactive modules are not scored — the
spurious-fire failure mode is already caught by the action_router flag check.

Modules:
  - action_router:   5-flag exact match (programmatic)
  - data_extractor:  field_id set + per-field value match (programmatic)
  - choice_builder:  options ⊆ schema enum (programmatic)
  - review_builder:  structure populated (programmatic; content from harness)
  - text_responder:  persona-leak regex (programmatic) + rubric judge (LLM)

Step 1 of build: programmatic only. Judge wired in later.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "packages" / "web-app" / "public" / "forms" / "masters-northfield.json"

DEFAULT_WEIGHTS = {
    "action_router":  0.20,
    "data_extractor": 0.15,
    "choice_builder": 0.05,
    "review_builder": 0.05,
    "text_responder": 0.55,
}
# Rationale: programmatic baseline is already 0.88 (model handles flags/fields
# well). The judge inside text_responder catches the harder behavioral failures
# (no-fabrication, persona-leak in nuanced ways, intent-match). Heavier
# text_responder weight forces GEPA to optimize for what the model actually
# struggles with, not the easy programmatic wins.

FORBIDDEN_PERSONAS = [
    "Jane Smith", "Jane Doe", "Alex Chen", "Maria Garcia", "Carlos Garcia",
    "Sarah Connor", "Alan Turing", "Fei-Fei Li", "David Silver", "Emily Chen",
    "Sarah Mitchell", "Manuel Blum",
]
FORBIDDEN_REGEX = re.compile(
    "|".join(re.escape(p) for p in FORBIDDEN_PERSONAS), re.IGNORECASE
)


def _input_haystack(case: dict | None) -> str:
    """Concatenate all input text — used to decide whether a persona
    reference is legitimate (the user IS that persona) vs hallucinated."""
    if case is None:
        return ""
    inp = case.get("input", {})
    parts = [
        json.dumps(inp.get("form_state", {}), ensure_ascii=False),
        " ".join(t.get("content", "") for t in inp.get("conversation_history", [])),
        inp.get("user_message", ""),
    ]
    return " ".join(parts).lower()


def _detect_persona_leak(pred_text: str, case: dict | None) -> tuple[bool, str]:
    """Return (passed, detail). A persona reference is OK only if it appears
    in the case input (form_state/history/user_message)."""
    if not pred_text:
        return True, ""
    pred_lower = pred_text.lower()
    haystack = _input_haystack(case)
    leaked = [
        p for p in FORBIDDEN_PERSONAS
        if p.lower() in pred_lower and p.lower() not in haystack
    ]
    if not leaked:
        return True, ""
    return False, f"response references persona(s) not in input: {leaked}"

FLAG_NAMES = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]


# ─────────────────────────────────────────────────────────────────────────
# Schema indexing
# ─────────────────────────────────────────────────────────────────────────

def _index_schema(schema: dict) -> dict[str, dict]:
    """Map every field_id (incl. group sub-fields as 'group.*.subfield') to defn."""
    out: dict[str, dict] = {}
    for sec in schema["schema"]["sections"]:
        for f in sec["fields"]:
            out[f["field_id"]] = f
            if f.get("type") == "group":
                for sf in f.get("fields", []):
                    out[f"{f['field_id']}.*.{sf['field_id']}"] = sf
    return out


def _load_schema_index() -> dict[str, dict]:
    return _index_schema(json.loads(SCHEMA_PATH.read_text()))


_SCHEMA_INDEX_CACHE: dict[str, dict] | None = None


def schema_index() -> dict[str, dict]:
    global _SCHEMA_INDEX_CACHE
    if _SCHEMA_INDEX_CACHE is None:
        _SCHEMA_INDEX_CACHE = _load_schema_index()
    return _SCHEMA_INDEX_CACHE


def normalize_field_id(field_id: str) -> str:
    """jobs.0.employer  →  jobs.*.employer  (for schema lookup)."""
    return re.sub(r"\.\d+\.", ".*.", field_id)


def get_field_def(field_id: str) -> dict | None:
    return schema_index().get(normalize_field_id(field_id))


def field_enum_values(field_id: str) -> list[str] | None:
    """Return list of enum values for a select/multi_select field, else None."""
    fd = get_field_def(field_id)
    if not fd:
        return None
    if fd.get("type") not in ("select", "multi_select"):
        return None
    opts = fd.get("options", [])
    return [o["value"] if isinstance(o, dict) else o for o in opts]


_ALL_ENUM_TOKENS_CACHE: set[str] | None = None


def all_schema_enum_tokens() -> set[str]:
    """Aggregate every value+label across every select/multi_select field.

    Used to lenient-check that predicted choice options aren't fabricated.
    Lenient because the case data doesn't tell us which field a choice is
    for (e.g., P2-ex5 extracts program but asks about start_term).
    """
    global _ALL_ENUM_TOKENS_CACHE
    if _ALL_ENUM_TOKENS_CACHE is not None:
        return _ALL_ENUM_TOKENS_CACHE
    tokens: set[str] = set()
    for fd in schema_index().values():
        if fd.get("type") not in ("select", "multi_select"):
            continue
        for o in fd.get("options", []):
            if isinstance(o, dict):
                if o.get("label"):
                    tokens.add(o["label"])
                if o.get("value"):
                    tokens.add(o["value"])
            else:
                tokens.add(str(o))
    _ALL_ENUM_TOKENS_CACHE = tokens
    return tokens


# ─────────────────────────────────────────────────────────────────────────
# Check result + module score
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    # Fractional credit in [0,1]. Used by multi-judge averaging where two
    # judges may disagree on a rubric item (→ 0.5). When unset, falls back
    # to 1.0 / 0.0 derived from `passed`. Aggregation uses `score`, not
    # `passed`, so partial-credit items are weighted correctly.
    score: float | None = None

    @property
    def effective_score(self) -> float:
        if self.score is not None:
            return self.score
        return 1.0 if self.passed else 0.0


@dataclass
class ModuleScore:
    module: str
    score: float          # in [0, 1]
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


# ─────────────────────────────────────────────────────────────────────────
# Value normalization (for field_value comparison)
# ─────────────────────────────────────────────────────────────────────────

def _norm_value(v: Any) -> str:
    """Normalize a field value for comparison.

    Handles bool↔string ('true'/'True'/True), date format equivalents,
    whitespace/case stripping. Errs on the side of leniency.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v).strip()
    # Bool-as-string
    sl = s.lower()
    if sl in ("true", "false"):
        return sl
    # Numeric strings: collapse "3.5" / "3.50" → "3.5"
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return f"{f:g}"
    except ValueError:
        pass
    return sl


def values_equal(a: Any, b: Any) -> bool:
    return _norm_value(a) == _norm_value(b)


# ─────────────────────────────────────────────────────────────────────────
# Per-module scorers
# ─────────────────────────────────────────────────────────────────────────

def score_action_router(gold_flags: dict, pred_flags: dict) -> ModuleScore:
    """F1 on the set of True flags.

    Caller only invokes this when at least one flag is True in gold OR pred
    (cases where both sides have all-False flags trivially "match" — that
    correctness is real but uninformative for ranking, so we skip the module
    entirely on those, mirroring the data_extractor inactive pattern).

    TP = flags True in both; FP = pred-only True; FN = gold-only True. F1
    cleanly captures both spurious fires (FP) and missed fires (FN) with
    graduated scoring.
    """
    checks: list[CheckResult] = []
    gold_set = {f for f in FLAG_NAMES if bool(gold_flags.get(f, False))}
    pred_set = {f for f in FLAG_NAMES if bool(pred_flags.get(f, False))}

    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    if tp == 0 and (fp + fn) == 0:
        f1 = 1.0  # caller should have skipped, but be safe
    elif tp == 0:
        f1 = 0.0
    else:
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)

    # Per-flag detail rows for GEPA feedback (informational, don't affect score)
    for f in FLAG_NAMES:
        g = f in gold_set
        p = f in pred_set
        ok = g == p
        checks.append(CheckResult(
            name=f"flag_{f}",
            passed=ok,
            detail="" if ok else f"predicted {p}, expected {g}",
        ))

    return ModuleScore("action_router", f1, checks)


def _any_flag_true(flags: dict) -> bool:
    return any(bool(flags.get(f, False)) for f in FLAG_NAMES)


def score_data_extractor(gold_ids: list, gold_vals: list,
                         pred_ids: list, pred_vals: list) -> ModuleScore:
    """Field-set match + per-field value match. Active only when gold says
    has_new_data is True (caller responsible)."""
    checks: list[CheckResult] = []
    gold_set = set(gold_ids)
    pred_set = set(pred_ids)

    # 1. Field-id set match (precision/recall → F1)
    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    if tp == 0 and (fp + fn) == 0:
        f1 = 1.0
    elif tp == 0:
        f1 = 0.0
    else:
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)
    checks.append(CheckResult(
        name="field_ids_match",
        passed=f1 >= 0.999,
        detail=f"F1={f1:.2f} (extra: {sorted(pred_set - gold_set)}, missing: {sorted(gold_set - pred_set)})",
    ))

    # 2. Per-overlap value match (only on TP fields)
    gold_map = dict(zip(gold_ids, gold_vals))
    pred_map = dict(zip(pred_ids, pred_vals))
    overlap = gold_set & pred_set
    if overlap:
        val_correct = sum(
            1 for fid in overlap
            if values_equal(gold_map.get(fid), pred_map.get(fid))
        )
        val_score = val_correct / len(overlap)
        for fid in sorted(overlap):
            ok = values_equal(gold_map.get(fid), pred_map.get(fid))
            checks.append(CheckResult(
                name=f"value_{fid}",
                passed=ok,
                detail="" if ok else f"predicted {pred_map.get(fid)!r}, expected {gold_map.get(fid)!r}",
            ))
    else:
        val_score = 1.0 if not gold_set else 0.0  # no overlap and gold is non-empty → all wrong

    # Module score: 60% set match, 40% value match
    score = 0.6 * f1 + 0.4 * val_score
    return ModuleScore("data_extractor", score, checks)


def score_data_extractor_inactive(pred_ids: list) -> ModuleScore:
    """When gold has_new_data=False, score = 1.0 if model also abstained, else 0."""
    ok = len(pred_ids) == 0
    return ModuleScore("data_extractor", 1.0 if ok else 0.0, [
        CheckResult(
            name="extract_abstain",
            passed=ok,
            detail="" if ok else f"model spuriously emitted {len(pred_ids)} field(s): {pred_ids}",
        )
    ])


def score_choice_builder_inactive(pred_question: str, pred_options: list) -> ModuleScore:
    ok = not pred_question and not pred_options
    return ModuleScore("choice_builder", 1.0 if ok else 0.0, [
        CheckResult(
            name="choice_abstain",
            passed=ok,
            detail="" if ok else f"model spuriously emitted choice (q={pred_question!r}, opts={pred_options})",
        )
    ])


def score_review_builder_inactive(pred_title: str, pred_content: str) -> ModuleScore:
    ok = not pred_title and not pred_content
    return ModuleScore("review_builder", 1.0 if ok else 0.0, [
        CheckResult(
            name="review_abstain",
            passed=ok,
            detail="" if ok else f"model spuriously emitted review (title={pred_title!r}, content={pred_content[:60]!r})",
        )
    ])


def score_text_responder(pred_text: str, case: dict | None = None,
                         pred: dict | None = None,
                         use_judge: bool = True) -> ModuleScore:
    """text_responder scoring: persona-leak regex (programmatic) + rubric judge.

    The persona-leak check is treated as a separate, weighted item; combined
    with the per-case rubric items into one weighted average.

    The judge now sees the FULL prediction (`pred`, the 5 module outputs),
    not just response_text. Rubric items can reason about cross-module
    consistency: did the response_text claim an action the field_ids did
    not perform? Did the model impose a value rather than answer?
    """
    checks: list[CheckResult] = []
    weights: list[float] = []

    leak_passed, leak_detail = _detect_persona_leak(pred_text or "", case)
    checks.append(CheckResult(
        name="no_persona_leak",
        passed=leak_passed,
        detail=leak_detail,
    ))
    # Low weight: this check passes trivially on most cases (only meaningful
    # for #8_training_data_hallucination seeds). Acts as a cheap tripwire,
    # not a primary signal.
    weights.append(0.5)

    if use_judge and case is not None:
        from rubrics import get_rubric_for_case
        from judge import judge_case
        rubric = get_rubric_for_case(case)
        # Judge sees full prediction (all 5 module outputs), not just text.
        if pred is None:
            pred = {"response_text": pred_text or ""}
        # No silent fallback. Judge is the dominant signal for text_responder
        # (weight 0.55); a failure here is a system error that must halt the
        # run, not be papered over with a programmatic-only score.
        # See: tuning/gepa/INCIDENT_2026-05-15_judge_silent_fallback.md
        # (judge.judge_case already retries JUDGE_MAX_ATTEMPTS times)
        answers = judge_case(case, pred, rubric)
        for item, ans in zip(rubric, answers):
            score = float(ans) if isinstance(ans, (int, float, bool)) else 0.0
            passed = score >= 0.5
            checks.append(CheckResult(
                name=f"rubric_{item['id']}",
                passed=passed,
                score=score,
                detail="" if passed else f"judge says no (score={score}) — {item['ask']}",
            ))
            weights.append(item["weight"])

    return _aggregate_text(checks, weights)


def _aggregate_text(checks: list[CheckResult], weights: list[float]) -> ModuleScore:
    total_w = sum(weights) or 1.0
    earned = sum(w * c.effective_score for c, w in zip(checks, weights))
    return ModuleScore("text_responder", earned / total_w, checks)


# ─────────────────────────────────────────────────────────────────────────
# Top-level scoring
# ─────────────────────────────────────────────────────────────────────────

def score_case(case: dict, pred: dict, weights: dict | None = None,
               use_judge: bool = True) -> dict:
    """Score one case.

    case  — full eval-case dict (input + correct_answer + cannot_targets + source)
    pred  — model prediction dict with keys matching correct_answer's shape
    use_judge — if False, skip LLM judge for text_responder (programmatic only)
    """
    w = weights or DEFAULT_WEIGHTS
    gold = case["correct_answer"]
    gold_flags = gold["flags"]
    pred_flags = pred.get("flags", {})

    modules: list[ModuleScore] = []

    # action_router: only score when at least one flag is True in gold or pred.
    # When both sides are all-False, the "match" is trivially correct and
    # tells us nothing — skip to avoid inflating the composite.
    if _any_flag_true(gold_flags) or _any_flag_true(pred_flags):
        modules.append(score_action_router(gold_flags, pred_flags))

    if gold_flags.get("has_new_data"):
        modules.append(score_data_extractor(
            gold.get("field_ids", []), gold.get("field_values", []),
            pred.get("field_ids", []), pred.get("field_values", []),
        ))
    elif pred.get("field_ids"):
        # Spurious fire — penalize
        modules.append(score_data_extractor_inactive(pred.get("field_ids", [])))

    # choice_builder & review_builder: only score on spurious-fire (gold
    # didn't ask for it, but model emitted output anyway). "Did the model
    # produce non-empty structure when expected" is too weak to be a useful
    # programmatic check — the rubric's `internally_consistent` item covers
    # cross-module coherence (e.g., needs_choice=True ⇒ question populated)
    # and the rubric's category-bad items cover content quality.
    if not gold_flags.get("needs_choice") and (pred.get("question") or pred.get("options")):
        modules.append(score_choice_builder_inactive(
            pred.get("question", ""), pred.get("options", []),
        ))

    if not gold_flags.get("wants_review") and (pred.get("summary_title") or pred.get("summary_content")):
        modules.append(score_review_builder_inactive(
            pred.get("summary_title", ""), pred.get("summary_content", ""),
        ))

    modules.append(score_text_responder(
        pred.get("response_text", ""), case=case, pred=pred, use_judge=use_judge,
    ))

    # Renormalize weights across active modules
    active_weights = {m.module: w[m.module] for m in modules}
    total_w = sum(active_weights.values())
    composite = sum(m.score * active_weights[m.module] for m in modules) / total_w

    return {
        "score": composite,
        "modules": modules,
        "feedback": _build_feedback(modules, composite),
    }


def _build_feedback(modules: list[ModuleScore], composite: float) -> str:
    lines = [f"Score: {composite:.3f}"]
    failed = [(m, c) for m in modules for c in m.failed]
    if not failed:
        lines.append("All checks passed.")
        return "\n".join(lines)
    lines.append("Failed checks:")
    for m, c in failed:
        lines.append(f"  [{m.module}] {c.name}: {c.detail}")
    passed_modules = [m.module for m in modules if not m.failed]
    if passed_modules:
        lines.append(f"Passed modules: {', '.join(passed_modules)}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# DSPy adapter (wire in once we plug into FormAssistant)
# ─────────────────────────────────────────────────────────────────────────

def dspy_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    """DSPy GEPA-compatible metric.

    `gold` is a dspy.Example carrying the full case dict on `.case`.
    `pred` is FormAssistant's prediction with the 5 module outputs.

    Returns dspy.Prediction(score, feedback) when pred_name is set
    (during GEPA reflection); else returns a float (during evaluation).
    """
    import dspy

    if isinstance(gold, dict):
        case = gold
    elif hasattr(gold, "case"):
        case = gold.case
    elif hasattr(gold, "toDict"):
        case = gold.toDict().get("case", gold.toDict())
    else:
        case = dict(gold)

    pred_dict = _extract_pred(pred)
    result = score_case(case, pred_dict)
    if pred_name is None:
        return result["score"]
    return dspy.Prediction(score=result["score"], feedback=result["feedback"])


def _extract_pred(pred) -> dict:
    """Pull the 5 module outputs from a FormAssistant prediction.

    FormAssistant returns set_fields/ask_choice/etc. — we map to our flag/field
    shape. Placeholder until we wire the actual prediction format.
    """
    if isinstance(pred, dict):
        return pred
    return {
        "flags": {f: getattr(pred, f, False) for f in FLAG_NAMES},
        "response_text":   getattr(pred, "response_text", ""),
        "field_ids":       list(getattr(pred, "field_ids", [])),
        "field_values":    list(getattr(pred, "field_values", [])),
        "question":        getattr(pred, "question", ""),
        "options":         list(getattr(pred, "options", [])),
        "summary_title":   getattr(pred, "summary_title", ""),
        "summary_content": getattr(pred, "summary_content", ""),
    }


def pred_to_flat_dict(pred) -> dict:
    """Persist-friendly flat schema (matches GEPA's iter_0_prog_0.json).

    Use this when writing predictions to JSON alongside scores — keeps the
    shape consistent across all inspection artifacts so they remain
    interchangeable and re-scorable.
    """
    if isinstance(pred, dict):
        if "flags" in pred:  # nested → flat
            flags = pred.get("flags") or {}
            return {
                "response_text":   pred.get("response_text", "") or "",
                **{f: bool(flags.get(f, False)) for f in FLAG_NAMES},
                "field_ids":       list(pred.get("field_ids", []) or []),
                "field_values":    list(pred.get("field_values", []) or []),
                "question":        pred.get("question", "") or "",
                "options":         list(pred.get("options", []) or []),
                "summary_title":   pred.get("summary_title", "") or "",
                "summary_content": pred.get("summary_content", "") or "",
            }
        return pred  # already flat
    return {
        "response_text":   getattr(pred, "response_text", "") or "",
        **{f: bool(getattr(pred, f, False)) for f in FLAG_NAMES},
        "field_ids":       list(getattr(pred, "field_ids", []) or []),
        "field_values":    list(getattr(pred, "field_values", []) or []),
        "question":        getattr(pred, "question", "") or "",
        "options":         list(getattr(pred, "options", []) or []),
        "summary_title":   getattr(pred, "summary_title", "") or "",
        "summary_content": getattr(pred, "summary_content", "") or "",
    }


JUDGE_ENV_KEYS = (
    "JUDGE_BACKEND", "JUDGE_MODEL", "JUDGE_TEMPERATURE",
    "JUDGE_CLAUDE_N", "JUDGE_CLAUDE_MODEL", "JUDGE_CLAUDE_EFFORT",
    "JUDGE_CLAUDE_TIMEOUT", "CLAUDE_BIN",
)


def capture_judge_env() -> dict:
    """Resolve every env var that affects judge behavior (or None if unset)."""
    return {k: os.environ.get(k) for k in JUDGE_ENV_KEYS}


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="Score eval cases against gold (self-test).")
    ap.add_argument("--cases", default=str(REPO_ROOT / "tuning" / "gepa" / "eval_cases.jsonl"))
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--no-judge", action="store_true",
                    help="Skip LLM judge (programmatic-only)")
    args = ap.parse_args()

    cases = [json.loads(l) for l in open(args.cases)]
    print(f"Loaded {len(cases)} cases. Scoring first {args.limit} with pred=gold "
          f"(self-test, judge={'OFF' if args.no_judge else 'ON'}).\n")
    for c in cases[: args.limit]:
        pred = c["correct_answer"]  # self-test: pred = gold
        result = score_case(c, pred, use_judge=not args.no_judge)
        print(f"--- {c['test_id']} ({', '.join(c['cannot_targets'])}) ---")
        print(result["feedback"])
        print()


if __name__ == "__main__":
    _cli()
