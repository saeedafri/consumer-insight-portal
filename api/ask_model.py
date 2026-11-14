"""Ask Coresight's model steps: find survey questions by meaning (a small model on our own CPU), and read what a
question asks for (OpenAI).

Who calls it: api/ask_index.py (vectors of every survey question and its analysts' asks, once per publish) and
api/assistant.py (one vector per new question; a plan when the page asks for the model's check). The model never sees or writes a figure: it picks one of the candidate survey questions api/ask_index.py
retrieved, the answers to focus on, the kind of answer, the grain and the cut. Dates the analyst names ("October
2026", "last 8 weeks") are read by rules (api/ask_reader.py); the arithmetic is api/ask_figures.py's.

  embed()   vectors for texts: BAAI's bge-small-en-v1.5 (int8 ONNX, 384 numbers, deploy/ask-model-download.py) run
            here, ~3 ms a question and no cost; it found the right survey question in the top 10 for 144 of 148
            golden questions, OpenAI's text-embedding-3-small for 135 at ~0.7 s a call (12 Nov 2026). Every survey
            question's vector is kept in VECTORS (logs/ask-vectors-<model>.npz) by the hash of its text, so a publish only
            embeds the questions that are new. Another model is a folder (CIP_ASK_EMBED_DIR) with its calibration.json:
            how it is read (pooling, prefixes) and its thresholds on its own scale (calibration; the v8 notebook exports one).
  read_pick() Ask's own reader (models/ask-reader, MiniLM L6 8-bit, 23 MB) picks one of the candidates, or "none of
            these", from the same lines the AI reads: ~70 ms on one thread, no cost. It learnt the picks of Qwen3-32B
            (scripts/colab/train_search_model_v6.ipynb); with no AI it took the golden set from 139 to 152 of 161.
  plan()    gpt-4o-mini (CIP_ASK_MODEL) with a strict JSON schema: ~1,500 tokens in, ~60 out, about $0.0003. Optional.

Cost guard: the search and the reader cost nothing (local). api/assistant.py asks the AI only when the reader is unsure
(its calibration.json "sure"), and the Ask page only after showing the quick answer (the check); every reading is kept in
logs/ask-readings.json, so a question is never paid for twice; every call's price is added to logs/ask-spend.json for
the month, and past CIP_ASK_BUDGET_USD (default $0.50) the
model is not called until the next month and the rules answer alone. Key: OPENAPI_KEY (or OPENAI_API_KEY); without it,
or on any error or a reply over CALL_SECONDS, the caller falls back to the rules. Repeated questions never reach here
(api/assistant.py ANSWERS).
"""
from __future__ import annotations

import functools
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
SPEND = LOGS / "ask-spend.json"
READINGS = LOGS / "ask-readings.json"   # every reading the model gave, by question and candidates: never paid for twice
EMBED_DIR = Path(os.environ.get("CIP_ASK_EMBED_DIR", Path(__file__).resolve().parents[1] / "models" / "bge-small-en-v1.5"))
# one cache per search model: vectors are kept by text, and a retrained model gives the same text another vector
# (a shared file would have mixed two models' vectors after a model change, 12 Nov 2026)
VECTORS = LOGS / f"ask-vectors-{EMBED_DIR.name}.npz"
EMBED_BATCH = 64   # texts run through the model at once, shortest first so little is padding
EMBED_TOKENS = 2048   # and at most ~this many tokens a batch: the model's working memory grows with batch × length², and
                      # ONNX Runtime keeps its peak; 64 long texts at once left ~400 MB behind (12 Nov 2026)
BULK = 200   # more new texts than this are encoded in a child process (embed_elsewhere): its memory goes when it exits
             # (a model change re-encodes ~18,000 texts: in the web process that took it from 500 MB to 1.1 GB, 12 Nov 2026)
PRICES = {"gpt-4o-mini": (0.15, 0.60), "gpt-5-nano": (0.05, 0.40),
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
          "(q; null if none answers it, or if the question names a specific thing, such as an activity, product or reason, that "
          "no candidate's wording or answers include; a topic alone, such as 'tariffs', means its main question); r: a second "
          "candidate only if it is just as likely, else null. Prefer the weekly tracker and questions asked in many waves (w) and recently, "
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


def read_calibration(folder: Path) -> dict:
    """A model's own thresholds (calibration.json beside it), {} when it has none. Each model scores on its own scale,
    so its thresholds are measured on the golden set when it is made (12 Nov 2026)."""
    try:
        return json.loads((folder / "calibration.json").read_text())
    except (OSError, ValueError):
        return {}


@functools.lru_cache(maxsize=1)
def calibration() -> dict:
    """The search model's own settings and thresholds (calibration.json beside it): how it reads (pooling: cls, mean or
    last; query_prefix, doc_prefix; dims kept; length; pad_token) and its scale (near_floor, gate, verified_near,
    ask_weight, standing, area_boost). bge-small has none: every default is its own, so swapping in another model is a
    folder with its calibration (scripts/colab/train_search_model_v8.ipynb writes one)."""
    return read_calibration(EMBED_DIR)


def padded(words, settings: dict, length: int):
    """A model's tokenizer, cut at its length and padded with its own pad token ([PAD], id 0, for BERT; not ModernBERT's)."""
    pad = settings.get("pad_token", "[PAD]")
    words.enable_truncation(int(settings.get("length", length)))
    words.enable_padding(pad_id=words.token_to_id(pad) or 0, pad_token=pad)
    return words


@functools.lru_cache(maxsize=1)
def encoder():
    """The local search model (tokenizer, ONNX session, settings), loaded on first use (~150 MB of memory), or None when
    its files are missing: Ask then searches by words alone."""
    try:
        import onnxruntime
        import tokenizers
        settings = calibration()
        words = padded(tokenizers.Tokenizer.from_file(str(EMBED_DIR / "tokenizer.json")), settings, 512)
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1   # one vCPU on Azure: never crowd the API
        return words, onnxruntime.InferenceSession(str(EMBED_DIR / "model_optimized.onnx"), options, providers=["CPUExecutionProvider"]), settings
    except Exception as exc:   # noqa: BLE001 — files missing or unreadable
        log.warning("Ask: no local search model in %s: %s", EMBED_DIR, type(exc).__name__)
        return None


def as_query(text: str) -> str:
    """A question (asked, an analyst's ask, a verified one) as the search model reads it: some models want a prefix on
    questions (calibration.json query_prefix; bge-small: none). api/assistant.py answer, api/ask_index.py."""
    return calibration().get("query_prefix", "") + text


def as_survey_question(text: str) -> str:
    """A survey question's text as the search model reads it (calibration.json doc_prefix; bge-small: none)."""
    return calibration().get("doc_prefix", "") + text


READER_DIR = Path(os.environ.get("CIP_ASK_READER_DIR", Path(__file__).resolve().parents[1] / "models" / "ask-reader"))


def describe_candidate(c: dict) -> str:
    """One candidate as the AI and Ask's own reader read it: waves, years, business name, wording to 90 letters, six
    answers to 32 (the reader learnt from exactly this line: change it and the reader must be retrained). api/assistant.py
    answer builds the candidates; read_pick and plan read them."""
    return (f"({c['waves']}w {c['first'][2:4]}-{c['last'][2:4]}) {c.get('name') or ''}: {c['text'][:90]} | "
            f"{'; '.join(a[:32] for a in c['answers'][:6])}")


@functools.lru_cache(maxsize=1)
def reader():
    """Ask's own reader (tokenizer, ONNX session, calibration): a small cross-encoder (MiniLM L6, 8-bit, 23 MB) that
    learnt Qwen3-32B's picks for 12,281 practice questions (scripts/colab/train_search_model_v6.ipynb), reading each
    candidate's line as the AI does. None when its files are absent: then the AI, else the nearest by meaning, picks."""
    try:
        import onnxruntime
        import tokenizers
        settings = read_calibration(READER_DIR)
        words = padded(tokenizers.Tokenizer.from_file(str(READER_DIR / "tokenizer.json")), settings, 192)   # as trained
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1   # one vCPU on Azure: never crowd the API
        session = onnxruntime.InferenceSession(str(READER_DIR / "model_optimized.onnx"), options, providers=["CPUExecutionProvider"])
        return words, session, settings
    except Exception:   # noqa: BLE001 — no reader: the AI, else meaning, picks
        return None


def read_pick(question: str, candidates: list[dict]) -> tuple[int | None, float] | None:
    """The reader's choice over numbered candidates: (its number, or None for "none of these"; its lead over the next
    choice in logits, "none of these" scoring 0 as trained), or None without the reader. ~70 ms for 12 on one thread."""
    model = reader()
    if model is None or not candidates:
        return None
    words, session, _ = model
    coded = words.encode_batch([(question, describe_candidate(c)) for c in candidates])
    feed = {"input_ids": np.array([c.ids for c in coded], np.int64), "attention_mask": np.array([c.attention_mask for c in coded], np.int64),
            "token_type_ids": np.array([c.type_ids for c in coded], np.int64)}
    inputs = {i.name for i in session.get_inputs()}   # ModernBERT-based readers take no token_type_ids
    try:
        choices = np.concatenate([[0.0], session.run(None, {k: v for k, v in feed.items() if k in inputs})[0].reshape(-1)])
    except Exception as exc:   # noqa: BLE001 — a reader that cannot run (another model's inputs): the AI, else meaning, picks
        log.warning("Ask reader failed: %s", type(exc).__name__)
        return None
    best, second = np.argsort(-choices)[:2]
    return (candidates[best - 1]["number"] if best else None), float(choices[best] - choices[second])


def embed(texts: list[str]) -> np.ndarray | None:
    """Unit vectors (len(texts) × the model's size, or its calibration "dims") from the local model, or None without it,
    pooled as the model was trained to be read (calibration "pooling": cls, bge's first token, the default; mean; or last,
    the last real token, as Qwen3's embedders are read)."""
    model = encoder()
    if not texts or model is None:
        return None
    words, session, settings = model
    inputs = {i.name for i in session.get_inputs()}
    pooling = settings.get("pooling", "cls")
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    out = None
    start = 0
    while start < len(order):
        longest = len(texts[order[min(start + EMBED_BATCH, len(order)) - 1]]) // 4 + 2   # ~4 characters a token
        batch = order[start:start + max(1, min(EMBED_BATCH, EMBED_TOKENS // longest))]
        start += len(batch)
        coded = words.encode_batch([texts[i] for i in batch])
        ids = np.array([c.ids for c in coded], np.int64)
        mask = np.array([c.attention_mask for c in coded], np.int64)
        hidden = session.run(None, {k: v for k, v in {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}.items()
                                    if k in inputs})[0]
        pooled = (hidden if hidden.ndim == 2 else hidden[:, 0] if pooling == "cls"
                  else hidden[np.arange(len(batch)), mask.sum(1) - 1] if pooling == "last"
                  else (hidden * mask[..., None]).sum(1) / np.maximum(mask.sum(1, keepdims=True), 1))
        if out is None:   # Matryoshka models keep their first "dims" numbers nearly as good, in less memory
            out = np.zeros((len(texts), int(settings.get("dims") or pooled.shape[1])), np.float32)
        out[batch] = pooled[:, :out.shape[1]]
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def read_vectors() -> dict[str, np.ndarray]:
    """The saved vectors by text hash ({} when there are none yet)."""
    try:
        with np.load(VECTORS) as kept:
            return dict(zip(kept["hashes"], kept["vectors"].astype(np.float32)))
    except (OSError, ValueError, KeyError):
        return {}


def embed_elsewhere(texts: list[str]) -> np.ndarray | None:
    """embed() in a child process at low priority (python -m api.ask_model): a few thousand texts cost this process
    nothing but the result (~1.5 KB a text), and the web answers by keywords meanwhile."""
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        given, made = Path(folder) / "texts.json", Path(folder) / "vectors.npy"
        given.write_text(json.dumps(texts))
        done = subprocess.run(["nice", "-n", "10", sys.executable, "-m", "api.ask_model", str(given), str(made)],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        if done.returncode or not made.exists():
            log.warning("Ask model: encoding in a child process failed: %s", (done.stderr or "")[-300:])
            return None
        return np.load(made)


def question_vectors(texts: dict[str, str], prune: bool = False) -> dict[str, np.ndarray]:
    """key → vector for each text, reusing the saved vectors of texts already embedded (by text hash). prune: drop
    saved vectors of texts no longer asked for (only the full list of survey questions does, api/ask_index.py)."""
    digest = {k: hashlib.sha1(t.encode()).hexdigest()[:16] for k, t in texts.items()}
    with LOCK:
        saved = read_vectors()
    missing = [k for k in texts if digest[k] not in saved]
    # encoded outside the lock: an AI check waiting on it waited 7 minutes behind a full re-encode (12 Nov 2026)
    made = (embed_elsewhere if len(missing) > BULK else embed)([texts[k] for k in missing]) if missing else None
    with LOCK:
        if made is not None:
            saved = {**read_vectors(), **{digest[k]: v for k, v in zip(missing, made)}}   # another process may have added some
            kept = set(digest.values())
            saved = {h: v for h, v in saved.items() if not prune or h in kept}
            try:
                LOGS.mkdir(exist_ok=True)
                # written aside, then renamed in one step: the publish's Ask check (etl/ask_quality.py) and the API share it
                part = VECTORS.with_suffix(f".{os.getpid()}.part")
                with part.open("wb") as f:
                    np.savez(f, hashes=np.array(list(saved)), vectors=np.array(list(saved.values()), np.float16))   # half size, same ranking
                os.replace(part, VECTORS)
            except OSError:
                log.warning("Ask model: vectors not saved")
            log.info("Ask model: embedded %d new texts", len(missing))
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
    # every word sent is paid for: ~40 tokens a candidate (waves, years, wording to 90 letters, 6 answers to 32: 20 cut
    # "I have started but not finished" to "I have started but n", 13 Nov 2026)
    listing = "\n".join(f"{c['number']}. {describe_candidate(c)}" for c in candidates)
    try:
        started = time.perf_counter()
        reply = call("chat/completions", {
            "model": model(), "temperature": 0, "max_tokens": 160,   # 80 cut off a reply naming several answers (JSONDecodeError, 11 Nov)
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


if __name__ == "__main__":   # embed_elsewhere's child: texts (JSON list) in, vectors (.npy) out
    import sys
    np.save(sys.argv[2], embed(json.loads(Path(sys.argv[1]).read_text())))
