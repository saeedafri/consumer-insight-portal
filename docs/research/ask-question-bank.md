# Ask Coresight: how every survey is made answerable, and how accuracy is measured (12 November 2026)

## What 99% means here

An answer is **right** when it uses a survey question that answers what was asked, from the right country, with the
period, cut and kind asked (a trend is a line, a cut shows its groups), and every figure is computed from the published
counts (exact by construction). Ask marks each answer:

- **Verified**: the question uses a survey question's stored name (its analyst name or an alias), so Ask answers from it
  directly. Target: right 99% of the time or more, measured on every survey.
- **Best match**: anything else (found by meaning, or a name several different questions share). The page says so and
  shows the question used and the alternatives, so an analyst checks it before quoting it.

No product answers 99% of free text with no checking: ThoughtSpot, Snowflake Cortex Analyst and Databricks Genie all
separate "trusted / verified" answers from the rest, as here.

## The workflow, every survey, automatically (etl/publish.py publish → etl/ask_quality.py after_publish)

| Step | What happens | Where |
|---|---|---|
| 1. Publish | The new wave's question files are written, as before | etl/publish.py |
| 2. Name | Every question wording not named yet gets an analyst name, aliases and eight example asks from the small model (~$0.002 a survey); kept in logs/ask-semantic.json on /home, so a deploy keeps them | etl/ask_semantic.py name_new |
| 3. Split shared names | Questions that got the same name but ask different things ("Economic outlook": the economy, and the pace of price rises) are named apart, once | etl/ask_semantic.py rename_shared |
| 4. Check | Every question the bank writes about the new surveys' questions (latest, trend, each cut its data holds, periods compared, top answers, one answer, season) is asked and scored, at low CPU priority, ~6 s a survey | etl/ask_quality.py check_surveys |
| 5. Show | Per survey: questions, named, asked, right, verified right, and the misses, on the Logs page | GET /api/v1/admin/ask/quality, logs/ask-quality.json |
| 6. Answer | The API's index reads the new names at its next build; a question using one is answered as Verified in ~5 ms | api/ask_index.py named |

A failure in steps 2-5 is logged and the publish stands. With no AI key, or the month's model budget spent, steps 2-3
wait for the next publish; the check still runs and shows the survey's questions without names.

By hand: `python -m etl.ask_semantic` (name into config/ask_semantic.json, reviewed in git),
`python -m etl.ask_quality --surveys <ids>` (check older surveys), `python -m etl.ask_quality --published <api/v1>`
(the whole catalogue, below).

## Who asks what (the bank's questions)

| Who | What they come for | How they ask |
|---|---|---|
| Analyst (Coresight research) | The exact figure for a report, its base, a cut, a change | "Tariff concerns by generation", "Recent clothing purchases by quarter" |
| Portal user (sales, editorial, events) | A number to quote, a chart to paste | "What do consumers say about Amazon Prime?", "Is it rising or falling?" |
| Client (retailers, brands, investors) | Who to target, what is growing | "Which generation over-indexes on Temu?", "Are women or men more likely to choose…?" |

Sources: Morning Consult AI and its connector, YouGov Crunch AI, NIQ Ask Arthur, Tastewise, Collage (vendor pages);
Quirks, FlexMR, Locally Optimistic (research practice); Coresight's weekly survey notes; CIP's own audit log.

## Results (quick answer, no AI model, staging's data of 12 Nov 2026)

| | Right |
|---|---|
| Verified answers, whole catalogue | **29,627 of 29,838 (99.3%)** |
| Newest four US weekly surveys (2, 9 Nov; 19, 26 Oct), all questions | 99.1% to 99.6% |
| The same, verified answers | 99.4% to 99.9% |
| Templated questions, whole catalogue (34,803) | 96.4% (analyst 96.8%, client 95.8%, user 95.8%) |
| Wording Ask never saw (3,801: the last two of each question's eight asks, held out from the search) | 40.4%, shown as Best match |
| Hand-written golden set (161) | 139 (86%) |
| Speed on the server | median 5.7 ms |

How it got there, each change measured on the same 5,000 questions: 71.3% → 75.4% (survey wording "past month" not a
period; a study asked in the period named; a quoted answer not the subject) → 79.0% (which generation / women or men /
South vs West read as cuts) → 82.0% (direction words kept: "spend more" is not "spend less"; a study that holds the cut
asked for) → 87.8% → 91.5% (shared names: the search picks among them, else the longest-running; one-word names;
"rising or falling" a trend). The bank also found a crash (a cut whose groups were never asked a question), now fixed.

## What is not yet 99%, and what moves it

- **Older one-off studies (2019-2023)**: many ask nearly the same thing in different words, so names collide. Step 3
  splits them at staging's first publish; the check shows the result per survey.
- **China (14 questions)**: no names yet (they were loaded after the last naming run, and there is no AI key here):
  88.2%; named at staging's first publish, then checked.
- **Wording no name covers (40.4%)**: answered as Best match. Each real question analysts type (cip_access_log) that
  an admin saves as verified on the Ask page becomes a stored answer, so the share of Verified answers grows with use.
- **Golden set "Economic outlook by generation"**: the name was given to the wrong questions; step 3 renames them.

The bank: `ask-question-bank.csv.gz` (38,604 rows: question, who, purpose, kind, country, season, the survey question
that answers it, and what Ask answered, how, in how long, and what was wrong).
