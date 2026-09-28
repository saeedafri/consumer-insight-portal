"""Survey-agnostic mapping: topics, demographic cuts, derived bands.

The point of this module is that a new wave should load without a code change.
Nothing here is required for a survey to work — an unmatched question gets a
topic of its own, an undetected demographic simply doesn't appear as a filter.
The rules in config/survey_map.yml only make the result tidier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "survey_map.yml"

TECHNICAL_TOPIC = "TECHNICAL"
FALLBACK_TOPIC = "UNCLASSIFIED"


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else CONFIG_PATH
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# ── topics ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TopicRule:
    priority: int
    topic: str
    family: str = "*"
    pattern: Optional[str] = None
    text_pattern: Optional[str] = None

    def matches(self, qcode: str, qtext: str, family: Optional[str]) -> bool:
        if self.family != "*" and (family or "") != self.family:
            return False
        if self.pattern and re.search(self.pattern, qcode):
            return True
        if self.text_pattern and re.search(self.text_pattern, qtext or "", re.I):
            return True
        return False


def topic_rules(cfg: Optional[dict] = None) -> list[TopicRule]:
    cfg = cfg if cfg is not None else load_config()
    rules = [TopicRule(**{k: v for k, v in r.items()}) for r in cfg.get("topics", [])]
    return sorted(rules, key=lambda r: r.priority)


def classify_topic(qcode: str, qtext: str = "", family: Optional[str] = None,
                   cfg: Optional[dict] = None) -> str:
    """Return a topic code for any question, known questionnaire or not."""
    for rule in topic_rules(cfg):
        if rule.matches(qcode, qtext, family):
            return rule.topic
    return FALLBACK_TOPIC


def is_technical(topic_code: str) -> bool:
    return topic_code == TECHNICAL_TOPIC


# ── demographic cuts ───────────────────────────────────────────────────────
PROFILE_DIMENSIONS = (
    "gender", "age", "relationship", "ethnicity", "income_band",
    "urbanicity", "political", "state_name", "outlook_income", "outlook_economy",
)


def resolve_profile_map(
    questions: Iterable[Any], family: Optional[str] = None, cfg: Optional[dict] = None
) -> dict[str, str]:
    """Decide which question supplies each demographic cut, for THIS survey.

    Order of preference:
      1. an explicit entry for this survey family in config
      2. auto-detection from the question wording
      3. nothing — the dimension is dropped and the portal hides that filter

    Returns {dimension: qcode} containing only the dimensions actually found.
    """
    cfg = cfg if cfg is not None else load_config()
    questions = list(questions)
    codes = {getattr(q, "qcode", "") for q in questions}

    resolved: dict[str, str] = {}

    explicit = (cfg.get("profile") or {}).get(family or "", {}) or {}
    for dimension, qcode in explicit.items():
        if qcode in codes:
            resolved[dimension] = qcode

    detect = cfg.get("profile_detect") or {}
    for dimension, pattern in detect.items():
        if dimension in resolved:
            continue
        for q in questions:
            if re.search(pattern, getattr(q, "qtext", "") or "", re.I):
                resolved[dimension] = q.qcode
                break
    return resolved


# ── derived values ─────────────────────────────────────────────────────────
def _band(value: Optional[int], bands: list[dict]) -> Optional[str]:
    if value is None:
        return None
    for b in bands:
        if b["min"] <= value <= b["max"]:
            return b["label"]
    return None


def age_band(age: Optional[int], cfg: Optional[dict] = None) -> Optional[str]:
    cfg = cfg if cfg is not None else load_config()
    return _band(age, cfg.get("age_bands", []))


def generation(age: Optional[int], cfg: Optional[dict] = None) -> Optional[str]:
    cfg = cfg if cfg is not None else load_config()
    return _band(age, cfg.get("generations", []))


@lru_cache(maxsize=1)
def _region_index() -> dict[str, str]:
    """State -> census region, keyed on both the full name and the postal code.

    The 09/21/26 export gives codes ('CT', 'NC'); a future wave or a different
    country may give names. Accepting both costs nothing and avoids a silently
    empty region filter, which is how this was first noticed.
    """
    cfg = load_config()
    codes = {str(k).strip().upper(): str(v) for k, v in (cfg.get("state_codes") or {}).items()}
    name_to_code = {v.strip().lower(): k for k, v in codes.items()}
    out: dict[str, str] = {}
    for region, states in (cfg.get("census_regions") or {}).items():
        for state in states:
            key = str(state).strip().lower()
            out[key] = region
            code = name_to_code.get(key)
            if code:
                out[code.lower()] = region
    return out


def census_region(state_name: Optional[str]) -> Optional[str]:
    if not state_name:
        return None
    return _region_index().get(str(state_name).strip().lower())


def parse_age(label: Optional[str]) -> Optional[int]:
    """D2 is asked in single years and exported as a label ('34', 'Under 18',
    '70+'). Pull the first number out; return None when there isn't one."""
    if label is None:
        return None
    m = re.search(r"\d+", str(label))
    return int(m.group()) if m else None
