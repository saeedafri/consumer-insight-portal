# How large AI systems answer, and the architecture Ask Coresight should keep (12 November 2026)

The question this answers: ChatGPT, Claude, Gemini and Grok seem to answer anything at once. What do they actually
do, what do companies that answer questions over their own data do, why does Ask struggle with wording it has never
seen, and what structure gives every analyst, user and client the same right answer, fast, on little RAM and CPU,
without API costs that grow with use?

Method: the public record (papers, model cards, open weights, vendors' engineering posts and documentation), what can
be observed from outside (tokenizers are published; Grok-1's weights are open), and experiments on our own catalogue.
The closed models' internals cannot be read; where this says how they work, it is what their makers and the open
models show.

## 1. How the large models work, from the bottom up

| Stage | What it is | In ChatGPT / Claude / Gemini / Grok | In Ask today |
|---|---|---|---|
| Tokenization | Text cut into pieces from a fixed vocabulary (byte-pair encoding or SentencePiece), each piece a number | GPT-4o/GPT-5: tiktoken `o200k_base`, ~200,000 pieces; Grok-1: SentencePiece, 131,072; Gemini: SentencePiece (~256,000 reported); Claude: its own, not published | bge-small's WordPiece, 30,522 pieces (`tokenizers`, Rust, microseconds) |
| Embedding | Each token looked up as a vector; the transformer turns the sequence into context-aware vectors | Thousands of dimensions per token (Grok-1: 6,144) | 384 dimensions; the first token's vector is the question's vector |
| Transformer | Layers of self-attention (every token weighs every other) and feed-forward networks | Decoder-only, tens of layers, mixture-of-experts in Grok-1 (8 experts, 2 per token, 314B weights) and reportedly the others | An encoder: 12 layers, 33M weights, ~3 ms on one CPU thread |
| Generation | One token at a time, each step reading a cache of earlier steps (KV cache) | Time to first token ~0.2-1 s, then tens of tokens a second; prompt caching and speculative decoding cut it | None: Ask never generates numbers or sentences with a model; it computes them |
| Retrieval (RAG) | Find the passages that answer, put them in the model's prompt | ChatGPT search, Claude projects, Gemini grounding: hybrid keyword + vector search, then a reranker | Keyword index + vector search over 3,082 questions and their asks |

Two facts matter most for us:

1. **The large models are not fast because they are big; they are fast at the parts that are precomputed.** Search
   indexes, embeddings of documents, KV and prompt caches are built before the question. Generation itself takes
   hundreds of milliseconds and more. Ask already computes in ~5-10 ms because its figures are prebuilt counts.
2. **A language model does not know our numbers, and is not trusted to produce them.** Every company that answers
   questions over its own data has the model read the question and choose; a deterministic engine computes.

## 2. What companies that answer questions over their own data do

| Company | What they built | The lesson |
|---|---|---|
| Snowflake (Cortex Analyst) | A semantic model (business names, synonyms, descriptions) and a Verified Query Repository; evaluations score against verified queries, with the queries under test removed first | Accuracy comes from the semantic layer and verified answers, measured honestly |
| Databricks (Genie) | Trusted assets: an answer from a parameterized example query or SQL function is labelled Trusted; benchmarks of 2-4 phrasings per question | Label what is verified; test every question in several wordings |
| Uber (QueryGPT) | An intent step maps the question to a business domain first, narrowing the search; evaluation scores intent, tables and SQL separately, from real logged questions with verified answers | Narrow before you search; score each step |
| Pinterest (text-to-SQL) | Table and query summaries embedded and searched; hit rate was 40% without table documentation and rose as documentation was weighted in | The description of each item matters more than the model |
| LinkedIn (SQL Bot) | Embedding retrieval of the top tables, then a re-ranker; a company-wide program to document tables, because retrieval failed where descriptions were missing | Documentation quality is the foundation |
| Anthropic (Contextual Retrieval) | Each chunk embedded with its context; keyword (BM25) and vector search together; a reranker: retrieval failures 5.7% → 3.7% → 2.9% → 1.9% | Hybrid search + context + reranking, each measured |
| Semantic caches (GPTCache and similar) | A question's vector compared with earlier questions; above a threshold, the stored answer is returned | Same meaning → same answer, but too low a threshold returns a wrong one |

The common process, in order: **describe the data well (semantic layer) → narrow, then retrieve with words and meaning
together → let a model only choose, never compute → verify and label trusted answers → evaluate every step on held-out
questions in several wordings → feed real questions back.** None of them claims 100% on free text; all separate
verified answers from best matches.

## 3. Why we struggle with wording we have never seen

Measured on our catalogue (section 5): of every wording the search never saw, the shipped bge-small finds the right
survey question for about 4 in 10. A hand check of 80 misses (12 Nov 2026):

| What the miss was | Share |
|---|---|
| Wrong: the right question exists and the wording points to it ("Why do people shop at Publix?" → the department-store question) | 45% |
| Equally right: another study asked the same thing, or the label was not the only answer | 27.5% |
| No single answer: vague, or the subject missing ("How does interest vary by income?") | 27.5% |

The causes, against what the large systems have:

1. **A general search model that has never seen our domain.** bge-small was trained on web text; "Publix", "BNPL",
   "Prime Big Deal Days", "over-indexes" mean little to it. The large models have read far more; companies fine-tune.
2. **No confidence gate.** Ask always answers its best guess. With the shipped model, its confidence (the gap to the
   next different question) barely separates right from wrong (section 5), so it cannot know when to ask instead.
3. **Ambiguity is real.** A quarter of the misses have no single right answer; the honest response is "did you mean A
   or B?", which no amount of search fixes.

## 4. The architecture: keep the structure, upgrade the meaning layer

Nothing in the large systems argues for sending each question to an AI model (cost grows with every question, ~1 s
each, numbers outside our control) or for a vector database (they matter at millions of vectors; we have ~25,000:
an exact numpy search is ~1-3 ms and needs no server). The structure we have is the one the industry converged on;
what is weak is the meaning layer, and the gate.

```
question
  │ 1. read (rules, ~1 ms): country, period, cut, kind, quoted answer         api/ask_reader.py
  │ 2. intent:                                                                  api/ask_index.py
  │      a. stored name or alias → that question (Verified)            hash lookup, microseconds
  │      b. else hybrid: keyword index + domain-tuned vectors over the catalogue and its asks   ~3-5 ms
  │      c. confidence gate: answer if the best beats the next different question by the margin;
  │         else "Did you mean A or B?" (never a silent guess)
  │ 3. canonical plan = (survey question, period, cut, kind, answers named)
  │ 4. answer cache keyed by the canonical plan: any wording of the same intent gets the same answer
  │ 5. compute exact figures from the published counts (numpy, ~5 ms)          api/ask_figures.py
  ▼
answer marked Verified, Matched, or a choice to make
```

Every publish, automatically (no model call per question asked):

| Step | Cost | Where |
|---|---|---|
| Name new questions, 8 example asks each, split shared names | ~$0.002 a survey, small model | etl/ask_semantic.py (built) |
| Embed the new questions and asks with the tuned model | seconds, local | api/ask_index.py add_vectors (built) |
| Check every question about the new survey; show it per survey | ~6 s a survey | etl/ask_quality.py (built) |
| Retrain the search model on the whole catalogue (it learns the domain, so new questions need no retraining to be found) | minutes on a laptop CPU; monthly, or when the check drops | new, if section 5 holds |

API cost then grows with the catalogue (a few new questions a week), never with how many people ask.

## 5. Experiments on our catalogue (12 November 2026)

Trained on Colab (an L4 GPU, under 1 compute unit a run): bge-small, our 3,076 survey questions, each question's name,
aliases and first six example asks; the last two asks and the 161 hand-written golden questions never trained on.

**Search alone** (no rules, no names): today's model finds the right question for 39.0% of unseen wording and 58.3%
of golden; trained 3 epochs, 50.8% and 66.9%; shrunk to 8-bit ONNX for the server, 50.1% and 66.3%, 34 MB (today 66 MB),
1.5 ms a question on one CPU thread (today 2.8 ms).

**Inside Ask** (names, rules, keywords, figures), where it counts:

| | Today's model | Trained v1 (its own floor) |
|---|---|---|
| 5,000 bank questions | 91.8% | 92.5% |
| Unseen wording | 39.3% | 47.6% |
| Golden, hand-written | **138/161** | 134/161 (lost 10 core tracker questions, won 6) |
| Gate on golden: right among answers shown | **86% → 97.6%** at 0.04 | 84.6% → 89.2% at 0.08 |

Lessons, each now in the code or the plan:
1. **Search-alone scores mislead.** +12 points alone became +0.7 inside Ask: a model is chosen by the whole pipeline.
2. **Thresholds belong to the model.** The off-topic floor (0.64) was tuned to today's model; the trained one scores on
   another scale (98% of real questions kept at 0.50). Each model folder now carries `calibration.json`, and each model
   its own vector cache (they were shared by text: a swap would have mixed two models' vectors).
3. **Near-twins must be one class in training.** The same question asked by several studies in other words was trained
   as each other's wrong answer, so v1 learned to be confident between them: its confidence no longer told right from
   wrong, and the gate could not use it. Today's model's confidence does (86% → 97.6%).
4. **Weight what analysts ask.** Equal weight per survey question pulled general wording toward old one-off studies.

**Decision:** the gate ships with today's model (0.04); v1 is kept out of production. Training v2 fixes 3 and 4, adds
Gemini-written asks, and is chosen only if Ask with it beats Ask today on the golden set and the bank, with the gate.

**Where 99% stands:** answers shown are 98.7% right on the bank and 97.6% on hand-written wording; the rest are asked to
choose (or the AI settles them). What lifts both the share answered at once and its accuracy, in order: v2 training,
analysts' real questions saved as verified (each fixes every later question worded like it), and the AI check only for
the unsure ones.

## Sources

- Anthropic, Contextual Retrieval (via InfoQ and Anthropic's cookbook): https://www.infoq.com/news/2024/09/anthropic-contextual-retrieval/ , https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide
- Uber, QueryGPT: https://www.uber.com/blog/query-gpt
- Snowflake, Cortex Analyst evaluations and Verified Query Repository: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations , https://docs.snowflake.com/user-guide/views-semantic/verified-query-repository
- Databricks, Genie benchmarks and trusted assets: https://docs.databricks.com/aws/en/genie/benchmarks
- Pinterest, text-to-SQL: https://medium.com/pinterest-engineering/how-we-built-text-to-sql-at-pinterest-30bad30dabff
- LinkedIn, SQL Bot (summary): https://www.zenml.io/llmops-database/building-a-production-text-to-sql-assistant-with-multi-agent-architecture
- Grok-1 open weights (architecture, tokenizer): https://github.com/alsora/grok-1 (mirror of xai-org/grok-1)
- OpenAI tokenizers (tiktoken): https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken , https://leehanchung.github.io/blogs/2024/05/15/gpt-4o-tokenizer/
- Inference latency (prefill, KV cache, prompt caching, speculative decoding): https://tianpan.co/blog/2025-10-30-llm-latency-optimization-production
- Fine-tuning embedding models on domain pairs: https://www.philschmid.de/fine-tune-embedding-model-for-rag , https://redis.io/blog/get-better-rag-by-fine-tuning-embedding-models/
- Exact versus approximate vector search at small scale: https://dadops-site.pages.dev/blog/vector-search-benchmarks/index.html
- Semantic caching and its thresholds: https://zilliz.com/blog/Yet-another-cache-but-for-ChatGPT
- Answer, clarify or abstain: https://arxiv.org/abs/2305.14613
