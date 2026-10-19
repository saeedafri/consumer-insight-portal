# Gaps the council added

This file lists only what the council found *beyond* the REA ledger ([`docs/REA Claude/02-identified-gaps.md`](../../REA%20Claude/02-identified-gaps.md), G-01 to G-44). Labels:
- **Fact-checked:** the moderator verified it against evidence.
- **Open:** a question nobody can answer from the repo.

| ID | Gap | Raised by | Status |
|---|---|---|---|
| CG-01 | **The hibernated-survey request has no owner and no deadline.** It is the highest-stakes item and the least specified. | Contrarian, Executor | Open. The owner sends it with a reply-by date. |
| CG-02 | **The gate has no date**, so "confirm external clients" could defer forever and turn hardening into a permanent state. | Contrarian, R1, R5 | Closed by the verdict: gate review on **Tue 1 Dec 2026**, and the next one no later than 2 Mar 2027 |
| CG-03 | **Was the leaked credential ever used?** Rotating it doesn't answer that. | R1–R5 | Open. Pull the Azure MySQL audit or connection logs for `mohdsaeedafri@%`. |
| CG-04 | **Bus factor of one.** No second operator is named, and the cloud move does not fix this. | Outsider, Contrarian, R1, R3, R5 | Open. Name a second operator in week 2 and hand them `docs/technical/08-operations-runbook.md`. |
| CG-05 | **Recovered waves need the same proof as wave 412:** reconcile against Forsta, recompute cube and concepts, re-run the tracker-line comparison. | R1, R2 | Open. Add it to the recovery exit criteria. |
| CG-06 | **Licence to resell or show panel data externally** is unknown. It gates any client product, syndication or AI layer. | Contrarian, R2–R5 | Open (legal) |
| CG-07 | **Cost and sponsor.** Nobody priced engineer-days, Azure spend or the tracker's commercial value, or named who decides at the gate. | R3 | Open |
| CG-08 | **Forsta reactivation or export may cost money or be limited by contract terms.** Older surveys may also already be gone. | R2 | Open. Ask in the same request as CG-01. |
| CG-09 | **The pending leak:** the untracked Gemini docs could be committed by accident. | R5, fact-check | Fact-checked (REA Claude E-01). Redact before any `git add docs/`. |
| CG-10 | **The backup is single-machine.** The off-machine copy failed, and the script is untracked. | R2, R4, R5, fact-check | Fact-checked (E-17) |
| CG-11 | **Privacy posture.** The respondent table holds a pseudonymous ID (an unsalted hash) and the Forsta UUID. A breach-duty assessment has not been done. | R4, fact-check | Open. Salting the hash is REA G-26. |
| CG-12 | **The framing itself leaned on rebutting one benchmark** ("61.8 s"), and plain-language definitions of the jargon were missing. | Outsider | Noted. The plain-language glossary is in `../action-plan/01-action-plan.md`. |

## Corrections the peer round needed

Advisors and reviewers assumed the leaked password was already "in public git history, forks and caches". The evidence says otherwise: it was **never committed** (`git log --all -S` finds nothing). So the fix is rotation plus redaction. Rewriting git history is not needed.
