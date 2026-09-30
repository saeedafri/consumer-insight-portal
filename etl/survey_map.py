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



def parse_age_band(label: Optional[str]) -> tuple[Optional[str], Optional[float]]:
    """A banded age answer -> (band, midpoint). A single-year answer is not a
    band; "under 18" matches no band on purpose (outside every cut)."""
    value = " ".join(str(label or "").split()).lower()
    for rule in load_config().get("age_band_labels") or []:
        if re.match(rule["pattern"], value):
            return rule["band"], float(rule["mid"])
    return None, None



_RANGE = [
    (re.compile(r"^(\d+)\s*-\s*(\d+)$"), lambda a, b: (int(a), int(b))),
    (re.compile(r"^(?:over|>)\s*(\d+)$"), lambda a: (int(a) + 1, 200)),
    (re.compile(r"^(\d+)\s*(?:\+|or (?:more|above|over|older))$"), lambda a: (int(a), 200)),
    (re.compile(r"^(?:under|below|less than)\s*(\d+)$"), lambda a: (18, int(a) - 1)),
]


def _containing(low: int, high: int, cuts: list) -> Optional[str]:
    return next((c["label"] for c in cuts if c["min"] <= low and high <= c["max"]), None)


def classify_age(label: Optional[str]) -> dict:
    """An age answer -> {age, band, gen, mid}.

    A single year ('34') gives all four. A range ('26-41', 'over 60') has no
    single age; it gets a band or generation only when it lies wholly inside
    one — '26-41' spans GenZ and Millennials, so it gets neither. Midpoints of
    the standard bands are the analysts' (age_band_labels)."""
    value = " ".join(str(label or "").split()).lower()
    for pattern, bounds in _RANGE:
        m = pattern.match(value)
        if not m:
            continue
        low, high = bounds(*m.groups())
        if high < 18:                                 # "Under 18": outside every cut
            return {"age": high, "band": None, "gen": None, "mid": high}
        cfg = load_config()
        _, known_mid = parse_age_band(value)
        return {"age": None,
                "band": _containing(low, high, cfg.get("age_bands", [])),
                "gen": _containing(low, high, cfg.get("generations", [])),
                # only an explicit "a - b" has a midpoint; "under 50" assumes its 18
                "mid": known_mid if known_mid is not None
                       else (low + high) / 2 if pattern is _RANGE[0][0] else None}
    age = parse_age(label)
    return {"age": age, "band": age_band(age), "gen": generation(age), "mid": age}

def income_mid_k(label: Optional[str]) -> Optional[float]:
    table = {k.lower(): v for k, v in (load_config().get("income_midpoints_k") or {}).items()}
    return table.get(" ".join(str(label or "").split()).lower())

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
    '70 or more'). Pull the first number out; return None when there isn't one.

    'Under 18' is below the number, not at it: read as 18 it would put an
    under-age respondent in GenZ and 18-29, which Forsta's banner excludes
    (09/28 had one — our GenZ said 62, the published table 61)."""
    if label is None:
        return None
    m = re.search(r"\d+", str(label))
    if not m:
        return None
    age = int(m.group())
    return age - 1 if re.match(r"\s*(under|below|less than)\b", str(label), re.I) else age
