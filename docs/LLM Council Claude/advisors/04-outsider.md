# Advisor 4: The Outsider

*Independent sub-agent (Claude Sonnet). It saw only `00-framing/framed-question.md`.*

**What alarms me as a newcomer: the plan debate is a distraction from a house that's on fire.**

Read cold, this document describes a company whose main data product has these problems:

- About two-thirds of the recent weekly data is missing, and the integrity check says "all good" (exit 0). That check is lying to you. Nobody outside this project would trust a number from this system.
- The whole thing runs on one person's laptop, on a schedule, and it has already failed silently. If that laptop closes, production stops.
- The database password is in a public repo and was pasted into docs by a reviewer. Fixing that is not a "plan" with a gate. It's something you do today, before reading anything else.

Plan G's week-one "triage" is the same list Plan C does on day 1 and week 1, so the real disagreement is only whether to build a React app now. Nobody has asked for that app; the doc says "no external clients today." Building a client-facing product for a client who doesn't exist, on data that is silently incomplete, is how you ship embarrassment. The first customer who spots the gap in the trend chart ends the product.

Jargon I can't evaluate and the doc never explains: "hibernated surveys," "panel-licence terms," "small-cell suppression," "harmonised concepts." If these gate the whole business, they should be in plain words at the top.

Also odd: the doc calls itself a fair frame, yet half its facts exist to knock down the "61.8 s" claim. That feels like winning an argument, not weighing a decision.

**My call:** Plan C. But it's one engineer. Twelve days of work for one person with no backup is the real risk, and neither plan names a second human.
