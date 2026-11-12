# Council transcript: advisors and peer reviews (12 Nov 2026)

# ADVISOR RESPONSES (de-anonymised; peer reviews used the letters in brackets)

**The Contrarian (was Response B):**

**The fatal flaw is trust, not missing features.** CIP is going to clients who already pay for Morning Consult (30k interviews a day), CivicScience (millions of responses a day) and YouGov. CIP's sample is about 400 unweighted opt-in adults a week, which means ±4.9 points on the total and worse on every subgroup. Data volume is not a moat, so trust is the only thing CIP can sell. And Ask Coresight is losing that trust today:

- **Temu, Gen Z vs Boomers:** it dropped Gen Z and answered from the wrong survey.
- **Thanksgiving turkey (never asked):** it made up a "100.0%" by joining waves under a reused question code.
- **"Last 6 months":** it read this as 12 months, and both halves show the same base.

The MCP connector sends these answers straight into a client's Claude chat, under Coresight's name, with no analyst checking them. One wrong number pasted into a client's board deck ends the renewal. The reused-code join also points to a data integrity bug, not just a parsing one: Cross-tab, Trends and Alerts may have the same problem. Freeze Ask over MCP until there is a strict "not in the surveys" refusal and an audit of every question code joined across waves.

**Procurement will block the sale before quality comes up:**
- Unknown emails get enterprise access, and no client is configured yet.
- No SOC 2, no SAML per tenant, no SCIM.
- One worker on 1 vCPU.
- No pricing.
- Scale numbers that disagree across docs, which a diligent buyer will notice.

**Ignore:** synthetic panels (Simile, Aaru), the 40+ market race, and matching agent features with GWI Spark or Morning Consult's agents. CIP loses all three on resources.

**The question you're avoiding:** why would a Numerator or Circana client pay for this when Ipsos, Deloitte ConsumerSignals and U. Michigan give toplines away free? "Lead the segment" assumes there is a segment. The only answer I see is Coresight's retail analysts interpreting a weekly series that has run since 2020. But Ask isn't grounded in Coresight's written reports, so the one thing nobody else has is the one thing the product leaves out. Six months: make it correct, make it pass procurement, connect it to the reports. Then sell.

**The First Principles Thinker (was Response E):**

**You're asking the wrong question.** "Lead its market segment" assumes CIP is in Morning Consult's segment. It isn't, and it never will be. 400 adults a week against MC's 30k a day, YouGov's 30M panel and GWI's 50 markets is not a gap you close in 6 months, or ever, on Coresight's budget. Every client in the brief already pays for scale. Selling them a smaller panel loses.

So what does a buyer get from CIP that they can't get from those vendors? Three things:
1. **Retail-specific question continuity since 2020.** The same retailer and sector questions, asked every week.
2. **Coresight analysts' interpretation**, tied to retailer earnings and news.
3. **A weekly US + China pair.** Almost nobody sells that.

CIP is the evidence layer behind Coresight's research. It is not a rival data platform. Build toward that.

**The most dangerous lag is trust, not features.** All three staging defects are confident wrong answers:
- The Temu question came back as Boomers only, from an April one-off study, with Gen Z dropped.
- The turkey question, which was never asked, came back as "100% answered 'Things cost more this year'".
- "Last 6 months" was read as 12 months, with both halves showing the same base.

On a ±4.9-point panel, one bad number in a client's deck ends the account. "Not in the surveys" has to be a first-class answer. Default to the latest weekly wave. Check that every requested group is present before answering. Merge the 5 z-test copies into one, because it decides which numbers get called significant. That's month one.

**Answer one competitor move:** grounding answers in your own reports. Euromonitor, Mintel and Statista all cite sources. Ask Coresight should answer with the figure, its base, and the Coresight report paragraph that explains it. Only Coresight has that paragraph. It is the moat.

**Ignore:**
- The MCP arms race. CIP already has one.
- Synthetic panels like Simile and Aaru.
- More markets.
- Snowflake and Power BI connectors.
- SOC 2, until a named deal requires it.
- Rewriting the browser perf meter and monitoring dashboard. Delete them and use Azure Monitor.

**The real gap:** `clients: {}`, and pricing is undecided. Nothing has been sold. Six months from now, "leading" should mean 3–5 paying Coresight subscribers using CIP inside their existing subscription, plus a log of the questions it failed to answer. That log is the roadmap. Competitor feature lists are not.

**The Expansionist (was Response D):**

Everyone will tell Coresight it is outgunned on sample size: 400 a week against Morning Consult's 30k a day. That's the wrong race. CIP's undervalued asset is **370 consecutive weekly waves since Dec 2020, tied to a retail analyst brand.** No panel vendor has that combination. Three upside plays:

**1. Sell to investors, not just brands.** Expected vs actual, the Retailer databank and the weekly trackers are close to an alt-data product already. Backtest five years of weekly shopper intent against retailers' reported comps, then sell a "pre-earnings consumer read" to the buy-side. That's the market Bloomberg Second Measure, Consumer Edge and Facteus sell into, and it pays several times what brand budgets do. Prosper puts its data on AWS Marketplace, so Coresight should list there too.

**2. Become the weekly US + China tracker, then add India.** GWI runs quarterly waves and Statista runs ad hoc studies. A same-week US and China read on Temu, Shein and trade-down is rare. The build team is in India, and Redseer and Axis My India only publish monthly. A weekly India wave would make it a three-market weekly tracker that nobody else offers.

**3. Make MCP the sales funnel.** Morning Consult's connector is an enterprise-only alpha, and YouGov licenses BrandIndex MCP separately. CIP's Ask already runs in milliseconds with a $0.50 a month cap on the optional LLM, so it is cheap enough to give away. Copy Numerator's free tracker and CivicScience's free Poll of the Day: free toplines in Claude and ChatGPT, with gated cross-tabs and Boards. Ground Ask in Coresight's written reports so every number comes with the analyst's verdict. That pairing is the moat Morning Consult can't copy.

**Bonus: license the ground truth.** Simile ($2B) and Aaru ($1B) need real weekly answers to calibrate their synthetic panels, and 190k responses over five years is exactly that. Selling them the data beats trying to compete with them.

**Answer:** the race to be inside AI tools (GWI Spark, Statista MCP), and Statista's audience applicability check. **Ignore:** the market-count and sample-size arms race. And fix the three Ask defects first, because a wrong answer kills a free funnel.

**The Outsider (was Response C):**

I'm a buyer who already pays for Morning Consult. Here is what I'd see.

**Why would I pay for this?** The brief compares feature lists. It never says in one sentence what CIP gives me that I can't get elsewhere. "400 people a week" next to "30,000 a day" ends the comparison unless you change what's being compared. Your real edge is a retail-research firm's own weekly panel, unbroken since 2020, tied to retailer shopper profiles and to the analysts I already read. So Ask must quote Coresight's written reports. I'd assume it already does. Finding out it doesn't would feel like a bait-and-switch.

**The three Ask defects decide whether I buy.** I ask about Gen Z vs Boomers at Temu, the answer drops Gen Z and uses an April study. I ask about turkey prices and get "100% said things cost more." I'd screenshot that and forward it to my team as proof the tool makes things up. A wrong answer given confidently is worse than no feature at all. Before any sale, Ask must say "we didn't ask that" and must use the latest weekly wave by default. Nothing else on the list matters as much.

**Unweighted by default is a trap.** I will read every percentage as "Americans." Make Census weighting the default, or put a label on every chart.

**"Unknown emails get enterprise"** reads to me as "anyone gets everything." My security team would end the evaluation over that.

**Things I don't care about:** MCP, Benjamini-Hochberg, 30 screens, the competitors' "agentic portfolios." Show me 3 screens, not 30. Don't chase the MCP race in your pitch. I don't know what it is.

**Code clean-up only matters if I can see it.** Five separate significance tests are fine until two screens give me different answers for the same week. Then I stop trusting all of them. Merge them into one. Skip the monitoring rewrite.

**Before anyone calls me:** decide pricing, use one consistent sample-size number everywhere, and have one real client set up.

**The Executor (was Response A):**

**Monday, before any sales call:** set unknown emails to deny-by-default. Right now `clients: {}` is empty and unknown emails get *enterprise*. Change the default to no access or demo, set up the first paying client's tenant, survey visibility and menus, and test it with a throwaway outside account. That is one day of work, and nobody should sign until it's done.

**Week 1-2: fix Ask Coresight before anyone outside sees it.** The three staging defects will each lose a deal on their own:
1. A two-group comparison ("Gen Z vs Boomers") has to return both groups, from the latest weekly wave by default.
2. When no question fits ("Thanksgiving turkey price"), Ask must say "not in the surveys" and not show a near match. Joins across a reused question code need a check that the wording matches.
3. "Last 6 months" means 26 weeks, one range.

Add all three to `scripts/ask_golden.yml` so they can't come back. The MCP connector already does what Morning Consult only offers in alpha, but it has to be trustworthy first.

**Week 2: merge the 5 z-tests into `shared/`.** A client who sees two screens disagree on significance won't come back.

**Month 1: start SOC 2 Type I with Vanta or Drata.** That's a contract signed this week, not engineering work. Procurement teams at clients who already pay YouGov will ask for it. Also add per-tenant SAML. OIDC already exists, so this is extending what's there.

**Month 1: pick a price and one set of public scale numbers.** Without them, sales can't send a quote.

**Months 2-6, in order:**
- An applicability check that shows the base n before analysis (Statista has one; it's the cheapest gap to close).
- Ask answers grounded in Coresight's written reports, which no panel vendor can copy.
- Results to Power BI through the existing API.

**Ignore:** competing on sample size (400/week vs 30k/day can't be won), synthetic panels, new markets, a BI warehouse, respondent-level delivery. Delete the 1,400-line home-built monitoring dashboard and use Azure Monitor.

None of this needs new infrastructure. Most of it is config, tests and contracts.

# PEER REVIEWS

**Review 1:**

**1. Strongest: A.** It is the only response that answers all three parts of the brief in order and as concrete actions. It treats "unknown emails get enterprise" as a day-one blocker, not a footnote. It turns the three Ask defects into golden tests so they can't come back. It counts SOC 2 as a contract to sign, not engineering work. Its weakness is that it keeps the reused-code join inside Ask. B is the only one to see that this is a data-integrity bug that may also affect Cross-tab, Trends and Alerts, and that point should be added to A's plan.

**2. Biggest blind spot: D.** It proposes four expansions: buy-side alt-data, a weekly India wave, a free MCP funnel and licensing data to synthetic-panel firms. The team is small and can't yet sell one product. D never mentions access control, SOC 2 or pricing. A backtest of retailer comps at n≈400 a week is statistically thin. Giving Ask away free spreads its confident wrong answers at scale. Licensing respondent data assumes Coresight has the rights to do so.

**3. What all five missed:**
- **Data rights.** Do the Forsta/Decipher panel terms and Baidu QSS (China's data-export rules) allow resale, API/MCP redistribution or licensing to third parties?
- **Respondent fraud.** In 2026, opt-in panels are being polluted by bots and LLMs answering surveys. At 400 a week, a few fake respondents move the headline numbers.
- **Liability and citation terms** for figures that land, unreviewed, in clients' AI tools.

**Review 2:**

**1. Strongest: A.** It's the only response that gives an ordered plan you can act on: deny-by-default access on day one, the three Ask fixes added to the golden test file, then merging the z-tests, a SOC 2 contract, pricing, and the applicability check. One flaw: it says to ignore BI connectors, then schedules Power BI for months 2-6. B makes the sharpest single point: the reused-code join is a data integrity bug, so Cross-tab, Trends and Alerts may be wrong too. A should take that on and audit those joins.

**2. Biggest blind spot: D.** It wants buy-side alt-data, a weekly India wave, a free funnel and licensing data to synthetic-panel firms, before one client is configured or procurement basics are in place. At n≈400, subgroups are too thin to backtest against retailer comps. Buy-side buyers also need data-provenance and MNPI (material non-public information) compliance, which D doesn't mention.

**3. What all five missed:**
- **Commissioned-study leakage.** Defect 1 pulled from a one-off study. Studies paid for by clients (T-Mobile) sit in the same store that Ask and MCP read across. One client's private data could reach another client's Claude chat.
- **Panel redistribution rights.** Does Coresight's licence for the Forsta/Decipher opt-in sample allow resale, API delivery, sending answers to outside LLMs, or (per D) licensing to Simile?
- **China data.** Baidu QSS responses served to US clients may raise PIPL (China's data-protection law) cross-border transfer questions.
- **Panel fraud and attention checks** on a 400-person opt-in sample.

**Review 3:**

**1. Strongest: B.** B is the only response that sees the reused-code join as possibly a data-integrity bug, not just an Ask parsing bug, and asks whether Cross-tab, Trends and Alerts have the same fault. It also lists the procurement blockers: the enterprise default, SOC 2, SAML, one worker and pricing. And it asks the hard question of why anyone pays when toplines are free. Its weakness is sequencing, which A does best.

**2. Biggest blind spot: D.** D proposes selling to investors, a free MCP funnel, a weekly India wave and licensing data to Simile and Aaru, all on 400 unweighted opt-in respondents a week. A backtest against comps at ±4.9 points, and worse for subgroups, won't convince the buy-side. Investors also bring compliance work (material non-public information, data provenance). A free funnel spreads wrong answers further. D ignores the "unknown email gets enterprise" hole and procurement. E's "skip SOC 2 until a named deal" is also risky.

**3. All five missed:**
- **Data rights.** Does the Forsta/Decipher panel contract or respondent consent allow resale, API or MCP distribution, or licensing to AI firms?
- **China.** Under PIPL, can Baidu survey data be moved to US Azure?
- **Weighted significance.** Plain z-tests on raked data overstate significance. They need a design-effect correction before the five copies are merged.
- **Credibility.** Benchmark CIP's series against U. Michigan or Ipsos to prove 400 a week tracks reality.

**Review 4:**

**1. Strongest: B.** It is the only response that reads the turkey defect as a likely data-integrity bug and not just an Ask parsing bug: questions joined across waves under a reused code could also corrupt Cross-tab, Trends and Alerts. That changes the fix from "patch Ask" to "audit every question code joined across waves." B also covers procurement blockers (open access, SOC 2, SAML, 1 vCPU) and asks why anyone would pay when Ipsos, Deloitte and Michigan give toplines away free. A is the best checklist (deny-by-default on day one, golden tests) but treats the defects as isolated. E has the best success measure (3–5 paying clients plus a log of failed questions).

**2. Biggest blind spot: D.** It pitches the buy-side, a free MCP funnel, India waves and licensing data to Simile and Aaru while Ask gives confidently wrong answers and unknown emails get enterprise access. Funds won't buy alpha from ~400 unweighted opt-in respondents without weighting, point-in-time history and backtest proof. D also never asks whether Coresight has the right to resell the data.

**3. All five missed:**
- **Data rights:** Can Forsta panel data (source 114) be resold or served raw through the API and MCP?
- **Commissioned-study leaks:** With open access, T-Mobile's private study is visible to any outside email.
- **China compliance:** PIPL cross-border transfer rules for the Baidu survey, and how US buyers see China data.
- **Opt-in panel fraud:** Bot and inattentive respondents, especially in Gen Z cuts.

**Review 5:**

**1. Strongest: B.** It is the only response that treats the reused-code join as possible data corruption rather than a parsing bug. If Cross-tab, Trends and Alerts share that join, the problem is bigger than Ask. B also lists every procurement blocker (enterprise access for unknown emails, no SOC 2 or SAML, one worker on 1 vCPU, no pricing, inconsistent scale numbers) and asks the hard question about free toplines. A is the best checklist to execute. E adds the best success measure: 3–5 paying clients plus a log of failed questions.

**2. Biggest blind spot: D.** It proposes four expansions (buy-side alt-data, a weekly India wave, a free MCP funnel, licensing data to Simile and Aaru) while leaving out access control, SOC 2 and the single-worker server. Buy-side buyers will backtest against reported comps, and an unweighted opt-in panel of 400 a week with ±4.9-point error, worse for subgroups, is unlikely to hold up. A free funnel also invites traffic that 1 vCPU can't serve.

**3. What all five missed:**
- **Data rights.** Does Coresight's Forsta/Decipher panel contract allow resale, API/MCP delivery, or licensing for AI calibration? The China data, collected through Baidu QSS, also falls under China's data-export rules (PIPL) once sent abroad.
- **Proof of accuracy.** No one proposed publishing CIP figures next to U. Michigan or Census benchmarks to show the panel tracks reality.
- **Opt-in fraud and bot screening**, which buyers will ask about.
