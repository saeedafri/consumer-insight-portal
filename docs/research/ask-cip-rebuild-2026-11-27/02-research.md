# Ask CIP rebuild: independent research to confirm or challenge the plan (27 Nov 2026)

What this is: an outside-in check of the planned rebuild of the "ask any question" feature (small local models +
precomputed figures + fixed sentence patterns, paid LLM only as a fallback). Written for whoever decides the
architecture and for the people who will build it. Read it before committing to the plan writer, the retriever work,
or the answer layout.

How it was done: public web sources only (vendor docs, papers, practitioner write-ups, GitHub). No company name,
product name, customer data, figures or person names from the brief were put in any search or URL; all queries used
generic terms. The `agent-reach` CLI is not installed on this machine, so, following that skill's own rule (built-in
tools first for public content), the research used web search, page fetch and the `gh` CLI for GitHub files.

How to read the evidence: each claim carries its URL. Labels used below:
**[paper]** peer-reviewed or arXiv preprint, **[docs]** vendor documentation, **[vendor]** vendor marketing or blog
(self-reported, not independently checked), **[blog]** practitioner write-up, **[estimate]** my own arithmetic or
judgement, not a measured source. Where a source could not be verified, it says so.

---

## 1. How ChatGPT, Claude, Gemini and Perplexity structure answers, and when they ask back

### Findings

- **Default is "take a stab, state the assumption", not "ask first".** OpenAI's Model Spec (section *Consider
  uncertainty, state assumptions, and ask clarifying questions when appropriate*): "Unless the cost of making the wrong
  assumption is too high or the task is too ambiguous or difficult with available information, GPT typically should
  take a stab at fulfilling the request and tell the user that it could be more helpful with certain information." It
  adds that "Trivial questions may waste the user's time ... and may be better if stated as an assumption that the user
  can correct", and elsewhere that the model should "provide an answer that remains useful across plausible
  interpretations". Its worked example ("Who's on the roster of the giants?") marks *asking* as good, *guessing from
  context* as good, and *guessing without context* as bad. [docs]
  https://github.com/openai/model_spec/blob/main/model_spec.md (also https://model-spec.openai.com/2025-12-18.html)
- **Ask at most one question at a time; short answers to simple questions.** Claude's published consumer system prompt:
  "Claude should give concise responses to very simple questions"; when it asks, "it tries to avoid overwhelming the
  person with more than one question per response"; and for explanations it should write prose, not bullet lists.
  [docs, via quote] https://simonwillison.net/2025/May/25/claude-4-system-prompt/ ;
  https://platform.claude.com/docs/en/release-notes/system-prompts
- **Follow-up suggestions are standard in answer engines.** Perplexity shows sources and suggested follow-up questions
  after each answer [blog] https://www.techtarget.com/searchEnterpriseAI/definition/Perplexity-AI ; a third-party API
  tutorial says it proposes 3-4 follow-ups generated from the answer just written (low-authority source)
  https://theneuralbase.com/perplexity-api/learn/advanced/follow-up-questions/ ; Perplexity even tested *sponsored*
  follow-up questions, which shows how prominent that slot is
  https://searchengineland.com/perplexity-begins-testing-ads-448277 . Google was seen testing follow-up suggestions in
  Gemini (not confirmed as rolled out) https://www.androidauthority.com/google-gemini-follow-up-question-suggestions-3595747/ ;
  Gemini's documented feature is "Double-check response", which highlights statements and lists related searches
  https://support.google.com/gemini/answer/14143489 . [docs/blog]
- **Charts in chat assistants are chosen by the model and often wrong first time.** ChatGPT's data-analysis help page:
  interactive charts cover bar, line, pie and scatter, and "ChatGPT may choose an analysis method or chart type that
  does not match your intent on the first try. Ask it to use a specific ... chart type". [docs]
  https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt
- **The data-analytics flavour of Gemini asks back on ambiguity and suggests follow-ups.** Looker Conversational
  Analytics "can propose follow-up questions to encourage deeper analysis"
  https://docs.cloud.google.com/looker/docs/conversational-analytics-looker-data ; a Google developer post for
  version 26.6 says the agent "now asks clarifying questions when a request is ambiguous"
  https://discuss.google.dev/t/what-s-new-in-conversational-analytics-in-looker/343075 . [docs]
- **LLMs are not good at deciding *when* something is ambiguous.** CLAMBER (ACL 2024, ~12K examples): chain-of-thought
  and few-shot prompting give only small gains in spotting ambiguity and "may lead to the over-confidence issue in
  small-scale LLMs"; models "fall short in generating high-quality clarifying questions". [paper]
  https://aclanthology.org/2024.acl-long.578

### What this means here

No major assistant documents a fixed "one sentence + three cards + chart" layout; that card pattern comes from BI tools
(section 2), not chat assistants. What the assistants *do* agree on: lead with the answer, keep simple answers short,
state assumptions instead of asking trivial questions, ask at most one question, and offer next questions. "Asking back
when ambiguous" should be the exception, decided by a measured signal (section 3, conformal sets), not by a model's
self-report.

---

## 2. How commercial natural-language-over-data and survey-insight products work

### Summary table

| Product | How the question is understood | Who writes the text | Charts / follow-ups | "No data" behaviour |
|---|---|---|---|---|
| ThoughtSpot Sage / Spotter | LLM output is turned into inspectable **search tokens** / an intent spec; a deterministic engine writes the SQL | LLM + tokens shown to user for checking | Auto "best fit" chart; single measure → KPI tile; line is the common default | Not documented |
| Tableau Pulse | Deterministic statistical **insight types** on a governed metrics layer | **Templates first**, then LLM summarises top 3 templated facts | Each insight type has its own visual; follow-ups grounded in detected insights | Enhanced Q&A only covers Pulse metrics |
| Tableau Ask Data (retired 2024) | Keyword-based mapping | n/a | n/a | Retired: "isn't 'natural' enough" |
| Power BI Q&A (retiring Feb 2027) | **Linguistic schema**: synonyms, phrasings, row labels, no generative AI | n/a | Visual from data model; admins review logged questions | Low-confidence matches shown with a dotted line |
| Power BI Copilot | Semantic model | LLM | Narrative footnotes link each statement to a visual | **May answer from general LLM knowledge** (anti-pattern) |
| Looker Conversational Analytics | LLM calls the **LookML semantic layer** API, no raw SQL | LLM | Suggests follow-ups; asks clarifying questions (26.6) | Not documented |
| GWI Spark | Questions in plain language over own survey data | LLM | Source chart + survey details shown; hands off to crosstab tool | Not documented |
| Morning Consult AI | Parses "demographics, timeframes, and topics", builds a demographic filter, retrieves data | LLM writes from retrieved data | Charts; MCP tools: search questions → data → SQL | Not documented |
| YouGov AI agent | Natural language over Profiles / Crunch data | Not documented | Crosstabs remain for advanced users | Not documented |
| Statista Research AI | RAG: picks **10** most relevant items | LLM (reported as a Claude 3 model) with inline citations | Source list with "last updated" dates | Librarians: misses relevant data; follow-ups repetitive |
| Circana Liquid AI (Emiri) | Claims grounding in own data + business rules | Not documented | Not documented | Not documented |
| dbt Semantic Layer (benchmark) | LLM picks metrics/dimensions; engine compiles | LLM | n/a | "tells you it can't answer ... never returns invalid data" |

### Evidence per product

- **ThoughtSpot.** Docs: Sage "translates your natural language query to a relational search" and users "can view the
  ThoughtSpot search phrases (also known as tokens) that matched ... to verify the measures, attributes and filters";
  accuracy "varies based on the complexity of the question". [docs] https://docs.thoughtspot.com/cloud/latest/search-sage .
  Its engineering blog: "The LLM's output is input to a compiler, not a query to a database." [vendor]
  https://www.thoughtspot.com/blog/agentql-sql-shaped-intent . Charts: "When you submit a query for the first time,
  ThoughtSpot analyzes the data and automatically selects the most appropriate chart"; a single measure becomes a KPI
  chart; editing a query keeps the chart type unless constraints force a change. [docs]
  https://docs.thoughtspot.com/cloud/latest/charts . (A "53% correct" figure seen in a search summary could not be
  found in the cited article, so it is not used.)
- **Tableau Pulse.** The Insights Service uses "standardized, deterministic statistical models" (period-over-period
  change, unexpected values, top contributors, trend change, etc.); insight summaries "use a large language model"
  grounded in those facts. [docs] https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm .
  Salesforce's write-up: feeding raw numbers to the LLM was hard, so they added an intermediate **templating** step
  where facts are rendered to text by multiple templates, then the LLM summarises the top three; prompts and templates
  were tuned over repeated evaluation rounds. [vendor] https://www.salesforce.com/blog/?p=100943 ;
  https://www.salesforce.com/blog/?p=98364 ; https://blog.salesforceairesearch.com/tag/tableau .
  Suggested questions are "grounded in the insights detected for your metrics"; answer pages show "key insights,
  relevant visualizations, source references, and suggested follow-up questions". [docs]
  https://help.tableau.com/current/online/en-us/pulse_ask_discover_qa.htm ;
  https://trailhead.salesforce.com/content/learn/modules/business-metrics-insights-with-tableau-pulse/work-with-ai-powered-insights
- **Tableau Ask Data retirement (the closest precedent to "users ask by intent").** Customers said Ask Data "isn't
  'natural' enough—you still have to understand some fundamental data concepts, field names, keywords"; it "uses a
  keyword-based system to map user intent". Retired Feb 2024. [vendor]
  https://www.tableau.com/blog/tableau-metrics-and-natural-language-query-evolve-tableau-pulse
- **Power BI Q&A.** "Q&A experiences are going away in February 2027" in favour of Copilot. The engine "relies on these
  names and their synonyms"; unapproved suggested synonyms are still used "with a lower priority ... shown with an
  orange dotted line indicating that it is low-confidence"; admins can **Review questions** users asked, including
  "words that weren't recognized" (last 28 days). [docs]
  https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-tooling-intro ; phrasings live in an editable
  YAML linguistic schema https://learn.microsoft.com/en-in/power-bi/natural-language/q-and-a-tooling-advanced .
- **Power BI Copilot.** "When a question is related to data in the semantic model, Copilot uses the semantic model ...
  Otherwise, it might answer from the large language model's (LLM's) general knowledge." [docs]
  https://learn.microsoft.com/lv-lv/Power-Bi/create-reports/copilot-ask-data-question . Narrative visual: footnotes
  link summary statements to the visuals they came from; "accuracy of the public preview may be limited". [docs]
  https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-create-narrative
- **Looker.** Google says its internal testing shows the semantic layer "reduces data errors in gen AI natural language
  queries by as much as two thirds". [vendor]
  https://cloud.google.com/blog/products/business-intelligence/how-lookers-semantic-layer-enhances-gen-ai-trustworthiness ;
  the LLM works through the semantic layer's APIs rather than writing raw SQL [vendor]
  https://services.google.com/fh/files/misc/conversational_analytics_in_looker.pdf
- **GWI Spark.** Answers "with sources attached", "the source chart and survey details shown alongside", outputs
  "connect straight into GWI's analysis tools". [vendor] https://www.gwi.com/platform/agent-spark ;
  API returns "the figures, the audience and the source" https://www.gwi.com/integrations/spark-api
- **Morning Consult.** "Our system interprets your natural language question, identifying key parameters like
  demographics, timeframes, and topics" and can "construct a demographic filter on the fly"; the LLM "combines the
  retrieved data with its language generation capabilities". [vendor]
  https://intel.morningconsult.com/mc-content/articles/introducing-morning-consult-ai . MCP connector exposes
  search-questions, a question→data tool and a SQL tool. [vendor]
  https://morningconsult.com/articles/how-the-morning-consult-ai-connector-mcp-works
- **YouGov.** AI agent over Profiles, later Crunch; crosstabs and filters stay for advanced users; MCP access sold
  separately. Mechanism undocumented. [vendor]
  https://yougov.com/en-us/articles/53941-launch-of-yougov-profiles-ai-agent-enables-conversational-exploration-of-high-quality-data ;
  https://www.research-live.com/article/news/yougov-adds-ai-agents-to-data-analytics-platform/id/5149303
- **Statista Research AI.** "identifies the 10 most relevant sources ... and feeds this information to the AI" [docs]
  https://www.statista.com/getting-started/content-types-overview-research-ai ; LLM reported as Claude 3 Sonnet [blog]
  https://libguides.usc.edu/blogs/marshall/statista-research-ai ; librarians found relevant data left out
  https://library.syracuse.edu/blog/Collection-Spotlight-Research-AI-from-Statista/ and follow-ups "very similar to the
  original question" https://scholarblogs.emory.edu/gbsl/?p=4975 . [blog]
- **Qualtrics.** "Qualtrics Assist" lets non-researchers ask about feedback in natural language; no documented
  natural-language crosstab feature found. [vendor]
  https://www.qualtrics.com/news/qualtrics-unveils-groundbreaking-ai-innovations-to-transform-understanding-of-customers-employees-and-prospects/
- **Circana.** Claims answers grounded in its own data, business rules and analytical logic; no technical detail.
  [vendor] https://circana.com/solutions/liquid-ai . Numerator and Glimpse: no public technical documentation found.
- **Semantic layer vs free SQL, measured.** dbt's 2026 benchmark (11 questions × 20 runs): with light modelling,
  text-to-SQL 90.0% / 84.1% vs semantic layer 98.2% / 100% (two frontier models). On the unmodelled schema the
  semantic layer scored 0% on multi-hop questions, but: "The Semantic Layer tells you it can't answer. It never returns
  invalid data. Text-to-SQL will cheerfully give you a wrong number." [vendor, small n]
  https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026

### What this means here

Every serious product keeps the **numbers deterministic** (semantic layer, tokens, statistical insight types) and
uses language models only to *understand* the question or to *phrase* already-computed facts. The one documented
product that is closest to "templates only" (Power BI Q&A, no generative AI) is being retired because synonym lists do
not keep up with how people ask; its keyword-based cousin (Ask Data) was retired for the same reason. The winning
pattern is **semantic layer + learned understanding + templated facts**, with the LLM never inventing a figure.

---

## 3. Low-cost architectures for unlimited questions on 1 vCPU / 4 GB

### 3a. Small encoders vs small generative models for "understand the question"

- Fine-tuned BERT-family encoders reach "competitive and often superior" classification performance at "one to two
  orders of magnitude lower cost and latency" than zero/few-shot LLM prompting. [paper] https://arxiv.org/abs/2602.06370
- Intent detection (2026): fine-tuned RoBERTa 95.9 vs zero-shot LLM 84.1 on ATIS; tied on CLINC150 (89.1 vs 88.5);
  RoBERTa ~1000× cheaper/faster. But the LLM was far better at **out-of-scope** recall (85.6 vs 58.1), and a
  classifier trained on one app's intents scored **0%** on a new app's intents. [paper] https://arxiv.org/abs/2608.20371
- SetFit (contrastive fine-tune of a sentence transformer + logistic head) is competitive with 8 examples per class.
  [paper] https://arxiv.org/abs/2209.11055 ; https://huggingface.co/blog/setfit . One practitioner benchmark on MASSIVE:
  22M-parameter SetFit 91.1% in ~2-5 ms vs a 20B zero-shot model 68.8% at ~3.4 s. [blog]
  https://avchauzov.github.io/blog/2026/intent-routing-architecture-tradeoffs
- Joint intent + slot encoders (JointBERT): ~98.6% intent / 97.0 slot F1 on SNIPS, 97.5% / 96.1 on ATIS. [paper]
  https://arxiv.org/abs/1902.10909
- Hybrid: SetFit-style classifier first, LLM only when uncertain, reached "within 2% of native LLM accuracy with 50%
  less latency". [paper] https://arxiv.org/abs/2410.01627 (EMNLP Industry 2024)

**Implication:** the plan's slots (market, demographic cut, period, answer type) are small closed sets, which is
exactly where encoders win. The *survey question* slot is not a closed small set (thousands of items, growing); that is
a retrieval problem, and the 0%-on-unseen-labels result is why it must stay retrieval, not a classifier head.

### 3b. Measured CPU speed of small generative models (the 1 vCPU problem)

- Qwen2.5-0.5B-Instruct Q4_0 (403 MiB) on a Raspberry Pi 5, llama.cpp: prompt processing 93 tok/s on 1 thread,
  174 tok/s on 2; generation 32 tok/s (1 thread), 34 tok/s (2). Generation peaks at 2 threads; prefill scales with
  cores. [docs] https://learn.arm.com/learning-paths/cross-platform/llm-decode-roofline/threads-and-size/
- A 1.5B Q4_K_M model generated 10.4 tok/s on a weak Intel i5 with no GPU; "models larger than 1.5B drop below 10 t/s".
  [blog] https://dev.to/ymir/how-i-tested-5-small-llms-on-a-weak-pc-intel-i5-no-gpu-and-found-a-winner-55cm
- llama.cpp server reuses the KV cache of a shared prompt prefix (`cache_prompt`, default on: "only the 'unseen' suffix
  is evaluated"), but warns results may be nondeterministic; it also accepts a `json_schema` for grammar-constrained
  output. [docs] https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Grammar-constrained decoding is cheap per token (XGrammar: <40 µs/token for JSON Schema). [paper]
  https://arxiv.org/abs/2411.15100 . Constrained JSON hurts *reasoning* tasks but can *help* classification tasks.
  [paper] https://aclanthology.org/2024.emnlp-industry.91
- Small-model JSON reliability varies: one comparison found a 0.8B model "fast but unreliable" and 1.5B "more
  consistent JSON structure". [blog]
  https://www.iunera.com/kraken/enterprise-ai/best-qwen-model-for-receipt-extraction-0-8b-vs-3b/

**[estimate] Latency budget for a generative plan writer on 1 x86 vCPU** (assume roughly Pi 5 class per core; measure
on the real box with `llama-bench -t 1`):

| Model | Prefill (25 new tokens, cached prefix) | Generate ~50-token JSON plan | Total |
|---|---|---|---|
| 0.5B Q4 | ~0.3 s | ~1.5 s (at ~32 tok/s) | **~1.5-2 s** |
| 0.5B Q4, no prefix cache, 400-token prompt | ~4 s | ~1.5 s | **~5-6 s** |
| 1.5-1.7B Q4 | ~0.8 s | ~5 s (at ~10 tok/s) | **~5-7 s** |

A generative plan writer cannot meet "well under 1 s" on this server. It also competes for the single core with the
API. It is viable only (a) offline, as a labeller or data generator, or (b) as a rarely-used *local* fallback instead
of the paid LLM, if a few seconds is acceptable for that minority of questions.

**[estimate] Encoder path on the same box:** rules/gazetteers for market, year and demographic words (<1 ms) + BM25 over
the question catalogue (ms) + one bge-small query embedding (tens of ms at most, int8) + brute-force cosine over tens of
thousands of vectors (ms) + MiniLM cross-encoder over top 20-30 pairs (~tens to ~200 ms) + template text and chart
spec (ms). Total roughly **0.1-0.3 s**. Sentence-Transformers' own CPU benchmarks found OpenVINO INT8 fastest on a
local Intel CPU but llama.cpp fastest on a cloud CPU instance, and advise testing on your own hardware [docs]
https://sbert.net/docs/sentence_transformer/usage/efficiency.html ; INT8 can even be slower than FP32 on some CPU
instruction sets [paper] https://arxiv.org/pdf/2609.16085 .

### 3c. Raising the retrieval recall ceiling

- **Hybrid BM25 + dense with Reciprocal Rank Fusion.** On a BEIR subset, RRF of learned sparse + BM25 raised nDCG@10
  18% over BM25 alone; RRF's suggested k=60; a tuned weighted combination beat RRF once ~40 annotated queries existed.
  [vendor] https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid
- **Document expansion (index how people ask, not only how the survey asks).** Appending predicted queries to each
  document lifted BM25 effectiveness ~15% (MS MARCO Recall@1000 85.3 → 89.3; T5 variant 94.7). [paper]
  https://arxiv.org/abs/1904.08375 . Doc2Query-- filters out generated queries a relevance model scores as off-topic,
  cutting noise and index size. [paper] https://arxiv.org/abs/2301.03266
- **Domain-adapting the dense retriever with synthetic queries + cross-encoder labels (GPL):** up to +9.3 nDCG@10 over
  an off-the-shelf dense retriever across six specialised domains. [paper] https://aclanthology.org/2022.naacl-main.168 .
  Hard-negative mining often fails to help in domain settings; listwise distillation from a cross-encoder did better.
  [paper] https://arxiv.org/abs/2502.19712 . One hard negative + in-batch negatives was enough for fine-tuning.
  [paper] https://arxiv.org/abs/2502.20204 . Practitioner example: bge-base nDCG@10 0.59 → 0.82 after fine-tuning
  with MultipleNegativesRankingLoss. [vendor] https://redis.io/blog/get-better-rag-by-fine-tuning-embedding-models/
- **Synonym annotations work.** On Spider-Syn, accuracy "dramatically drops by eliminating ... explicit correspondence
  between NL questions and table schemas"; adding synonym annotations to the schema input was the more effective of two
  defences. [paper] https://arxiv.org/abs/2106.01065 . Power BI Q&A is built on the same idea (approved and suggested
  synonyms, phrasings). [docs] https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-tooling-intro
- **Query rewriting with small models is weak.** "Rewriting techniques degrade when using a small LLM (e.g. smaller than
  4B of parameters)". [paper] https://arxiv.org/html/2511.05301v2 . HyDE helps short casual queries against formal text
  but adds an LLM round trip and can narrow retrieval on ambiguous questions. [vendor]
  https://www.elastic.co/search-labs/es/blog/hyde-semantic-search-elasticsearch . On 1 vCPU, prefer moving this work
  offline into document expansion.

### 3d. Synthetic training data, teacher bias and why 98% became 57%

- Real users write short, underspecified queries: **6.8 words vs 15.7** for corpus-generated synthetic questions; real
  traffic concentrated on 53 sources vs 165 for synthetic; configurations that looked strong on synthetic questions
  showed a "substantial performance drop" on real ones, and tuning on synthetic picked a retriever up to 8× slower.
  [paper, CIKM 2026] https://arxiv.org/abs/2609.14579
- Spider-Realistic (explicit column names removed) and Spider-Syn (synonyms) exist because benchmark questions copy the
  schema's words; RAT-SQL+BERT lost ~21.5 exact-match points on Spider-Syn, T5-3B ~12.2. [paper]
  https://arxiv.org/abs/2010.12773 ; https://arxiv.org/abs/2210.12674
- LLM-generated training data works for low-subjectivity tasks but its **diversity is limited**, and the gap to real
  data widens on subjective instances. [paper] https://aclanthology.org/2023.emnlp-main.647

The brief's numbers (98% on tuned sets, 57% on unseen, training questions reworded from survey text) match this
pattern exactly: the model learned to match survey wording, which real users do not use. More synthetic data generated
the same way will not fix it; the generator must be pushed toward short, intent-style, non-overlapping phrasing, and
real questions must anchor training and testing.

### 3e. Calibration, abstention and "ask back"

- Neural networks are typically over-confident; temperature scaling fixes calibration without changing accuracy.
  [paper] https://arxiv.org/abs/1706.04599 . Temperature scaling is monotone, so it does not change which items are
  accepted at a given coverage; it only moves where the threshold sits. [paper] https://arxiv.org/pdf/2609.19072
- **Conformal Intent Classification and Clarification (CICC, NAACL Findings 2024)** turns any classifier's scores into a
  set guaranteed to contain the right answer at a chosen rate (e.g. 99%). Rule: set size 1 → answer; 2 to `th` →
  ask "did you mean A, B or C?"; larger than `th` → treat as out-of-scope / hand off. `th` = 7 in most experiments
  (advised "no higher than seven"), 4 for one product. Calibration used ~20% of each dataset. Share of queries needing a
  clarification question ranged from ~2-3% (ATIS, CLINC150) to ~13-26% (ACID, Banking77). A tuned variant reached
  out-of-scope F1 0.90-0.91. [paper] https://arxiv.org/abs/2403.18973 ; https://aclanthology.org/2024.findings-naacl.156
- **Routing to an expensive model only when needed:** RouteLLM routers cut cost "by over 2x" without substantially
  compromising quality. [paper] https://arxiv.org/abs/2406.18665 ; https://lmsys.org/blog/2024-07-01-routellm/

### 3f. Active learning from real question logs

- Two strong classifiers flag likely misclassifications in production logs, topic-cluster them, and send them for
  labelling: reached 100% of full performance while annotating only 36% of data. [paper]
  https://aclanthology.org/2023.law-1.6
- A commercial assistant's domain classifier gained more accuracy per annotation budget from a selection technique than
  from random or entropy sampling. [paper] https://arxiv.org/abs/1908.11404
- Power BI Q&A ships a "Review questions" screen showing unrecognised words in user questions for exactly this loop.
  [docs] https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-tooling-intro

---

## 4. Data-to-text: templates vs LLM-written text for numbers

- **Symbolic (rule and template-based) systems make fewer semantic errors overall** than neural systems; non-LLM neural
  systems are more fluent but make more semantic errors; LLM systems "require improvement particularly in addressing
  superfluous" content (15 systems, WebNLG, word-span error annotation). [paper]
  https://aclanthology.org/2024.inlg-main.47
- **More than 80% of open-LLM data-to-text outputs contain at least one semantic error**, per both human annotators and
  a GPT-4-based metric (Llama 2, Mistral, Zephyr). [paper, ACL 2024] https://arxiv.org/abs/2401.10186
- Even large models misstate numbers in data summaries: 3,312 factual errors annotated in LLM sports summaries;
  structured JSON input reduces error rates; one 70B model made more number errors. [paper]
  https://aclanthology.org/2025.ynlg-main.3.pdf . Correcting flawed table input cut factual errors 57-62%. [paper]
  https://arxiv.org/abs/2404.04103
- Reiter: accuracy is "perhaps the biggest challenge in neural NLG (including chatGPT)"; core error types are incorrect
  numbers, named entities and words. [blog, NLG researcher]
  https://ehudreiter.com/2023/02/07/evaluating-factual-accuracy-in-complex-data-to-text/
- Templates are faithful but less varied and fluent; neural text is fluent but struggles with faithfulness. [paper,
  survey] https://arxiv.org/abs/2203.05227 . In the E2E NLG Challenge a template system built in a few hours was
  competitive with neural ones. [paper] https://aclanthology.org/W18-6557 ; findings https://arxiv.org/abs/1901.07931
- Industry practice converges on a hybrid: Tableau Pulse renders facts through templates before any LLM sees them
  (section 2); Power BI's narrative footnotes tie each sentence to a visual.

**Making templates read naturally (practical, [estimate] from the above):** write one plain-English *lexicalisation*
per survey question once ("shop online at least weekly", "plan to cut back on dining out"), human-checked, so templates
read "31% of US adults shop online at least weekly" instead of quoting the questionnaire. Keep 2-3 alternates per
sentence pattern and pick one deterministically (e.g. by question id) so tests stay stable. Let the template choose the
verb from the statistics: "rose/fell" only when the change is statistically meaningful, "little changed" otherwise. At
~400 respondents a week the 95% margin of error on a 50% figure is about ±4.9 points (1.96 × √(0.25/400)); a
week-to-week move of 3 points is usually noise, and a template that says "rose" for it would be wrong in a way an LLM
would also happily repeat.

---

## 5. Chart choice

- FT Visual Vocabulary groups charts by the relationship to show: deviation, correlation, ranking, distribution,
  **change over time** ("Give emphasis to changing trends"), **magnitude** ("Show size comparisons ... Usually ... a
  'counted' number"), **part-to-whole**, spatial, flow. Line is "the standard way to show a changing time series";
  columns work for change over time "best with only one series"; ordered bars display ranks "much more easily when
  sorted"; **bar (horizontal) is "Good when the data are not time series and labels have long category names"**;
  slope suits 2-3 points; diverging stacked bar is "Perfect for presenting survey results which involve sentiment".
  [docs] https://github.com/Financial-Times/chart-doctor/blob/main/visual-vocabulary/README.md
- Datawrapper: line is "usually a solid choice" for time; with few time points "a column chart is usually a good fit";
  "a bar chart is often a safer pick for small screens than a column chart" because column labels overlap or turn
  sideways; pies are hard to compare; for survey answers with several options "stacked bar charts might be your best
  option". [docs] https://www.datawrapper.de/blog/chart-types-guide . Datawrapper also argues for 100% stacked bars over
  diverging bars for Likert scales so neutrals stay visible. [docs] https://blog.datawrapper.de/divergingbars
- ThoughtSpot: one measure → KPI tile; keep the chart type stable across follow-up edits unless the data forces a
  change. [docs] https://docs.thoughtspot.com/cloud/latest/charts

**Rule set that follows from this ([estimate]):** single number → card only; one series over ≥4 time points → line;
2-3 time points → columns or slope; one wave, answer options or demographic groups → **horizontal** bars sorted by value
(survey labels are long; phones); agree/disagree scales → 100% stacked horizontal bar; two groups × several options →
grouped horizontal bars; net/difference scores → diverging bar.

---

## 6. Honest evaluation of natural-language question answering

- Re-used test sets inflate scores: fresh test sets for ImageNet showed 11-14% accuracy drops (3-15% for CIFAR-10),
  mostly from slightly harder, differently-drawn examples; model *rankings* largely held. [paper]
  https://arxiv.org/abs/1902.10811
- Synthetic-question benchmarks overstate real-user performance and can pick the wrong system (6.8 vs 15.7 words; up to
  8× latency cost). [paper] https://arxiv.org/abs/2609.14579
- Lexical overlap between question and schema inflates scores (Spider-Syn / Spider-Realistic). [paper]
  https://arxiv.org/abs/2106.01065 ; https://arxiv.org/abs/2010.12773
- **Recall ceiling ([estimate], from the brief's own numbers):** a reranker can only choose among what the retriever
  hands it. End-to-end 79% against 78% top-6 recall means the reranker already converts almost everything it is given;
  15% of real questions never reach the top 20. The loss is in retrieval, not in ranking or in plan writing.
- **Sample size ([estimate]):** with 232 test questions, a 79% score has a 95% interval of about ±5.2 points
  (1.96 × √(0.79×0.21/232)). Changes smaller than ~5 points cannot be told apart from noise. ±3 points needs about 700
  labelled real questions; ±2 points about 1,500.
- **Measure abstention honestly:** report accuracy-at-coverage (risk-coverage) and the share of questions sent to
  "ask back" or the paid LLM, not just top-1 accuracy. [paper] https://arxiv.org/abs/2403.18973

---

## Verdict

### What the research CONFIRMS

1. **Code computes every figure; models never write numbers.** This is how every credible product works (ThoughtSpot
   tokens, Looker/dbt semantic layers, Tableau statistical insight types), and it is the only way failures look like
   "can't answer" rather than a wrong number (dbt benchmark).
2. **Fixed sentence patterns + per-question plain-English phrases written once offline.** Template systems make fewer
   semantic errors than neural ones; open LLMs put at least one semantic error in >80% of data-to-text outputs; Tableau
   Pulse templates facts before any LLM touches them.
3. **Small local models for understanding, paid LLM only as fallback.** Fine-tuned encoders match or beat LLM prompting
   on closed-set classification at 10-1000× lower cost; hybrid routing keeps accuracy within ~2% of LLM-only at half the
   latency; RouteLLM-style routing cuts cost >2×.
4. **Follow-up suggestions and evidence (question wording, base, date).** Standard across Perplexity, Tableau Pulse,
   Looker, GWI, Statista; Tableau grounds follow-ups in detected facts.
5. **A precomputed-data design fits the 1 vCPU budget** for the encoder path (~0.1-0.3 s estimated).

### What the research CHALLENGES

1. **The generative "plan writer" (Qwen 0.5-1.7B) on the live path.** Measured CPU speeds put a 0.5B model at ~1.5-2 s
   and a 1.5-1.7B model at ~5-7 s per plan on one core, even with prefix caching; it cannot meet "well under 1 s" and
   would block the only core. It also does not attack the measured bottleneck (retrieval misses).
2. **Training on survey-worded synthetic questions.** The 98% → 57% collapse is the documented synthetic-vs-real and
   lexical-overlap failure (Kucia & Gawlik 2026; Spider-Syn/Realistic). More of the same data will repeat it.
3. **Treating "which survey question" as something a model can learn as a label.** It is an open, growing set (new
   waves, new questions); classifiers score 0% on labels they have not seen. Keep it as retrieval + rerank; use
   classifier heads only for the small closed slots.
4. **"Ask back when ambiguous" as a model judgement.** LLMs are poor at recognising ambiguity (CLAMBER), and the
   assistants' own guidance is "answer with a stated assumption unless a wrong guess is costly". Ask back only when a
   calibrated candidate set has 2-4 genuinely different answers; for market, default to the market the question
   implies (or US) and show a one-tap switch.
5. **Vertical bars for category comparisons.** Survey answer labels are long and many users are on phones; FT and
   Datawrapper both point to **horizontal**, sorted bars.
6. **The 79% / 232-question scoreboard as a decision tool.** ±5 points of noise; tuning and testing on the same real
   questions leaks. Decisions need a frozen, time-split, larger real test set.

### Concrete recommendations

**Live path (target p95 < 500 ms on 1 vCPU):**

1. **Slots by rules first, small heads second.** Market, years/periods, waves and demographic words come from a
   gazetteer in `config/*.yml` (synonyms there too, Power BI-style). Answer type (latest / trend / compare groups /
   breakdown / ranking) from a logistic head on the same bge-small embedding (SetFit-style); add a JointBERT-style
   tagger only if rules miss real spans in the logs.
2. **Retrieve at the "concept" level.** Group the same question asked across waves and years into one concept with one
   lexicalised phrase; retrieve concepts, let code pick waves and series. Fewer, more distinct candidates, and new waves
   need no retraining. ([estimate]; follows from the 0%-on-unseen-labels and recall findings.)
3. **Hybrid retrieval:** BM25 + bge-small (int8, ONNX or OpenVINO, benchmark both on the real vCPU) fused with RRF
   (k=60), then the MiniLM cross-encoder over the top 20-30. Measure recall@20/@50 before and after each change.
4. **Document expansion offline:** for every concept, have an open model (on Colab) write 15-30 *short, intent-style*
   questions (target ~5-8 words, persona-driven, forbidden to reuse the survey wording), filter them with the
   cross-encoder (Doc2Query--), and index them alongside the survey text. This moves query rewriting off the 1 vCPU.
5. **Fine-tune bge-small** with MultipleNegativesRankingLoss on (real logged question → concept) pairs plus the filtered
   synthetic pairs, one hard negative each, cross-encoder as teacher (GPL / listwise distillation). Never train on the
   test split.
6. **Calibrated decisions (conformal sets on cross-encoder scores, CICC):** set of 1 → answer; 2-4 → "Did you mean …"
   chips (this *is* the ask-back UI, and it costs nothing); larger set or top score below the out-of-scope threshold →
   paid LLM fallback, which may only choose concept ids and slot values from a supplied list (JSON schema), never
   numbers. If the LLM also finds nothing → honest "we haven't asked that; closest we have: X, Y" (never fall back to
   general knowledge, unlike Power BI Copilot). Fit thresholds on a calibration split of real questions.
7. **Templates:** sentence patterns per answer type × direction × significance; verbs driven by a significance test on
   the two bases; base (n) and wave date always shown; small-base warning below a set n. Cards fixed per answer type
   (latest / change / range; highest / lowest / gap). Follow-ups generated by code from the plan (other cut, other
   market if that concept exists there, longer period, nearest related concept), shown only if data exists.
8. **Charts by rule** (section 5), horizontal bars for categories.

**Offline / Colab:**

9. **Repurpose the Qwen LoRA as an offline labeller and question generator, not a live planner.** Use it (or a paid
   model under a capped budget) to propose labels for logged questions; send only disagreements between it and the
   cross-encoder to a person (the 36%-annotation result). If a local generative fallback is still wanted, keep it to
   0.5B Q4 with grammar-constrained JSON, prefix caching and 1 thread, and only behind the conformal "unsure" gate.
10. **Active learning loop:** log every question with its candidate set and outcome; weekly, label the uncertain and
    the frequent; add them to training and to the calibration split; publish a "review questions" view like Power BI's.

**Evaluation:**

11. Freeze a **time-split real test set** (train/tune on questions before a date, test on questions after), grow it
    toward ~700 labelled questions (±3 points), and never tune on it. Report separately: retrieval recall@6/@20/@50,
    slot accuracy, end-to-end accuracy, ask-back rate, fallback rate, and accuracy-at-coverage. Keep one small
    synthetic "capacity" set, but never use it to choose between designs.

### Pitfalls to avoid

- Prefill, not generation, dominates generative latency when the prompt carries a schema; never put the catalogue in a
  local model's prompt.
- INT8 is not always faster; benchmark on the actual server CPU before choosing ONNX vs OpenVINO.
- llama.cpp prompt caching can make outputs nondeterministic; tests that pin exact plans will flake.
- A teacher model labelling with one fixed prompt bakes its bias into every label; vary prompts and human-check
  disagreements.
- Synthetic generators spread questions evenly across the catalogue; real users cluster on a few topics. Weight
  evaluation by real frequency.
- Saying "rose"/"fell" on non-significant moves at n≈400 is the most likely *factual* error in a template system.

### Expected results ([estimate], to be verified on the time-split test)

The biggest gains should come from retrieval recall (document expansion + hybrid + fine-tuned bi-encoder), because 15%
of real questions currently never reach the top 20. If recall@20 moves from 85% into the low-to-mid 90s, end-to-end
accuracy on *answered* questions should rise with it, while the conformal gate turns most remaining errors into
"did you mean" chips or the paid fallback instead of wrong answers. All of this stays on the encoder path at roughly
0.1-0.3 s per answer with no paid call for the large majority of questions.
