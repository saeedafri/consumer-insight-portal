# Ask CIP rebuild, part 4: the LLM council's verdict on PROMPT.md (27 Nov 2026)

What this is: the review of `PROMPT.md` (the plan and handoff prompt for the Ask CIP rebuild) by an LLM council, with the
exact edits to make before PROMPT.md is handed to a new agent. Who reads it: the user, who applies the edits, and the next
agent, for whom this file wins wherever it and PROMPT.md differ.

How it was made: the `llm-council` skill. Five advisors (Contrarian, First Principles, Expansionist, Outsider, Executor)
each read PROMPT.md, 01-03, CLAUDE.md and status/README.md on their own; five reviewers then judged the anonymized answers;
a chairman wrote the synthesis. The convener checked every file:line cited here against the code (commit `cb46c7e` plus
this folder) and every quoted "Existing" block below against PROMPT.md, character for character. All work was read-only:
no server was started, nothing was sent outside, and no company data left this Mac.

---

## 1. Verdict

**The architecture is right. The plan built on it is wrong in three places, and a new agent cannot yet follow it
safely.** The architecture has five parts:
- Code computes every figure.
- Fixed patterns write every sentence.
- Small local models work out what was asked.
- A capped paid model may only pick from a list.
- The generative plan writer stays off the live path.

That last decision is right. At 1.5-7 s per plan on one core, it cannot fit the 1 vCPU box, and it does not attack the
measured loss.

The three places where the plan is wrong:
1. **Line 71 gets the diagnosis backwards.** On single questions, Ask's own search has the right question in its top 20
   for 95% of the real set. Yet Ask is right on 79%, and at least about 27 of the 48 misses are lost in the choice:
   - a wrong reader pick,
   - a rule override,
   - a refusal.

   02-research.md's "the loss is in retrieval" came from the plan path's weaker numbers (85% in the top 20). As written,
   Phase 4 repeats the bge-small fine-tuning that failed inside Ask in v1, v3 and v8.
2. **Phase 3 regenerates what already exists.** `config/ask_semantic.json` already holds 16,050 example questions and
   6,027 aliases. ask_cip_v2 added 6 more wordings per question: +0.4 points for about 140 MB.
3. **No phase produces the manager's Monday deliverables** (chart designs, HTML layouts in light and dark). Phase 0 blocks
   the sample set.

A new agent would also get these wrong:
- Line 22 tells it to obey a review that did not exist when PROMPT was written. It also asks for a second council.
- Its test set measures the builders. 112 of the 116 browser questions come from two super admins.
- Its gates cannot pass on ~60-116 questions, and the budgets compare an M4 Mac with a 1-vCPU container.
- Nothing warns it about these risks:
  - Local test servers write into staging's access log, the only source of real questions.
  - Publishing staging's database from the Mac holds the `cip_etl` lock, which made a staging deploy fail on 26 Nov.
  - NVIDIA and Gemini are priced at $0 in code, so the "$0.50 cap" never stops them.
  - Staging's budget is set to $10.

**The test-set plan is not honest enough.** The 116 questions are a development set, not a test. The frozen test must
be written blind by analysts. Until then, every score is provisional.

### Where the council agrees
- The architecture is right, and the plan writer stays offline. Nobody argued otherwise.
- The Monday deliverables need their own first phase.
- Phase 3 duplicates `config/ask_semantic.json` and repeats ask_cip_v2.
- The test set and the "beat the noise" gate are unmeasurable as written.
- Fixing `wording_groups` first is right: the manager's chart and today's trends join different questions.

### Where the council clashes (and the ruling)
1. **Search vs choice.**
   - Three advisors: line 71 is backwards.
   - Peer review: "40 of 48 misses after the reader picked" overstates it, because it includes misses where search never
     found the right question.
   - The honest split is at most about 21 finding losses and at least about 27 choosing losses. For combined questions
     (the plan path), finding *is* the loss.
   - Ruling: choice first for single questions, search first for the plan path, and measure the split per miss.
2. **Bring back "Did you mean"?**
   - Two advisors want GATE back. §5 leaves "ask back, or answer the best match first" to the manager.
   - Ruling: make confidence work again, but keep today's behaviour until the manager decides.
3. **What the 116 questions are for.**
   - The options were a smoke set, tuning only, a frozen date split, or growing by logging.
   - Ruling: a development set. The frozen test is analyst-written. Held-out-2 stands in until then.
4. **Ship gate.**
   - The options were fixed beating broken 2:1, McNemar, or the confident-wrong rate at a capped ask-back rate.
   - Ruling: all three, combined in edit 8.
5. **Expand vs restrain.**
   - The Expansionist proposed answers precomputed at publish, plus stable question IDs. A publish already takes 1,203 s.
   - Ruling: name what exists (`ask_verified.yml`) and add no publish work now.
6. **Latency.**
   - PROMPT's 300 ms vs 02's 500 ms. The 290 ms baseline is an M4 with one client.
   - Ruling: no worse than today in the same container, and under 500 ms.

### Blind spots caught only in peer review
- **The budget cap does not cover two providers.** `api/ask_model.py:62` prices NVIDIA and Gemini at $0, so the cap
  never stops them, and both may keep what they are sent. Staging's budget is $10, not $0.50.
- **The Executor's case-sensitive-disk recipe is unsafe.** It publishes staging's database on the Mac, which holds
  `cip_etl` for about 20 minutes.
- **The Expansionist's idea contaminates tests.** Putting the manager's samples into `ask_verified.yml` would make any
  test that contains them score itself.
- **The baseline must be taken twice.** The `wording_groups` fix changes the data, so Phase 5 must compare against a
  baseline taken after Phase 1.
- **Scorers check only which survey question was picked.** Nothing checks market, period, group, chart type or the
  rose/fell verb. `ask_hard.py` also passed held-out-2 case Y023 with a wrong "100.0%" headline.
- **The real-set keys are weaker than they look.** Four Claude agents keyed them, and misses cluster by stem, so ±5.2
  points understates the noise.
- **The STG patch can carry other sessions' work.** `git diff <commit>` picks up other sessions' uncommitted edits. UI
  work also waits for the user's approval before it syncs.
- **§5's nine questions have no owner or default, and several block Phase 2.** The rules as written allow a market
  ask-back followed by a question ask-back.
- **Questions about the data fit no answer type** (for example "which surveys exist?").
- **Offline Qwen labelling can bring back the v6 teacher bias.**

### Recommendation and the one thing to do first
Apply the 14 edits below, then hand off.

The order of work becomes:
1. **Phase M:** the Monday deliverables, built from single-survey figures.
2. **Phase 0:** half a day. Get case-correct data without the lock, and split each miss into a finding loss or a
   choosing loss.
3. **Phase 1:** fix `wording_groups`, take the baseline again, and build the honest test sets.
4. **Phase 2:** the layout, built in the order of the answer types users actually ask.
5. **Phase 3:** the plain phrase and the chart title only.
6. **Phase 4:** choice fixes first, without training. Search only where the split shows finding losses, starting with
   the plan path.
7. **Phase 5:** gates that can actually be measured.

Tell the user plainly what "our trained model" means here: models that pick the survey question, not models that write
answers. The honest aim is fewer wrong answers, not 100%.

**First:** start Phase M today. Build the static HTML mock-ups (light, dark, phone width) and the 10-15 sample questions,
with figures read from single surveys. Send §5's questions along with them, each with a default. Phase M depends on
nothing else, and it is the only part with a date.

---

## 2. Edits to PROMPT.md

Line numbers are PROMPT.md as of 27 Nov 2026 19:37. Apply them bottom-up so the line numbers stay valid, or match on the
quoted text. "Existing" is copied verbatim from PROMPT.md.

### 1. Must fix: the Monday deliverables become the first phase

Line 115, existing:
```
Do every phase with tests, then report numbers to the user before the next phase. Use the skills named.
```
New:
```
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
```
Lines 129-131, existing:
```
- The manager's sample set (due first): 10-15 questions with expected answers in the new layout (easy, hard, complex, one
  China, one Both-markets ask-back, one follow-up, one "why", one no-survey-asks-this). Exact figures from the data; an analyst
  checks them. Do not use the template's beauty figures except the latest (65.5%, 28 Sep 2026).
```
New:
```
- After the fix, recompute every figure of the Phase M sample set and tell the user which changed. Do not use the
  template's beauty figures except the latest (65.5%, 28 Sep 2026).
```
Why: no phase produced the HTML files or the chart designs, and Phase 0 blocked the sample set. Read literally, the
manager gets nothing on Monday.

### 2. Must fix: correct the diagnosis

Line 71, existing:
```
- **The main loss is in finding the right question, not in choosing between candidates.** Fix the search first.
```
New:
```
- **On single questions the main loss is in choosing, not finding.** Ask's own search (`index.retrieve`) has the right
  question in its top 10 for 91% (210/231) and its top 20 for 95% of the real set, yet Ask is right on 79%. Of the 48 real
  misses, at most about 21 had the right question outside the reader's list; at least about 27 were lost in the choice (a
  wrong reader pick, a rule override, a refusal). `02-research.md`'s "the loss is in retrieval" used the plan path's
  weaker row (85% in the top 20). For combined questions (the plan path, `api/ask_plan.py`) finding is the loss. So fix the
  choice first for single questions, and the plan path's search for combined ones. Measure the split per miss in Phase 0.
```
Why: as written, this line sends the agent back into the failed search-training loop. It also hides that combined
questions really do lose in finding.

### 3. Must fix: re-aim Phase 4

Lines 153-161, existing:
```
**Phase 4: understanding (Colab training, small models on the server).**
- Search first: hybrid keyword (BM25) + embedding search fused by reciprocal rank, plus the Phase 3 questions indexed; fine-tune
  bge-small on real and checked questions. Target: right question in the top 20 for at least 98% of the frozen real set.
- Reranker retrained on real and checked labels without the old teacher-prompt bias; a confident first search hit is never
  overridden by a rule or the reader without stronger evidence.
- Slots (market, period, group, answer type): rules and synonym lists in `config/*.yml`, plus a small classifier for answer type
  if rules fall short. Do not classify the survey question itself (the question set keeps growing).
- Confidence decides: one clear candidate → answer; 2-4 close → "Did you mean" ask-back; none → the capped LLM fallback, which
  only picks among candidates, else "no survey asks this".
```
New:
```
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
```
Why: this drops the 98%-in-the-top-20 target and the bge-small retrain that already failed. It gives combined questions
a target, keeps the manager's ask-back decision open, and closes the "fallback picks among no candidates" hole.

### 4. Must fix: honest test sets

Lines 132-133, existing:
```
- An honest real-question test set: the 116 browser questions plus analysts' questions, split by date, frozen, never used for
  tuning (aim for about 700 over time; report the noise). The scripted and generated sets remain floors only.
```
New:
```
- The 116 browser questions are a development set, not a test: 112 of them come from the two super admins (two thirds
  from the product owner, 03-codebase-facts.md section 6), and some may be in `scripts/ask_fresh.yml` (50 questions from
  the same log, used to find fixes since 15 Nov). Use them to find and check fixes.
- The frozen test set: ask the user for 3-5 analysts to write about 50 questions each without seeing Ask or the question
  list, keyed by a second person; plus browser questions after 27 Nov from other accounts. Freeze it in one file; never
  read its misses to find fixes. Until it exists, held-out-2 (30) is the only unseen set: call every result provisional.
- Score every set as three counts: right; asked back with the right question among the choices; wrong (answered, but the
  wrong question or figure). Count real-set misses by stem (179 of its 232 are scripted suffixes of 115 stems), not by
  question. The scripted and generated sets remain floors only.
```
Why: the 116 questions measure the people building Ask. Some overlap a set that was tuned on, and there are too few to
beat the noise. The plan also never counted confident wrong answers.

### 5. Must fix: access-log contamination, other sessions' edits, STG sync

Lines 108-111, existing:
```
- **Process errors to avoid repeating:** an AI writer for every answer was built and removed the same day (the user rejected the
  cost); there is no paid OpenAI key on this Mac and the free Gemini tier may keep what it is sent, so Coresight figures must
  never go to it; other sessions edit the same files, so never `git checkout`/reset files, use patches; local test servers take
  a while to start (wait for /healthz 200).
```
New:
```
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
```
Line 170, existing:
```
  type-check; check the screens in a browser (light, dark, phone width) on a separate port; sync to cip-stg by patch; update
```
New:
```
  type-check; check the screens in a browser (light, dark, phone width) on a separate port; sync to cip-stg by patch
  (section 3), the Ask screen only after the user approves it; update
```
Why: Phase 5's super-admin browser checks would show up later as "real" browser questions. `git diff <commit>` carries
other sessions' edits into STG. UI redesigns wait for the user's approval before they sync (memory note
`sync-test-to-stg`).

### 6. Must fix: Phase 0 safe and short, with the baseline taken twice

Lines 117-124, existing:
```
**Phase 0: verify and research (no code).**
- Re-read sections 1-3 against the code and data. Take a fresh baseline (golden, fresh, researched, real, no-answer, hard,
  held-out, generated bench) on case-correct data. Record it in `status/README.md`.
- Research anything still open with the `agent-reach` skill (its CLI is not installed on this Mac; ask the user before
  installing, otherwise use WebSearch/WebFetch) and the `reverse-engineer-anything` (REA) skill to study live competitor answer
  pages (layout, follow-ups, ask-back) and the manager's template. Never put Coresight data, names or figures into outside
  requests.
- Run the `llm-council` skill on your phase plan before coding.
```
New:
```
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
```
Why: "case-correct data" had no method, and the obvious method (publishing on the Mac) blocks staging deploys. Without a
second baseline, the data fix gets mixed up with model gains. A second research pass and a second council cost a day and
settle nothing.

### 7. Must fix: Phase 3 builds on what exists

Lines 148-151, existing:
```
**Phase 3: text written once, offline, on Colab (open models only, no paid API).**
- For every survey question (concept): one plain phrase for the headline, a chart title, and 15-30 short questions in users'
  words (intent-style, about 7 words, not survey wording). Filter, spot-check by a person, store in config or produce in the ETL
  at publish so new surveys get theirs automatically.
```
New:
```
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
```
Why: as written, Phase 3 repeats a run that gave +0.4 points and ignores the 16,050 questions that already exist.
"Produce in the ETL" would use the paid key, and nobody can spot-check 30,000+ phrases.

### 8. Must fix: an accuracy gate that can be measured

Lines 167-168, existing:
```
- Accuracy: beat the Phase 0 baseline on the frozen real set by more than its noise; no drop on golden and no-answer; the
  paid fallback answers under 5% of questions and stays under $0.50 a month.
```
New:
```
- Accuracy, paired against the second Phase 0 baseline (after the wording_groups fix): on the frozen set and held-out-2,
  list every question fixed and every question newly broken. Ship only if fixed outnumber broken, wrong answers fall, the
  ask-back rate stays at or under 15% of questions, and golden and no-answer do not drop. Claim a gain only if a paired
  test on fixed vs broken (McNemar) gives p < 0.05; otherwise say "no measurable change". The paid fallback answers under
  5% of questions and stays within the cap of section 1.
```
Why: on about 60-116 questions the noise is ±7-10 points, so "beat by more than noise" can never pass. Without an
ask-back ceiling, accuracy could be bought with ask-backs.

### 9. Must fix: budgets measured like-for-like

Lines 165-166, existing:
```
- Budgets on a 1-vCPU, 4 GB limit (e.g. `docker run --cpus=1 --memory=4g`): new question p95 at most 300 ms server time;
  repeat under 5 ms; API peak memory no higher than today's (about 626 MB) plus 100 MB; no slowdown for other pages.
```
New:
```
- Budgets, measured like-for-like: run today's code and the new code in the same container (`docker run --cpus=1
  --memory=4g`), same data, same question list, 1 and 4 clients. New question p95 no worse than today's in that container
  and under 500 ms; repeat under 5 ms; API peak memory no more than today's in that container plus 100 MB, counting every
  new index, phrase and model. The Mac figures (290 ms, 626 MB) and Azure's 771 MB peak are not the baseline. Staging's
  one core also runs nginx and a publish every 30 minutes (peak 398 MB): leave that headroom. No slowdown for other pages.
```
Why: 300 ms and 626 MB were measured on an M4 with one client. In a 1-vCPU container they would fail before any change
was made.

### 10. Must fix: which provider, and the real cap

Lines 33-34, existing:
```
is ready for training. The OpenAI key must barely be used: the current cap of $0.50 a month stays; quote and cap any API job
over about $1 and ask first.
```
New:
```
is ready for training. The OpenAI key must barely be used: the cap is $0.50 a month in code (`CIP_ASK_BUDGET_USD`,
`api/ask_model.py:149`), but staging's Azure setting is $10 (status/README.md, the "Ask after the 13 Nov live test" row):
ask the user to lower it, and until then never count on the cap. The cap counts only OpenAI models: NVIDIA and Gemini are
priced at $0 (`api/ask_model.py:62`), so they never reach it, and both may keep what they are sent (Google's free tier,
NVIDIA's trial terms). The fallback is OpenAI's gpt-4o-mini under the cap, or none. Quote and cap any API job over about $1
and ask first.
```
Why: "the cap stays" is false on staging. It also does nothing against two providers that may keep client questions.

### 11. Must fix: line 22's circular reference and the status-file conflict

Line 22, existing:
```
   - `04-council-verdict.md`: the LLM council's review of this plan (apply what it says before starting).
```
New:
```
   - `04-council-verdict.md`: the council's review of this plan (27 Nov 2026). Where it and this file differ, it wins. If it
     is missing, stop and ask the user. Do not run another council on this plan.
```
Line 15, existing:
```
2. `status/README.md` (what is done, pending, stuck; update it when you start, finish or get stuck on an item).
```
New:
```
2. `status/README.md` (what is done, pending, stuck; update it when you start, finish or get stuck on an item). Two rows
   meet this plan: "Ask plan writer" (In progress, waiting for the Colab run, then llama.cpp on the server) is superseded,
   since the plan writer stays offline: move it to Pending when you start. "Ask CIP without AI per answer" (Pending, the
   user's go) is this work: set it to In progress. The "Ask rebuild" row's rule still holds: a trained model only where a
   fresh held-out set shows a gap rules cannot close.
```
Why: a new agent would either stall on a missing file or run the council twice. It also could not tell whether
status/README.md or PROMPT wins on the plan writer.

### 12. Should fix: Phase 2 order, significance, and what the tests check

Lines 136-141, existing:
```
- Implement the layout from `01-template-spec.md` for every answer type it defines (latest value, trend, compare groups, rank
  answers, two periods, one group within another question, two answers combined, grids, multi-select, ranges, nets, China,
  Both-markets ask-back, typed follow-up, "why" and unusual readings, ambiguous ask-back, no survey asks it, small samples, a
  period the survey did not run). Work through G1-G34.
- The headline is one sentence from a pattern per answer type; "rose"/"fell" only when the change is significant, otherwise
  "about the same" (at about 400 people the margin is about +/-4.9 points).
```
New:
```
- First sort the 116 browser questions by answer type (T1-T20 in `01-template-spec.md` section 4.4) and count questions
  that fit none (for example "which surveys do you have?"). Build the types in that order, one at a time, each with its
  gaps from G1-G34, and report the order before you start. Every type in 01 is in scope; the order is not.
- The headline is one sentence from a pattern per answer type; "rose"/"fell" only when the change is significant by the
  existing two-proportion test (`api/dashboards.py:86` significant, 01-template-spec.md section 4.2), otherwise "about the
  same". Never hard-code a margin: +/-4.9 points is one figure at 400 people; a change between two such surveys needs about
  +/-6.9.
- Leave one test per answer type that checks the market, period, group, chart type and headline verb, not only which
  survey question was picked.
```
Why: T1-T20 plus G1-G34 in one unordered phase invites overbuilding. A hard-coded 4.9 would call noise a rise. And
today's scorers never check the new layout.

### 13. Should fix: §5 gets an owner, a deadline and defaults

Lines 173-177, existing:
```
## 5. Open questions to ask the user (the manager decides)
From `01-template-spec.md`: show "unweighted"? keep the number of people asked in Excel? horizontal bars for long ranked lists
(the chart guides recommend them)? a weekly view for weekly questions? a side-by-side option for Both? does a country named in
the question override the selector? neutral or green/red arrows? always ask back when two questions fit, or answer the best
match first and offer the other (today's choice, 12 Nov)? how to warn about small samples without showing the base?
```
New:
```
## 5. Open questions for the manager (send them with the Monday deliverables; build with the default until answered)
From `01-template-spec.md`: show "unweighted"? [no; say "Census-weighted" only when it applies] keep the number of people
asked in Excel? [no] horizontal bars for long ranked lists (the chart guides recommend them)? [vertical, as decided; the
mock-ups show both] a weekly view for weekly questions? [no] a side-by-side option for Both? [no: US and China buttons]
does a country named in the question override the selector? [yes] neutral or green/red arrows? [neutral] always ask back
when two questions fit, or answer the best match first and offer the other? [answer the best match and offer the others,
today's choice] how to warn about small samples without showing the base? ["Fewer than 50 people answered here: read
with caution", 01 section 4.3] a market and a question ask-back in the same answer? [ask the market only, then answer the
best match and offer the others]
```
Why: several of these block Phase 2. Nothing said who answers them, by when, or what to build in the meantime.

### 14. Should fix: tell the user what "trained model" means

Line 181, existing (insert the new text after it):
```
any decision needed. Plain words, short. Never claim a gain you did not measure.
```
New (added after line 181):
```
In your first report, tell the user plainly what "our trained model" means here: small models on our server pick which
survey question, market, group and period a question means; code computes every figure; fixed patterns write every
sentence; no model writes text. Today it picks right for 79% of the real set and 15 of 30 unseen combined questions. The
honest aim is fewer wrong answers, with "Not what you meant?" or "no survey asks this" for the rest, not 100%.
```
Why: the user expects "the trained model answers everything". Without this, the agent will overpromise against a 15/30
unseen baseline.

---

## 3. Disagreements left open

| # | Question | Options | Who decides | Default until decided |
|---|---|---|---|---|
| 1 | Ask back when two survey questions fit? | Ask first; or answer the best match and offer the others | Manager | Answer the best match and offer the others (today, 01 C24) |
| 2 | Who writes the blind test questions and checks the sample answers? | 3-5 named analysts; or the user alone | User, with the manager | Samples marked "awaiting analyst check"; held-out-2 plus post-27-Nov browser questions from other accounts; every result labelled provisional |
| 3 | Staging's AI budget | Lower `CIP_ASK_BUDGET_USD` from 10 to 0.50; or keep it | User | Treat staging as uncapped; add no new paid calls there |
| 4 | A paid fallback at all? | gpt-4o-mini under the cap; or none | User | None until a funded key and the cap are confirmed; answer "no survey asks this" with the closest questions |
| 5 | Bar direction and showing the base | Vertical as decided, or horizontal (02's advice); hide the base, or show it | Manager | Vertical, base hidden, small-sample warning in words; the mock-ups show both bar directions for one ranked list |
| 6 | Market default | Both with an ask-back (decided); or the market the question implies, otherwise US (02's advice) | Manager | Both; a country named in the question wins; never two ask-backs in one answer |
| 7 | Latency target | 300 ms; or no worse than today and under 500 ms | User | No worse than today's p95 in the same container, and under 500 ms |
| 8 | Fine-tune bge-small again? | Yes; or no | User, after Phase 0's per-miss split | No, unless the split shows finding losses that hybrid search cannot fix; score it only inside Ask |
| 9 | The plan-writer notebook and data | Keep for offline labelling; or retire | User | Pending, offline only; fix its candidate-insertion flaw (`scripts/ask_plan_pairs.py:256`, `:323`) before any use |
| 10 | Expansionist ideas not adopted now: answers precomputed at publish, stable question IDs used by every label, logging ask-back choices and MCP asks (no emails) as free labels | Adopt now; or later | User | Later: a publish already takes 1,203 s; revisit once the ask-back decision (1) is made |
