# Council verdict: CIP vs competitors (12 Nov 2026)

5 advisors (Contrarian, First Principles, Expansionist, Outsider, Executor), 5 anonymous peer reviews, 1 chairman.
Check after the verdict: the served Trends for Q22 holds one wave, so the reused-code join is in Ask's concept layer, not in Cross-tab / Trends data.

## Where the Council Agrees

- **Trust is the most dangerous lag, more than any missing feature.** All five said the three Ask defects (Gen Z dropped, made-up "100%" turkey answer, "6 months" read as 12) are confident wrong answers. Over MCP they reach a client's chat with no analyst checking them. One bad number in a board deck ends the renewal.
- **"Not in the surveys" must be a proper answer.** Ask should default to the latest weekly wave, return every group the question names, and treat "last 6 months" as 26 weeks.
- **Don't race on scale.** 400 a week against Morning Consult's 30k a day can't be won. All five said to ignore synthetic panels and the race to add markets. Four of five also said to ignore the agent feature race.
- **The moat is Ask grounded in Coresight's written reports.** All five named it: the figure, its base, and the analyst paragraph that explains it. No panel vendor can copy that.
- **Merge the 5 z-test copies.** If two screens disagree on significance, clients stop trusting all of them.
- **Sales basics are missing.** There is no pricing, scale numbers differ across docs, `clients: {}` is empty, and unknown emails get enterprise access.

## Where the Council Clashes

- **SOC 2 now or later.** The Executor and the Contrarian say procurement at YouGov-buying clients will ask for it, and signing with Vanta or Drata is a contract, not engineering. The First Principles Thinker says wait for a named deal. The real disagreement is about lead time. Type I takes months, so waiting for a deal means losing that deal.
- **Expand or focus.** The Expansionist wants a buy-side alt-data product, a weekly India wave, a free MCP funnel and licensing data to Simile and Aaru. The other four say focus: one product isn't sold yet. The Expansionist is betting on upside; the others are betting on execution capacity.
- **MCP's role.** The Expansionist sees it as the sales funnel. The Outsider says buyers don't know what it is. The First Principles Thinker says the race is over, since CIP already has one. All three can be true: it is distribution, not a pitch.
- **BI connectors.** The Executor contradicts itself: it says to ignore them, then schedules Power BI. The First Principles Thinker says ignore them.
- **Weighting.** Only the Outsider says unweighted-by-default will be read as "Americans." The rest don't mention it.

## Blind Spots the Council Caught

- **The reused-code join is a data-integrity bug, not just an Ask bug.** Only the Contrarian saw it, and all five reviews raised it. Cross-tab, Trends and Alerts may join under the same reused codes. The fix becomes an audit of every question code joined across waves.
- **Commissioned studies can leak.** Defect 1 pulled from a one-off study. Combined with "unknown email gets enterprise," a client-paid study (T-Mobile) may be visible to any outsider and to another client's Claude chat.
- **Data rights.** Do the Forsta/Decipher panel terms allow resale, API/MCP delivery, sending answers to outside LLMs, or licensing for AI calibration? For the Baidu China data, PIPL rules on cross-border transfer apply.
- **Weighted significance.** Plain z-tests on raked data overstate significance. They need a design-effect correction, built in before the five copies are merged.
- **Opt-in panel fraud.** At 400 a week, a few bot or LLM respondents move headline numbers, especially in Gen Z cuts.
- **Proof of accuracy.** No advisor proposed benchmarking CIP's series against U. Michigan or Ipsos.
- **Buy-side compliance** (material non-public information, data provenance) sinks the Expansionist's investor play for now.

## The Recommendation

- **Position CIP as the evidence layer behind Coresight research, sold inside existing subscriptions.** It is not a rival to Morning Consult.
- **Month 1, safety and correctness:**
  - Deny unknown emails by default, and lock each client-commissioned study to the client who paid for it.
  - Audit question codes reused across waves on every screen, not just Ask.
  - Fix the 3 Ask defects and add each to `scripts/ask_golden.yml`.
  - Merge the z-tests into one, with the design-effect correction.
  - Get a legal opinion on Forsta and PIPL data rights.
  - Set pricing and one public set of scale numbers.
  - Sign the SOC 2 Type I contract. On lead time, I side with the Executor and the Contrarian.
- **Months 2–4, the moat:**
  - Ground Ask in Coresight's written reports, with citations.
  - Add an applicability check that shows the base n before analysis.
  - Label every chart weighted or unweighted.
  - Publish a benchmark against U. Michigan.
  - Add bot and attention screening.
  - Add per-tenant SAML.
- **Months 4–6:** offer free toplines through MCP only after the golden tests hold. Run the comps backtest as a cheap, internal experiment.
- **Answer:** source citations (Euromonitor, Mintel, Statista) and Statista's applicability check.
- **Ignore:** sample size, market count, synthetic panels, agent feature-matching, and the warehouse connector.
- **Success at 6 months:** 3–5 paying subscribers, plus a log of the questions Ask failed to answer, which becomes the roadmap.

## The One Thing to Do First

Change the access default so unknown emails get no access instead of enterprise, and restrict client-commissioned studies to the client who paid for them. Right now a client's private data may be readable by anyone. That one exposure outweighs every competitor gap.
