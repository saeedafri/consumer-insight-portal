# Ask CIP today: the facts a rebuilder needs (27 Nov 2026)

Who this is for: the engineer agent who will rebuild Ask CIP's answers and retrain its model. Everything below was read
from the code at commit `cb46c7e` (cip-test, branch master, clean tree) or measured on this Mac on 27 Nov 2026 with no AI
provider reachable (no OpenAI key, `CIP_ASK_PROVIDER=none`), Ask's caches copied to a scratch folder, and no row written
to staging's access log. Numbers that differ from the ones in circulation are marked **(differs)**.

Read first: `CLAUDE.md` (rules, section 7 here) and `status/README.md` (the rows naming Ask, lines 26-27, 42, 58-65,
100, 115-117, 153-155).

---

## 1. One question, end to end

### 1.1 The page: `frontend/src/screens/Ask.tsx` (417 lines)

- `ask()` (Ask.tsx:314) POSTs `/api/v1/ask` with `{question, quick: true}` (Ask.tsx:332), plus `key` when a suggestion or
  follow-up button was pressed, `weighted` when the Weighted switch is on, and `previous` / `previous_key` (the last
  answered question and its source key, Ask.tsx:328-330) so a typed follow-up ("What about Gen Z?") is read with it.
- If the quick answer says `check: true`, the page asks again with `{check: true}` (Ask.tsx:341-350) and swaps the reply
  only when the second answer's `understood` is `"model"` (the AI). With no AI key `check` is never true.
- While typing (250 ms pause) it calls `GET /api/v1/ask/suggest` (Ask.tsx:360-367): spelling fix + up to 6 survey
  questions by analyst name. No model.
- **Chart only when asked** (Ask.tsx:26 `ASKS_CHART = /\b(chart|graph|plot|visuali[sz]e|draw)\b/i`, Ask.tsx:189
  `useState(ASKS_CHART.test(question))`, Show/Hide chart button Ask.tsx:266-267). The API still returns `chart` every
  time; only the page hides it.
- Client view / Analyst view (Ask.tsx:396-399, kept in localStorage `cip_ask_view`); "Not what you meant?" chips when
  `unsure` (Ask.tsx:205, 260-262); Copy for an email / a slide built from the answer's own sentences, no AI
  (Ask.tsx:138-151); admins can "Save as verified" (POST `/api/v1/admin/ask/verified`, Ask.tsx:199-202).
- `EXAMPLES` (Ask.tsx:21-24) are the 8 example questions shown on an empty page.

### 1.2 The route: `api/main.py`

| Route | Lines | What it does |
|---|---|---|
| `POST /api/v1/ask` | main.py:829-843 | reads the body, calls `ask_answer`, writes one `cip_access_log` row (`action='ask'`, target = question[:300], detail = mode, source links, `asked_as`) via `audit.record` |
| `ask_answer()` | main.py:759-778 | feature check (`ask`), per-minute limit (`config/access.yml:167-169`: ask 10, ask_check 10, ask_suggest 240), at most `ASK_SLOTS` questions computed at once (main.py:108, default **2**, `CIP_ASK_SLOTS`), wait `ASK_WAIT` 8 s then 503 "busy"; then `assistant.ask` in a thread |
| `read_ask_index()` / `warm_ask()` | main.py:735-750 | builds `assistant.index_for` from the pinned publication; run at start and by the minute loop after a publish (main.py:237-252, 304) |
| `GET /api/v1/ask/suggest` | main.py:781-790 | `assistant.suggest` |
| `GET /api/v1/ask/history` | main.py:796-813 | the caller's own last 30 questions from `cip_access_log` |
| `POST /api/v1/admin/ask/verified` | main.py:816-826 | `assistant.save_verified` → `logs/ask-verified.json` |
| `GET /api/v1/admin/ask/quality` | main.py:1101-1105 | `logs/ask-quality.json` (per-publish self-test) |

The MCP connector's `ask` tool calls the same `ask_answer` (api/mcp.py:106-109). MCP calls are **not** written to the
access log (status/README.md:102).

### 1.3 The engine: `api/assistant.py` (2,018 lines)

`ask()` (assistant.py:1983-2018): reads a follow-up with the last question (`follow_on`, assistant.py:193-224), looks the
answer up in the in-memory cache `ANSWERS` (key: index object, access scope, quick, key, weighted, lower-cased question;
`KEEP_ANSWERS = 500`, LRU), else calls `answer()`, adds `corrected` / `asked_as`, and when the AI settled it saves the
reading (`learn`, assistant.py:764 → `logs/ask-learned.json`, max 5,000).

`answer()` (assistant.py:1436-1962), in order:

1. Spelling put right (`index.correct_spelling`, toward survey words and long-running retailer/brand answers).
2. **Combined questions** go to the plan path first: `ask_plan.answer` (assistant.py:1448 → api/ask_plan.py:371). It
   fires only when `COMBINED` matches (ask_plan.py:330: among, of people who, vs, more likely, both/and, either, not,
   funnel, significance, age ranges like 18-34) and `needs_plan` says the single-question path cannot do it
   (ask_plan.py:358). The plan is run on each week's respondents by `api/ask_engine.py run` (ask_engine.py:128) from each
   wave's `people.json.gz` bitsets. US weekly tracker weeks only. `understood: "plan"`, with `read_as` chips.
3. "Among X, Y" (`among_condition`, assistant.py:1195), significance words stripped (tested later), weighting words
   (assistant.py:1478-1485).
4. Refusals by rule: a bare follow-up (1487), "who also bought" overlap (1490), "did X cause Y" answered only as what
   people reported (1495-1506), more than two kinds of group (1514), "average price" (1516), an unknown 3-6 letter
   acronym (1521-1526).
5. Topic verdict from `config/dashboards.yml` ask words (1507, `topic_verdict` 987), "summarize this week" overview from
   `config/weekly_report.yml ask_overview` (1510, `overview` 1058), two kinds of group at once from the cross-tab files,
   4 waves pooled (1512, `two_groups` 1327).
6. One country per question (1531; US unless China is named, `config/countries.yml ask_words`).
7. Keyword hits (`index.find`, twice: subject and whole question, 1532-1540).
8. Stored name (`index.named`, 1544): a question using a survey question's analyst name or alias is answered from it,
   `understood: "named"`, no model.
9. Embed subject and whole question (bge-small, ~3 ms, 1572); verified / learned match by vector (`verified_for`,
   `VERIFIED_NEAR` 0.91) with the same named answers and groups (1574-1587).
10. Candidates: `index.retrieve` (1588) = nearest by meaning (`CANDIDATES` 10) + up to 4 found only by words; refused
    as "none of the surveys asks this" when the best closeness is under `NEAR_FLOOR` and not every word matched (1594).
11. Candidate shaping (1603-1631): only questions asked within `CURRENT_DAYS` = 365 days for "latest/last N"; + the 3
    longest-running questions (≥15 waves) that list an answer the question names (e.g. "Amazon" in the retailer lists);
    event questions dropped unless an event is named; one per wording (longest-running); answer-naming lists first.
12. **The reader** (`ask_model.read_pick`, 1634): a MiniLM cross-encoder scores each candidate line; its pick is
    "sure" when its lead over the next choice is ≥ `READER_SURE` (2.0 logits, from `models/ask-reader/calibration.json`).
13. **The AI** (`ask_model.plan`, 1638-1645) only when not quick, the reader unsure, nothing verified and a key set. A
    reader pick using every subject word beats an AI "none" or an AI pick missing a word.
14. Rule overrides on the pick (1665-1720): the longest-running list naming the asked retailer/brand wins unless the pick
    asks more; an unsure pick last asked over a year ago gives way to the nearest still-asked question; a ≤2-wave pick
    gives way to a longer question with the same answers; a trend needs ≥3 waves; an unsure pick missing a rare subject
    word (idf ≥ `RARE_WORD` 3.3) gives way to a candidate that uses every one.
15. `GATE` (0.04) "choose" (1729) and the "not asked" refusal when the pick misses the subject (`unasked`, 1738).
16. Figures (1787-1801): `ask_figures.compute` on the pick, falling back to near-equal matches when the period or group
    named is missing; "last month" not asked → latest figures with a note (1804-1810); a re-read of periods without the
    survey's own time words (1826-1839); among-group figures (1840); nets from `config/ask_nets.yml` and dashboard tiles,
    "any", scale sides (1842-1848); weighting (1863-1870).
17. Words (`write` 415, `brief` 545, `in_words` 270, `week_by_week` 530, `ask_figures.middle` for median/average of
    dollar bands, `elsewhere` 316 for the same answer in other studies), chart (`chart` 372-412), table (`figure_table`
    1965), follow-ups (`follow_ups` 703-724).

Chart choice (assistant.py:372-412): over time → `line` (one line per group for a cut; a yes/no draws its main answer
only); exactly two periods with no grain → `dumbbell`; one period by a cut → `stacked` (single choice, ≤ `SPLIT_MAX` 6
answers), `heatmap` (≥ `HEATMAP_MIN` 4 groups and 4 answers) or `grouped`; one period, single choice ≤6 answers →
`split`; else ranked `bar` (≤12).

**The sentences are templates.** No model writes a word. `write()` produces the source line and figure sentences,
`brief()` the tiles and the one-sentence `takeaway`, `in_words()` the plain-English lead ("About four in five US adults
surveyed (79.2%) bought …"), assembled into `headline` at assistant.py:1915-1947.

### 1.4 The other modules

| File | Lines | Job |
|---|---|---|
| `api/ask_reader.py` | 265 | Rules only (~1 ms): `read()` (216-265) gives `{question, country, kind: share/count/top/trend/change, when: [period specs], grain, cuts, top, merge, compare, about}`. Periods (`periods`, 91), grains (`GRAINS` 26), cut words (`CUT_VALUES` 33, `CUT_DIMS` 54, income groups by dollar range `INCOME_GROUPS` 48), kinds (`KINDS` 58), the subject `about` after `FILLER` (64) is removed. `by_cut()` (76) rewrites named groups as "by generation" for the reader. |
| `api/ask_index.py` | 690 | `Index` (211): every published question file → entries; `find` (462, idf × field weight: name 3.5, wording 3, topic 2.5, answers 2, older wording 1.5, `FIELDS` 63); `retrieve` (507: vectors + nearest analyst ask at `ASK_WEIGHT` 0.3 + `STANDING` ≤0.06 for long-running/recent + `AREA_BOOST` 0.03); `named` (541); `load_verified` (572); `counts` (627, one question's cells over every code it was asked under, 48 MB byte-capped cache `COUNT_CACHE_MB`). |
| `api/ask_model.py` | 464 | `embed` (304, bge-small int8 ONNX, one thread), vector cache `logs/ask-vectors-<model>.npz` (16-bit), child-process encoding above 200 new texts (`BULK`); `read_pick` (284) the reader; `describe_candidate` (258) the exact line the reader and the AI read (change it and the reader must be retrained); `plan` (393) the optional AI with a strict JSON schema (`SCHEMA` 74, prompt `SYSTEM` 82). |
| `api/ask_plan.py` | 463 | Part-by-part candidate search (`candidates` 50, `PER_PART` 10), rule plan filler (`fill` 242), `answer` (371). |
| `api/ask_engine.py` | 184 | Runs a plan over each wave's respondents (bit masks): share, top, counts, chain, among, by groups, both/either/not, test, weighted. |
| `api/ask_figures.py` | 261 | Exact pooled figures (`compute` 164): people ÷ base from published counts; grains wave, biweek, 4week, month, quarter, year (`AUTO_WAVES` 26, `AUTO_MONTHS` 36); `moved` (250) change and z-test; `middle` (229) band median/average. |

### 1.5 Thresholds and caches (all in code unless a calibration.json overrides)

| Name | Value | Where | Meaning |
|---|---|---|---|
| `READER_SURE` | 2.0 | assistant.py:48, models/ask-reader/calibration.json | reader lead (logits) from which its pick is final |
| `NEAR_FLOOR` | 0.64 | assistant.py:60 (bge-small has no calibration.json) | below this closeness and not every word found: "no survey asks this" |
| `GATE` | 0.04 | assistant.py:67 | margin to the next different question for a meaning-only answer, else "choose" |
| `VERIFIED_NEAR` | 0.91 | ask_index.py:55 | closeness to a verified/learned question to reuse its plan |
| `RARE_WORD` | 3.3 idf | assistant.py:71 | a subject word an unsure pick must not miss |
| `CURRENT_DAYS` | 365 | assistant.py:53 | "latest / last N / this week" only from questions asked within a year of the newest wave; older answers say "Last asked …" (1946) |
| `CANDIDATES` / `WORD_CANDIDATES` | 10 / 4 | assistant.py:54, ask_index.py:45 | candidates by meaning / extra by words (+3 long-running answer lists) |
| `TREND_FROM` | 3 | assistant.py:55 | with no time named, a question asked in ≥3 waves is answered as a trend |
| `JUNK_BELOW`, `MIN_MATCH`, `OWN_WORDING`, `NEAR_EQUAL` | 0.35, 0.45, 0.8, 0.8 | assistant.py:56-81 | keyword-match cut-offs |
| `SMALL_BASE` | 50 | assistant.py:83 | small-base note; groups under it never "highest" |
| `ANSWERS` / `KEEP_ANSWERS` | 500 answers | assistant.py:51, 93 | per process, cleared at each new publication |
| `ASK_SLOTS` / `ASK_WAIT` | 2 / 8 s | main.py:108-109 | concurrent Ask computations per worker |
| AI budget | $0.50 / month default (`CIP_ASK_BUDGET_USD`; staging set to 10, status/README.md:153) | ask_model.py:148 | `logs/ask-spend.json`; this Mac's November file shows $0.58 over 4,245 calls |
| AI timeout / pause | 6 s / 900 s after 401/429 | ask_model.py:64-67 | |
| AI readings cache | newest 20,000 | ask_model.py:434 (`logs/ask-readings.json`, 944 entries on this Mac) | never paid twice |

**Fact worth knowing:** with the reader installed, the `GATE` "choose" branch is effectively dead. `understood` becomes
`"reader"` whenever the reader returns any pick (assistant.py:1646-1657), and "choose" needs `understood == "meaning"`
(1729). In 393 measured answers on :8013 none came back as `choose`. Uncertainty is shown only through `unsure: true` and
the "Not what you meant?" chips.

The AI providers (all optional, none on by default): OpenAI `gpt-4o-mini` with `OPENAPI_KEY` (ask_model.py:96, 144);
NVIDIA `nemotron-3.5-lightning` only with `CIP_ASK_PROVIDER=nvidia` (measured worse than no AI, status/README.md:68);
Google `gemini-3.5-flash-lite` only with `CIP_ASK_PROVIDER=gemini` (waiting for deploy, off until set; real set 202/232
with it, status/README.md:58). This Mac's `.env` holds `GEMINI_API_KEY` and `NVIDIA-API` but no `CIP_ASK_PROVIDER`, so no
AI runs here unless someone sets it. The per-publish naming step (`etl/ask_semantic.py`, called from
`etl/ask_quality.py after_publish`) does call OpenAI (~$0.03 per 1,000 new wordings) when a key is set.

### 1.6 What the answer JSON holds

From `answer()`'s return (assistant.py:1949-1962) and `ask()`:

| Field | Meaning |
|---|---|
| `mode` | `figures`, `none` (with `no_source: true`), or `choose` |
| `answer` | every sentence joined (`write`) |
| `headline` | the one-sentence lead shown first |
| `takeaway` | what the figures tell (from `brief`) |
| `tiles` | up to 3 `{label, value, note}` |
| `points`, `notes` | the other figure sentences; qualifying notes (small base, gaps, codes joined, weighting) |
| `scope` | `{country, period, waves, base}` |
| `sources` | `[{id, key, qcode, question, name, family, survey_id, wave_date, waves, link}]` |
| `source_line` | "From “wording” (family, code, asked in N waves, first – last)." |
| `chart` | `{type, categories, series:[{name, data}], unit, bases?}` |
| `table` | `{head, rows, bases, cell_bases}` |
| `understood` | `verified`, `named`, `learned`, `name`, `reader`, `model`, `meaning`, `rules`, `topic`, `plan` |
| `unsure`, `check`, `margin` | Ask's doubt; whether the page should ask for the AI check; meaning margin |
| `suggestions` | other matching questions `{qcode, text, family, key, alt}` |
| `next` | up to 3 follow-ups `{question, key}` |
| `overview` | the same answer in other studies, or the weekly overview lines |
| `verify` | the plan an admin can save as verified |
| `plan`, `codes`, `weighting`, `series` | the rules' reading, codes joined, `weighted`/`unweighted`, takeaway series |
| `corrected`, `asked_as`, `read_as` | spelling fix; follow-up as read; plan-path chips |

Median reply size measured: 4.8 KB of JSON.

---

## 2. The data

### 2.1 What is published

Ask reads only the ETL's published files: `api/v1/questions/<family>/<study type>/<code>.json.gz` (one question across
every wave and cut: waves, wordings, answers, cuts and the cell arrays w, c, a, n people, b base), `api/v1/waves.json.gz`,
and for the plan path and weighting each wave's `waves/<id>/people.json.gz` (respondent bitsets and Census weights).

Two publications are on this Mac:

| | `data/published/current` (default of every scorer) | `data/published/preview/current` |
|---|---|---|
| Built | 10 Nov 2026 (version 20261110T203738) | 27 Nov 2026 (20261127T085815) from staging's database |
| Waves | 374, US only (271 tracker, 24 annual, 79 ad hoc), 18 Jan 2018 – 9 Nov 2026 | 558: US 377 (273 tracker, 24 annual, 80 ad hoc) + China 181 tracker |
| Question files | – | 2,720 (603 in CSI-US tracker, 14 in CSI-CN tracker) |
| Ask index entries | 3,150 (US) | 3,157 (US 3,143, China 14) |
| Entries joined across 2+ codes | 261 (max 30 codes) | 359 (max 30) |
| Entries asked in 1 wave / ≥3 / ≥15 / ≥52 waves | 2,717 / 283 / 92 / 17 | 2,647 / 333 / 121 / 35 |

**Warning: this Mac's disk is case-insensitive.** Staging (Linux) has both `q1…q6.json.gz` and `Q1…Q6.json.gz` in
`CSI-US/tracker`; here each pair collapses into one file. `current` kept the lower-case files (q1-q6, 196 waves from Aug
2022), `preview` kept the upper-case ones (Q1-Q6 joined back to 28 Dec 2020, 268 waves). So the weekly core questions
(activities, in-store and online categories, food and nonfood retailers) differ between the two copies and from staging.
status/README.md:78 already warns that local publications built on a Mac are wrong for these questions; a faithful local
test needs a case-sensitive volume or staging's own files.

### 2.2 Surveys, waves and cadence (preview, 27 Nov)

- 102 survey families. Two weekly trackers: **US** `CSI-US` 273 waves, 28 Dec 2020 – 23 Nov 2026, median 414 qualified
  respondents a week; **China** `CSI-CN` 181 waves, 6 Feb 2023 – 9 Nov 2026, median 562. The other 100 are annual or
  ad hoc studies (97 asked once; Online Grocery 3 times, Holiday Shopping and Spending 2, Back to School 2), 2018-2026,
  most of 400-2,100 people, some client studies of 35-300.
- Inside the US weekly tracker, rotating modules (from `waves.json.gz modules`, median gap between waves):
  **weekly** Holiday tracker (22 waves), MidEast gas price shock (17 + 2); **monthly** Tariffs + inflation (19),
  GenAI (18), GLP-1 (15), Financial health (15), Returns (2); **quarterly** 13 sector modules (Apparel, Beauty,
  Department stores, Drugstore, eCommerce, Footwear, Home furnishings, Home improvement, Luxury, Mass merchants,
  Off-price/dollar, Social commerce; 6-7 waves each since Jul 2025) plus Holiday, Shrink, Labor Day, Easter; **annual**
  event retros (Single's Day, Halloween, Big Deal Days, Holiday shopping); about 50 one-off modules (events, client topics).

### 2.3 Questions per country and type

From every published wave book (`waves/<id>/book.json.gz`, preview):

| Country | Wave-question rows | Distinct (family, code, wording) | single | multi | grid_single |
|---|---|---|---|---|---|
| US | 10,594 | 4,742 | 5,850 rows (2,724 distinct) | 4,485 (1,901) | 259 (117) |
| China | 2,534 | 14 | 1,810 (10) | 724 (4) | 0 |

No `numeric`, `text` (open-ended), `grid_multi` or `datetime` question reaches the books although the database schema
has them (sql/001_schema.sql:93). Open-ended answers appear only as coded themes (etl/publish.py:117, `open_ends`).
Typed dollar/percent questions were loaded without their numbers (28 "$" and 13 "%" of 83 single-answer questions,
status/README.md:112); Ask skips any question whose only answer is a unit (`UNIT_ONLY`, ask_index.py:61).

### 2.4 Cuts per country (`config/countries.yml`)

- US: gender (2), generation (GenZ, Millennial, GenX, Boomer), age_band (18-29, 30-44, 45-60, Over 60), income_band (7
  bands, merged by Ask into Low < $50k / Middle $50-99k / High $100k+, ask_reader.py:48), census_region (4),
  urbanicity (3).
- China: gender, age_band (18-25, 26-41, 42-57, 57-76, 77+), income_band (6 RMB bands), urbanicity (Tier 1, Tier 2,
  Other city). No generation or region.
- Ages the survey does not cut by (18-34, 55+) and groups defined by answers go through the plan path (people.json).

### 2.5 How one question's history joins across codes

The tracker renumbers questions often. Two joins make "all waves" mean all of them:

1. In the ETL, `shared/data/payloads.py question` (rule `same_question_codes`) writes into each file the waves of other
   codes with the same exact wording when ≥60% of answers match; those waves are listed as `borrowed`, and Ask reads only
   a file's own waves (ask_index.py:236-242).
2. In Ask's index (ask_index.py:271-307): parts with the same family, study type and the same set of words (minus
   "select all that apply…") become one entry; a wave counts only if ≥60% (`SAME_ANSWERS`) of its answers are the
   entry's own (old reused codes are dropped wave by wave). A code reused for a different question is split by wording
   (`wording_groups`, ask_index.py:191: ≥50% shared 4+-letter words and never across two holidays) into `code#1`,
   `code#2`. Example: the weekly nonfood retailer list is one entry `CSI-US/tracker/Q5#1` with codes Q12_2, Q10_2, Q6_2,
   Q7, Q5, q0007: 268 waves, 28 Dec 2020 – 23 Nov 2026. `index.counts(key)` (ask_index.py:627) then stitches the cells of
   every part into one series, answers and cuts matched by label.

### 2.6 The config Ask reads

| File | Size | What |
|---|---|---|
| `config/ask_semantic.json` | 2,002 entries (1.6 MB), keyed by a hash of the wording | per wording: `name`, `aliases` (6,027 in all), `asks` (16,050 analyst-style questions), `topic` (18 areas), `text`. Written by gpt-4o-mini via `etl/ask_semantic.py`; a publish adds `logs/ask-semantic.json` on top. In the preview index 3,038 of 3,157 entries have a name; 24,350 asks (with repeats across codes) are embedded as a second index |
| `config/ask_verified.yml` | 39 entries (`question`, `code`, `kind`, `period`, 8 with `key`, 2 with `focus`) | approved question → plan; plus admins' `logs/ask-verified.json` and the AI's `logs/ask-learned.json` (109 entries here, untagged by model, so ignored) — 37 resolve on preview |
| `config/search_synonyms.yml` | 26 groups (holiday, AI, GLP-1, dining out, worried, finances, sentiment, …) | a synonym counts as the word at 0.8 in `find` |
| `config/ask_nets.yml` | BD5 and EC6 | "Use / Have / Access to Amazon Prime" = own + household (codes 1, 2) |
| `config/dashboards.yml` | tiles and `ask` words | dashboard nets ("Started" = Still + Finished shopping) and topic verdicts |
| `config/weekly_report.yml` | `ask_overview`, `net_words` | summary questions; better/worse scale words |
| `config/countries.yml` | US, CN | cuts and `ask_words` |

---

## 3. The models

### 3.1 Files under `models/`

| Folder | Files | In the image? | Used? |
|---|---|---|---|
| `bge-small-en-v1.5` | model_optimized.onnx 66.5 MB (int8, Qdrant export, pinned revision), tokenizer 0.7 MB, no calibration.json | yes: downloaded at build by `deploy/ask-model-download.py` (Dockerfile:28-29) | **yes**, the search model (`CIP_ASK_EMBED_DIR` to swap) |
| `ask-reader` | model_optimized.onnx 23.0 MB (MiniLM L6, 8-bit), tokenizer 0.7 MB, calibration.json (`sure` 2.0, length 192) | yes: tracked in git, `COPY models/ask-reader/` (Dockerfile:43-44) | **yes**, the reader (`CIP_ASK_READER_DIR` to swap) |
| `bge-cip-v1`, `-v2a`, `-v2b`, `-v3a`, `-v3b` | 33.9 MB each + calibration (near_floor 0.50, gate 0) | no (git-ignored) | no: trained 12-13 Nov, not adopted |

Logs hold stale vector caches for bge-cip-v1…v3b and v5-int8 (14.6 MB each), unused.

Both models load lazily on the first question (`encoder`, `reader` are `lru_cache`d), one ONNX thread each.

### 3.2 Memory and speed, measured 27 Nov on this Mac (Apple M4, Python 3.13, onnxruntime 1.31.1)

A copy of the API on `127.0.0.1:8013` (preview data, staging's database read-only, no AI, audit off, signed in by a
dependency override), then stopped. One process, `ASK_SLOTS` 2:

| Moment | RSS |
|---|---|
| Started, index built in the background (3,157 entries, 5.3 s) | 161-184 MB |
| After the first question (encoder + reader loaded; 471 ms) | 421 MB |
| After 393 different questions (real + golden sets), one at a time | 524 MB |
| After 393 more, 4 clients at once | **626 MB** |

| Latency (server + local HTTP) | median | p90 | p95 | max |
|---|---|---|---|---|
| New question, one at a time (393) | 89 ms | 203 ms | 290 ms | 658 ms |
| Same question again (answer cache) | 1 ms | 1 ms | 1 ms | 54 ms |
| New wordings, 4 clients at once | 249 ms | 449 ms | 517 ms | 994 ms (14.4 questions/s) |

The scorers' own processes peak at 400-505 MB (index, vectors, both models, count cache). Per question in the scorer:
golden median 82-91 ms, slowest 0.44-0.78 s.

Earlier staging and load figures (not re-measured): staging served 20 questions in 11-80 ms server time (10 Nov);
memory with Ask loaded 463 MB (platform review 20 Nov); 100 simultaneous users locally 819 → 612 MB after ASK_SLOTS 6 →
2, Ask queues at ~12 questions/s on one core (status/README.md:79); first start embeds ~18-21k texts (~2 min) then
reads `logs/ask-vectors-*.npz` (status/README.md:160, 168); Azure peak 771 MB on 5 Nov (memory note).

### 3.3 The Colab history (what each round trained, its result, adopted or not)

Notebooks are in `scripts/colab/`. Their uploaded data and downloaded results lived in `~/Downloads/cip-colab` and
`~/Downloads/Collab/...` and on Google Drive: **neither Downloads folder exists on this Mac any more** (searched 27 Nov);
only `scripts/colab/runs/2026-11-21` and `-22` (replay reports, a candidate reader, `cip-colab-inputs.zip`) remain in the
repo, git-ignored. Fetch anything else from Drive.

| Round | Date | What it trained | Result | Adopted |
|---|---|---|---|---|
| v1 | 12 Nov | bge-small fine-tuned on catalogue asks, InfoNCE, 3 epochs (`train_search_model_v1.ipynb`) | search alone better (unseen 39.0 → 50.8% first) but inside Ask golden 138 → 134; with gate 89.2% right vs 97.6% | no |
| v2a / v2b | 12 Nov | + near-twin batches, long-running weighted, + look-alikes | golden 133 / 128 inside Ask | no |
| v3a / v3b | 13 Nov | + 36,570 Qwen2.5-7B synthetic queries, hard negatives, MarginMSE from bge-reranker-v2-m3 | golden 134 vs 136; with gate 88.2% vs 97.6% | no |
| v4 | 13 Nov | (docs/research/ask-cip-model-training.md Part 18) | tested in Ask, not used | no |
| v5 | 13-14 Nov | labels checked by gpt-4.1/4.1-mini ($9.19), 19,085 bad practice questions removed | no AI: final exam 86.3 → 87.0%, big exam 83.1 → 84.3%, +56-166 MB | no |
| test_teacher | 14 Nov | Qwen3-32B / Qwen2.5-32B in the AI's place (`test_teacher.ipynb`) | Qwen3-32B 153/161 (gpt-4.1 155, no AI 139) | chosen as teacher |
| **v6** | 14 Nov | MiniLM L6 cross-encoder **reader** distilled from Qwen3-32B's picks on 12,281 practice questions (`train_search_model_v6.ipynb`, `scripts/ask_v6.py`) | golden no AI 139 → 154; big exam 2,495/3,000; +~125 MB, ~70 ms | **yes: `models/ask-reader` (second run)** |
| v7 | 14 Nov | L6 and L4 on 1,000 labels re-checked by Claude + 238 none questions | golden 154 all three; no gain | no |
| v8 | 15 Nov | 12 search models scored, 2 bge-small fine-tunes, 3 bigger readers (Granite R2, GTE ModernBERT) | fine-tuned bge-small right-first 79.5 → 86.1% alone, but **inside Ask golden 152 vs 154**, fresh 41 vs 43; Granite R2 reader 154 / fresh 41 at 1.1 s | no |
| v8b | 15 Nov | v8's fine-tune re-exported at 32-bit for a like-for-like test | **never run** (status/README.md:155: "optional") | – |
| ask_cip_train / Gemini-ask-cip-train | 20-21 Nov | reader retrained on approved metadata, CPU preflight first | candidate in `runs/2026-11-21/cip-candidate.zip` | no (see next row) |
| ask_cip_v2 | 21-22 Nov | Qwen3 doc2query wordings (6x), a new reader on them, replay of 38,604-52,707 bank questions | new reader golden 156 → 144, fresh 48 → 44, researched 45 → 40; 6x wordings +0.4 points for ~140 MB | no |
| plan writer | 22-23 Nov | Qwen2.5-0.5B/1.5B and Qwen3-0.6B/1.7B LoRA to write the plan JSON from 22,800 pairs (`ask_plan_writer.ipynb`, `scripts/ask_plan_pairs.py`) | **waiting for the Colab run**; no result in the repo; notebook has no saved outputs | – |

**Correction to the circulating claim "v8b better alone but 152 vs 154 inside Ask":** that was v8's fine-tuned
bge-small (better alone, 152 vs 154 inside Ask, docs/research/ask-cip-model-training.md, v8's run); v8b was never run.

**The known flaw in the plan writer's data, confirmed:** `scripts/ask_plan_pairs.py:256` (`shown`: `pool =
list(codes)`) and `:323` (`real_cases`: `pool = list(codes) + [...]`) always put the plan's own question codes among the
6 candidates the model sees. Every training pair and the held-out score assume the right question is present. At answer
time the plan path's part-by-part search (`ask_plan.candidates`) has the right question in its top 6 for only 79% of
real questions (section 4.3), so the model must be scored on the search's own 6 before its held-out number means
anything.

---

## 4. Test sets and scorers

### 4.1 The sets

| File | Cases | What it is | Honest? |
|---|---|---|---|
| `scripts/ask_golden.yml` | 161 (9 want none, 1 China) | analyst-style questions, written 11 Nov | tuned on for 2 weeks: a floor check, not a measure |
| `scripts/ask_fresh.yml` | 50 (3 none) | real staging questions 23 Oct – 14 Nov, answers written by reading candidates | used since 15 Nov to find fixes: no longer unseen |
| `scripts/ask_researched.yml` | 58 (4 none) | Claude-written from Coresight's public headlines | draft key |
| `scripts/ask_real.yml` | 232 (1 none) | "what people typed" 23 Oct – 22 Nov, keys marked blind by 4 Claude agents | **see warning below** |
| `scripts/ask_review_none.yml` | 60 strings | questions no survey answers | scored by turning each into `{q, want: none}` |
| `scripts/ask_hard.yml` | 132 | multi-question plans with figures from raw weekly files (14 Sep – 16 Nov 2026) | tuned on |
| `scripts/ask_heldout.yml` | 30 | written after the hard set | its misses were read: seen |
| `scripts/ask_heldout2.yml` | 30 | written 22 Nov, never tuned on | the only unseen hard set |
| `scripts/ask_review_questions.yml`, `ask_review_marks.yml` | 32, 105 | review-sheet inputs | – |
| `docs/research/ask-question-bank.csv.gz` | 38,604 rows | generated bank with answer keys (the "big exam" samples 3,000-6,000 from it) | generated wording |

**Warning on the "real" set:** 179 of its 232 questions end in a templated suffix ("latest wave", "by generation",
"by income", "in 2026"); they are 115 distinct stems, e.g. "Have consumers bought anything on TikTok Shop?" four times.
They come from scripted runs that hit staging, not from people typing. The truly human questions are few (section 6).

### 4.2 How to run (no AI; never set `CIP_ASK_PROVIDER` or `OPENAPI_KEY` for these)

```bash
cd /Users/mohdsaeedafri/All-Code-Base/cip-test
.venv/bin/python scripts/ask_golden.py --quick                                   # golden, data/published/current
.venv/bin/python scripts/ask_golden.py --quick --questions scripts/ask_fresh.yml
.venv/bin/python scripts/ask_golden.py --quick --questions scripts/ask_researched.yml
.venv/bin/python scripts/ask_golden.py --quick --questions scripts/ask_real.yml
.venv/bin/python scripts/ask_golden.py --quick --published data/published/preview/current/api/v1   # other data
.venv/bin/python scripts/ask_hard.py --published data/published/preview/current/api/v1 --cases scripts/ask_heldout2.yml
.venv/bin/python scripts/ask_hard.py ... --candidates     # does the plan search hold every question a plan needs
.venv/bin/python scripts/ask_bench.py --count 2000 --seed 7 --show 0     # generated questions
```

Cautions: without `--quick`, `ask_golden.py` loads `OPENAPI_KEY` from `.env` if present (ask_golden.py:179-184) and may
spend. The scorers write Ask's vector cache in `logs/` (and prune it to the publication scored); copy it aside first if
another run depends on it. The hard sets need waves up to 16 Nov, so only the preview copy can score them. `ask_hard.py`
counts a case right when every expected figure appears anywhere in the headline, sentences or table: Y023 of held-out-2
was scored right while its headline said "100.0%" each week, because the table held the expected shares.
`scripts/colab/ask_cip_v2.py replay` scores tens of thousands of bank questions (Colab, `runs/2026-11-22`).

### 4.3 Scores, 27 Nov 2026, no AI

| Set | `current` (10 Nov data) | `preview` (27 Nov data) | Circulating figure |
|---|---|---|---|
| golden | **158/161** (98%) | 159/161 | 158/161 ✔ |
| fresh | **48/50** | 47/50 | 48/50 ✔ |
| researched | **48/58** | 45/58 | 48/58 ✔ |
| real | **184/232** (79%) | 181/232 | 184/232 ✔ |
| no-answer (60) | **55/60** | 56/60 | 55/60 ✔ |
| hard (132) | – (needs 16 Nov) | **67/132 (differs)** | 80/132 (22 Nov) |
| held-out-1 (30) | – | **18/30 (differs)** | 21/30 |
| held-out-2 (30) | – | **15/30 (differs)** | 17/30 |
| held-out-2: plan search holds every needed question | – | 29/29 plans, 22 ms median | – |

The 22 Nov hard-set scores were taken on a publication that no longer exists here; today's preview (a Mac build, with
the q/Q collision of 2.1) scores 13, 3 and 2 lower. Re-baseline the hard sets on staging's files before comparing a
rebuild with them. Held-out-2 misses today: Y001, Y003, Y016, Y021 (top nonfood retailers "in the latest survey"
answered from a 20 Jun 2022 one-off), Y022, Y026, Y028 and others listed in `hard-heldout2.json` (scratchpad).

Remaining misses on `current`: golden 3 (AI assistants → D28; groceries online trend → EC4; China, no China data);
fresh 2 (holiday groceries → New Year; tariff worry not drawn as a trend); no-answer 5 answered anyway (work from home,
smartwatch, gym membership, smoking, second home); real 48: 40 after the reader picked (a wrong pick, or its pick refused), 7 refused before any pick, 1 from a
stored name. Recurring real misses: inflation worries → D13, TikTok Shop → EH1/SL2, eating out less → GP4 (GLP-1), cutting back
→ FWC5 (FIFA), financial optimism → CS2 (economy), Gen Z gift spend → HX2, groceries online by month → q3 kept refusing.

**Search recall on the real set (231 with an answer, `current`)** — where the right question first appears:

| Search | 1st | top 3 | top 6 | top 10 | top 20 | anywhere |
|---|---|---|---|---|---|---|
| Ask's own `index.retrieve` on the subject (before the reader and rules) | 145 (63%) | 174 (75%) | 201 (87%) | 210 (91%) | 220 (95%) | 222 (96%) |
| The plan path's part-by-part `ask_plan.candidates` (what the plan writer would see) | 126 (55%) | 166 (72%) | 182 (79%) | 193 (84%) | 196 (85%) | 200 (87%) |

The circulating "54% first, 78% in top 6, 85% in top 20" is the second row (over 232). Ask's own single-question search
is clearly better (63% / 87% / 95%); a plan writer fed by `ask_plan.candidates` starts from the weaker list.

**Generated bench** (`scripts/ask_bench.py --count 2000 --seed 7`, `current`): right question **44.1%** (differs:
44.8% on 21 Nov), in the first 5 shown 47.6%, right figures 43.1%; by wording exact 84.5%, about 35.9%, by name 33.1%,
with a typo 27.2%; median 50.5 ms, p95 127 ms, peak 504 MB. The bench is strict (the exact target question or the same
wording) and its wordings are generated, so it tracks regressions, not real accuracy.

---

## 5. Infrastructure limits

- Azure App Service `csr-awa-cip-portal-stg`, plan **P0v3: 1 vCPU, 4 GB**, Central US (memory note
  `cip-azure-test-webapp.md`). One container: nginx (serves published files), gunicorn with **1** Uvicorn worker on the
  container's own 127.0.0.1:8000 (`deploy/start.sh:34`, `WEB_CONCURRENCY` default 1), and the ETL loop (publish every
  30 minutes, `deploy/etl-loop.sh`) in the same box. The Mac's old :8000 server and tunnel were retired on 10 Nov
  (memory note `mac-jobs-retired.md`); CLAUDE.md's rule still says never touch :8000.
- Both ONNX sessions run with one thread (`intra_op_num_threads = 1`, ask_model.py:237, 277) so Ask never takes the
  whole core; at most 2 questions are computed at once (main.py:108).
- Measured: 5 Nov Azure peak 771 MB (~19% of 4 GB), start-up publish ~8 min of full CPU, 388 req/s at 73% CPU; a full
  publish from staging's database 1,203 s wall, peak 398 MB (status/README.md:34); Ask about 12 questions/s on one core.
  Round trip India → Central US ~232 ms; a new TLS connection ~1 s.
- Budget for any new model on the server: it shares 4 GB and one core with nginx, the API (~0.5-0.6 GB with Ask) and the
  publish (~0.4 GB). A model that needs a GPU or more than ~1 s of one core per question does not fit. The image is
  built on Bitbucket (`bitbucket-pipelines.yml`, max 25 min a step, Docker 3 GB); a large model download lengthens every
  uncached build.
- Training runs only on Google Colab under the company's Google AI Pro plan (compute units, no extra bill); the user
  prefers Colab units to any paid API, and any API job over $1 needs a quote and a cap first (memory note).

---

## 6. Real user questions: where they are

- **Staging's database**, table `cip_access_log` (sql/008_access.sql:7-21), schema `cip_stg` on
  `csr-mysql8-flex-stg.mysql.database.azure.com`. One row per Ask question: `ts`, `email`, `client`, `role`,
  `action='ask'`, `target` (the question, first 300 characters), `detail` JSON (`mode`, source links, `asked_as` for a
  follow-up), `ip_hash` (keyed hash, never the address), `user_agent`. Written by `shared/core/audit.py record` from
  api/main.py:841. MCP asks are not logged.
- Counted 27 Nov 2026 (aggregate SELECTs only, no question or email read): **66,846 ask rows**, 23 Oct – 27 Nov 2026,
  56 accounts, 28,708 distinct questions. Of them **385 came from a browser** (5 accounts: 2 super admins, 366 asks /
  112 distinct; 3 analysts, 19 asks / 7 distinct), **116 distinct browser questions** in all (366 answered with
  figures, 17 none, 2 choose). The rest are scripts: `Python-urllib` 45,498, no user agent 20,625 (51 accounts: the
  10 Nov load test and replays), `cip-probe/1` 305, curl 13.
- To export the human questions (read-only, from a machine on the VPN; strip emails before anything leaves):

```sql
SELECT ts, role, client IS NULL AS staff, target AS question, detail
FROM cip_access_log
WHERE action = 'ask' AND user_agent LIKE 'Mozilla%'
ORDER BY ts;
```

- Local copies: `scripts/ask_fresh.yml` (50 human questions to 14 Nov), `scripts/ask_real.yml` (232, mostly templated,
  to 22 Nov), `logs/ask-questions.jsonl` (15 lines, 12 Nov), `logs/ask-learned.json` (109 AI-settled readings),
  `logs/ask-readings.json` (944 AI readings). Staging keeps its own `logs/ask-*.json` on `/home` (learned, verified,
  readings, quality).
- Privacy: `email` and `client` are personal or client-identifying; keep them out of any training file, notebook or
  upload. Questions may name a client's interests: treat the question text as internal. Colab may receive question
  wording and survey wording, never respondents or figures (docs/research/ask-cip-model-training.md Part 12.3). Never
  test against staging's `/api/v1/ask` without saying so: every call adds a row to this log and pollutes it (the
  measuring copy used for this brief turned `audit.record` off).
- Bottom line: there are about **120 distinct real human questions**, two thirds of them from the product owner. A
  real test set big enough to train on does not exist yet; status/README.md:115-117 (Pending) asks for 50+ real analyst
  questions checked by hand.

---

## 7. Rules that bind the next agent (from CLAUDE.md and memory)

1. **Never commit, push, merge, rebase or tag** in cip-test or cip-stg (CLAUDE.md:3-6). Tell the user what to commit.
2. **Never stop, restart or call the server on 127.0.0.1:8000** or cloudflared (CLAUDE.md:8-15). Test on another port
   (e.g. `.venv/bin/python -m uvicorn api.main:app --port 8013` with `CIP_PUBLISH_DIR=data/published/preview`,
   `CIP_DEMO_LOGIN=1`, a generated `CIP_SESSION_SECRET`; sign in as the super admin
   `/auth/dev-login?email=mohdsaeedafri@coresight.com`), stop only that port's pid. A local API reads staging's database
   and writes its sign-ins and asks to staging's access log.
3. Code style (CLAUDE.md:20-34): every file opens with a plain-English header (what, who calls it, when); a one-line
   docstring per function; comments say why; verb-first plain names; leading `_` only when truly private; minimal code;
   rules that may change live in `config/*.yml`; heavy work in the ETL, never at page open; every calculation leaves one
   test.
4. **Review with ponytail**: `/ponytail ultra`, then `/ponytail-review` on the diff, apply its cuts and say what was cut
   (CLAUDE.md:35-36).
5. **Docs in step**: every feature or change goes, in the same words, to `frontend/src/screens/WhatsNew.tsx` and
   `docs/CHANGELOG.md`; any API route or MCP tool change also to `docs/API.md` and `frontend/src/screens/ApiGuide.tsx`.
   `tests/test_docs.py` fails if they differ, a route is undocumented, or `frontend/src/news.ts LATEST_RELEASE` is not
   the newest changelog date (CLAUDE.md:37-39).
6. **status/README.md**: read it first; update its row in the same change when starting, finishing or stuck, using the
   standard at its top (exactly one status: Done, Waiting for deploy, In progress, Pending, Stuck; dates written out;
   one line per item) (CLAUDE.md:40-41).
7. **Before finishing**: `/code-review` as a second reader, the full test suite
   (`.venv/bin/python -m pytest -q`, 757 tests collected today), the frontend type-check (`cd frontend && npx tsc
   --noEmit`, as .github/workflows/ci.yml:41), and look at any touched screen in a browser (CLAUDE.md:42-43).
8. **Sync to cip-stg** after tests pass: `git diff <commit before the task> -- <files>` in cip-test, then
   `git apply --check` and `git apply` in `/Users/mohdsaeedafri/All-Code-Base/cip-stg` (branch `stg-deploy`, working tree
   only); run the tests there with cip-test's venv (memory note `sync-test-to-stg.md`). Today every Ask file
   (`api/assistant.py`, `ask_*.py`, `Ask.tsx`, `config/ask_semantic.json`) is identical in both repos; cip-stg has
   `models/ask-reader` only.
9. Change only what was asked; keep a screen's look and library (memory note). Confirm before deleting anything.
10. AI spend: Colab units yes; the OpenAI/Gemini/NVIDIA keys stay minimal; quote and cap any paid job over $1.

---

## 8. Git state and the chart decision

- HEAD `cb46c7e` (27 Nov 2026 17:47 IST, "Refactor weekly topics handling…"): touches only weekly topics, tests and
  status. **The "chart only when asked" change came in `26a1a9c`** (27 Nov 13:58 IST, 20 lines of Ask.tsx changed, WhatsNew and
  CHANGELOG entry "Ask CIP: the chart only when you ask for it", WhatsNew.tsx:11-12, docs/CHANGELOG.md:13-15); `cb46c7e`
  contains it as history. status/README.md:42 lists it as Waiting for deploy. Tree clean.
- The manager's new layout (`~/Downloads/ask-cip-in-platform-v4.html`, 27 Nov 15:00, Figtree font, Coresight red
  `#C8102E`) draws a chart card inside the answer by default, which reverses `ASKS_CHART`. Reversing it touches
  Ask.tsx:26, 189, 266-273, and needs a new WhatsNew + CHANGELOG entry (test_docs.py checks them).
- Pending items that name Ask (status/README.md): the plan writer (In progress, line 26: waiting for the Colab run;
  score it on the search's own 6 and the real set); Ask without AI per answer, plain templates and pick fixes (Pending,
  line 116: "the user's go"); 50+ real analyst questions as the test set (line 117); misses list (line 100); Gemini as
  opt-in check (Waiting for deploy, line 58).
