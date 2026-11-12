# Ask Coresight question bank: who asks what, and how Ask scores (12 November 2026)

The bank itself is `ask-question-bank.csv` (10,707 rows), written by `scripts/ask_question_bank.py` from the
published catalogue (3,082 survey questions: 3,068 US, 14 China, staging's data of 12 Nov 2026). Every row names the
survey question that answers it, so a right answer is known before the question is asked.

## Who uses the portal, and what they ask

Sources: how comparable products describe their users (Morning Consult AI and its AI Connector, YouGov's Crunch AI
agent, NIQ Ask Arthur, Tastewise, Collage), market-research practice writing (Quirks, FlexMR, Locally Optimistic,
QuestionPro, Attest), Coresight's own published weekly survey notes, and the 63 questions people typed in CIP's
audit log (`cip_access_log`, action `ask`). Reddit's search could not be read on 12 Nov 2026 (the site returned an
error page), so no Reddit thread is used.

| Who | What they come for | How they ask | In the bank |
|---|---|---|---|
| Analyst (Coresight research team) | The exact figure for a report: a wave, its base, a cut, a change and whether it is significant; a series for a chart | Short, precise, often the question's own name: "Tariff concerns by generation", "BD5 trend since Aug 2025", "Q3 2026 vs Q3 2025" | 6,202 rows: latest with base, trend, by generation / income / region, Gen Z vs Boomers, year vs year, by quarter, top answers |
| Portal user (Coresight staff outside research: sales, editorial, events) | A number to quote and a chart to paste | Plain words, one topic: "What do consumers say about Amazon Prime?", "Is holiday spending rising or falling?" | 2,268 rows: what consumers say, one answer's share, rising or falling, season-specific |
| Client (retailers, brands, investors) | A decision: who to target, whether something is growing, what changed since last year | A business question with the topic inside: "Should we act on tariff concerns?", "Which generation over-indexes on buy now pay later?" | 2,237 rows: decision, target audience, momentum, year on year |

What comparable products show: users want the figure *with* its audience, period and comparison (Morning Consult's
example: one brand's favorability by quarter, in three countries, for one audience); the answer must come from the
vendor's own survey data, never from the model; and an answer built from a verified, curated question is labelled as
such. Seasons drive a large share of retail questions (holiday, back-to-school, Black Friday, Prime Day, Valentine's,
Easter, Mother's and Father's Day, Memorial Day, Fourth of July, Halloween, Thanksgiving): 2,213 bank rows name one.

## How Ask scores on the bank (quick answer, no AI model)

| | Right |
|---|---|
| All 10,707 | 4,795 (44.8%), of which 1,042 from the same question asked in another study |
| Analyst / user / client | 46.8% / 61.3% / 22.4% |
| Latest / top answers / year vs year / trend / cut | 52.3% / 68.0% / 73.0% / 38.9% / 33.6% |
| Speed | median 11.6 ms, 95th percentile 18.7 ms (the server's own time) |

The 161-question golden set scores 86% because it asks about the topics people ask most; the bank covers every
question in the catalogue, including 2019-2023 ad hoc studies that asked nearly the same question with other words.
What goes wrong: the wrong survey question (4,241), a cut the survey cannot give or did not show (1,290; some ad hoc
and business-to-business studies hold no generation or income, so the bank's cut row is itself unanswerable there),
no answer (268), no trend (113).

## What reaches 99%

Choosing one of 3,082 questions from free text cannot reach 99%: many questions differ only by study and year, and a
client's "Should we act on…" carries few of the survey's words. The products that claim trust do the same thing:
a verified question is answered from its stored answer, exactly; anything else is labelled as a best match.

1. A verified-answer table built from this bank once reviewed: the exact wording (normalised) → the survey question,
   period, cut and kind. A match is answered from it at once (a dictionary lookup, under a millisecond on the server)
   and marked verified; these rows are right by construction.
2. Questions near a verified one (same meaning, other words) take its reading, then the figures are computed as now.
3. When two studies asked the same question, Ask says which it used and offers the other, instead of choosing silently.
4. The bank's rows that fail today become the test: the score is reported per persona and kind after every change.
