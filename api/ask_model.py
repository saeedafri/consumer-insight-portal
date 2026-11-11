"""Ask Coresight's model steps (OpenAI): find survey questions by meaning, and read what a question asks for.

Who calls it: api/ask_index.py (vectors of every survey question, once per publish) and api/assistant.py (one plan per
new question). The model never sees or writes a figure: it picks one of the candidate survey questions api/ask_index.py
retrieved, the answers to focus on, the kind of answer, the grain and the cut. Dates the analyst names ("October
2026", "last 8 weeks") are read by rules (api/ask_reader.py); the arithmetic is api/ask_figures.py's.

  embed()   vectors for texts: text-embedding-3-small at 256 numbers each (~$0.02 per million tokens). Every survey
            question's vector is kept in VECTORS (logs/ask-vectors.json) by the hash of its text, so a publish only
            embeds the questions that are new; one question asked costs a few millionths of a dollar.
  plan()    gpt-4o-mini (CIP_ASK_MODEL) with a strict JSON schema: ~1,500 tokens in, ~60 out, about $0.0003.

Cost guard: api/assistant.py asks the model only when the rules are unsure (~5% of questions); every reading is kept in
logs/ask-readings.json, so a question is never paid for twice; every call's price is added to logs/ask-spend.json for
the month, and past CIP_ASK_BUDGET_USD (default $0.50) the
model is not called until the next month and the rules answer alone. Key: OPENAPI_KEY (or OPENAI_API_KEY); without it,
or on any error or a reply over CALL_SECONDS, the caller falls back to the rules. Repeated questions never reach here
(api/assistant.py ANSWERS).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger("cip.ask")
LOGS = Path(__file__).resolve().parents[1] / "logs"
VECTORS = LOGS / "ask-vectors.json"
SPEND = LOGS / "ask-spend.json"
READINGS = LOGS / "ask-readings.json"   # every reading the model gave, by question and candidates: never paid for twice
EMBED_MODEL, EMBED_SIZE = "text-embedding-3-small", 256
PRICES = {"text-embedding-3-small": (0.02, 0.0), "gpt-4o-mini": (0.15, 0.60), "gpt-5-nano": (0.05, 0.40),
          "gpt-4.1-mini": (0.40, 1.60), "gpt-5-mini": (0.25, 2.00)}   # $ per million tokens in, out (OpenAI, 11 Nov 2026)
CALL_SECONDS = 6
LOCK = threading.Lock()
CUTS = ["none", "gender", "generation", "age_band", "income_band", "census_region", "urbanicity"]
# the reply in short names (output tokens cost 4x input): q candidate number or null, a answer labels named, k kind,
# g grain, c cut, p period
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["q", "r", "a", "k", "g", "c", "p"],
          "properties": {"q": {"type": ["integer", "null"]}, "r": {"type": ["integer", "null"]},
                         "a": {"type": "array", "items": {"type": "string"}},
                         "k": {"type": "string", "enum": ["share", "count", "top", "trend", "compare"]},
                         "g": {"type": "string", "enum": ["auto", "wave", "biweek", "4week", "month", "quarter", "year"]},
                         "c": {"type": "string", "enum": CUTS},
                         "p": {"type": "string", "enum": ["named", "latest", "all", "previous", "first_vs_latest"]}}}
# every word here is paid for on every new question (~200 tokens); each rule is one the measured misses needed
SYSTEM = ("You map an analyst's question about Coresight's US consumer surveys to ONE numbered candidate survey question "
          "(q; null if none answers it); r: a second candidate only if it is just as likely, else null. Prefer the weekly tracker and questions asked in many waves (w) and recently, "
          "unless a study, holiday or time is named; when candidates ask the same thing, the one with most waves. For how "
          "many or what share of people use, own, have or do X, pick the question asking whether people do X, not a "
          "follow-up asked only of those who do (how much, why, how often). A retailer or brand named (Amazon, Walmart) "
          "means its share among a retailer question's answers; an event question (Prime Day, Big Deal Days) only when "
          "the event is named. a: answer labels the user names, copied exactly, [] if none. k: count=how many people, "
          "top=which/most/best/rank, trend=over time, compare=versus, else share. c: a demographic named (Gen Z → "
          "generation, women → gender, by region → census_region), else none. p: named=dates or a span given, latest, "
          "previous=last week, first_vs_latest, else all. Never write numbers.")


FILLER = set("a an the of to in on for do does did is are was were have has had people how many much what which who "
              "share percentage percent please show me tell".split())


def same_question(question: str) -> str:
    """The words that make a question, sorted: "How many people have subscribed to Amazon Prime?" and "amazon prime,
    how many subscribed" share one saved reading."""
    return " ".join(sorted(set(re.findall(r"[a-z0-9]+", question.lower())) - FILLER))


KEY_NAMES = ("OPENAPI_KEY", "OPENAI_API_KEY", "OPEN_API_KEY", "OPENAI_KEY")   # the setting under any of its usual names


def key_name() -> str | None:
    """The environment variable the key is read from (never its value), or None: shown on the admin health report."""
    # any case: an Azure app setting typed "open_api_key" is the same key (11 Nov 2026: staging's was not found)
    return next((n for wanted in KEY_NAMES for n in os.environ if n.upper() == wanted and os.environ[n].strip()), None)


def key() -> str:
    name = key_name()
    return os.environ[name].strip() if name else ""


def status() -> dict:
    """For /api/v1/admin/health and the start-up log: is the model on, and why not."""
    now = spent()
    return {"on": ready(), "key_from": key_name(), "model": model(), "budget_usd": budget(), "spent_usd": round(now["usd"], 5),
            "calls": now["calls"], "why_off": None if ready() else ("no key: set OPENAPI_KEY" if not key_name() else "monthly cap reached")}


def model() -> str:
    return os.environ.get("CIP_ASK_MODEL", "gpt-4o-mini")


def budget() -> float:
    return float(os.environ.get("CIP_ASK_BUDGET_USD", "0.5"))


def spent() -> dict:
    """{"month": "2026-11", "usd": 0.0123, "calls": 41}: this month's model spend (logs/ask-spend.json)."""
    month = time.strftime("%Y-%m")
    try:
        found = json.loads(SPEND.read_text())
        return found if found.get("month") == month else {"month": month, "usd": 0.0, "calls": 0}
    except (OSError, ValueError):
        return {"month": month, "usd": 0.0, "calls": 0}


def charge(name: str, tokens_in: int, tokens_out: int) -> float:
    """Add one call's price to the month's spend; the price, in dollars."""
    price_in, price_out = PRICES.get(name, (1.0, 4.0))   # an unknown model is costed high: the cap stays a cap
    usd = tokens_in * price_in / 1e6 + tokens_out * price_out / 1e6
    with LOCK:
        now = spent()
        now.update(usd=round(now["usd"] + usd, 8), calls=now["calls"] + 1)
        try:
            LOGS.mkdir(exist_ok=True)
            SPEND.write_text(json.dumps(now))
        except OSError:
            log.warning("Ask model spend not saved")
    return usd


def ready() -> bool:
    """A key, and this month's spend under the cap."""
    return bool(key()) and spent()["usd"] < budget()


def call(path: str, body: dict, seconds: float = CALL_SECONDS) -> dict:
    request = urllib.request.Request(f"https://api.openai.com/v1/{path}", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=seconds) as reply:
        return json.load(reply)


def embed(texts: list[str]) -> np.ndarray | None:
    """Unit vectors (len(texts) × EMBED_SIZE), or None without a key, over the cap or on an error."""
    if not texts or not ready():
        return None
    try:
        out = []
        for start in range(0, len(texts), 500):   # the API takes up to 2,048 inputs; 500 keeps each request small
            reply = call("embeddings", {"model": EMBED_MODEL, "input": texts[start:start + 500], "dimensions": EMBED_SIZE})
            charge(EMBED_MODEL, reply["usage"]["prompt_tokens"], 0)
            out += [d["embedding"] for d in sorted(reply["data"], key=lambda d: d["index"])]
        vectors = np.array(out, np.float32)
        return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
    except Exception as exc:   # noqa: BLE001 — no vectors: the keyword search alone
        log.warning("Ask model: embeddings failed: %s", type(exc).__name__)
        return None


def question_vectors(texts: dict[str, str], prune: bool = False) -> dict[str, np.ndarray]:
    """key → vector for each text, reusing the saved vectors of texts already embedded (by text hash). prune: drop
    saved vectors of texts no longer asked for (only the full list of survey questions does, api/ask_index.py)."""
    digest = {k: hashlib.sha1(t.encode()).hexdigest()[:16] for k, t in texts.items()}
    try:
        saved = {h: np.array(v, np.float32) for h, v in json.loads(VECTORS.read_text()).items()}
    except (OSError, ValueError):
        saved = {}
    missing = [k for k in texts if digest[k] not in saved]
    if missing:
        made = embed([texts[k] for k in missing])
        if made is not None:
            saved.update({digest[k]: v for k, v in zip(missing, made)})
            try:
                LOGS.mkdir(exist_ok=True)
                kept = set(digest.values())
                VECTORS.write_text(json.dumps({h: [round(float(x), 5) for x in v] for h, v in saved.items() if not prune or h in kept}))
            except OSError:
                log.warning("Ask model: vectors not saved")
            log.info("Ask model: embedded %d new survey questions", len(missing))
    return {k: saved[digest[k]] for k in texts if digest[k] in saved}


def plan(question: str, candidates: list[dict]) -> dict | None:
    """The model's reading of a question over numbered candidates ({number, text, family, waves, first, last, answers}),
    checked: pick is a candidate or None, focus only that candidate's own answer labels. None when it cannot run."""
    if not candidates:
        return None
    memo = hashlib.sha1(json.dumps([same_question(question), [c["text"] for c in candidates]]).encode()).hexdigest()[:20]
    with LOCK:
        try:
            kept = json.loads(READINGS.read_text())
        except (OSError, ValueError):
            kept = {}
    if memo in kept:
        return {**kept[memo], "usd": 0.0, "seconds": 0.0}
    if not ready():
        return None
    # every word sent is paid for: ~40 tokens a candidate (waves, years, wording to 110 letters, 6 short answers)
    listing = "\n".join(f"{c['number']}. ({c['waves']}w {c['first'][2:4]}-{c['last'][2:4]}) {c.get('name') or ''}: {c['text'][:90]} | "
                        f"{'; '.join(a[:20] for a in c['answers'][:6])}" for c in candidates)   # the business name first
    try:
        started = time.perf_counter()
        reply = call("chat/completions", {
            "model": model(), "temperature": 0, "max_tokens": 80,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{question}\n{listing}"}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "plan", "strict": True, "schema": SCHEMA}}})
        usd = charge(model(), reply["usage"]["prompt_tokens"], reply["usage"]["completion_tokens"])
        log.info("Ask model: %d tokens in, %d out, $%.6f", reply["usage"]["prompt_tokens"], reply["usage"]["completion_tokens"], usd)
        found = json.loads(reply["choices"][0]["message"]["content"])
    except Exception as exc:   # noqa: BLE001 — network, timeout, refusal, bad JSON: the rules answer
        log.warning("Ask model: plan failed: %s", type(exc).__name__)
        return None
    found = {"pick": found.get("q"), "alt": found.get("r"), "focus": found.get("a", []), "kind": found.get("k", "share"), "grain": found.get("g", "auto"),
             "cut": found.get("c", "none"), "period": found.get("p", "all")}
    numbers = {c["number"]: c for c in candidates}
    picked = numbers.get(found["pick"])
    labels = {a.lower(): a for a in (picked["answers"] if picked else [])}
    found["pick"] = picked["number"] if picked else None
    found["alt"] = found["alt"] if found["alt"] in numbers else None
    found["focus"] = [labels[f.lower()] for f in found["focus"] if f.lower() in labels]
    found["seconds"], found["usd"] = round(time.perf_counter() - started, 2), usd
    with LOCK:
        try:
            kept = json.loads(READINGS.read_text())
        except (OSError, ValueError):
            kept = {}
        kept[memo] = {k: found[k] for k in ("pick", "alt", "focus", "kind", "grain", "cut", "period")}
        try:
            READINGS.write_text(json.dumps(dict(list(kept.items())[-20000:])))   # the newest 20,000 readings, ~3 MB
        except OSError:
            log.warning("Ask model: reading not saved")
    return found
