# Prompt for the next agent: Ask CIP rebuild (manager's answer layout for every question, our own trained model, near-zero AI cost)

Copy everything below the line into a new Claude Code session opened in `/Users/mohdsaeedafri/All-Code-Base/cip-test`.

---

You are taking over the Ask CIP rebuild in Coresight's Consumer Intelligence Platform (CIP). Ask CIP lets clients and analysts
type any question about Coresight's consumer surveys in their own words and get an answer. There is no limit to the questions
people may ask, so everything you build must work for every question, not for a handful of examples.

## 0. Read first (in this order) and verify, do not trust

1. `CLAUDE.md` (hard rules: never commit or push; never stop, restart or call the live server on 127.0.0.1:8000 or cloudflared;
   test on another port; how code is written; docs sync; status file; ponytail review; full tests before finishing).
2. `status/README.md` (what is done, pending, stuck; update it when you start, finish or get stuck on an item).
3. The findings of the previous session, all in `docs/research/ask-cip-rebuild-2026-11-27/`:
   - `01-template-spec.md`: the manager's template reverse-engineered with REA, the full layout for every answer type, conflicts,
     open questions, and 34 gaps (G1-G34) with file:line and the smallest change for each.
   - `02-research.md`: independent outside research with sources (how ChatGPT/Claude/Gemini and data products answer; CPU
     latency of small models; retrieval; templates vs LLM text; chart choice; honest evaluation).
   - `03-codebase-facts.md`: the current pipeline, data, models, test sets, logs, memory and speed, with file:line and commands.
   - `04-council-verdict.md`: the LLM council's review of this plan (apply what it says before starting).
4. The manager's template: `~/Downloads/ask-cip-in-platform-v4.html` (open it in a browser, light and dark). Its chart numbers
   are wrong data (see section 3); use its layout, not its figures.

Every number below came from the previous session. Re-measure anything you rely on before acting on it.

## 1. What the user and the manager want

**The user's goal (27 Nov 2026):** "We planned to train our model with our own data so that everything could be answered without
AI's help. AI would only be used in rare cases where we can't get an answer; otherwise, everything should rely on the trained
model." Any number of questions, each answered fast, with minimum RAM, CPU, response time and server latency. Google Colab Pro
is ready for training. The OpenAI key must barely be used: the current cap of $0.50 a month stays; quote and cap any API job
over about $1 and ask first.

**The manager's decisions (meeting notes, 27 Nov; they override the template where they differ):**
- One view: remove Client view / Analyst view.
- Market selector: US, China or Both, default Both. When Both is selected and the question has results in both markets, Ask
  asks which survey's results the user wants. Every answer names the country.
- Same layout for every answer: a direct answer first (one plain sentence), then three summary cards (for example highest,
  lowest, difference), then a chart that fits the question, then the evidence (question asked, survey, date). Plain words.
- Chart fits the question: vertical bars to compare categories (such as generations), a line for trends over time. The chart is
  shown in every answer. This reverses the "chart only when asked" change (`ASKS_CHART` in `frontend/src/screens/Ask.tsx`,
  added in commit 26a1a9c). The user agreed on 27 Nov to follow the manager's layout.
- Period options follow how often the survey runs: a quarterly survey supports quarterly and yearly views; a monthly survey
  supports monthly, quarterly and yearly views.
- Keep: dig deeper / follow-up questions, export of the chart and numbers to Excel, copy the full answer. A New question button
  opens a fresh chat; the earlier one stays in History.
- Placeholder "Ask a question in your own words". Remove "Answers come from survey data." Keep the question asked and the source.
  Hide internal details: question code, base, latest-data metadata.
- The manager also asked for: 10-15 sample questions with expected answers (easy, hard and complex), chart and graph designs
  before the follow-up call on Monday (30 Nov 2026), and the Ask CIP HTML layout files including dark mode.

## 2. The architecture to build (why it can be cheap)

Every answer has the same parts. Only the first needs a trained model; the rest is code, data, or text written once:

| Step | What | Made by | Cost per answer |
|---|---|---|---|
| Understand | which survey question(s), market, demographic group, period, answer type | trained models on our server (search + reranker + small slot models/rules) | $0 |
| Compute | every figure, change, significance, highest/lowest | code from the published data (exists: `api/ask_figures.py`, `api/ask_engine.py`) | $0 |
| Write | the headline sentence, card labels, chart title | fixed sentence patterns per answer type + one plain phrase per survey question written **once** offline (e.g. "bought beauty products in the past three months") | $0 |
| Show | cards, chart, evidence, dig-deeper chips, ask-back | screen + rules | $0 |
| Fallback | only when the models are unsure or nothing matches | the paid LLM, allowed only to choose among supplied candidates and slot values, never to write numbers; else say "no survey asks this" and show the closest questions | rare, capped |

The outside research (`02-research.md`) confirms this pattern (code computes, templates write, small local models understand,
LLM as fallback) and it changes two earlier ideas:
- **Do not put the generative "plan writer" (Qwen 0.5-1.7B) on the live path.** On one CPU it needs about 1.5-2 s (0.5B) to
  5-7 s (1.5B) per plan. Use it, or a bigger open model on Colab, offline: to label real questions and to write training
  questions and phrases.
- **The main loss is in finding the right question, not in choosing between candidates.** Fix the search first.

## 3. What has been done, what went wrong, and why retraining did not help

- **Pipeline today:** rules (`api/ask_reader.py`) → bge-small search (`api/ask_index.py`) → MiniLM cross-encoder reader
  (`api/ask_model.py` read_pick, `models/ask-reader`) → optional gpt-4o-mini check (`plan()`, $0.50/month cap) → exact figures
  (`api/ask_figures.py`, `ask_engine`) → f-string sentences (`api/assistant.py` brief/write/in_words/answer). Answers are cached
  (ANSWERS). Thresholds: GATE, NEAR_FLOOR, READER_SURE, RARE_WORD, CURRENT_DAYS=365.
- **Colab rounds v1-v8 (search model, reranker, reader) all trained "finding the question". None touched the wording**, which is
  why the answers stayed vague. v6 copied Qwen3-32B's picks, and the reader learned that teacher prompt's bias ("a topic alone
  means its main question", "prefer questions asked in many waves"). v8's fine-tuned search scored 152 vs 154 inside Ask. v8b
  and the plan writer (`ask_plan_writer.ipynb`, `scripts/ask_plan_pairs.py`) were never run. The Colab files are no longer on
  this Mac (`~/Downloads/Collab` is gone); they are on the user's Google Drive.
- **The plan writer's data is flawed:** `scripts/ask_plan_pairs.py:256` and `:323` always insert the right question into its 6
  candidates, so its training and held-out score assume what the search does not deliver.
- **Scores were tuned on the sets they were measured on.** Golden 158/161 vs unseen held-out-2 15-17/30. The "real" set is
  184/232 (79%), but 179 of its 232 questions are scripted suffixes of 115 stems, so it overstates variety and carries about
  +/-5 points of noise.
- **Search recall:** Ask's own search (`index.retrieve`) has the right question 1st for 63%, in the top 6 for 87%, in the top 20
  for 95% (the plan path's `ask_plan.candidates`: 54/78/85).
- **Overrides throw away right answers:** "cutting back because of tariffs" → search 1st TF8 (right), the reader picks TF3;
  "groceries this week" → search 1st q4 (right), a named-answer rule picks G2 (a May 2026 annual).
- **The "which did you mean" step never runs:** with the reader installed, every pick is labelled "reader", so GATE cannot
  trigger (0 of 393 answers).
- **Wrong trend data (fix before anything else):** `api/ask_index.py:191-208` (`wording_groups`) joins a wording to a group when
  it shares half its words with the group's last member, so different questions chain together. The manager's beauty example
  mixes five questions: Aug 2022's 54.8% is footwear, Nov 2024's 88.8% is "bought anything online". The real beauty series runs
  25 Nov 2024 (68.2%) to 28 Sep 2026 (65.5%). 12 joined series (151 surveys) certainly mix questions, up to about 64 by a
  broader test; the same fault joins footwear / off-price / drug-store spending.
- **Real questions are scarce:** staging's access log has 66,846 Ask rows (23 Oct-27 Nov) but only 385 from a browser: 116
  distinct questions from 5 people (two super admins). The rest are scripts and load tests. Export queries and privacy notes are
  in `03-codebase-facts.md`.
- **This Mac's disk ignores letter case:** `q1..q6` and `Q1..Q6` collide, so local copies of the weekly core questions differ
  from staging's. Score on a case-sensitive volume or on staging's files.
- **Memory and speed today** (M4 Mac, :8013, 27 Nov data): 161 MB at start, 421 MB after the first question, 626 MB peak with 4
  clients; new question 89 ms median, 290 ms p95; repeat 1 ms; 14.4 questions/s. Staging (Azure P0v3) has 1 vCPU and 4 GB for
  nginx, the API and the publish together, so it is slower.
- **Process errors to avoid repeating:** an AI writer for every answer was built and removed the same day (the user rejected the
  cost); there is no paid OpenAI key on this Mac and the free Gemini tier may keep what it is sent, so Coresight figures must
  never go to it; other sessions edit the same files, so never `git checkout`/reset files, use patches; local test servers take
  a while to start (wait for /healthz 200).

## 4. What to do, in order, with a gate at each step

Do every phase with tests, then report numbers to the user before the next phase. Use the skills named.

**Phase 0: verify and research (no code).**
- Re-read sections 1-3 against the code and data. Take a fresh baseline (golden, fresh, researched, real, no-answer, hard,
  held-out, generated bench) on case-correct data. Record it in `status/README.md`.
- Research anything still open with the `agent-reach` skill (its CLI is not installed on this Mac; ask the user before
  installing, otherwise use WebSearch/WebFetch) and the `reverse-engineer-anything` (REA) skill to study live competitor answer
  pages (layout, follow-ups, ask-back) and the manager's template. Never put Coresight data, names or figures into outside
  requests.
- Run the `llm-council` skill on your phase plan before coding.

**Phase 1: correct data and the test sets (highest priority).**
- Fix `wording_groups` so only the same question joins over the years (same answers and same meaning, not half the words);
  audit every joined series and list the ones that change; leave a test that fails if two different questions join again.
- The manager's sample set (due first): 10-15 questions with expected answers in the new layout (easy, hard, complex, one
  China, one Both-markets ask-back, one follow-up, one "why", one no-survey-asks-this). Exact figures from the data; an analyst
  checks them. Do not use the template's beauty figures except the latest (65.5%, 28 Sep 2026).
- An honest real-question test set: the 116 browser questions plus analysts' questions, split by date, frozen, never used for
  tuning (aim for about 700 over time; report the noise). The scripted and generated sets remain floors only.

**Phase 2: the answer layout for every question (no model needed).**
- Implement the layout from `01-template-spec.md` for every answer type it defines (latest value, trend, compare groups, rank
  answers, two periods, one group within another question, two answers combined, grids, multi-select, ranges, nets, China,
  Both-markets ask-back, typed follow-up, "why" and unusual readings, ambiguous ask-back, no survey asks it, small samples, a
  period the survey did not run). Work through G1-G34.
- The headline is one sentence from a pattern per answer type; "rose"/"fell" only when the change is significant, otherwise
  "about the same" (at about 400 people the margin is about +/-4.9 points).
- Chart: line for time, bars for categories, shown in every answer (remove `ASKS_CHART`). Excel export holds the chart and the
  numbers (openpyxl is installed; today only the table is exported).
- Market selector (API input + screen), ask-back when both markets match (list the US/China question pairs in config, since
  China asks only Q1-Q9), China by age group (no generation cut), one view, New question, placeholder, internals hidden.
- Docs in the same words in `WhatsNew.tsx` and `docs/CHANGELOG.md`; API changes also in `docs/API.md` and `ApiGuide.tsx`.

**Phase 3: text written once, offline, on Colab (open models only, no paid API).**
- For every survey question (concept): one plain phrase for the headline, a chart title, and 15-30 short questions in users'
  words (intent-style, about 7 words, not survey wording). Filter, spot-check by a person, store in config or produce in the ETL
  at publish so new surveys get theirs automatically.

**Phase 4: understanding (Colab training, small models on the server).**
- Search first: hybrid keyword (BM25) + embedding search fused by reciprocal rank, plus the Phase 3 questions indexed; fine-tune
  bge-small on real and checked questions. Target: right question in the top 20 for at least 98% of the frozen real set.
- Reranker retrained on real and checked labels without the old teacher-prompt bias; a confident first search hit is never
  overridden by a rule or the reader without stronger evidence.
- Slots (market, period, group, answer type): rules and synonym lists in `config/*.yml`, plus a small classifier for answer type
  if rules fall short. Do not classify the survey question itself (the question set keeps growing).
- Confidence decides: one clear candidate → answer; 2-4 close → "Did you mean" ask-back; none → the capped LLM fallback, which
  only picks among candidates, else "no survey asks this".
- The plan writer only offline (labelling, training data), unless it is shown to meet the latency budget below.

**Phase 5: measure, gate, ship.**
- Budgets on a 1-vCPU, 4 GB limit (e.g. `docker run --cpus=1 --memory=4g`): new question p95 at most 300 ms server time;
  repeat under 5 ms; API peak memory no higher than today's (about 626 MB) plus 100 MB; no slowdown for other pages.
- Accuracy: beat the Phase 0 baseline on the frozen real set by more than its noise; no drop on golden and no-answer; the
  paid fallback answers under 5% of questions and stays under $0.50 a month.
- Run the `llm-council` skill on the results, `/code-review`, the ponytail review, the full test suite and the frontend
  type-check; check the screens in a browser (light, dark, phone width) on a separate port; sync to cip-stg by patch; update
  `status/README.md`. Tell the user what to commit; never commit yourself.

## 5. Open questions to ask the user (the manager decides)
From `01-template-spec.md`: show "unweighted"? keep the number of people asked in Excel? horizontal bars for long ranked lists
(the chart guides recommend them)? a weekly view for weekly questions? a side-by-side option for Both? does a country named in
the question override the selector? neutral or green/red arrows? always ask back when two questions fit, or answer the best
match first and offer the other (today's choice, 12 Nov)? how to warn about small samples without showing the base?

## 6. How to report
After each phase: what changed (files), the numbers before and after, what was cut in the ponytail review, what is left, and
any decision needed. Plain words, short. Never claim a gain you did not measure.
