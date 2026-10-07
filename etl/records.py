"""The shapes every adapter shares: a parsed question, and the loader's label
convention (a ticked item holds its label, an unticked one "NO TO: <label>").

The Forsta Excel exports these were first written for are retired (Oct 2026):
Forsta loads through the API (etl/forsta_api.py), the legacy and Qualtrics
history through their own adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

NO_TO = "NO TO: "


def clean_text(value: Any) -> str:
    """Collapse every run of whitespace to one space.

    Forsta's datamap writes some labels with non-breaking spaces
    ('Spent\xa0a lot less…') while the raw export uses ordinary ones. Compared
    as-is the label->code lookup misses and the answer loads with no code, so
    every label passes through here, on every sheet."""
    return " ".join(str(value).split())


@dataclass
class ParsedQuestion:
    qcode: str
    qtext: str
    qtype: str = "text"
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    options: list[tuple[int, str]] = field(default_factory=list)
    rows: list[tuple[str, str]] = field(default_factory=list)
    flags: tuple = ()                        # Forsta: t = technical, v = virtual/derived
    bipolar: dict = field(default_factory=dict)   # row code -> (left statement, right statement)

    @property
    def is_multi(self) -> bool:
        return bool(self.rows) and (self.value_min, self.value_max) == (0, 1)


def normalise_label_cell(value: Any) -> tuple[Optional[int], Optional[str]]:
    """Turn a label-format cell into (code, label) for multi-punch columns.

    'NO TO: Gone to a bar' -> (0, 'Gone to a bar')
    'Gone to a bar'        -> (1, 'Gone to a bar')
    '' / None              -> (None, None)
    """
    if value is None:
        return None, None
    s = clean_text(value)
    if not s:
        return None, None
    if s.startswith(NO_TO):
        return 0, s[len(NO_TO):].strip()
    return 1, s
