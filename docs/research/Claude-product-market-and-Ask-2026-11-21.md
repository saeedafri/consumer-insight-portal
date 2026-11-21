# CIP: product, market and Ask CIP review (21 Nov 2026)

What CIP can do, where it stands against the market, what makes Ask CIP answers confusing, what was fixed today,
and what to do next before launch. Evidence: the local review server on :8001 (published data of 10 Nov, newest
wave 16 Nov 2026), the Ask golden set, the code, and web research (sources at the end).

**Method note on REA.** The REA reverse-engineering toolkit (github.com/morluto/rea) is installed and connected as an
MCP server. It is built for shipped binaries, packages and runtimes. Its own instructions say to use normal repository
tools when the full source is available, which is the case for CIP. It cannot legitimately be pointed at competitors'
private platforms. So the competitor picture below comes from their public pages, and CIP's picture from its code and
its running screens.

## 1. What CIP does today

| Area | What a user gets | Menu |
|---|---|---|
| Ask CIP | A question in plain words is answered from the published survey figures, with a chart, sample sizes, the source question and follow-ups. It runs on our own search model, with an AI check only when unsure. About 0.08 s median. | Home question box (not in the left menu) |
| Weekly US tracker | Each wave's Overview, Questions, Cross-tabs (significance at 95%), Trends, Compare waves, Audiences, What changed, Weekly report, Survey preview | Core research › Shopping & Spending |
| China weekly tracker | The same screens for the Baidu China survey, plus the analysts' weekly report | Core research › China weekly tracker |
| Databanks | Retailer databank (reach, shopper profile, sentiment), Sector databank, In store vs online, Expected vs actual | Core research |
| Trackers | Topic dashboards (holiday, tariffs, GenAI and others) | Trackers |
| Find | Survey library, Search questions, Launch schedule | Explore |
| Share | Boards (pinned views), Excel, PowerPoint, CSV and PNG exports, alerts, API keys and the MCP connector (Claude and ChatGPT can query CIP) | Explore › Boards, export buttons, API guide |
| Run the research | Fieldwork, Forsta pages, Upload survey, Logs, Access | Research operations, Administration |

Scale: 374 waves (271 weekly), about 191,000 qualified responses, every wave since Dec 2020 plus studies since 2018.

## 2. Where CIP stands against the market

| Competitor | Their AI or natural-language feature | What CIP can learn |
|---|---|---|
| Morning Consult (MorningConsult.AI, AI Connector) | Plain-language questions over its own tracking data, and an MCP connector into ChatGPT and Claude | CIP already has MCP. Show it on the public pages as a headline feature. |
| YouGov (AI agent across Profiles and Crunch) | An agent kept inside one dataset, with crosstabs kept for experts | Say which survey an answer comes from (done today: the source now has the question's name) |
| GWI Spark / Agent Spark | Answers traced to surveyed people, with the sample and source in the answer and in its API | Keep n, wave and question as fields in every answer, not only in prose (done: `scope.base`, `sources.name`) |
| Statista Research AI | Retrieval answers with numbered sources | Show the collection date, not a publish date (CIP already does) |
| NIQ Ask Arthur, Circana Liquid AI | Chat over retail purchase data, "grounded in governed data" | The closest rivals for retail clients. CIP's edge is the exact question wording and n under each figure. |
| Numerator | AI summaries on reports, no question box | Auto-written takeaways per wave (CIP's dashboards have takeaways already) |
| Qualtrics, Toluna | Synthetic respondents | Opposite positioning: CIP answers only from real respondents. Say so. |
| Forsta / Displayr | AI for survey set-up and coding, no Q&A | Not a rival in retrieval |

**Where CIP is ahead:** a weekly US tracker every week since 2020 (none of the sources found claims the same); every
figure with its base and exact wording; significance colour only when significant; retail cuts (retailers, sectors,
channels, expected vs actual); answers in about 0.1 s from our own model, no per-question AI cost.

**Where CIP lags:** sample size (about 400 a week against panels of hundreds of thousands), so small groups must be
flagged or left out; distribution (Morning Consult and GWI are inside ChatGPT and Claude: CIP's MCP exists but is not
marketed); Ask still answers some questions it should refuse (section 3).

**Suggested launch message (USP):** "Ask anything about US shoppers and get the answer in one sentence, with the chart,
the exact survey question and how many people answered — from a real weekly survey since 2020."

## 3. Ask CIP: what was confusing, and what changed today

Tested live on :8001 with real analyst questions.

| Question | Before | Now |
|---|---|---|
| How worried are people about tariffs? | "Top 5 on 28 Sep 2026: 1. Higher prices for goods 53.1%; 2. US companies cutting jobs… 33.3%; 3. … 4. … 5. …" | "“Higher prices for goods” leads at 53.1%, 19.8 points ahead of “US companies cutting jobs because of higher costs” (33.3%)." Then: 28 Sep 2026 · 1 survey wave · 403 respondents · Source TF3: Concerns about tariffs |
| Which retailers do people shop at most? | A Walmart line chart over 25 quarters | A ranking: "“Walmart” leads at 51.7%, 10.4 points ahead of “Amazon” (41.3%)", ranked bars |
| amazon prime by income | "By income band, …: under $25,000 39.1%, $25,000 - $49,999 46.8%, … (seven figures)", and a "Highest" of 59.4% while the chart showed 69.0% | One sentence on the range, ending "(4 groups under 50 respondents left out)", so the chart and the sentence agree |
| Client view | Answer sentence and chart. The key figures (tiles) showed only in Analyst view. | Key-figure tiles in both views |

The answer now follows the order the research found in ChatGPT, Tableau Agent and Perplexity: the answer in one sentence,
then where it comes from and how many people, then the key numbers, then the chart, then follow-ups. A count ("how many
people…") and an answer for one named group ("among Gen Z") keep their former first sentence, which names the people
and the group.

Checks: the Ask golden set scores 151 of 161 before and after the change, median 0.08 s. The full test suite passes
(662), plus two new tests. The frontend type-check passes.

### Still open in Ask (later on 21 Nov: Fed rate cuts now refused, Gen Z vs boomers answered by generation, “started” summed as the dashboard does)

| Question | What happens | Why it matters |
|---|---|---|
| Fed rate cuts | Answered from the gas-prices question (67.2% "Yes") | A wrong answer stated with confidence is the biggest launch risk. Already pending in status: a "not asked" check on the question's key words |
| Do Gen Z shop on Amazon more than boomers? | No answer (mode none) | A two-group comparison inside a retailer list. Needs the reader to pick the retailer question with a generation cut. |
| What share started holiday shopping? | Leads with "Still shopping 44.1%" | "Started" means Still shopping + Finished. Needs answers to be summed (a net), which Ask does not do yet. |

## 4. Charts: the rule Ask follows

Ask already picks the chart from the shape of the figures (api/assistant.py `chart`), and it matches the published
practice (FT Visual Vocabulary, ThoughtSpot):

| Shape of the answer | Chart |
|---|---|
| One figure | Tile |
| One question, several answers, one period | Ranked horizontal bars |
| One choice in up to 6 parts that add to 100% | One segmented bar (donut offered) |
| Over time | Line (a yes/no draws only the main answer) |
| Two periods compared | Dumbbell (before → after) |
| By a group, single choice | 100% stacked bars with each group's n |
| Many answers by 4+ groups | Heatmap table with n |
| Multi-select ("select all") | Ranked bars, never a pie |

No change needed. A diverging bar for agree/disagree scales is the one form not yet used.

## 5. How the big players train and improve, and the next steps for CIP on Colab Pro

Large search and answer systems are evaluated on a fixed test set first. Their retrieval models are fine-tuned on
(query, right document) pairs with hard negatives: near-miss documents mined from the same catalogue. A reranker then
re-scores the top candidates, and a threshold on its score decides when to refuse. Preference training (RLHF, DPO) is
used for writing style, not for picking the right table. CIP's own record (docs/research/ask-cip-model-training.md)
shows fine-tuned search models v1–v8 did not beat today's bge-small inside Ask. So the next steps target what the
misses above show:

1. **Test set from real questions.** Take the analysts' own asks from the access log, check them by hand, and keep
   them out of training. Include questions that must be refused ("Fed rate cuts", "average turkey price"). Score
   recall@5, MRR and the share of refusals that are right. (Pending item: "50+ real analyst questions".)
2. **A refusal check before more training.** For each answer, test whether the question's key subject word (rate,
   turkey, dining) appears in the chosen question's wording, answers or synonyms. Tune it on the test set so recall
   does not drop.
3. **Then, on Colab Pro:** train a small cross-encoder reranker on the top 20 candidates. Use hard negatives mined with
   sentence-transformers `mine_hard_negatives`, split by question (not by phrasing) so the score is honest. Ship it
   only if it beats today's golden score of 151/161 and refuses better. The notebook scripts/colab/ask_cip_train.ipynb
   is the place for it.

## 6. Menus: proposals (all three applied later on 21 Nov, the Access page too)

The left menu is grouped and readable (Explore, Core research, Trackers, Reference, Research operations,
Administration). Three things would make it clearer for a first-time client:

1. **Put Ask CIP back in the menu, at the top of Explore.** It is the USP, but today it is reached only from Home's box.
   It was taken out of the menu on 15 Nov.
2. **Name the two trackers alike:** "Shopping & Spending" is the US weekly tracker, next to "China weekly tracker".
   For example "US weekly tracker" and "China weekly tracker".
3. **One line of help on hover** for the databanks and trackers (what each answers), so a client knows where to start.

## Sources

Morning Consult AI Connector: morningconsult.com/articles/how-the-morning-consult-ai-connector-mcp-works ·
YouGov AI agent: yougov.com/en-us/articles/54795 · GWI Agent Spark: gwi.com/gwi-launches-agent-spark ·
Statista Research AI: statista.com/getting-started/content-types-overview-research-ai ·
NIQ Ask Arthur: nielseniq.com/global/en/news-center/2026/niq-launches-ask-arthur-chat-to-expand-access-to-consumer-insights-through-ai/ ·
Circana Liquid AI: circana.com/solutions/liquid-ai · Numerator AI: numerator.com/press ·
Tableau Agent answers: tableau.com/blog/tableau-pulse-enhanced-qa · Databricks Genie trusted assets:
docs.databricks.com/aws/en/genie/trusted-assets · ThoughtSpot KPI chart: docs.thoughtspot.com/software/latest/chart-kpi ·
FT Visual Vocabulary: github.com/Financial-Times/chart-doctor · Hard negatives: sbert.net/docs/package_reference/util/hard_negatives.html ·
Reranker training: huggingface.co/blog/train-reranker. Vendor claims are their own; chart and base-size presentation
for Morning Consult, NIQ and Circana could not be verified from public pages.
