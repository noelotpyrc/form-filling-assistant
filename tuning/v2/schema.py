"""Form schema model — v0 flat-field scope (groups + files deferred, doc-18 §2).

Loads packages/web-app/public/forms/*.json (same source the v1 harness reads)
into an ordered list of Fields. Booleans are modelled as Yes/No choices so the
composer can offer them as ask_choice like any other select.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NORTHFIELD = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"

SCALAR_TYPES = {"text", "textarea", "date", "email", "phone", "number"}
CHOICE_TYPES = {"select", "multi_select", "boolean"}
SKIP_TYPES = {"group", "file"}  # v0 scope cut — deferred to v1.5 / v2.5
CHOICE_BUTTON_MAX = 8  # selects with more options than this are asked as free text
                       # (e.g. the 15-country fields), not rendered as buttons


@dataclass
class Field:
    field_id: str
    label: str
    type: str
    required: bool
    section_id: str
    options: list[tuple]      # [(value, label)] for choices; [] otherwise
    condition: dict | None    # {field_id, operator, value} or None
    min: float | None = None
    max: float | None = None

    @property
    def is_choice(self) -> bool:
        return self.type in CHOICE_TYPES

    @property
    def button_choice(self) -> bool:
        """A choice small enough to render as clickable buttons. Large selects
        (countries) are asked as free text instead (the validator option-matches
        whatever the user types)."""
        return self.is_choice and len(self.options) <= CHOICE_BUTTON_MAX

    @property
    def is_multi(self) -> bool:
        return self.type == "multi_select"


@dataclass
class Schema:
    form_id: str
    name: str
    fields: list[Field]            # flat-only, in schema order
    by_id: dict[str, Field]

    def field(self, fid: str) -> Field | None:
        return self.by_id.get(fid)


def _options(raw: dict) -> list[tuple]:
    t = raw["type"]
    if t == "boolean":
        return [(True, "Yes"), (False, "No")]
    out = []
    for o in raw.get("options", []):
        if isinstance(o, dict):
            out.append((o["value"], o.get("label", str(o["value"]))))
        else:  # bare string option
            out.append((o, str(o)))
    return out


def parse_schema(raw: dict) -> Schema:
    """Build a Schema from a parsed form-JSON dict (e.g. the web app's
    `form_schema` request field), so serve and offline use share one path.

    Fields are ordered by the form's declared `instructions.section_order` (the
    same order the legacy LLM A prompt used — program first, then personal, …),
    falling back to physical section order. This is the agenda's walk order."""
    fields: list[Field] = []
    sections = raw["schema"]["sections"]
    order = (raw.get("instructions") or {}).get("section_order")
    if order:
        rank = {sid: i for i, sid in enumerate(order)}
        sections = sorted(sections, key=lambda s: rank.get(s.get("section_id", ""), len(order)))
    for sec in sections:
        sid = sec.get("section_id", "")
        for f in sec["fields"]:
            if f["type"] in SKIP_TYPES:
                continue
            fields.append(Field(
                field_id=f["field_id"],
                label=f.get("label", f["field_id"]),
                type=f["type"],
                required=bool(f.get("required")),
                section_id=sid,
                options=_options(f),
                condition=f.get("condition"),
                min=f.get("min"),
                max=f.get("max"),
            ))
    return Schema(
        form_id=raw["form_id"],
        name=raw["name"],
        fields=fields,
        by_id={f.field_id: f for f in fields},
    )


def load_schema(path: str | Path = NORTHFIELD) -> Schema:
    return parse_schema(json.load(open(path)))
