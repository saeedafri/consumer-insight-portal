# LLM Council Claude: the CIP review

**Date:** 20 October 2026 · **Moderator:** Claude (Opus 5.5, Claude Code) · **Method:** the `llm-council` skill (Karpathy-style), run as real independent sub-agents

The council reviewed the codebase, its assets, and two competing plans:
- **Plan G:** Gemini's REA build plan, a React/FastAPI rewrite.
- **Plan C:** Claude's REA build plan, hardening plus a gate.

It was grounded in the verified facts from [`docs/REA Claude/`](../REA%20Claude/00-README.md).

| Folder | Contents |
|---|---|
| [00-framing/](00-framing/framed-question.md) | The neutral question every advisor received |
| [advisors/](advisors/) | Five independent responses (Sonnet sub-agents): Contrarian, First Principles, Expansionist, Outsider, Executor |
| [peer-reviews/](peer-reviews/01-peer-reviews.md) | The anonymised bundle, five reviews, the tally, and the moderator's fact-check |
| [chairman-verdict/](chairman-verdict/01-chairman-verdict.md) | The final verdict (Opus sub-agent) |
| [identified-gaps/](identified-gaps/01-council-gaps.md) | Twelve gaps the council added beyond the REA ledger |
| [action-plan/](action-plan/01-action-plan.md) | The dated plan to the 1 Dec 2026 gate, plus a plain-language glossary |
| [comparison-vs-gemini/](comparison-vs-gemini/01-claude-vs-gemini.md) | Claude vs Gemini: method, accuracy, coverage, recommendations, what Gemini did best, and a merged plan |

**Peer-review result:**
- Strongest: the First Principles Thinker (3 of 5 votes). The Executor and Contrarian got 1 each.
- Biggest blind spot: the Expansionist (5 of 5). It argued for selling the data without addressing the leak, the gaps or the licence.

**Verdict:** run Plan C, amended by the council. Review the rewrite at a dated gate on **Tue 1 Dec 2026**.

**First action:** today, send the Forsta admin a written request to reactivate or export the 51 hibernated surveys, with a reply-by date.

**Model used: Claude.**
