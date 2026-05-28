"""state_check.py — deterministic helpers for context augmentation and output coercion.

Purpose: replace tasks the SFT model is unreliable at with deterministic Python.
See doc-16 mapping for which CANNOT each helper targets:

  compute_state_summary   — CANNOT #3 (cross-check two states): humanized "filled vs missing"
  compute_group_indices   — CANNOT #5 (group-field index management): "current entries / next index"
  coerce_value            — CANNOT #6 (inconsistent value serialization): True/true, list, number
  validate_against_schema — CANNOT #7 (wrong field/value): drop unknown fields, snap selects to enum

These don't modify the model — they (a) enrich what the model sees in context (state
summary, group indices), and (b) clean what the model emits before it reaches the
browser (value coercion, schema validation). Treats the model as one component in
a larger pipeline whose other components are deterministic.

Field-id notation: schema uses dotted (`degrees.0.institution`). Model emits dotted.
form_state in the harness uses dashed (`degrees-0-institution`). All helpers
normalize internally to dotted; conversion happens at the boundaries.
"""

from __future__ import annotations

import json
import re
from typing import Any


# ══════════════════════════════════════════════════════════════════════
# Field-id normalization
# ══════════════════════════════════════════════════════════════════════

_GROUP_INDEX_RE = re.compile(r"^([a-zA-Z_]+)([-.])(\d+)\2(.+)$")


def normalize_field_id(fid: str) -> str:
    """`degrees-0-institution` → `degrees.0.institution`. Idempotent."""
    return fid.replace("-", ".") if isinstance(fid, str) else fid


def parse_group_field_id(fid: str) -> tuple[str, int, str] | None:
    """Returns (group_id, index, sub_field_id) for group fields, else None.

    Accepts both dotted and dashed notation.
    """
    m = _GROUP_INDEX_RE.match(fid)
    if not m:
        return None
    return m.group(1), int(m.group(3)), m.group(4)


# ══════════════════════════════════════════════════════════════════════
# Schema helpers
# ══════════════════════════════════════════════════════════════════════

def _walk_sections(schema: dict):
    """Yield each section in the schema."""
    sch = schema.get("schema") or schema
    for section in sch.get("sections", []) or []:
        yield section


def _find_field_def(schema: dict, field_id: str) -> dict | None:
    """Locate a field definition by id (handles `degrees.0.institution` →
    looks up the `institution` sub-field inside the `degrees` group)."""
    fid = normalize_field_id(field_id)
    parsed = parse_group_field_id(fid)
    if parsed:
        group_id, _idx, sub = parsed
        for section in _walk_sections(schema):
            for f in section.get("fields", []):
                if f.get("field_id") == group_id and f.get("type") == "group":
                    for sf in f.get("fields", []):
                        if sf.get("field_id") == sub:
                            return sf
        return None
    for section in _walk_sections(schema):
        for f in section.get("fields", []):
            if f.get("field_id") == fid:
                return f
    return None


# ══════════════════════════════════════════════════════════════════════
# Value coercion (CANNOT #6)
# ══════════════════════════════════════════════════════════════════════

_TRUE_LITERALS = {"true", "yes", "1", "y"}
_FALSE_LITERALS = {"false", "no", "0", "n"}


def coerce_value(field_def: dict | None, raw):
    """Coerce a raw extracted value to the schema's expected type.

    Examples:
      bool field, raw="True"               → True
      bool field, raw=True                 → True
      multi_select, raw="['a','b']"        → ["a", "b"]
      multi_select, raw="a, b"             → ["a", "b"]
      number, raw="3.85"                   → 3.85

    Pass-through for strings, dates, files, unknown types.
    Returns the original raw value when coercion fails (caller can decide
    whether to drop or accept).
    """
    if field_def is None:
        return raw
    ftype = field_def.get("type")

    if ftype == "boolean":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, str):
            s = raw.strip().lower()
            if s in _TRUE_LITERALS:
                return True
            if s in _FALSE_LITERALS:
                return False
        return raw

    if ftype == "number":
        if isinstance(raw, (int, float)):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            try:
                if "." in s:
                    return float(s)
                return int(s)
            except ValueError:
                try:
                    return float(s)
                except ValueError:
                    return raw
        return raw

    if ftype == "multi_select":
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            # Try JSON parse first
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s.replace("'", '"'))
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            # Fall back to comma-split
            if "," in s:
                return [t.strip() for t in s.split(",") if t.strip()]
            if s:
                return [s]
        return raw

    return raw


# ══════════════════════════════════════════════════════════════════════
# Schema validation (CANNOT #7 — drop unknown fields, snap selects to enum)
# ══════════════════════════════════════════════════════════════════════

def _enum_values(field_def: dict) -> list[str]:
    opts = field_def.get("options") or []
    out = []
    for o in opts:
        if isinstance(o, dict):
            v = o.get("value")
            if v is not None:
                out.append(str(v))
        else:
            out.append(str(o))
    return out


def _enum_label_to_value(field_def: dict) -> dict[str, str]:
    """Build a label-or-value → canonical-value lookup, lower-cased."""
    out = {}
    for o in field_def.get("options") or []:
        if isinstance(o, dict):
            v = str(o.get("value", ""))
            label = str(o.get("label", v))
            if v:
                out[v.lower()] = v
                out[label.lower()] = v
        else:
            s = str(o)
            out[s.lower()] = s
    return out


def validate_against_schema(schema: dict, field_id: str, value) -> tuple[bool, Any, str | None]:
    """Validate one field/value against the schema.

    Returns (is_valid, corrected_value, reason_if_dropped).
    - is_valid=False, reason set: drop this field/value from the action.
    - is_valid=True, corrected_value: the value to actually use (may be coerced
      from label → value, or coerced type-wise).
    """
    field_def = _find_field_def(schema, field_id)
    if field_def is None:
        return False, value, f"unknown_field:{field_id}"

    ftype = field_def.get("type")

    # Step 1: type coercion
    coerced = coerce_value(field_def, value)

    # Step 2: enum validation for selects
    if ftype == "select":
        valid_values = _enum_values(field_def)
        if not valid_values:
            return True, coerced, None
        s_val = str(coerced).strip()
        if s_val in valid_values:
            return True, s_val, None
        # Try snap to enum via label/value match
        lookup = _enum_label_to_value(field_def)
        snapped = lookup.get(s_val.lower())
        if snapped:
            return True, snapped, None
        return False, coerced, f"value_not_in_enum:{field_id}={value!r}"

    if ftype == "multi_select":
        valid_values = _enum_values(field_def)
        items = coerced if isinstance(coerced, list) else [coerced]
        out_items = []
        lookup = _enum_label_to_value(field_def) if valid_values else {}
        for it in items:
            s_it = str(it).strip()
            if not valid_values or s_it in valid_values:
                out_items.append(s_it)
                continue
            snapped = lookup.get(s_it.lower())
            if snapped:
                out_items.append(snapped)
        if not out_items:
            return False, coerced, f"all_values_invalid:{field_id}={value!r}"
        return True, out_items, None

    # Non-enum types: accept the coerced value
    return True, coerced, None


# ══════════════════════════════════════════════════════════════════════
# State summary (CANNOT #3) — humanized filled vs missing
# ══════════════════════════════════════════════════════════════════════

def _has_value(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    if isinstance(v, dict):
        return len(v) > 0
    return True


def _humanize_value(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def _filled_indices_for_group(group_id: str, form_state: dict) -> list[int]:
    """Find which entry-indices have been started for a group."""
    found = set()
    for k in form_state.keys():
        nk = normalize_field_id(k)
        parsed = parse_group_field_id(nk)
        if parsed and parsed[0] == group_id:
            if _has_value(form_state[k]):
                found.add(parsed[1])
    return sorted(found)


def compute_state_summary(schema: dict, form_state: dict) -> dict:
    """Walk the schema, classify each field as filled / empty (with required flag),
    and produce a humanized summary string for context injection.

    Returns:
      {
        "filled":   [(field_id, label, humanized_value), ...],
        "missing_required": [(field_id, label), ...],
        "sections": [{title, complete, filled_count, total_required}],
        "all_required_complete": bool,
        "humanized": "Already provided: ... | Still needed: ..."
      }
    """
    state = {normalize_field_id(k): v for k, v in (form_state or {}).items()}

    filled = []
    missing_required = []
    sections_summary = []

    for section in _walk_sections(schema):
        sec_required_total = 0
        sec_required_filled = 0
        for f in section.get("fields", []):
            fid = f.get("field_id")
            ftype = f.get("type")
            req = bool(f.get("required"))
            label = f.get("label", fid)

            if ftype == "group":
                # Per-entry handling: an entry counts as "filled" if any of its
                # required sub-fields has a value; "complete" if all required ones do.
                indices = _filled_indices_for_group(fid, state)
                req_subs = [sf for sf in f.get("fields", []) if sf.get("required")]
                if req:
                    # The group as a whole counts as required if no entries exist.
                    if not indices:
                        sec_required_total += 1
                        missing_required.append((fid, label))
                    else:
                        # Each entry's required sub-fields are individually checked.
                        for i in indices:
                            for sf in req_subs:
                                sec_required_total += 1
                                key = f"{fid}.{i}.{sf['field_id']}"
                                if _has_value(state.get(key)):
                                    sec_required_filled += 1
                                    filled.append((key, f"{sf.get('label', sf['field_id'])} (entry {i+1})", _humanize_value(state[key])))
                                else:
                                    missing_required.append((key, f"{sf.get('label', sf['field_id'])} (entry {i+1})"))
                continue

            v = state.get(fid)
            if _has_value(v):
                filled.append((fid, label, _humanize_value(v)))
                if req:
                    sec_required_total += 1
                    sec_required_filled += 1
            else:
                if req:
                    sec_required_total += 1
                    missing_required.append((fid, label))

        sections_summary.append({
            "title": section.get("title", ""),
            "filled_count": sec_required_filled,
            "total_required": sec_required_total,
            "complete": sec_required_total > 0 and sec_required_filled == sec_required_total,
        })

    all_complete = len(missing_required) == 0

    # Humanized summary string for context injection.
    if filled:
        filled_part = "Already provided: " + "; ".join(
            f"{label} = {val}" for _fid, label, val in filled
        )
    else:
        filled_part = "Already provided: nothing yet."
    if missing_required:
        missing_part = "Still needed (required): " + ", ".join(
            label for _fid, label in missing_required
        )
    else:
        missing_part = "All required fields are complete."

    return {
        "filled": filled,
        "missing_required": missing_required,
        "sections": sections_summary,
        "all_required_complete": all_complete,
        "humanized": filled_part + " | " + missing_part,
    }


# ══════════════════════════════════════════════════════════════════════
# Group indices summary (CANNOT #5)
# ══════════════════════════════════════════════════════════════════════

def compute_group_indices(schema: dict, form_state: dict) -> dict:
    """For each group field, return existing indices and the next available.

    Returns:
      {
        "<group_id>": {
          "label": "Degrees",
          "filled_indices": [0, 1],
          "next_index": 2,
          "max_items": int | None
        },
        ...
      }
    """
    state = {normalize_field_id(k): v for k, v in (form_state or {}).items()}
    out = {}
    for section in _walk_sections(schema):
        for f in section.get("fields", []):
            if f.get("type") != "group":
                continue
            gid = f.get("field_id")
            indices = _filled_indices_for_group(gid, state)
            next_idx = (max(indices) + 1) if indices else 0
            out[gid] = {
                "label": f.get("label", gid),
                "filled_indices": indices,
                "next_index": next_idx,
                "max_items": f.get("max_items"),
            }
    return out


def humanize_group_indices(indices_summary: dict) -> str:
    """Render group indices as a one-line context snippet."""
    parts = []
    for gid, info in indices_summary.items():
        label = info["label"]
        filled = info["filled_indices"]
        if not filled:
            parts.append(f"{label}: no entries yet (next would be entry 1)")
        else:
            parts.append(
                f"{label}: {len(filled)} entry/entries (entries {', '.join(str(i+1) for i in filled)}); next would be entry {info['next_index']+1}"
            )
    return " | ".join(parts) if parts else ""
