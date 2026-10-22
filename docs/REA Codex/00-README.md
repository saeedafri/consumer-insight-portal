# Consumer Insight Portal investigation

Date: 21 October 2026, Asia/Kolkata. Author: Codex. Target: current working tree at HEAD `135c49634010c47658be3af643782f5ed184b643`, including pre-existing uncommitted changes.

CIP has a substantial survey analytics foundation. Its immediate competitive constraint is the consistency and repeatability of delivery: authorization differs across serving paths, analytical policies differ across screens, and the running local frontend/backend show contract failures. Persistent analyst workflows, presentation exports, customer alerts and governed AI are the next commercial opportunities. Purchase panels and POS intelligence require data rights and suppliers; interface features cannot supply them.

## Reading order

1. [System and data reconstruction](01-system-and-data.md).
2. [Consolidated gap register](02-gap-register.md).
3. [Competitor landscape](competitor-landscape.md) and [structured source register](competitor-sources.json).
4. [Proposed changes and acceptance gates](03-recommendations.md).
5. [Backend evidence](backend-evidence.md) and [frontend evidence](frontend-evidence.md).
6. [Verification and limitations](04-verification.md).
   [Implementation specifications](05-implementation-specifications.md) explain the proposed engineering contracts and acceptance checks. [Structured gap register](gap-register.json) contains31 open findings.
7. [LLM Council Codex](../LLM%20Council%20Codex/00-README.md): independent recommendations, anonymous reviews, chairman verdict and final validation.

## Evidence rules

**Source observed** means code exists in this checkout. **Runtime observed** means a specific controlled local browser journey was captured. **Vendor advertised** means an official public page describes the capability. **Inferred** means an analytical conclusion from those observations. **Unknown** remains unverified.

A source implementation is not a deployed capability. A vendor announcement is not independent performance proof. The competitive set is broad and bounded; it is not every competitor worldwide. No authenticated competitor tenant, proprietary source, private API or commercial contract was inspected.

The supplied name “Sirkana Unify Plus” resolves to **Circana Unify+**. REA captured its public product page; the public workflow does not expose its internal analytical engine.

## Stored evidence

The [evidence folder](evidence/) contains REA static analysis, local browser journeys, Circana public-page capture, isolated test results, source hashes and the exported REA ledger. The canonical REA bundle is approximately 33 MB before compression; summary files are easier to review. The bundle reports zero session-level unknown records, but the static graph itself contains **5,616 semantic unknowns**. These are distinct counters.

Old `REA Claude`, `REA Gemini` and council documents remain historical. Claims from them were not promoted into current findings without new support. This investigation does not certify current staging counts, rotate secrets, change access, commit code, restart the shared server or deploy fixes.

