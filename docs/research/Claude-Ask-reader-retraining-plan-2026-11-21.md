# Ask CIP: plan to retrain the reader on Colab (21 Nov 2026)

What to train, on what, how to judge it, and who does each step, so Ask picks the right survey question for the
misses that word-count rules cannot fix. No paid AI is used at any step (Colab compute only).

## 1. Why the reader, and not a new model

Ask finds about ten candidate survey questions by meaning, then its **reader** (`models/ask-reader`, a 23 MB MiniLM
cross-encoder distilled on 14 Nov from Qwen3-32B's picks, see ask-cip-model-training.md "v6") picks one or
"none of these". A reranker is exactly this kind of model, so the job is a better reader, not a new component.

Measured on 21 Nov (scratchpad `recall.py`, all three test sets, quick mode):

| Remaining miss | Right question among the candidates? |
|---|---|
| TikTok Shop purchases, Gen Z clothing online, groceries online (2), millennials' retailers, holiday groceries, tariff worry trend, personal finances (2), dining out cut back, AI assistants | Yes, 11 of 11, at positions 0-7 (8 of 11 in the first four) |
| Spend less on entertainment, Thanksgiving turkey | No survey asks it: the reader must learn "none of these" |
| Gen Z gift spend | No: the search, not the reader (the holiday budget question is not retrieved) |
| China economy | No China waves in the local copy: data, not a model |

So 13 of the 15 are the reader's to fix. Today's scores, the baseline any new reader must beat:

| Set | Today | Kept out of training |
|---|---|---|
| Golden (161, hand-checked) | 158 | Yes: the release exam |
| Fresh (50, real staging questions) | 48 | Yes: never tuned on |
| Researched (58, Claude's draft) | 48 | Only its reviewed copy may enter training (step 2) |
| Bench (2,000 generated, seed 7) | 44.8% right question | Yes |
| Teacher, Qwen3-32B (14 Nov) | 155 of 161 | |

## 2. The blocker: reviewed questions

`scripts/colab/ask_cip_train.py` (prepare → CPU preflight → train → evaluate and calibrate) refuses to train without
human-reviewed questions: at least 35 distinct ones in its dev split, 30 in test and 30 in "future" (asked after the
training publication), each split with answerable and "none" examples. Splits are hashed by question group (about 15%
test, 15% dev, the rest train), so this needs **about 250 reviewed questions**. Today there are about 20 distinct real
analyst asks (cip_access_log, 12 Nov), and the golden and fresh sets must stay out.

**The review sheet** (built 21 Nov 2026: `python scripts/ask_review_sheet.py build --out reports/ask-review-sheet.xlsx
--asks`, 230 questions; the research team fills it, about 2-3 hours). Only questions that reach the reader are in it
(a question matched by a stored name teaches it nothing), and never one from the golden or fresh sets:

| Source | Questions |
|---|---|
| Real asks typed in a browser on staging (cip_access_log), not already in the other sets | 12 |
| The researched set, scripts/ask_researched.yml | 53 |
| The misses above, two wordings each (scripts/ask_review_questions.yml; China left out, no China data locally) | 25 |
| Generated questions Ask gets wrong (scripts/ask_bench.py, seed 11; the bench scores seed 7), the generator's answer always among the choices; ones whose "wrong" pick has the same wording under another code are left out | 140 |

One row per question: the question, Ask's pick, its top 5 candidates (code, wording, waves, last asked). The reviewer
marks the right key, "none", or "also right" for near-twins (the same question another year). The sheet becomes the
`--expert` JSONL ({q, key, also, country, kind, observed_at, group}): `python scripts/ask_review_sheet.py read
reports/ask-review-sheet.xlsx --out reports/ask-reviewed.jsonl`, which stops on a mark it cannot read. The trainer counts
"also right" twins as acceptable picks (ask_cip_train.py record, checked 21 Nov on a scratch prepare: a twin marked
also right came through as a second acceptable choice), so a twin is never taught as a wrong answer (the v6 big-exam
lesson: 53 of 85 "losses" were twins).

## 3. Training on Colab Pro

1. **Prepare on the Mac** (`ask_cip_train.py prepare`). A reviewed question asked after the training publication's
   newest wave goes to the "future" split, so the sheet's questions (asked up to 21 Nov) can fill train, dev and test
   only with a training publication whose newest wave is on or after 21 Nov: `--train-published` staging's next weekly
   publication (from 23 Nov), rebuilt with the answer-label fix (prepare refuses the 10 Nov one: its manifest lacks
   `rules.answer_labels`), and `--test-published` the publication a week or more later; the analysts' questions in
   between, reviewed in a second short sheet, are the "future" split (checked 21 Nov on a scratch copy: with an older
   training publication every reviewed row went to "future"),
   `--expert` the reviewed JSONL, `--bank` docs/research/ask-question-bank.csv.gz (38,604 generated questions).
2. **Preflight on CPU** (`preflight`): must print ready. It checks the splits, the reviewed counts and the shipped files.
3. **Train on Colab** (`train`, GPU runtime: an L4 is enough for a 22M-parameter MiniLM; the 14 Nov run used an A100
   only for the 32B teacher). Start from today's reader, not from scratch, so it keeps what it knows. Three settings, one
   run each: epochs 1 / 2 / 3. Hard negatives come free: every case carries its own candidate list, so the near-misses
   (the luxury list for "clothing online", the beauty list for "TikTok") are what it learns against.
4. **No new teacher labels** unless the reviewed rows are too few: relabelling with Qwen3-32B costs ~2½-3 A100 hours
   and its picks are 155 of 161, below what reviewed labels give.
5. **Export** 8-bit ONNX plus a new `calibration.json` (its "sure" threshold recalibrated on dev: the gate that decides
   when Ask answers at once).

Colab time: a few minutes of L4 a run for the student. Check the units left on Colab's Resources panel before starting;
the free tier is not enough for the A100 relabel if that turns out to be needed.

## 4. When it ships (all must hold)

| Gate | Pass mark |
|---|---|
| Golden, inside Ask, quick mode | ≥ 158 of 161, no answer that is right today lost without a hand-checked reason |
| Fresh | ≥ 48 of 50 |
| Researched (reviewed copy, rows outside training) | none right today lost, and at least 4 of the 13 reader misses fixed across the sets |
| ask_cip_train test and future splits | beats today's reader on both, "none" right on the reviewed no-answer rows |
| Bench, 2,000 seed 7 | ≥ 44.8% |
| Speed and size | median ≤ 80 ms a question, file ≤ 30 MB |
| Processor | scored on x86 (staging's Azure workers) as well as the Mac: the 8-bit file picks differently on Arm and x86 (14 Nov: 26 of 746 picks) |

Then also run the three sets with today's word-count rules switched off (RARE_WORD switch, stale-pick rule, `unasked`).
If the new reader alone scores as well, those rules are deleted: one model instead of three heuristics.

## 5. Release and rollback

The reader is three files in git (`models/ask-reader/`), copied into the image by deploy/Dockerfile. Release: replace
the three files, run the full tests and the three sets, sync to cip-stg; the user commits and pushes. Rollback: the
previous three files from git. No code change unless the rules in section 4 are deleted.

## 6. Who does what

| Step | Who | Time |
|---|---|---|
| Build the review sheet | Claude | done 21 Nov: reports/ask-review-sheet.xlsx |
| Mark the sheet | Research team | 2-3 hours |
| Prepare, preflight, upload the bundle to Drive | Claude | an hour |
| Run the notebook (needs the user's Google account) | The user | ~30 min of attention |
| Score inside Ask on Mac and x86, report against the gates | Claude | an hour |
| Decide and commit | The user | |

## 7. Risks

- **Too few reviewed questions**: the preflight says so before any GPU time is spent; add more real asks as they come.
- **Training on the researched set then scoring on it**: only its reviewed copy is used, split by group, and the
  researched score in section 4 is read on its test split alone.
- **Overfitting to the gates**: golden and fresh never enter training; the bench and the future split are the checks
  nobody tunes on.
- **Gen Z gift spend and China** stay open: a search change and China data, outside this plan.
