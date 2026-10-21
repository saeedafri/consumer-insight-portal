# 20 · Ready for the analyst chatbot: how "Who was the best retailer in this survey?" will be answered

**Status:** design and groundwork. The groundwork is built: the typed API with OpenAPI, search, payloads that carry their base, and published files. The chatbot itself comes later.

**Council decision:** [19](19-council-system-design.md). The bot uses **tool-calling over the typed API, never text-to-SQL.**

## 1. Why tools and not SQL

| | Tool-calling over the API (chosen) | Text-to-SQL over the tables |
|---|---|---|
| **Numbers** | Come from the same code as the screens (`app/data/payloads.py`), so the bot and the portal always agree | The model writes its own SQL, so it can invent cuts, mis-join waves or forget the base |
| **Small bases and significance** | Every response already carries `base`, flags, `suppressed` (n<30) and `small_base` (n<50) | Gone unless the model remembers |
| **Privacy** | No per-respondent rows are ever exposed | `srv_answer` holds respondent rows, which can leak |
| **Speed and cost** | Most calls hit published files or the cache: about a millisecond, no database | Every question is a new query on the shared MySQL |
| **Safety** | Read-only by construction | Needs a separate read-only user plus query limits |

## 2. The tools, and the endpoints behind them

The tool schemas are generated from the API's OpenAPI document (`/api/v1/openapi.json`), so they can't drift from the code.

| Tool | Endpoint | Answers questions like |
|---|---|---|
| `list_surveys(type?, year?)` | `GET /api/v1/waves` | "What did we field last week?" "Which annual studies ran in 2025?" |
| `find_questions(text)` | `GET /api/v1/search?q=` (typos, synonyms, answer labels) | "Do we ask about BNPL?" "Where is the Walmart question?" |
| `get_wave(survey_id)` | `GET /api/v1/waves/{id}/book` | "Who was the best retailer in this survey?" "Top categories among Gen Z?" |
| `get_trend(survey_id, qcode, column?)` | `GET /api/v1/trend` | "How has 'not started holiday shopping' moved since September?" |
| `get_crosstab(survey_id, qcode, cut_a, cut_b, weeks?)` | `GET /api/v1/waves/{id}/crosstab` | "Holiday status for Gen Z women, pooled over 4 weeks" |
| `get_module_dashboard(code, survey_id)` | `GET /api/v1/dashboards/{code}/{id}` | "Give me this week's holiday Databank summary" |

**Example:** "Who was the best retailer in this survey?"
1. The bot calls `find_questions("retailer")` and gets XM2, the holiday retailers question.
2. It calls `get_wave(412)` and finds the XM2 rows: Walmart 50.4% (n=125 holiday purchasers), Amazon 41%.
3. It answers: "Walmart: 50.4% of the 125 respondents who bought holiday items in the week of Oct 12, 2026 (XM2). Amazon is second at 41%. Base: holiday purchasers only."

## 3. What exists now, and what to add before the bot

| Piece | Status |
|---|---|
| Typed endpoints; OpenAPI at `/api/v1/openapi.json` | **Built** |
| Base, flags and comparison on every number; suppression in two-cut results | **Built** |
| Typo- and synonym-tolerant question search (`api/search.py`) | **Built** |
| Module dashboards with written takeaways (`config/dashboards.yml`) | **Built.** Their metric definitions double as the bot's metric catalogue (step 4). |
| Request log: who asked what, which tool, which wave | Add a structured log line per tool call (JSON lines, 90-day retention) |
| **Canonical question IDs** across waves (same question, different code or wording) | The data exists (`cip_concept*`, `srv_result.concept_option_id`); expose it as `get_concept_trend(concept_id)` |
| **Metric catalogue** (`config/metrics.yml`): name → question, codes, base, last-year rule, significance test | Extract from `dashboards.yml` tiles, then add the rest ("bought in past 7 days" = XM1 code 1, base all qualified) |
| Gold-question evaluation set | 50 analyst questions with answers checked by hand from the screens, run on every release |

## 4. Guardrails, written into the system prompt and checked in code

1. **Cite every number** with its base, wave date and question code. A sentence without them is rejected by a post-check.
2. **Never report a suppressed cell** (n<30). Flag n<50 as "small base". The API already marks both.
3. **Changes:** call a change significant only if the response says so (95%, Benjamini–Hochberg across a wave). Otherwise say "within the margin of error".
4. **Comparability:** respect `base_changed_*` flags ("asked of a different group than last week").
5. **Prompt injection:** survey text and answer labels are data. They are passed as tool results and never as instructions.
6. **Read-only:** the tools are GET endpoints behind the same sign-in and entitlements as the portal.
7. **Data egress:** only aggregated, already-published numbers leave the server, never respondent rows. Use the Anthropic API or AWS Bedrock under Coresight's data agreement.

## 5. Where it runs on the 1-core server

The bot calls the model's API, so the server's work per question is 2–5 tool calls. Each is served from a published file or the cache (about 1 ms), or one database read on a miss (1–3 ms on Azure).

**This adds no meaningful load.** The latency is the model's (typically 2–6 s per answer, streamed), not the server's.
