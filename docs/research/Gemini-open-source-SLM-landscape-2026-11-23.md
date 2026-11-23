# Ready-Made Open-Source Small LLMs & Rerankers for Ask CIP (23 November 2026)

**Author:** Gemini (Independent Model & Architecture Research)  
**Date:** 23 November 2026  
**Repository State Inspected:** `cip-test` `HEAD 0e57418` (`api/ask_plan.py`, `api/ask_engine.py`, `api/ask_model.py`, `scripts/colab/ask_plan_writer.ipynb`, `status/README.md`)

---

## 1. Executive Answer

1. **You are NOT training a model from scratch.** CIP already uses pretrained open-source Hugging Face models (`BAAI/bge-small-en-v1.5`, 66.5 MB; `cross-encoder/ms-marco-MiniLM-L-6-v2` fine-tuned as `models/ask-reader`, 23.0 MB), and the notebook you already started ([scripts/colab/ask_plan_writer.ipynb](../../scripts/colab/ask_plan_writer.ipynb)) LoRA-tunes existing Apache-2.0 Alibaba models (`Qwen2.5-0.5B/1.5B-Instruct`, `Qwen3-0.6B/1.7B`) while **Cell 7b already benchmarks two ready-made models with zero training** (`Qwen3-4B-Instruct-2507` and `Qwen3-1.7B` with 5 worked examples).
2. **Yes — strong, commercially licensed, ready-to-use small ChatGPT-style LLMs exist today** across Hugging Face and GitHub (`Qwen3-4B-Instruct-2507`, `Qwen3-1.7B/0.6B`, `Qwen3.5-0.8B/2B/4B`, `ibm-granite/granite-4.0-h-micro` & `granite-4.0-1b`, `microsoft/Phi-4-mini-instruct`, `HuggingFaceTB/SmolLM3-3B`, `google/gemma-4-E2B-it`, and ultra-tiny `cactus-compute/cactus` Needle).
3. **Why a generic ready-made model alone still hits two engineering limits for Ask CIP:**
   - **Domain schema gap:** No pretrained model knows CIP's compact bitset plan JSON (`ask`, `among`, `by`, `op: chain`, `both/either/not`, `D1/D2/D5/D6/D7`) without either **5–8 few-shot examples in every prompt** (~1,500–2,000 input tokens → slow prefill on 1 vCPU Azure) OR a **lightweight LoRA adapter** (what your notebook is testing) + **`llama.cpp` JSON-Schema / GBNF constrained decoding**.
   - **Azure App Service CPU/RAM physics:** CIP runs Nginx + FastAPI + ETL + BGE + MiniLM (`~435 MiB` RSS) inside a single CPU-only container (`deploy/Dockerfile`). A 4B `Q8_0` model (`4.28 GB`) or multimodal `Gemma 4 E2B` (`3.11–5.05 GB`) will blow past small App Service RAM budgets and crawl at `1–5 tok/s` on 1 vCPU. Only **`0.6B–2B` (`Q4_K_M` ~0.5–1.3 GB)** runs comfortably on 1–2 vCPU, *or* you route the ~20% hard queries to a fast hosted open-weight API (Groq / Fireworks / DeepInfra / Together at `\$0.05–\$0.30 / 1M` tokens).

---

## 2. Tools & Sources Actually Executed (Full Transparency)

| Tool / Skill Requested | Actual Availability & What Ran | Result |
|---|---|---|
| **Hugging Face Hub Live API** (`huggingface.co/api/models`) | Executed live (read-only) | Verified exact parameter counts, download counts, **commercial licenses**, gated status, last-modified dates, and **exact `Q4_K_M` / `Q8_0` GGUF byte sizes** for 40+ 2025–2026 models. |
| **GitHub CLI (`gh search repos` — Agent Reach `dev` backend) & GitHub REST API** | `gh` installed & authenticated | Verified live stars, licenses, and push dates for `llama.cpp` (136k★), `private-gpt` (57.6k★), `BitNet` (42.4k★), `Chat2DB` (28.4k★), `pandas-ai` (24k★), `vanna` (23.8k★), `WrenAI` (18.4k★), `outlines` (16k★), `cactus-compute/cactus` (14.9k★), `llama-cpp-python` (10.7k★), `SQLBot` (7.2k★), `FlashRank` (1k★). |
| **`last30days` v4.6.0 skill (Python engine)** | Ran live (`--quick`, keyless local mode) | Pulled live Oct–Nov 2026 threads from **Reddit** (`r/LocalLLaMA`, `r/LocalLLM`, `r/ollama` — 4 threads, 1,221 upvotes) and **Hacker News** (2 stories, 486 pts), supplemented by direct HN Algolia queries across 7 model families. |
| **Web Search (`search_web`)** | 8 live queries | Covered Reddit `r/LocalLLaMA` CPU tool-calling threads, LinkedIn enterprise SLM production posts, BFCL v3/v4 benchmarks, `llama.cpp` 1–2 vCPU speed tests, rerankers, and hosted open-weight APIs. |
| **`agent-reach` CLI (`opencli`, `mcporter`, `rdt`, `twitter`, `bili`, `yt-dlp`)** | **Not installed on PATH** (`command not found`) | Only `gh` (and `ollama`, server stopped) are present locally. Direct Reddit JSON endpoint returned HTTP `403` (covered instead via `last30days` + `search_web`). |
| **Instagram skills (`ig-audit`, `ig-reel`, `ig-plan`, etc.) & `favstash`** | Checked skill definitions + `favstash` MCP | Installed `ig-*` skills are **content-creation/analytics tools for posting on your own Instagram**, not search scrapers. Instagram search requires `opencli` + logged-in Chrome or a `SCRAPECREATORS_API_KEY` (unconfigured). `favstash` had `0` saved items on this topic. |
| **LinkedIn MCP (`linkedin`)** | Checked `linkedin_get_auth_status` (authenticated) | LinkedIn MCP exposes only profile/posting/event tools (no feed/post search API); LinkedIn SLM discussions were researched via `search_web` (`site:linkedin.com`). |
| **REA (`reverse-engineer-anything`)** | Checked `SKILL.md` + `inspect_artifact.json` | REA targets compiled binaries, APKs, Electron apps, firmware, and packet captures; its own `SKILL.md` instructs skipping REA for normal source repos. Inspected CIP's shipped ONNX binaries (`bge-small-en-v1.5` 66.5 MB; `ask-reader` 23.0 MB) directly with `onnxruntime` instead. |

---

## 3. Ready-Made Commercially Safe Open-Weight Small LLMs (Verified Live on HF Hub, Nov 2026)

Every model below is **non-gated** and carries a **permissive commercial license (Apache-2.0 or MIT)** verified directly from the Hugging Face Hub API on `2026-11-23`.

| Model (Hugging Face ID) | Total Params | License | Exact GGUF `Q4_K_M` | Exact GGUF `Q8_0` | Est. 1–2 vCPU Speed (`llama.cpp`) | Status vs `ask_plan_writer.ipynb` | Verdict for Ask CIP |
|---|---:|---|---:|---:|---|---|---|
| **`Qwen/Qwen3-0.6B`** | 0.75B | Apache-2.0 | ~0.52 GB | **0.64 GB** | ~15–45 tok/s (`Q4`), ~10–30 (`Q8`) | **Already in Cell 7** | Best ultra-lightweight CPU option (fits easily alongside existing `~435 MiB` API worker). Needs LoRA + JSON grammar for high plan accuracy. |
| **`Qwen/Qwen3-1.7B`** | 2.03B | Apache-2.0 | ~1.10 GB | **1.83 GB** | ~6–22 tok/s (`Q4`), ~4–15 (`Q8`) | **Already in Cell 7 & 7b** | Strongest CPU-practical sweet spot (`BFCL Live 74.6`). Use **`Q4_K_M` (~1.1 GB)** on tight Azure RAM; `Q8_0` (`1.83 GB`) needs ≥4 GB container headroom. |
| **`Qwen/Qwen3-4B-Instruct-2507`** | 4.02B | Apache-2.0 | **2.50 GB** | 4.28 GB | ~2–9 tok/s (`Q4`), ~1–6 (`Q8`) | **Already in Cell 7b (zero-shot)** | Best pure-text non-thinking 4B zero-shot JSON/tool caller (`6.73M` downloads). Great zero-shot test baseline, but slow on 1 vCPU Azure. |
| **`Qwen/Qwen3.5-0.8B`** *(Mar 2026)* | 0.87B | Apache-2.0 | **0.53 GB** | **0.81 GB** | ~30–45 tok/s (`Q4` multi-core) | **NEW — Not in notebook yet** | Newer Gated-DeltaNet hybrid successor to Qwen3-0.6B (`2.34M` dl). Note: multimodal VLM checkpoint (`image-text-to-text`); test text-only GGUF compatibility first. |
| **`Qwen/Qwen3.5-2B`** *(Mar 2026)* | 2.27B | Apache-2.0 | **1.28 GB** | **2.01 GB** | ~10–25 tok/s (`Q4`) | **NEW — Not in notebook yet** | Direct 2026 successor to `Qwen3-1.7B` (`5.18M` dl). High priority to add to Cell 7b zero-shot benchmark! |
| **`ibm-granite/granite-4.0-1b`** | 1.63B | Apache-2.0 | **1.02 GB** | **1.74 GB** | ~15–35 tok/s (`Q4`) | **NEW — Not in notebook yet** | Enterprise-focused pure text-generation model built for low-latency structured extraction & tool use. |
| **`ibm-granite/granite-4.0-h-micro`** | 3.19B | Apache-2.0 | **1.94 GB** | 3.40 GB | ~12–30 tok/s (`Q4`, hybrid Mamba-2) | **NEW — Not in notebook yet** | **Top zero-shot contender to add to Cell 7b!** Hybrid Mamba-2 + Transformer cuts CPU prefill/memory bottlenecks and targets enterprise JSON schemas. |
| **`microsoft/Phi-4-mini-instruct`** | 3.84B | MIT | **2.49 GB** | 4.08 GB | ~3–10 tok/s (`Q4`) | **NEW — Not in notebook yet** | Top-tier restraint on `r/LocalLLaMA` tool-calling benchmarks (rarely misfires/hallucinates tools). Strong Cell 7b zero-shot contender. |
| **`HuggingFaceTB/SmolLM3-3B`** | 3.08B | Apache-2.0 | **1.92 GB** | 3.28 GB | ~10–25 tok/s (`Q4`) | **NEW — Not in notebook yet** | Dual-mode (no-think) with native XML/JSON tool calling (~95% schema compliance). |
| **`google/gemma-4-E2B-it`** *(2026)* | 5.12B *(E2B)* | Apache-2.0 | **3.11 GB** | 5.05 GB | ~10–25 tok/s (`Q4` multi-core) | **NEW — Watch RAM!** | First Apache-2.0 Gemma! Strong reasoning, **but** carries `5.12B` total weights (multimodal/per-layer embeddings) → `3.11 GB` even at `Q4_K_M`, heavy for small Azure containers. |
| **`cactus-compute/cactus` (Needle)** | 26M–100M | Apache-2.0 | **< 0.05 GB** | — | Ultra-fast CPU | **NEW — Micro edge option** | 14.9k★ GitHub (`776` HN pts May 2026). Byte-level grammar-constrained tool calling in `< 50 MB`; needs domain tuning on CIP's schema, best if RAM is ultra-tight. |
| **`microsoft/BitNet-b1.58-2B-4T`** | 2.4B (1.58-bit) | MIT | ~0.4–1.2 GB (`I2_S`) | N/A | ~30–50 tok/s (`bitnet.cpp`) | **NEW — Speed specialist** | Blazing CPU throughput via ternary weights, but weaker out-of-the-box JSON schema discipline without custom grammar wrapper. |

---

## 4. Models & Open-Source Frameworks Explicitly Ruled Out (and Why)

| Model / Project | Why Ruled Out for Commercial Ask CIP |
|---|---|
| `Salesforce/xLAM-2-1b-fc-r`, `xLAM-2-3b-fc-r`, `MadeAgents/Hammer2.1-1.5b`, `jinaai/jina-reranker-v2-base-multilingual` | **`cc-by-nc-4.0` (Non-Commercial)** — legally prohibited in a commercial enterprise platform. |
| `Qwen/Qwen2.5-3B-Instruct`, `LiquidAI/LFM2.5-1.2B-Instruct`, `LiquidAI/LFM2-1.2B-Tool` | Restricted custom licenses (`other`: Qwen2.5-3B is research-only; Liquid LFM2 caps free commercial use under `\$10M` revenue). |
| `google/functiongemma-270m-it`, `google/gemma-3-1b/4b-it`, `meta-llama/Llama-3.2-1B/3B-Instruct` | Gated non-Apache/MIT terms; Google's own benchmark shows FunctionGemma gets only `58%` single-turn / `10–39%` multi-turn zero-shot (still requires fine-tuning); `r/LocalLLaMA` repeatedly flags Llama-3.2-3B for poor abstention restraint. |
| **Text-to-SQL / BI Agents:** `Canner/WrenAI` (18.4k★), `vanna-ai/vanna` (23.8k★), `sinaptik-ai/pandas-ai` (24k★), `dataease/SQLBot` (7.2k★) | These generate **SQL** against live databases and still require an LLM underneath. Ask CIP's `api/ask_engine.py` already computes exact cross-question bitset joins over prebuilt `people.json.gz` files in **sub-millisecond NumPy** with zero DB load—replacing it with Text-to-SQL would increase latency, DB load, and multi-tenant SQL risk. |
| **Heavy Rerankers (`bge-reranker-v2-m3`, `Qwen3-Reranker-0.6B`, `zerank-1-small`)** | Already measured in [ask-cip-model-training.md](ask-cip-model-training.md) Part 18: 149M–600M rerankers took `~1.1–1.2 s` per question on 1 vCPU without lifting end-to-end scores above Ask's existing `23 MB` MiniLM + hybrid retrieval (`97–98%` top-14 recall). |

---

## 5. Third Path Worth Knowing: Zero-Training Hosted Open-Weight APIs (Pennies/Month, 0 Azure RAM)

CIP's `api/ask_model.py` **already uses standard OpenAI-compatible `chat/completions` with strict `json_schema`** and caches every reading permanently in `logs/ask-readings.json` (so repeated questions cost `\$0`). Instead of cramming a 2–4 GB GGUF LLM into a 1–2 vCPU Azure web container, you can also test routing **only the ~15–20% hard combined questions** (where `api/ask_plan.py` rules fall short) to fast hosted open-weight providers:

- **Fireworks AI / Together AI / DeepInfra / Groq / Cerebras:** Host Apache-2.0 **Qwen3 / Llama 4** models with OpenAI-compatible JSON schema decoding at **`\$0.05–\$0.30` per 1M tokens** (`~\$0.0001–\$0.0003` per *uncached* hard question, sub-second latency, **0 extra RAM on Azure**).
- **Important privacy note:** Only send candidate question text and schema (already sanitized in `ask_model.py`), **never** raw respondent rows or private client-restricted survey text unless covered by a zero-data-retention (ZDR) enterprise DPA.

---

## 6. Concrete Action Plan for Your Already-Running Colab Job

1. **Let your current `scripts/colab/ask_plan_writer.ipynb` finish** — it is NOT training from scratch; it already compares 4 LoRA-tuned Qwen models against 2 zero-shot ready-made models (`Qwen3-4B-Instruct-2507` and `Qwen3-1.7B`) on `ask_heldout2` (`30` unseen hard questions) and saves progress to Drive.
2. **After it finishes, add a quick ~10-minute Cell 7b zero-shot pass** (reusing the same `RUN = "v1"` Drive folder so Steps 3–7 are skipped!) to test the 3 strongest newer commercial ready-made models we found:
   - `ibm-granite/granite-4.0-h-micro` (Apache-2.0, Mamba-2 hybrid)
   - `microsoft/Phi-4-mini-instruct` (MIT, strong restraint)
   - `Qwen/Qwen3.5-2B` (Apache-2.0, newer 2026 successor to Qwen3-1.7B)
3. **Production serving safeguards before shipping any local GGUF model on Azure:**
   - Export and benchmark **`Q4_K_M`** alongside Cell 8's `Q8_0` (`Qwen3-1.7B` `Q8_0` is `1.83 GB` + KV cache on top of `~435 MiB` existing RSS, whereas `Q4_K_M` is `~1.10 GB`, and `Qwen3-0.6B` is `0.52–0.64 GB`).
   - Always enable **`llama.cpp` JSON-Schema / GBNF grammar constraints** at inference time so malformed JSON drops to `0%`.
   - Ship the local GGUF model **only if** its `held-out-2` score clearly beats your deterministic rules (`17/30` in `status/README.md`) while keeping 1-vCPU latency and total container RSS inside your Azure App Service tier limits.
