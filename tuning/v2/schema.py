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


def load_schema(path: str | Path = NORTHFIELD) -> Schema:
    raw = json.load(open(path))
    fields: list[Field] = []
    for sec in raw["schema"]["sections"]:
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
