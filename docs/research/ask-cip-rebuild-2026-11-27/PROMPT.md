# Prompt for the next agent: Ask CIP rebuild (manager's answer layout for every question, our own trained model, near-zero AI cost)

Copy everything below the line into a new Claude Code session opened in `/Users/mohdsaeedafri/All-Code-Base/cip-test`.

---

You are taking over the Ask CIP rebuild in Coresight's Consumer Intelligence Platform (CIP). Ask CIP lets clients and analysts
type any question about Coresight's consumer surveys in their own words and get an answer. There is no limit to the questions
people may ask, so everything you build must work for every question, not for a handful of examples.

## 0. Read first (in this order) and verify, do not trust

1. `CLAUDE.md` (hard rules: never commit or push; never stop, restart or call the live server on 127.0.0.1:8000 or cloudflared;
   test on another port; how code is written; docs sync; status file; ponytail review; full tests before finishing).
2. `status/README.md` (what is done, pending, stuck; update it when you start, finish or get stuck on an item). Two rows
   meet this plan: "Ask plan writer" (In progress, waiting for the Colab run, then llama.cpp on the server) is superseded,
   since the plan writer stays offline: move it to Pending when you start. "Ask CIP without AI per answer" (Pending, the
   user's go) is this work: set it to In progress. The "Ask rebuild" row's rule still holds: a trained model only where a
   fresh held-out set shows a gap rules cannot close.
3. The findings of the previous session, all in `docs/research/ask-cip-rebuild-2026-11-27/`:
   - `01-template-spec.md`: the manager's template reverse-engineered with REA, the full layout for every answer type, conflicts,
     open questions, and 34 gaps (G1-G34) with file:line and the smallest change for each.
   - `02-research.md`: independent outside research with sources (how ChatGPT/Claude/Gemini and data products answer; CPU
     latency of small models; retrieval; templates vs LLM text; chart choice; honest evaluation).
   - `03-codebase-facts.md`: the current pipeline, data, models, test sets, logs, memory and speed, with file:line and commands.
   - `04-council-verdict.md`: the council's review of this plan (27 Nov 2026). Where it and this file differ, it wins. If it
     is missing, stop and ask the user. Do not run another council on this plan.
4. The manager's template: `~/Downloads/ask-cip-in-platform-v4.html` (open it in a browser, light and dark). Its chart numbers
   are wrong data (see section 3); use its layout, not its figures.

Every number below came from the previous session. Re-measure anything you rely on before acting on it.

## 1. What the user and the manager want

**The user's goal (27 Nov 2026):** "We planned to train our model with our own data so that everything could be answered without
AI's help. AI would only be used in rare cases where we can't get an answer; otherwise, everything should rely on the trained
model." Any number of questions, each answered fast, with minimum RAM, CPU, response time and server latency. Google Colab Pro
is ready for training. The OpenAI key must barely be used: the cap is $0.50 a month in code (`CIP_ASK_BUDGET_USD`,
`api/ask_model.py:149`), but staging's Azure setting is $10 (status/README.md, the "Ask after the 13 Nov live test" row):
ask the user to lower it, and until then never count on the cap. The cap counts only OpenAI models: NVIDIA and Gemini are
priced at $0 (`api/ask_model.py:62`), so they never reach it, and both may keep what they are sent (Google's free tier,
NVIDIA's trial terms). The fallback is OpenAI's gpt-4o-mini under the cap, or none. Quote and cap any API job over about $1
and ask first.

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
- **On single questions the main loss is in choosing, not finding.** Ask's own search (`index.retrieve`) has the right
  question in its top 10 for 91% (210/231) and its top 20 for 95% of the real set, yet Ask is right on 79%. Of the 48 real
  misses, at most about 21 had the right question outside the reader's list; at least about 27 were lost in the choice (a
  wrong reader pick, a rule override, a refusal). `02-research.md`'s "the loss is in retrieval" used the plan path's
  weaker row (85% in the top 20). For combined questions (the plan path, `api/ask_plan.py`) finding is the loss. So fix the
  choice first for single questions, and the plan path's search for combined ones. Measure the split per miss in Phase 0.

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
  never go to it; local test servers take a while to start (wait for /healthz 200).
- **Every local test API writes to staging's access log.** It reads staging's database, and `shared/core/audit.py record`
  has no off switch, so its sign-ins and asks land in `cip_access_log`, the only source of real questions. Score with the
  scorers (they call the engine, not the route). For browser checks, write the account and the start and end times in your
  report and leave those rows out of every export of real questions. Do not add an off switch to the audit log unasked.
- **Other sessions edit the same files.** Never `git checkout`/reset files. Before your first edit of a file, copy it to the
  scratchpad; build the cip-stg patch from those copies for your files only (paths relative to the repo root), then
  `git apply --check` and `git apply` in cip-stg's working tree. The user may commit mid-session, so never diff against HEAD.

## 4. What to do, in order, with a gate at each step

Do every phase with tests, then report numbers to the user and wait for their go before the next phase. Use the skills named.

**Phase M (first; due Monday 30 Nov 2026): the manager's deliverables. Nothing else comes before it.**
- Layout files: static HTML in `docs/research/ask-cip-rebuild-2026-11-27/mockups/`, built from the v4 template's look (never
  its figures), light and dark, phone width. One answer card per answer type the sample questions use, each with its chart
  design (line for time, vertical bars for categories). For one long ranked list (retailers) draw vertical and horizontal
  bars side by side so the manager can choose (01-template-spec.md C17). Do not touch `Ask.tsx` in this phase.
- Sample set: 10-15 questions with expected answers in the new layout (easy, hard, complex; one China, one Both-markets
  ask-back, one follow-up, one "why", one no-survey-asks-this). Read each figure from one survey's published file: every
  trend Ask draws today goes through the broken `wording_groups` (section 3). For a trend, check that every wave's wording
  is the same (01-template-spec.md section 0 lists the real beauty series). Use `data/published/preview/current` (it has
  China; `current` does not) and avoid the weekly core questions q1-q6 / Q1-Q6, which differ from staging's on this Mac.
  Write each figure's survey, date and file next to it. Mark the set "awaiting analyst check" and ask the user who checks
  it. Keep these questions out of every tuning set and out of `config/ask_verified.yml`.
- Send the open questions of section 5 with them, each with the default you used.
- Done when the user has opened the files in a browser in both themes.

**Phase 0: verify and baseline (no code; about half a day).**
- Re-read sections 1-3 against the code and data. Set meanings are in `03-codebase-facts.md` section 4.1, thresholds in
  section 1.5, the commands in section 4.2 (always `--quick`, so no paid key is read).
- Case-correct data: make a case-sensitive disk image (`hdiutil create -size 10g -type SPARSE -fs "Case-sensitive APFS"
  -volname cip-cs ~/cip-cs`) and copy staging's published files into it; ask the user how to get them. Do not publish from
  staging's database on this Mac without the user's yes: a publish holds the shared `cip_etl` lock for about 20 minutes
  (1,203 s on 27 Nov), and on 26 Nov a long local run made a staging deploy fail (pipeline #96). If they say yes, check
  `SELECT IS_USED_LOCK('cip_etl')` first and never run it during a deploy.
- Take the baseline (golden, fresh, researched, real, no-answer, hard, held-out-1, held-out-2, generated bench) and the
  speed and memory baseline of Phase 5 in the same container. For each real-set miss, record whether the right question
  was missing from the reader's list (a finding loss) or in it (a choosing loss). Record it all in `status/README.md`.
- Take the baseline again after Phase 1: the wording_groups fix changes series, so Phase 5 compares against the second one.
- `02-research.md` is the research and `04-council-verdict.md` is the review: do no new outside research unless a question
  they leave open blocks you, and run no new council on this plan.

**Phase 1: correct data and the test sets (highest priority).**
- Fix `wording_groups` so only the same question joins over the years (same answers and same meaning, not half the words);
  audit every joined series and list the ones that change; leave a test that fails if two different questions join again.
- After the fix, recompute every figure of the Phase M sample set and tell the user which changed. Do not use the
  template's beauty figures except the latest (65.5%, 28 Sep 2026).
- The 116 browser questions are a development set, not a test: 112 of them come from the two super admins (two thirds
  from the product owner, 03-codebase-facts.md section 6), and some may be in `scripts/ask_fresh.yml` (50 questions from
  the same log, used to find fixes since 15 Nov). Use them to find and check fixes.
- The frozen test set: ask the user for 3-5 analysts to write about 50 questions each without seeing Ask or the question
  list, keyed by a second person; plus browser questions after 27 Nov from other accounts. Freeze it in one file; never
  read its misses to find fixes. Until it exists, held-out-2 (30) is the only unseen set: call every result provisional.
- Score every set as three counts: right; asked back with the right question among the choices; wrong (answered, but the
  wrong question or figure). Count real-set misses by stem (179 of its 232 are scripted suffixes of 115 stems), not by
  question. The scripted and generated sets remain floors only.

**Phase 2: the answer layout for every question (no model needed).**
- First sort the 116 browser questions by answer type (T1-T20 in `01-template-spec.md` section 4.4) and count questions
  that fit none (for example "which surveys do you have?"). Build the types in that order, one at a time, each with its
  gaps from G1-G34, and report the order before you start. Every type in 01 is in scope; the order is not.
- The headline is one sentence from a pattern per answer type; "rose"/"fell" only when the change is significant by the
  existing two-proportion test (`api/dashboards.py:86` significant, 01-template-spec.md section 4.2), otherwise "about the
  same". Never hard-code a margin: +/-4.9 points is one figure at 400 people; a change between two such surveys needs about
  +/-6.9.
- Leave one test per answer type that checks the market, period, group, chart type and headline verb, not only which
  survey question was picked.
- Chart: line for time, bars for categories, shown in every answer (remove `ASKS_CHART`). Excel export holds the chart and the
  numbers (openpyxl is installed; today only the table is exported).
- Market selector (API input + screen), ask-back when both markets match (list the US/China question pairs in config, since
  China asks only Q1-Q9), China by age group (no generation cut), one view, New question, placeholder, internals hidden.
- Docs in the same words in `WhatsNew.tsx` and `docs/CHANGELOG.md`; API changes also in `docs/API.md` and `ApiGuide.tsx`.

**Phase 3: one plain phrase per survey question, written once, offline (open models on Colab, no paid API).**
- Already built: `config/ask_semantic.json` holds, per wording, a `name` (a noun label such as "Spending on apparel from
  livestreams"), 6,027 aliases and 16,050 analyst-style questions, written by gpt-4o-mini in `etl/ask_semantic.py` and
  embedded as a second index; `config/ask_verified.yml` (39 entries) answers near-repeats exactly (`VERIFIED_NEAR` 0.91,
  `api/ask_index.py:55`). Do not regenerate the questions: ask_cip_v2 (21-22 Nov) added 6 more wordings per question for
  +0.4 points and about 140 MB. Never add a test-set question to `ask_verified.yml`.
- Add only what Phase 2's sentence patterns need: for every survey question (after the wording_groups fix) one phrase that
  fits a sentence ("bought beauty products in the past three months") and a chart title. Store them next to the existing
  fields; a person checks a random 100 and every phrase the sample set uses. A new survey falls back to its `name` until
  the next run: `etl/ask_semantic.py` uses the paid key, so it does not write them at publish.
- Add more user-style questions only for words a miss list shows are missing.
- You cannot run Colab: write the notebook, the user runs it on Colab Pro, and tell them which output file to download where.

**Phase 4: understanding (choice first; training only where a measured loss needs it).**
- Choice first, no training: a confident first search hit is never overridden by a rule or the reader without stronger
  evidence (the TF8 and q4 cases in section 3). Score each change in minutes with `scripts/ask_golden.py --quick` on the
  development set. Then retrain the reader only on labels a person checked: a model's labels (Qwen offline or any other)
  are proposals, and a person checks every one that disagrees with today's reader (v6 learned its teacher's bias).
- Search second, only where Phase 0's split shows finding losses: first the plan path (`ask_plan.candidates`, 85% in the
  top 20; `scripts/ask_hard.py --candidates`), then single-question misses outside the reader's list. Try hybrid keyword
  (BM25) + embedding search fused by reciprocal rank before any training. Fine-tune bge-small only if that falls short,
  and score it inside Ask, never alone: v1, v3 and v8 were each better alone and worse inside Ask.
- Combined questions stay on the rule-filled plan path (the plan writer is offline). Find fixes on the hard set and
  held-out-1; held-out-2 (15/30 today) only measures. Read each held-out-2 headline yourself: `ask_hard.py` counts a case
  right when the figures appear anywhere (03-codebase-facts.md section 4.2).
- Slots (market, period, group, answer type): rules and synonym lists in `config/*.yml`, plus a small classifier for answer type
  if rules fall short. Do not classify the survey question itself (the question set keeps growing).
- Make confidence work again: today every pick is labelled "reader", so GATE never fires (0 of 393). One clear candidate →
  answer. Two to four close candidates → what Ask does is the manager's open question (section 5); until answered, keep
  today's choice (answer the best match and offer the others under "Not what you meant?", 01-template-spec.md C24). Many
  weak candidates, none clear → the capped fallback (section 1), which may only pick among them, never write a figure.
  Nothing above the floor, or no fallback → "no survey asks this" with the closest questions. Never two ask-backs in one
  answer.
- The plan writer only offline (labelling, training data), unless it is shown to meet the latency budget below.

**Phase 5: measure, gate, ship.**
- Budgets, measured like-for-like: run today's code and the new code in the same container (`docker run --cpus=1
  --memory=4g`), same data, same question list, 1 and 4 clients. New question p95 no worse than today's in that container
  and under 500 ms; repeat under 5 ms; API peak memory no more than today's in that container plus 100 MB, counting every
  new index, phrase and model. The Mac figures (290 ms, 626 MB) and Azure's 771 MB peak are not the baseline. Staging's
  one core also runs nginx and a publish every 30 minutes (peak 398 MB): leave that headroom. No slowdown for other pages.
- Accuracy, paired against the second Phase 0 baseline (after the wording_groups fix): on the frozen set and held-out-2,
  list every question fixed and every question newly broken. Ship only if fixed outnumber broken, wrong answers fall, the
  ask-back rate stays at or under 15% of questions, and golden and no-answer do not drop. Claim a gain only if a paired
  test on fixed vs broken (McNemar) gives p < 0.05; otherwise say "no measurable change". The paid fallback answers under
  5% of questions and stays within the cap of section 1.
- Run the `llm-council` skill on the results, `/code-review`, the ponytail review, the full test suite and the frontend
  type-check; check the screens in a browser (light, dark, phone width) on a separate port; sync to cip-stg by patch
  (section 3), the Ask screen only after the user approves it; update
  `status/README.md`. Tell the user what to commit; never commit yourself.

## 5. Open questions for the manager (send them with the Monday deliverables; build with the default until answered)
From `01-template-spec.md`: show "unweighted"? [no; say "Census-weighted" only when it applies] keep the number of people
asked in Excel? [no] horizontal bars for long ranked lists (the chart guides recommend them)? [vertical, as decided; the
mock-ups show both] a weekly view for weekly questions? [no] a side-by-side option for Both? [no: US and China buttons]
does a country named in the question override the selector? [yes] neutral or green/red arrows? [neutral] always ask back
when two questions fit, or answer the best match first and offer the other? [answer the best match and offer the others,
today's choice] how to warn about small samples without showing the base? ["Fewer than 50 people answered here: read
with caution", 01 section 4.3] a market and a question ask-back in the same answer? [ask the market only, then answer the
best match and offer the others]

## 6. How to report
After each phase: what changed (files), the numbers before and after, what was cut in the ponytail review, what is left, and
any decision needed. Plain words, short. Never claim a gain you did not measure.
In your first report, tell the user plainly what "our trained model" means here: small models on our server pick which
survey question, market, group and period a question means; code computes every figure; fixed patterns write every
sentence; no model writes text. Today it picks right for 79% of the real set and 15 of 30 unseen combined questions. The
honest aim is fewer wrong answers, with "Not what you meant?" or "no survey asks this" for the rest, not 100%.
