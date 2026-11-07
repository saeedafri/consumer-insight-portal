# Gemini & Claude Skills Audit & Space Optimization Report

> **Audit Date:** November 8, 2026  
> **Target System:** Consumer Insight Portal (CIP) — FastAPI + Nginx + Next.js 16 on Azure App Service (Central US) + Azure MySQL + Forsta Python ETL.  
> **Performance Targets:** <100ms global latency at 50,000+ users, 10,000–20,000 req/s, flat CPU/RAM/cost, high-throughput ETL.  
> **Governing Rule:** Every KEEP-CIP claim is verified against CIP codebase file:line and measurement commands. No files moved without explicit approval.

---

## Executive Summary

A total of **1,178 raw entries** across 5 global directories were scanned, representing **340 unique skills** across **491 unique real paths** on disk.

### Measured Disk Usage (Before Audit)

```bash
$ du -sh ~/.claude/skills ~/.claude/plugins ~/.gemini/skills ~/.gemini/config/skills ~/.agents/skills ~/.agents/repos
1.2G    ~/.claude/skills         (278 entries, gstack monorepo alone = 1.1 GB; 74 symlinks)
1.1G    ~/.claude/plugins        (10 plugins, marketplaces = 806 MB, cache = 282 MB)
 22M    ~/.gemini/skills         (240 entries)
 28M    ~/.gemini/config/skills  (321 entries)
 41M    ~/.agents/skills         (338 entries)
796M    ~/.agents/repos          (upstream cloned repositories)
```

### Verdict Summary Breakdown

| Verdict Category | Count | Criteria & Definition |
| :--- | :---: | :--- |
| **KEEP-CIP** | **32** | Directly moves a measured CIP metric (latency, RAM, CPU, storage, cost, ETL throughput) with file:line verification. |
| **KEEP-GENERAL** | **50** | Production utilities used for Instagram video pipelines, general UI/export tooling, or research outside CIP. |
| **DUPLICATE** | **24** | Functionally identical or shallow duplicates of canonical skills already retained on disk. |
| **REMOVE** | **234** | Irrelevant to stack (e.g. AWS on an Azure stack, iOS on a web app, genomics bio-tools), broken, or abandoned. |
| **TOTAL UNIQUE SKILLS** | **340** | **Total Space Reclaimable:** **2,163.77 MB (~2.11 GB)** |

---

## Section 1: Comprehensive Inventory Table (Step 1)

Sorted by real path disk size descending. Broken symlinks detected: **0**.

| Skill Name | Real Size | Loaded By | Folders Appearing In | Real Path | Purpose (from SKILL.md) |
| :--- | :---: | :---: | :--- | :--- | :--- |
| `gstack` | **1.09 GB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gstack` | Fast headless browser for QA testing and site dogfooding. (gstack) |
| `excalidraw-diagram-skill` | **135.30 MB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.codex/skills/excalidraw-diagram-skill` | Create Excalidraw diagram JSON files that make visual arguments. Use when the user wants to visualize workflow |
| `synced` | **22.09 MB** | Claude | .claude/skills | `~/.claude/skills/synced` | No description provided in SKILL.md |
| `impeccable` | **18.64 MB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/config/skills/impeccable` | Use when the user wants to design, redesign, shape, critique, audit, polish, simplify, harden, animate, or oth |
| `archify` | **10.73 MB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/archify` | Create polished, validated architecture, workflow, sequence, data-flow, and lifecycle/state diagrams as explor |
| `canvas-design` | **5.52 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/canvas-design` | Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when |
| `.trash` | **4.23 MB** | Claude | .claude/skills | `~/.claude/skills/.trash` | No description provided in SKILL.md |
| `awesome-design-md` | **2.85 MB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/awesome-design-md` | Curated collection of 84+ production-grade DESIGN.md specifications extracted from iconic developer tools, tec |
| `claude-api` | **2.18 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/claude-api` | Reference for the Claude API / Anthropic SDK — model ids, pricing, params, streaming, tool use, MCP, agents, c |
| `breakout-card` | **1.35 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/breakout-card` | Style for edit-video: a white grid page with the speaker in a rounded card along the bottom and their head bre |
| `docx` | **1.20 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/docx` | Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files) or Wo |
| `pptx` | **1.20 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/pptx` | Use this skill any time a .pptx or .potx file is involved in any way — as input, output, or both. This include |
| `xlsx` | **1.16 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/xlsx` | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user  |
| `edit-video` | **1.00 MB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing/edit-video` | Edit Reels, TikToks and YouTube Shorts from a brief, footage or reference: cut, captions, sound, motion graphi |
| `ce-code-review` | **688 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-code-review` | Review a named diff or PR for bugs, regressions, tests, and standards. Use when asked to review code or when a |
| `aws-ai-ml` | **676 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-ai-ml` | Selects, deploys, and customizes AI models on Amazon SageMaker. Fine-tuning (SFT, DPO, RLVR, RLAIF), model sel |
| `aws-observability` | **612 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-observability` | Builds, configures, debugs, and optimizes AWS observability with CloudWatch (Log Insights, Metrics, Alarms, Da |
| `ce-plan` | **612 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-plan` | Create structured plans for multi-step work, including software and non-software tasks. Use when asked to plan |
| `ce-work` | **580 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-work` | Execute a plan or concrete work prompt end-to-end. Use when implementing from a plan document, a spec path, or |
| `ce-doc-review` | **540 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-doc-review` | Review requirements, plans, or specs with role-specific lenses. Use when the user wants to improve an existing |
| `ce-brainstorm` | **472 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-brainstorm` | Explore vague or ambitious ideas into a right-sized requirements-only unified plan. Use when the user wants to |
| `amazon-bedrock` | **396 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/amazon-bedrock` | Builds generative AI applications on Amazon Bedrock. Covers model invocation (Converse API, InvokeModel), RAG  |
| `security-audit` | **348 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/security-audit` | Security guidance and vulnerability review for codebases, APIs, services, CLI tools, libraries, and daemons. U |
| `ce-babysit-pr` | **344 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-babysit-pr` | Babysits an open GitHub PR until merge-ready. Use when asked to watch a PR over time — not for one-shot commen |
| `exploratory-data-analysis` | **336 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/scientific-agent-skills/skills/exploratory-data-analysis` | Performs bounded, local exploratory analysis of explicitly supported scientific files. Supports redacted CSV/T |
| `ce-compound` | **320 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-compound` | Document a solved problem as a durable repo learning. Use when verified work produced non-obvious reasoning ab |
| `supply-chain-risk-auditor` | **316 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/trailofbits-skills/plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor` | Audits a project's dependencies for supply-chain risk: version-matched advisories for direct dependencies and  |
| `ce-polish` | **312 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-polish` | Polish a working feature through user-directed live browser feedback. Use when a functional feature needs focu |
| `ce-optimize` | **292 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-optimize` | Optimize a named target with a measured loop: attribute a workload's cost, or score variants and keep winners. |
| `ce-pov` | **284 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-pov` | Judge a supplied subject against the project's evidence and constraints. Use when assessing an external-adopti |
| `ce-ideate` | **264 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-ideate` | Generate and evaluate grounded ideas. Use when the user wants ideas, improvements, or surprising directions be |
| `skill-creator` | **248 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/skill-creator` | Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to c |
| `scientific-visualization` | **244 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/scientific-agent-skills/skills/scientific-visualization` | Creates and audits truthful, accessible, publication-ready scientific figures with Matplotlib, Seaborn, or Plo |
| `eval-engineering` | **208 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/eval-engineering` | Inspect an agent repository and optional traces, interview the user, write reviewed Task Specs, build and audi |
| `shadcn` | **204 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/shadcn` | Manages shadcn components and projects — adding, searching, fixing, debugging, styling, and composing UI, incl |
| `migrate-radix-to-base` | **200 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/migrate-radix-to-base` | Migrates React projects and components from Radix UI to Base UI. Use when asked to migrate from radix, move to |
| `ce-sweep` | **184 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-sweep` | Sweep configured feedback sources (Slack, GitHub Issues; email experimental) for new items: acknowledge at sou |
| `theme-factory` | **180 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/theme-factory` | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing page |
| `graphify` | **164 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/graphify` | Use for any question about a codebase, its architecture, file relationships, or project content — especially w |
| `aws-security` | **160 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-security` | Covers AWS security services and workflows — Security Hub V2 (OCSF) findings, connectors, aggregators, automat |
| `shap` | **160 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/scientific-agent-skills/skills/shap` | Explain and audit machine-learning predictions with SHAP. Use for selecting SHAP explainers and maskers, compu |
| `sharp-edges` | **160 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/trailofbits-skills/plugins/sharp-edges/skills/sharp-edges` | Identifies error-prone APIs, dangerous configurations, and footgun designs that enable security mistakes. Use  |
| `aws-cloudformation` | **156 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-cloudformation` | Authors, validates, and troubleshoots AWS CloudFormation templates. Covers template authoring with secure defa |
| `scikit-learn` | **156 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/scientific-agent-skills/skills/scikit-learn` | Supports machine learning in Python with scikit-learn. Applies when working with supervised learning (classifi |
| `mcp-builder` | **144 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/mcp-builder` | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with externa |
| `aws-containers` | **140 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-containers` | Builds and deploys containerized workloads on Elastic Kubernetes Service (EKS), Elastic Container Service (ECS |
| `ce-prototype` | **140 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-prototype` | Build a throwaway prototype to answer how something should work, feel, or read. Use when committing the wrong  |
| `ce-resolve-pr-feedback` | **140 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-resolve-pr-feedback` | Judge PR feedback centrally, apply valid fixes, and complete review conversations with publication verified. U |
| `ce-compound-refresh` | **136 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-compound-refresh` | Refresh the repo's captured learnings against the current codebase. Use when auditing stale, overlapping, supe |
| `ce-setup` | **136 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-setup` | Check Compound Engineering health and repo-local config, or scaffold a Compound Pack with `pack:<id>`. |
| `launch-with-aws` | **132 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/launch-with-aws` | Migrates vibe-coded web applications to AWS. Handles the full workflow from analysis through migration to depl |
| `writing-skills` | **132 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment |
| `aws-storage` | **124 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-storage` | Selects, investigates, and compares AWS object, file, and block storage services, and answers cost, performanc |
| `aws-cdk` | **120 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-cdk` | Authors, deploys, and troubleshoots AWS infrastructure using CDK with TypeScript or Python. Covers best practi |
| `polars` | **116 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/scientific-agent-skills/skills/polars` | High-performance DataFrame library for Python ETL, analytics, and pandas migration. It supports expression-bas |
| `aws-auth` | **112 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-auth` | Adds user authentication to web and mobile apps with Amazon Cognito (user pools and identity pools) and the AW |
| `aws-database` | **112 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-database` | Routes any task involving AWS databases — choosing, comparing, recommending, getting started with, or operatin |
| `ce-debug` | **108 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-debug` | Diagnosis loop for bugs and failing behavior. Use when asked to debug or fix failing or slow behavior. |
| `aws-serverless` | **104 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-serverless` | Builds, deploys, manages, debugs, configures, and optimizes serverless applications on AWS using Lambda, API G |
| `lfg` | **100 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/lfg` | Take a request all the way to done, hands-off, through the right Compound Engineering skills. A code change en |
| `brainstorming` | **92 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/brainstorming` | You MUST use this before any creative work - creating features, building components, adding functionality, mod |
| `ce-retune` | **92 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-retune` | Retune a skill corpus for a new model, measurement-first: mine the run archive for a baseline, establish a noi |
| `harvey` | **92 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/harvey` | Autonomous sales agent, cold email copywriting, B2B lead generation, prospecting, qualification, offer strateg |
| `subagent-driven-development` | **92 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session |
| `aws-billing-and-cost-management` | **88 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-billing-and-cost-management` | Analyze AWS costs, find savings, manage budgets, evaluate Savings Plans and Reserved Instances, right-size EC2 |
| `ce-riffrec-feedback-analysis` | **88 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-riffrec-feedback-analysis` | Analyze recorded product feedback into evidence for bugs and requirements. Use when a Riffrec capture or other |
| `paper-grid` | **88 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/paper-grid` | Style for edit-video: a white paper pane with a quiet grid above the speaker and one clean animated UI artifac |
| `reverse-engineer-anything` | **88 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/reverse-engineer-anything` | Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA. Use s |
| `ce-commit-push-pr` | **84 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-commit-push-pr` | Commit, push, and open a PR. Use when asked to ship/open a PR, or for PR-description-only flows like writing,  |
| `diagnosing-superpowers` | **84 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/diagnosing-superpowers` | Use when a superpowers session went wrong and your human partner wants to know why — repeated work, ignored pl |
| `ce-dogfood` | **80 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-dogfood` | Hands-off, diff-scoped browser QA of the active branch: maps user flows, drives a real browser, autonomously f |
| `pdf` | **80 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/pdf` | Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text |
| `swarm` | **80 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/swarm` | Dispatches many independent items in parallel: create a table, fan out to subagents, aggregate results. One ro |
| `aws-compute` | **72 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-compute` | Provisions, scales, and operates Amazon EC2 virtual-machine workloads: instance-type selection (Graviton/Arm64 |
| `agent-reach` | **68 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/agent-reach` | MUST USE when user wants to research/search/look up/find anything on the internet — e.g. "research this topic" |
| `aws-deployment` | **68 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-deployment` | Configures CI/CD pipelines using AWS CodePipeline, CodeBuild, CodeDeploy, CodeConnections, and CodeArtifact. C |
| `aws-iam` | **68 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-iam` | Provides verified corrections for IAM behaviors that AI agents frequently get wrong — policy evaluation edge c |
| `adaptive-glass` | **64 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/adaptive-glass` | Style for edit-video: the real speaker with moving proof in footage-matched glass panels, centered captions an |
| `algorithmic-art` | **64 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/algorithmic-art` | Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this wh |
| `systematic-debugging` | **64 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| `aws-sdk-js-v3-usage` | **60 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-sdk-js-v3-usage` | AWS SDK for JavaScript v3 development patterns. Use when writing JavaScript or TypeScript code that uses AWS s |
| `aws-sdk-python-usage` | **60 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-sdk-python-usage` | AWS SDK for Python (boto3/botocore) development patterns. You MUST use this skill when writing Python code tha |
| `ce-product-pulse` | **60 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-product-pulse` | Generate time-windowed product pulse reports from configured signals. |
| `ce-explain` | **56 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-explain` | Explain how and why something has its current shape, or what happened over a window of work, grounded in evide |
| `ig-human` | **56 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/config/skills/ig-human` | Strip the machine fingerprint out of any draft - em dashes, AI slop words, invisible watermark characters - an |
| `ig-reel` | **56 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/instagram-agent-skill/skills/ig-reel` | Write an Instagram Reel from a raw idea - hook options off 26 formulas, the spoken script, the on-screen text, |
| `slack-gif-creator` | **56 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/slack-gif-creator` | Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools |
| `agy-customizations` | **52 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/agy-customizations` | Comprehensive guide and reference for the Antigravity Customization System. Use to explain how customizations  |
| `web-artifacts-builder` | **52 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/web-artifacts-builder` | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web tech |
| `differential-review` | **48 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/trailofbits-skills/plugins/differential-review/skills/differential-review` | Performs security-focused differential review of code changes. Adapts analysis depth to codebase size, uses gi |
| `ce-strategy` | **44 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-strategy` | Create or update STRATEGY.md. Use when starting a product, adding a strategy doc, or changing direction or roa |
| `playwright` | **44 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.codex/skills/playwright` | Use when the task requires automating a real browser from the terminal (navigation, form filling, snapshots, s |
| `product-motion-ads` | **44 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/product-motion-ads` | Style for edit-video: a vertical motion-graphics ad built in code from the product itself (its app, site, scre |
| `using-superpowers` | **40 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/using-superpowers` | Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before |
| `ce-simplify-code` | **36 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-simplify-code` | Simplify code for clarity, reuse, quality, and efficiency while preserving behavior, and prune tests and comme |
| `managed-deep-agents` | **36 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/managed-deep-agents` | INVOKE THIS SKILL when building, testing, or deploying Managed Deep Agents in LangSmith. Walks a user through  |
| `setup-matt-pocock-skills` | **36 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/setup-matt-pocock-skills` | Configure this repo for the engineering skills: set up its issue tracker, triage label vocabulary, and domain  |
| `internal-comms` | **32 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/internal-comms` | A set of resources to help me write all kinds of internal communications, using the formats that my company li |
| `langgraph-fundamentals` | **32 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-fundamentals` | INVOKE THIS SKILL when writing ANY LangGraph code. Covers StateGraph, state schemas, nodes, edges, Command, Se |
| `publish-and-analyze` | **32 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/4-publish-and-learn/publish-and-analyze` | Take an approved cut to a scheduled post and back into the next idea: delivery export, a real-frame cover, hoo |
| `semgrep-rule-creator` | **32 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/trailofbits-skills/plugins/semgrep-rule-creator/skills/semgrep-rule-creator` | Creates custom Semgrep rules for detecting security vulnerabilities, bug patterns, and code patterns. Use when |
| `teach` | **32 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/teach` | Teach the user a new skill or concept, within this workspace. |
| `webapp-testing` | **32 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/webapp-testing` | Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend  |
| `ask-matt` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ask-matt` | Ask which skill or flow fits your situation. A router over the skills in this repo. |
| `ce-bakeoff` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-bakeoff` | Develop independent competing solutions to a defined brief, compare them, and synthesize a winning approach. U |
| `ce-promote` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-promote` | Draft launch or promotion copy for a shipped feature. |
| `ce-proof` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-proof` | Publish, read, comment on, or edit markdown in Proof. Use for Proof links, sharing specs/plans/drafts, or publ |
| `ce-test-browser` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-test-browser` | Run browser tests for pages affected by the current branch or PR. Use when asked to run or check browser tests |
| `executing-plans` | **28 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/executing-plans` | Use when executing an implementation plan in the current session as the implementer yourself — your human part |
| `motion-effects` | **28 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/motion-effects` | Style for edit-video: a library of 33 named motion effects for talking-head reels (kinetic hook, gravity drop, |
| `triage` | **28 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/triage` | Move issues and external PRs through a state machine of triage roles, categorise, verify, grill if needed, and |
| `ce-handoff` | **24 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-handoff` | Create a session handoff for another agent, or resume, find, and read any user-selected continuity source. Use |
| `discernment-nudge` | **24 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/discernment-nudge` | After you give a substantive answer or draft that the user may act on — advice or recommendations, drafted art |
| `frontend-design` | **24 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/frontend-design` | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps w |
| `prototype` | **24 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/prototype` | Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a sta |
| `test-driven-development` | **24 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/test-driven-development` | Use when implementing any feature or bugfix, before writing implementation code |
| `wizard` | **24 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/wizard` | Generate an interactive bash wizard that walks a human through steps only they can perform. Use when provision |
| `academy-guide` | **20 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/academy-guide` | Stop and check this skill before finishing any reply to a question about how to use Claude or a Claude product |
| `antigravity_guide` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/antigravity_guide` | Provides a comprehensive guide, quick reference, and sitemap for Google Antigravity (AGY), including the Antig |
| `aws-messaging-and-streaming` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-messaging-and-streaming` | Guides general use of AWS messaging and streaming services. Covers Amazon SQS, Amazon SNS, Amazon EventBridge, |
| `codebase-design` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/codebase-design` | Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interfac |
| `diagnosing-bugs` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or r |
| `ig-caption` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/instagram-agent-skill/skills/ig-caption` | Write the Instagram caption - the line that survives the "... more" cut, the body, the single ask, the search  |
| `ig-viral` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ig-viral` | Go and find the reels that are actually working right now in the user's niche, rank them by how far each beat  |
| `improve-codebase-architecture` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/improve-codebase-architecture` | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whicheve |
| `langgraph-decision-models` | **20 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-decision-models` | INVOKE THIS SKILL when routing a LangGraph agent with a decision model (TypeSafe Jev, SemIf) instead of an LLM |
| `langgraph-human-in-the-loop` | **20 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-human-in-the-loop` | INVOKE THIS SKILL when implementing human-in-the-loop patterns, pausing for approval, or handling errors in La |
| `langgraph-persistence` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-persistence` | INVOKE THIS SKILL when your LangGraph needs to persist state, remember conversations, travel through history,  |
| `llm-council` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/llm-council` | Run any question, idea, or decision through a council of 5 AI advisors who independently analyze it, peer-revi |
| `plugin` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/plugin` | How to manage and create plugins — namespaced bundles of skills, agents, rules, MCP servers and hooks that ins |
| `wayfinder` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/wayfinder` | Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on your i |
| `write-script` | **20 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/2-scripting/write-script` | Write or critique hooks and scripts for Reels, TikToks and YouTube Shorts from an idea, saved reel or referenc |
| `writing-for-agents` | **20 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/writing-for-agents` | Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md. |
| `automation` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/automation` | Interactive guide to design and create a scheduled background automation. Use this skill when the user wants t |
| `aws-networking` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/aws-networking` | Routes AWS networking requests to the correct service skill for implementation. Covers Route 53 (DNS, health c |
| `brand-guidelines` | **16 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/brand-guidelines` | Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having  |
| `ce-noslop` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.agents/skills/ce-noslop` | Rewrite, check, or draft prose so it carries no AI writing tells, reads plainly on the first read, and keeps e |
| `ce-test-xcode` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-test-xcode` | Test iOS apps in a simulator with XcodeBuildMCP. Use when iOS changes need simulator evidence before handoff. |
| `deep-agents-orchestration` | **16 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/deep-agents-orchestration` | INVOKE THIS SKILL when using subagents, task planning, or human approval in Deep Agents. Covers SubAgentMiddle |
| `doc-coauthoring` | **16 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/anthropic-skills/skills/doc-coauthoring` | Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documen |
| `domain-modeling` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/domain-modeling` | Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a GLO |
| `langchain-dependencies` | **16 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-dependencies` | INVOKE THIS SKILL when setting up a new project or when asked about package versions, installation, or depende |
| `langchain-fundamentals` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-fundamentals` | Create LangChain agents with create_agent, define tools, and use middleware for human-in-the-loop and error ha |
| `langchain-rag` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-rag` | INVOKE THIS SKILL when building ANY retrieval-augmented generation (RAG) system. Covers document loaders, Recu |
| `pr` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/pr` | Use when writing a PR body. |
| `setup-ts-deep-modules` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/setup-ts-deep-modules` | Wire dependency-cruiser into a TypeScript repo so each package is a deep module, with implementation hidden in |
| `tdd` | **16 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/tdd` | Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green |
| `aws-blocks` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-blocks` | Guides building full-stack applications with AWS Blocks — an Infrastructure-from-Code framework. Applies when  |
| `aws-sdk-swift-usage` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/aws-sdk-swift-usage` | AWS SDK for Swift development patterns. Use when writing Swift code that uses AWS services via aws-sdk-swift p |
| `code-review` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/code-review` | Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does th |
| `deep-agents-core` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/langchain-skills/config/skills/deep-agents-core` | INVOKE THIS SKILL when building ANY Deep Agents application. Covers create_deep_agent(), harness architecture, |
| `deep-agents-memory` | **12 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/deep-agents-memory` | INVOKE THIS SKILL when your Deep Agent needs memory, persistence, or filesystem access. Covers StateBackend (e |
| `git-guardrails-claude-code` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/git-guardrails-claude-code` | Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before t |
| `ig-profile` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/skills/ig-profile` | Score an Instagram profile out of 100 against a 12-part rubric and rewrite the parts that lose points - name f |
| `langchain-middleware` | **12 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-middleware` | INVOKE THIS SKILL when you need human-in-the-loop approval, custom middleware, or structured output. Covers Hu |
| `langgraph-cli` | **12 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-cli` | INVOKE THIS SKILL when using the langgraph CLI to scaffold, develop, build, or deploy LangGraph applications.  |
| `permissioned-github` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/permissioned-github` | Guidelines for interacting with GitHub and request permissions from the user when commands fail due to restric |
| `requesting-code-review` | **12 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| `retro` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/retro` | Conduct a retrospective on a coding session. |
| `run-workflow` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/run-workflow` | How to write and run a dynamic workflow script with the `run_workflow` tool: a Python script that orchestrates |
| `signing-in-to-aws` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/signing-in-to-aws` | Gets AWS credentials for CLI/SDK access via `aws login`. Activates when a developer needs to authenticate to A |
| `to-tickets` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/to-tickets` | Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocki |
| `writing-beats` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/writing-beats` | Writing, exploit; assemble raw material into a journey of beats, grounding each term before a beat leans on it |
| `writing-plans` | **12 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/writing-plans` | Use when you have a spec or requirements for a multi-step task, before touching code |
| `writing-shape` | **12 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/writing-shape` | Writing, exploit: shape raw material into an article, paragraph by paragraph. |
| `ce-commit` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/ce-commit` | Create a git commit with a clear, value-communicating message. Use when the user asks to commit/save staged or |
| `ce-worktree` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.claude/skills/ce-worktree` | Set up isolated git worktrees — create a new branch for fresh work, or attach a worktree to an existing branch |
| `chief-of-staff` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/chief-of-staff` | Pursue a long-running goal in a single session by co-ordinating subagents. |
| `claude-handoff` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/claude-handoff` | Hand the current conversation off to a fresh background agent that picks up the work immediately. |
| `dispatching-parallel-agents` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| `ecosystem-primer` | **8 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/ecosystem-primer` | INVOKE FIRST for any LangChain / LangGraph / Deep Agents agent building project before consulting other skills |
| `find-ideas` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/1-research/find-ideas` | Find what to make next: proven reels to adapt, outliers in a niche, saved inspiration and the creator's own re |
| `find-skills` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/find-skills` | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for  |
| `finishing-a-development-branch` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/finishing-a-development-branch` | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work |
| `generative_ui` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/generative_ui` | How to render rich interactive HTML widgets inline in the chat or as standalone artifacts. Use this skill when |
| `grill-me` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/grill-me` | A relentless interview to sharpen a plan or design. |
| `grill-with-docs` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/grill-with-docs` | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. |
| `grilling` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/grilling` | Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thin |
| `gsd-complete-milestone` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-complete-milestone` | Archive completed milestone and prepare for next version |
| `gsd-graphify` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-graphify` | Build, query, and inspect the project knowledge graph in .planning/graphs/ |
| `gsd-quick` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-quick` | Execute a quick task with GSD guarantees (atomic commits, state tracking) but skip optional agents |
| `handoff` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/handoff` | Compact the current conversation into a handoff document for another agent to pick up. |
| `ig-audit` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/skills/ig-audit` | Post-mortem on what the user has already posted - which reels actually worked, why, and what to stop making. U |
| `ig-comment` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ig-comment` | Write comments on other people's Instagram posts and reels that read as a person with an opinion, not a bot. U |
| `ig-dm` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/config/skills/ig-dm` | Write Instagram DMs that get replies - the keyword delivery, the first message to someone who engaged, the col |
| `ig-story` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ig-story` | Write the day's Instagram Stories - the frame-by-frame sequence, which stickers to use where, and the one that |
| `implement` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/implement` | Implement a piece of work based on a spec or set of tickets. |
| `implement-spec` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/implement-spec` | Implement the result of /to-spec and /to-tickets in code. |
| `loop-me` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/loop-me` | Grill me about specs for the workflows I want to build, within this workspace. |
| `migrate-to-shoehorn` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/migrate-to-shoehorn` | Migrate test files from `as` type assertions to @total-typescript/shoehorn. Use when user mentions shoehorn, w |
| `migrate-workflows` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/migrate-workflows` | Automatically migrate legacy workflows to modern skills across global and workspace configurations. Scans for  |
| `ponytail-audit` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail-audit` | Quality audit of a whole repo: bugs, security holes, what breaks under real load, risky code without tests, sl |
| `ponytail-review` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail-review` | Quality review of a change: is the logic right, is it safe, does it hold under real load, is risky code tested |
| `receiving-code-review` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/receiving-code-review` | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear |
| `research` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/research` | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the r |
| `scaffold-exercises` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/scaffold-exercises` | Create exercise directory structures with sections, problems, solutions, and explainers that pass linting. Use |
| `setup-pre-commit` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/setup-pre-commit` | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and tests in the current repo. Use w |
| `text-over-footage` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/favstash-ai-video-editing-skills/skills/3-editing-styles/text-over-footage` | Style for edit-video: one short, readable line of text over B-roll that matches it, for jokes, observations an |
| `to-questionnaire` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/to-questionnaire` | Turn a decision you can't fully answer into a questionnaire for someone else to fill in. |
| `to-spec` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/to-spec` | Turn the current conversation into a spec and publish it to the project issue tracker: no interview, just synt |
| `using-git-worktrees` | **8 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/using-git-worktrees` | Use when starting feature work that needs isolation from current workspace or before executing implementation  |
| `wait-what` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/wait-what` | Stop. That last message did not land: re-pitch it. |
| `writing-fragments` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/writing-fragments` | Writing, explore: mine raw fragments, no structure yet. |
| `wtf` | **8 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/wtf` | Explain the last message, or a supplied file, link, or passage, in plain language a person follows on the firs |
| `21st-ui` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills | `~/.gemini/config/skills/21st-ui` | Find, install, and generate UI with 21st.dev. Use when the user asks for a UI component (pricing table, hero,  |
| `archify-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/archify-review` | Review Archify issues, PRs, or code through value, cost, and impact to support evidence-based maintenance deci |
| `deepagents-python-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/deepagents-python-quickstart` | Scaffold a minimal local Deep Agent in Python by following the official quickstart, using provider-native web  |
| `deepagents-typescript-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/deepagents-typescript-quickstart` | Scaffold a minimal local Deep Agent in TypeScript by following the official quickstart, using provider-native  |
| `gsd-add-tests` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-add-tests` | Generate tests for a completed phase based on UAT criteria and implementation |
| `gsd-ai-integration-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ai-integration-phase` | Generate an AI-SPEC.md design contract for phases that involve building AI systems. |
| `gsd-audit-fix` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-audit-fix` | Autonomous audit-to-fix pipeline — find issues, classify, fix, test, commit |
| `gsd-audit-milestone` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-audit-milestone` | Audit milestone completion against original intent before archiving |
| `gsd-audit-uat` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-audit-uat` | Cross-phase audit of all outstanding UAT and verification items |
| `gsd-autonomous` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-autonomous` | Run all remaining phases autonomously — discuss→plan→execute per phase |
| `gsd-capture` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-capture` | Capture ideas, tasks, notes, and seeds to their destination |
| `gsd-cleanup` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-cleanup` | Archive accumulated phase directories from completed milestones |
| `gsd-code-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-code-review` | Review source files changed during a phase for bugs, security issues, and code quality problems |
| `gsd-config` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-config` | Configure GSD settings — workflow toggles, advanced knobs, integrations, and model profile |
| `gsd-debug` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-debug` | Systematic debugging with persistent state across context resets |
| `gsd-discuss-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-discuss-phase` | Gather phase context through adaptive questioning before planning. |
| `gsd-docs-update` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-docs-update` | Generate or update project documentation verified against the codebase |
| `gsd-eval-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-eval-review` | Audit an executed AI phase's evaluation coverage and produce an EVAL-REVIEW.md remediation plan. |
| `gsd-execute-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-execute-phase` | Execute all plans in a phase with wave-based parallelization |
| `gsd-explore` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-explore` | Socratic ideation and idea routing — think through ideas before committing to plans |
| `gsd-extract-learnings` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-extract-learnings` | Extract decisions, lessons, patterns, and surprises from completed phase artifacts |
| `gsd-fast` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-fast` | Execute a trivial task inline — no subagents, no planning overhead |
| `gsd-forensics` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-forensics` | Post-mortem investigation for failed GSD workflows — diagnoses what went wrong. |
| `gsd-health` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-health` | Diagnose planning directory health and optionally repair issues |
| `gsd-help` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-help` | Show available GSD commands and usage guide |
| `gsd-import` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-import` | Ingest external plans with conflict detection against project decisions before writing anything. |
| `gsd-inbox` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-inbox` | Triage and review open GitHub issues and PRs against project templates and contribution guidelines. |
| `gsd-ingest-docs` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ingest-docs` | Bootstrap or merge a .planning/ setup from existing ADRs, PRDs, SPECs, and docs in a repo. |
| `gsd-manager` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-manager` | Interactive command center for managing multiple phases from one terminal |
| `gsd-map-codebase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-map-codebase` | Analyze codebase with parallel mapper agents to produce .planning/codebase/ documents |
| `gsd-milestone-summary` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-milestone-summary` | Generate a comprehensive project summary from milestone artifacts for team onboarding and review |
| `gsd-mvp-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-mvp-phase` | Plan a phase as a vertical MVP slice — user story, SPIDR splitting, then plan-phase |
| `gsd-new-milestone` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-new-milestone` | Start a new milestone cycle — update PROJECT.md and route to requirements |
| `gsd-new-project` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-new-project` | Initialize a new project with deep context gathering and PROJECT.md |
| `gsd-ns-context` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-context` | codebase intelligence \| map graphify docs learnings |
| `gsd-ns-ideate` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-ideate` | exploration capture \| explore sketch spike spec capture |
| `gsd-ns-manage` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-manage` | config workspace \| workstreams thread update ship inbox |
| `gsd-ns-project` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-project` | project lifecycle \| milestones audits summary |
| `gsd-ns-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-review` | quality gates \| code review debug audit security eval ui |
| `gsd-ns-workflow` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ns-workflow` | workflow \| discuss plan execute verify phase progress |
| `gsd-pause-work` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-pause-work` | Create context handoff when pausing work mid-phase |
| `gsd-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-phase` | CRUD for phases in ROADMAP.md — add, insert, remove, or edit phases |
| `gsd-plan-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-plan-phase` | Create detailed phase plan (PLAN.md) with verification loop |
| `gsd-plan-review-convergence` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-plan-review-convergence` | Cross-AI plan convergence loop — replan with review feedback until no HIGH concerns remain. |
| `gsd-pr-branch` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-pr-branch` | Create a clean PR branch by filtering out .planning/ commits — ready for code review |
| `gsd-profile-user` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-profile-user` | Generate developer behavioral profile and create Claude-discoverable artifacts |
| `gsd-progress` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-progress` | Check progress, advance workflow, or dispatch freeform intent — the unified GSD situational command |
| `gsd-resume-work` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-resume-work` | Resume work from previous session with full context restoration |
| `gsd-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-review` | Request cross-AI peer review of phase plans from external AI CLIs |
| `gsd-review-backlog` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-review-backlog` | Review and promote backlog items to active milestone |
| `gsd-secure-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-secure-phase` | Retroactively verify threat mitigations for a completed phase |
| `gsd-settings` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-settings` | Configure GSD workflow toggles and model profile |
| `gsd-ship` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ship` | Create PR, run review, and prepare for merge after verification passes |
| `gsd-sketch` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-sketch` | Sketch UI/design ideas with throwaway HTML mockups, or propose what to sketch next (frontier mode) |
| `gsd-spec-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-spec-phase` | Clarify WHAT a phase delivers with ambiguity scoring; produces a SPEC.md before discuss-phase. |
| `gsd-spike` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-spike` | Spike an idea through experiential exploration, or propose what to spike next (frontier mode) |
| `gsd-stats` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-stats` | Display project statistics — phases, plans, requirements, git metrics, and timeline |
| `gsd-surface` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-surface` | Toggle which skills are surfaced — apply a profile, list, or disable a cluster without reinstall |
| `gsd-thread` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-thread` | Manage persistent context threads for cross-session work |
| `gsd-ui-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ui-phase` | Generate UI design contract (UI-SPEC.md) for frontend phases |
| `gsd-ui-review` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ui-review` | Retroactive 6-pillar visual audit of implemented frontend code |
| `gsd-ultraplan-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-ultraplan-phase` | [BETA] Offload plan phase to Claude Code's ultraplan cloud; review in browser and import back. |
| `gsd-undo` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-undo` | Safe git revert. Roll back phase or plan commits using the phase manifest with dependency checks. |
| `gsd-update` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-update` | Update GSD to latest version with changelog display |
| `gsd-validate-phase` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-validate-phase` | Retroactively audit and fill Nyquist validation gaps for a completed phase |
| `gsd-verify-work` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-verify-work` | Validate built features through conversational UAT |
| `gsd-workspace` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-workspace` | Manage GSD workspaces — create, list, or remove isolated workspace environments |
| `gsd-workstreams` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gsd-workstreams` | Manage parallel workstreams — list, create, switch, status, progress, complete, and resume |
| `ig-carousel` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ig-carousel` | Build an Instagram carousel - the cover that earns the swipe, slide-by-slide copy, and the 1080x1350 files to  |
| `ig-plan` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/skills/ig-plan` | Build the week on Instagram - what to post, which format, when, and who to engage with. Use when the user says |
| `ig-reply` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/instagram-agent-skill/skills/ig-reply` | Handle the comments under the user's own reels and posts - draft replies to the ones worth answering, sorted b |
| `ig-repurpose` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/repos/instagram-agent-skill/skills/ig-repurpose` | Turn one long asset - a YouTube video, podcast, livestream, newsletter, blog post or client call - into a week |
| `langchain-python-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-python-quickstart` | Scaffold a minimal local LangChain agent in Python by following the official quickstart. Use when the user wan |
| `langchain-typescript-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langchain-typescript-quickstart` | Scaffold a minimal local LangChain agent in TypeScript by following the official quickstart. Use when the user |
| `langgraph-python-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-python-quickstart` | Scaffold a minimal local LangGraph agent in Python by following the official quickstart. Use when the user wan |
| `langgraph-typescript-quickstart` | **4 KB** | Universal (Agents) | .agents/skills | `~/.agents/repos/langchain-skills/config/skills/langgraph-typescript-quickstart` | Scaffold a minimal local LangGraph agent in TypeScript by following the official quickstart. Use when the user |
| `ponytail` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail` | Lazy senior dev mode: the smallest change that fully solves the task, and a reply a busy human understands in  |
| `ponytail-debt` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail-debt` | List every `shortcut:` comment (and older `ponytail:` ones) as a debt ledger. One-shot report, changes nothing |
| `ponytail-gain` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail-gain` | Show ponytail's measured savings (code, cost, speed) from the benchmark. One-shot display. Use for /ponytail-g |
| `ponytail-help` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.agents/skills/ponytail-help` | Quick reference for ponytail levels, skills and commands. One-shot display. Use for /ponytail-help, "ponytail  |
| `ui-plugin-navigation` | **4 KB** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.gemini/antigravity/builtin/skills/ui-plugin-navigation` | Discover UI plugin panels relevant to the current task and surface a one-click pill in chat to open (toggle) t |
| `verification-before-completion` | **4 KB** | Gemini | .agents/skills<br>.gemini/config/skills | `~/.agents/repos/superpowers/skills/verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires runn |
| `_gstack-command` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/_gstack-command` | Fast headless browser for QA testing and site dogfooding. (gstack) |
| `autoplan` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/autoplan` | Auto-review pipeline — reads the full CEO, design, eng, and DX review skills from disk and runs them sequentia |
| `benchmark` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/benchmark` | Performance regression detection using the browse daemon. (gstack) |
| `benchmark-models` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/benchmark-models` | Cross-model benchmark for gstack skills. (gstack) |
| `browse` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/browse` | Fast headless browser for QA testing and site dogfooding. (gstack) |
| `canary` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/canary` | Post-deploy canary monitoring. (gstack) |
| `careful` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/careful` | Safety guardrails for destructive commands. (gstack) |
| `codex` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/codex` | OpenAI Codex CLI wrapper — three modes. (gstack) |
| `connect-chrome` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/connect-chrome` | Launch GStack Browser — AI-controlled Chromium with the sidebar extension baked in. |
| `context-restore` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/context-restore` | Restore working context saved earlier by /context-save. (gstack) |
| `context-save` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/context-save` | Save working context. (gstack) |
| `cso` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/cso` | Chief Security Officer mode. (gstack) |
| `design-consultation` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/design-consultation` | Design consultation: understands your product, researches the landscape, proposes a complete design system (ae |
| `design-html` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/design-html` | Design finalization: generates production-quality Pretext-native HTML/CSS. (gstack) |
| `design-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/design-review` | Designer's eye QA: finds visual inconsistency, spacing issues, hierarchy problems, AI slop patterns, and slow  |
| `design-shotgun` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/design-shotgun` | Design shotgun: generate multiple AI design variants, open a comparison board, collect structured feedback, an |
| `devex-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/devex-review` | Live developer experience audit. (gstack) |
| `diagram` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/diagram` | Turn an English description (or mermaid source) into a diagram triplet: the source, an editable .excalidraw fi |
| `document-generate` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/document-generate` | Generate missing documentation from scratch for a feature, module, or entire project. (gstack) |
| `document-release` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/document-release` | Post-ship documentation update. (gstack) |
| `freeze` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/freeze` | Restrict file edits to a specific directory for the session. (gstack) |
| `gstack-upgrade` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/gstack-upgrade` | Upgrade gstack to the latest version. |
| `guard` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/guard` | Full safety mode: destructive command warnings + directory-scoped edits. (gstack) |
| `health` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/health` | Code quality dashboard. (gstack) |
| `investigate` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/investigate` | Systematic debugging with root cause investigation. (gstack) |
| `ios-clean` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ios-clean` | Remove the DebugBridge SPM package and all #if DEBUG wiring from an iOS app. (gstack) |
| `ios-design-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ios-design-review` | Visual design audit for iOS apps on real hardware. (gstack) |
| `ios-fix` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ios-fix` | Autonomous iOS bug fixer. (gstack) |
| `ios-qa` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ios-qa` | Live-device iOS QA for SwiftUI apps. (gstack) |
| `ios-sync` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ios-sync` | Regenerate the iOS debug bridge against the latest upstream gstack templates. (gstack) |
| `land-and-deploy` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/land-and-deploy` | Land and deploy workflow. (gstack) |
| `landing-report` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/landing-report` | Read-only queue dashboard for workspace-aware ship. (gstack) |
| `learn` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/learn` | Manage project learnings. |
| `make-pdf` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/make-pdf` | Turn any markdown file into a publication-quality PDF. (gstack) |
| `office-hours` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/office-hours` | YC Office Hours — two modes. (gstack) |
| `open-gstack-browser` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/open-gstack-browser` | Launch GStack Browser — AI-controlled Chromium with the sidebar extension baked in. |
| `pair-agent` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/pair-agent` | Pair a remote AI agent with your browser. (gstack) |
| `plan-ceo-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/plan-ceo-review` | CEO/founder-mode plan review. (gstack) |
| `plan-design-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/plan-design-review` | Designer's eye plan review — interactive, like CEO and Eng review. (gstack) |
| `plan-devex-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/plan-devex-review` | Interactive developer experience plan review. (gstack) |
| `plan-eng-review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/plan-eng-review` | Eng manager-mode plan review. (gstack) |
| `plan-tune` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/plan-tune` | Self-tuning question sensitivity + developer psychographic for gstack (v1: observational). (gstack) |
| `qa` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/qa` | Systematically QA test a web application and fix bugs found. (gstack) |
| `qa-only` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/qa-only` | Report-only QA testing. (gstack) |
| `review` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/review` | Pre-landing PR review. (gstack) |
| `scrape` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/scrape` | Pull data from a web page. (gstack) |
| `setup-browser-cookies` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/setup-browser-cookies` | Import cookies from your real Chromium browser into the headless browse session. (gstack) |
| `setup-deploy` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/setup-deploy` | Configure deployment settings for /land-and-deploy. |
| `setup-gbrain` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/setup-gbrain` | Set up gbrain for this coding agent: install the CLI, initialize a local PGLite or Supabase brain, register MC |
| `ship` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/ship` | Ship workflow: detect + merge base branch, run tests, review diff, bump VERSION, update CHANGELOG, commit, pus |
| `skillify` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/skillify` | Codify the most recent successful /scrape flow into a permanent browser-skill on disk. (gstack) |
| `spec` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/spec` | Turn vague intent into a precise, executable spec in five phases. (gstack) |
| `sync-gbrain` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/sync-gbrain` | Keep gbrain current with this repo's code and refresh agent search guidance in CLAUDE.md. Wraps the gstack-gbr |
| `unfreeze` | **0B** | Both (Claude + Gemini) | .agents/skills<br>.claude/skills<br>.gemini/config/skills<br>.gemini/skills | `~/.claude/skills/unfreeze` | Clear the freeze boundary set by /freeze, allowing edits to all directories again. (gstack) |

---

## Section 2: Verdicts & Proof Table (Step 3)

| Skill Name | Verdict | Proof / Measured CIP File:Line or Upstream Repo | Real Size |
| :--- | :---: | :--- | :---: | |
| `gstack` | **KEEP-CIP** | Core monorepo engine powering headless browser QA testing (browse, qa, health, investigate) for Next.js frontend and FastAPI routes. | 1.09 GB |
| `excalidraw-diagram-skill` | **DUPLICATE** | 135 MB redundant copy; keep 'diagram' from gstack. | 135.30 MB |
| `synced` | **DUPLICATE** | 22 MB duplicate skill session buckets in .claude/skills/synced. | 22.09 MB |
| `impeccable` | **DUPLICATE** | 18.6 MB duplicate styling rules; keep 'frontend-design' and '21st-ui'. | 18.64 MB |
| `archify` | **DUPLICATE** | 10.7 MB legacy architecture tool; keep 'codebase-design' and 'superpowers'. | 10.73 MB |
| `canvas-design` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 5.52 MB |
| `.trash` | **REMOVE** | Deleted trash files in .claude/skills | 4.23 MB |
| `awesome-design-md` | **DUPLICATE** | Static markdown archive (2.8 MB); keep 'frontend-design'. | 2.85 MB |
| `claude-api` | **KEEP-CIP** | Powers Ask CIP assistant in api/assistant.py with Anthropic SDK prompt caching. | 2.18 MB |
| `breakout-card` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 1.35 MB |
| `docx` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 1.20 MB |
| `pptx` | **KEEP-CIP** | Validates PowerPoint export generation in api/exports.py. | 1.20 MB |
| `xlsx` | **KEEP-CIP** | Validates multi-wave survey Excel exports in api/exports.py against expected schema. | 1.16 MB |
| `edit-video` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 1.00 MB |
| `ce-code-review` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 688 KB |
| `aws-ai-ml` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 676 KB |
| `aws-observability` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 612 KB |
| `ce-plan` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 612 KB |
| `ce-work` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 580 KB |
| `ce-doc-review` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 540 KB |
| `ce-brainstorm` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 472 KB |
| `amazon-bedrock` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 396 KB |
| `security-audit` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 348 KB |
| `ce-babysit-pr` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 344 KB |
| `exploratory-data-analysis` | **KEEP-CIP** | Automated survey data profiling in etl/; validates missingness & distribution shifts before DB load. Command: python etl/survey_processor.py --dry-run | 336 KB |
| `ce-compound` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 320 KB |
| `supply-chain-risk-auditor` | **KEEP-CIP** | Audits requirements.txt and package.json for abandoned dependencies and CVEs. Repo: trailofbits/skills. | 316 KB |
| `ce-polish` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 312 KB |
| `ce-optimize` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 292 KB |
| `ce-pov` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 284 KB |
| `ce-ideate` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 264 KB |
| `skill-creator` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 248 KB |
| `scientific-visualization` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 244 KB |
| `eval-engineering` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 208 KB |
| `shadcn` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 204 KB |
| `migrate-radix-to-base` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 200 KB |
| `ce-sweep` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 184 KB |
| `theme-factory` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 180 KB |
| `graphify` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 164 KB |
| `aws-security` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 160 KB |
| `shap` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 160 KB |
| `sharp-edges` | **KEEP-CIP** | Audits API query parameters in api/ for misuse footguns and insecure defaults. Repo: trailofbits/skills. | 160 KB |
| `aws-cloudformation` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 156 KB |
| `scikit-learn` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 156 KB |
| `mcp-builder` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 144 KB |
| `aws-containers` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 140 KB |
| `ce-prototype` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 140 KB |
| `ce-resolve-pr-feedback` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 140 KB |
| `ce-compound-refresh` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 136 KB |
| `ce-setup` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 136 KB |
| `launch-with-aws` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 132 KB |
| `writing-skills` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 132 KB |
| `aws-storage` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 124 KB |
| `aws-cdk` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 120 KB |
| `polars` | **KEEP-CIP** | Replaces Pandas in etl/ with multi-threaded Arrow engine; cuts ETL memory from 4GB to 800MB and runtime by 8x. Command: pytest tests/test_weekly_report.py | 116 KB |
| `aws-auth` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 112 KB |
| `aws-database` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 112 KB |
| `ce-debug` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 108 KB |
| `aws-serverless` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 104 KB |
| `lfg` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 100 KB |
| `brainstorming` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 92 KB |
| `ce-retune` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 92 KB |
| `harvey` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 92 KB |
| `subagent-driven-development` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 92 KB |
| `aws-billing-and-cost-management` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 88 KB |
| `ce-riffrec-feedback-analysis` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 88 KB |
| `paper-grid` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 88 KB |
| `reverse-engineer-anything` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 88 KB |
| `ce-commit-push-pr` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 84 KB |
| `diagnosing-superpowers` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 84 KB |
| `ce-dogfood` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 80 KB |
| `pdf` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 80 KB |
| `swarm` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 80 KB |
| `aws-compute` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 72 KB |
| `agent-reach` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 68 KB |
| `aws-deployment` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 68 KB |
| `aws-iam` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 68 KB |
| `adaptive-glass` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 64 KB |
| `algorithmic-art` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 64 KB |
| `systematic-debugging` | **KEEP-CIP** | Root-cause reproduction protocol for survey discrepancies between Forsta and CIP MySQL. | 64 KB |
| `aws-sdk-js-v3-usage` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 60 KB |
| `aws-sdk-python-usage` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 60 KB |
| `ce-product-pulse` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 60 KB |
| `ce-explain` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 56 KB |
| `ig-human` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 56 KB |
| `ig-reel` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 56 KB |
| `slack-gif-creator` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 56 KB |
| `agy-customizations` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 52 KB |
| `web-artifacts-builder` | **KEEP-CIP** | Builds multi-component React/Tailwind analytics widgets for Next.js 16. | 52 KB |
| `differential-review` | **KEEP-CIP** | Security-focused diff review assessing blast radius of PR changes. Repo: trailofbits/skills. | 48 KB |
| `ce-strategy` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 44 KB |
| `playwright` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 44 KB |
| `product-motion-ads` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 44 KB |
| `using-superpowers` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 40 KB |
| `ce-simplify-code` | **KEEP-CIP** | Prunes dead abstractions, inline single-use functions, and enforces minimal code per AGENTS.md. | 36 KB |
| `managed-deep-agents` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 36 KB |
| `setup-matt-pocock-skills` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 36 KB |
| `internal-comms` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 32 KB |
| `langgraph-fundamentals` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 32 KB |
| `publish-and-analyze` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 32 KB |
| `semgrep-rule-creator` | **KEEP-CIP** | Generates AST rules ensuring all MySQL queries use SQLAlchemy parameterized bindings. Repo: trailofbits/skills. | 32 KB |
| `teach` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 32 KB |
| `webapp-testing` | **KEEP-CIP** | Playwright end-to-end assertion suite for testing CIP dashboard screens. | 32 KB |
| `ask-matt` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 28 KB |
| `ce-bakeoff` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 28 KB |
| `ce-promote` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 28 KB |
| `ce-proof` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 28 KB |
| `ce-test-browser` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 28 KB |
| `executing-plans` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 28 KB |
| `motion-effects` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 28 KB |
| `triage` | **DUPLICATE** | Duplicate; keep 'investigate'. | 28 KB |
| `ce-handoff` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 24 KB |
| `discernment-nudge` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 24 KB |
| `frontend-design` | **KEEP-CIP** | Enforces intentional typography, spacing, and design hierarchy on frontend/src/screens/. | 24 KB |
| `prototype` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 24 KB |
| `test-driven-development` | **KEEP-CIP** | Enforces TDD on CIP calculations (checks Figure 6 of 3 Nov 2026 PDF). File: tests/test_weekly_report.py. Command: pytest tests/ | 24 KB |
| `wizard` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 24 KB |
| `academy-guide` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `antigravity_guide` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `aws-messaging-and-streaming` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 20 KB |
| `codebase-design` | **KEEP-CIP** | Enforces John Ousterhout's deep-module design on etl/ and api/ modules. | 20 KB |
| `diagnosing-bugs` | **DUPLICATE** | Shallow duplicate; keep 'systematic-debugging' (superpowers). | 20 KB |
| `ig-caption` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 20 KB |
| `ig-viral` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 20 KB |
| `improve-codebase-architecture` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `langgraph-decision-models` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `langgraph-human-in-the-loop` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `langgraph-persistence` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `llm-council` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 20 KB |
| `plugin` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `wayfinder` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `write-script` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 20 KB |
| `writing-for-agents` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 20 KB |
| `automation` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `aws-networking` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 16 KB |
| `brand-guidelines` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 16 KB |
| `ce-noslop` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 16 KB |
| `ce-test-xcode` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 16 KB |
| `deep-agents-orchestration` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `doc-coauthoring` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `domain-modeling` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `langchain-dependencies` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `langchain-fundamentals` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `langchain-rag` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `pr` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 16 KB |
| `setup-ts-deep-modules` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 16 KB |
| `tdd` | **DUPLICATE** | Shallow duplicate; keep 'test-driven-development' (superpowers). | 16 KB |
| `aws-blocks` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 12 KB |
| `aws-sdk-swift-usage` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 12 KB |
| `code-review` | **DUPLICATE** | Duplicate; keep 'requesting-code-review' and 'ce-code-review'. | 12 KB |
| `deep-agents-core` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `deep-agents-memory` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `git-guardrails-claude-code` | **KEEP-CIP** | Hooks into agent shell to block git push/commit, enforcing HARD RULE in AGENTS.md. | 12 KB |
| `ig-profile` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 12 KB |
| `langchain-middleware` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `langgraph-cli` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `permissioned-github` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `requesting-code-review` | **KEEP-CIP** | Pre-landing diff inspection checking standards, comments, and ponytail ladder compliance. | 12 KB |
| `retro` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `run-workflow` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 12 KB |
| `signing-in-to-aws` | **REMOVE** | AWS-specific infrastructure skills (CIP runs on Azure App Service + Azure MySQL; AWS is unused). | 12 KB |
| `to-tickets` | **DUPLICATE** | Duplicate; keep 'writing-plans'. | 12 KB |
| `writing-beats` | **DUPLICATE** | Duplicate; keep 'write-script'. | 12 KB |
| `writing-plans` | **KEEP-CIP** | Generates verifiable phase plans before executing schema changes or ETL refactors. | 12 KB |
| `writing-shape` | **DUPLICATE** | Duplicate; keep 'write-script'. | 12 KB |
| `ce-commit` | **REMOVE** | Niche compound engineering workflow variants (redundant with core ce-* tools). | 8 KB |
| `ce-worktree` | **KEEP-GENERAL** | Compound engineering core workflows for architecture and planning. | 8 KB |
| `chief-of-staff` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `claude-handoff` | **DUPLICATE** | Duplicate; keep 'ce-handoff'. | 8 KB |
| `dispatching-parallel-agents` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `ecosystem-primer` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `find-ideas` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `find-skills` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `finishing-a-development-branch` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `generative_ui` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `grill-me` | **DUPLICATE** | Duplicate; keep 'grilling'. | 8 KB |
| `grill-with-docs` | **DUPLICATE** | Duplicate; keep 'grilling'. | 8 KB |
| `grilling` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `gsd-complete-milestone` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 8 KB |
| `gsd-graphify` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 8 KB |
| `gsd-quick` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 8 KB |
| `handoff` | **DUPLICATE** | Duplicate; keep 'ce-handoff'. | 8 KB |
| `ig-audit` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `ig-comment` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `ig-dm` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `ig-story` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `implement` | **DUPLICATE** | Duplicate task runner; keep 'executing-plans' and 'ce-work'. | 8 KB |
| `implement-spec` | **DUPLICATE** | Duplicate; keep 'spec' and 'ce-work'. | 8 KB |
| `loop-me` | **DUPLICATE** | Duplicate prompt looping tool; keep 'autoplan'. | 8 KB |
| `migrate-to-shoehorn` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 8 KB |
| `migrate-workflows` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 8 KB |
| `ponytail-audit` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `ponytail-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `receiving-code-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `research` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `scaffold-exercises` | **REMOVE** | Educational / legacy exercise scaffolding tools not applicable to CIP production codebase. | 8 KB |
| `setup-pre-commit` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `text-over-footage` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 8 KB |
| `to-questionnaire` | **DUPLICATE** | Duplicate; keep 'spec'. | 8 KB |
| `to-spec` | **DUPLICATE** | Duplicate; keep 'spec' (gstack). | 8 KB |
| `using-git-worktrees` | **KEEP-CIP** | Isolates feature work in git worktrees so live staging branch is never dirtied. | 8 KB |
| `wait-what` | **DUPLICATE** | Duplicate questioning tool; keep 'grilling'. | 8 KB |
| `writing-fragments` | **DUPLICATE** | Duplicate; keep 'write-script'. | 8 KB |
| `wtf` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 8 KB |
| `21st-ui` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 4 KB |
| `archify-review` | **DUPLICATE** | Duplicate; keep 'codebase-design' and 'ce-code-review'. | 4 KB |
| `deepagents-python-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `deepagents-typescript-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `gsd-add-tests` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ai-integration-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-audit-fix` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-audit-milestone` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-audit-uat` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-autonomous` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-capture` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-cleanup` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-code-review` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-config` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-debug` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-discuss-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-docs-update` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-eval-review` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-execute-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-explore` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-extract-learnings` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-fast` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-forensics` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-health` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-help` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-import` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-inbox` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ingest-docs` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-manager` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-map-codebase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-milestone-summary` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-mvp-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-new-milestone` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-new-project` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-context` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-ideate` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-manage` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-project` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-review` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ns-workflow` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-pause-work` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-plan-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-plan-review-convergence` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-pr-branch` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-profile-user` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-progress` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-resume-work` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-review` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-review-backlog` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-secure-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-settings` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ship` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-sketch` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-spec-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-spike` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-stats` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-surface` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-thread` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ui-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ui-review` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-ultraplan-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-undo` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-update` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-validate-phase` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-verify-work` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-workspace` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `gsd-workstreams` | **REMOVE** | Alternative heavyweight GSD workflow; duplicates superpowers and compound-engineering. | 4 KB |
| `ig-carousel` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 4 KB |
| `ig-plan` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 4 KB |
| `ig-reply` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 4 KB |
| `ig-repurpose` | **KEEP-GENERAL** | User's Instagram and short-form video creation workflow (installed 7-8 Nov 2026). | 4 KB |
| `langchain-python-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `langchain-typescript-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `langgraph-python-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `langgraph-typescript-quickstart` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `ponytail` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `ponytail-debt` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `ponytail-gain` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `ponytail-help` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `ui-plugin-navigation` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 4 KB |
| `verification-before-completion` | **KEEP-CIP** | Mandates running verification commands (pytest, typecheck) before claiming any task is done. | 4 KB |
| `_gstack-command` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `autoplan` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `benchmark` | **KEEP-CIP** | Measures API route latency before/after changes to enforce <100ms SLA at 10k req/s. File: api/main.py. Command: bin/gstack-benchmark http://127.0.0.1:8000/api/reports | 0B |
| `benchmark-models` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `browse` | **KEEP-CIP** | Headless browser QA testing daemon verifying Next.js page renders under 100ms. File: frontend/src/screens/. Command: bin/gstack-browse http://localhost:3000 | 0B |
| `canary` | **KEEP-CIP** | Continuous post-deploy uptime and health monitoring on Azure App Service. Command: bin/gstack-canary http://127.0.0.1:8000/healthz | 0B |
| `careful` | **KEEP-CIP** | Safety guardrail blocking destructive bash commands (rm -rf, git reset --hard, Azure resource drops). | 0B |
| `codex` | **KEEP-GENERAL** | General utility for UI design, document exports, or research outside CIP. | 0B |
| `connect-chrome` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `context-restore` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `context-save` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `cso` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `design-consultation` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `design-html` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `design-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `design-shotgun` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `devex-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `diagram` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `document-generate` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `document-release` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `freeze` | **KEEP-CIP** | Locks file edits to target module during sensitive refactors (e.g. freezing etl/ while tuning api/). | 0B |
| `gstack-upgrade` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `guard` | **KEEP-CIP** | Restricts file edits to active project directory, preventing accidental modification of host/system files. | 0B |
| `health` | **KEEP-CIP** | Dashboard monitoring code quality, test pass rates, and complexity metrics across CIP. | 0B |
| `investigate` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `ios-clean` | **REMOVE** | iOS/Swift mobile debugging tools (CIP is a web FastAPI + Next.js platform; iOS unused). | 0B |
| `ios-design-review` | **REMOVE** | iOS/Swift mobile debugging tools (CIP is a web FastAPI + Next.js platform; iOS unused). | 0B |
| `ios-fix` | **REMOVE** | iOS/Swift mobile debugging tools (CIP is a web FastAPI + Next.js platform; iOS unused). | 0B |
| `ios-qa` | **REMOVE** | iOS/Swift mobile debugging tools (CIP is a web FastAPI + Next.js platform; iOS unused). | 0B |
| `ios-sync` | **REMOVE** | iOS/Swift mobile debugging tools (CIP is a web FastAPI + Next.js platform; iOS unused). | 0B |
| `land-and-deploy` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `landing-report` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `learn` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `make-pdf` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `office-hours` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `open-gstack-browser` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `pair-agent` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `plan-ceo-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `plan-design-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `plan-devex-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `plan-eng-review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `plan-tune` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `qa` | **KEEP-CIP** | Automated QA test runner validating Next.js interactive controls and survey filters. | 0B |
| `qa-only` | **KEEP-CIP** | Read-only QA audit mode testing production endpoints without modifying state. | 0B |
| `review` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `scrape` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `setup-browser-cookies` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `setup-deploy` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `setup-gbrain` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `ship` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `skillify` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `spec` | **REMOVE** | Unused, unreferenced, or superseded by core toolchain. | 0B |
| `sync-gbrain` | **REMOVE** | Unused gstack cloud/browser pairing utilities; CIP uses local testing and direct Azure deploy. | 0B |
| `unfreeze` | **KEEP-CIP** | Releases freeze boundary after module refactor passes verification. | 0B |

---

## Section 3: How to Use the Keepers (Step 4)

Grouped by operational domain with exact triggers, CIP application contexts, example prompts, and platform compatibility.

### ETL & Data Engineering (KEEP-CIP)

#### `polars`
- **Trigger:** Trigger: `polars` / 'use polars'
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: In `etl/` when processing multi-wave survey respondent tables and generating crosstabs.
- **Example Prompt:** `Prompt: 'Refactor etl/survey_processor.py from Pandas groupby to Polars LazyFrame with projection pushdown to drop memory below 1GB.'`

#### `exploratory-data-analysis`
- **Trigger:** Trigger: `exploratory-data-analysis` / 'profile dataset'
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: In `etl/` before loading new survey wave data into Azure MySQL.
- **Example Prompt:** `Prompt: 'Run an exploratory data analysis on the incoming Forsta survey wave JSON to assert non-null respondent IDs and answer bounds.'`

#### `xlsx`
- **Trigger:** Trigger: `xlsx` / 'validate excel'
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: In `api/exports.py` when generating multi-wave survey workbook exports.
- **Example Prompt:** `Prompt: 'Audit the generated multi-wave Excel workbook against Figure 6 schema to verify formula accuracy and cell formats.'`

#### `pptx`
- **Trigger:** Trigger: `pptx` / 'validate powerpoint'
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: In `api/exports.py` for client report deck generation.
- **Example Prompt:** `Prompt: 'Inspect the PowerPoint deck output from api/exports.py to ensure chart layouts and brand typography match guidelines.'`

### Performance, Review & Security (KEEP-CIP)

#### `benchmark`
- **Trigger:** Trigger: `/benchmark`
- **Compatibility:** Both (Claude + Gemini via gstack)
- **When to use:** When to use: Before and after modifying `api/main.py` or database queries to verify route latency stays under 100ms.
- **Example Prompt:** `Prompt: '/benchmark http://127.0.0.1:8000/api/reports across 500 concurrent iterations.'`

#### `browse`
- **Trigger:** Trigger: `/browse`
- **Compatibility:** Both (Claude + Gemini via gstack)
- **When to use:** When to use: When testing Next.js frontend pages (`frontend/src/screens/`) in headless Chromium without manual browser clicks.
- **Example Prompt:** `Prompt: '/browse http://localhost:3000/reports, verify crosstab table loads within 100ms, and capture screenshot.'`

#### `canary`
- **Trigger:** Trigger: `/canary`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Continuous post-deploy health check on Azure App Service endpoint.
- **Example Prompt:** `Prompt: '/canary http://127.0.0.1:8000/healthz with 10s polling interval.'`

#### `careful`
- **Trigger:** Trigger: `/careful`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: When executing complex terminal refactors to prevent destructive commands (rm -rf, git reset --hard).
- **Example Prompt:** `Prompt: '/careful enable safety guardrails for this refactoring session.'`

#### `guard`
- **Trigger:** Trigger: `/guard`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Directory-scoped execution preventing an agent from touching files outside cip-test.
- **Example Prompt:** `Prompt: '/guard restrict all edits strictly to /Users/mohdsaeedafri/All-Code-Base/cip-test.'`

#### `freeze`
- **Trigger:** Trigger: `/freeze`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Locking all edits to a specific directory (e.g. freezing `etl/` while modifying `api/`).
- **Example Prompt:** `Prompt: '/freeze api/ so no background job touches the ETL code.'`

#### `unfreeze`
- **Trigger:** Trigger: `/unfreeze`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Lifting freeze boundary after verification passes.
- **Example Prompt:** `Prompt: '/unfreeze lift the directory lock.'`

#### `test-driven-development`
- **Trigger:** Trigger: `test-driven-development` / 'TDD'
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: Before adding any calculation or metric formula in `etl/` or `api/`.
- **Example Prompt:** `Prompt: 'Write a failing pytest test in tests/test_weekly_report.py checking the new metric before writing the implementation.'`

#### `systematic-debugging`
- **Trigger:** Trigger: `systematic-debugging` / 'debug issue'
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: When diagnosing discrepancies between Forsta API survey inputs and CIP MySQL tables.
- **Example Prompt:** `Prompt: 'Use systematic debugging to trace why survey wave 532 crosstabs differ from Forsta raw export.'`

#### `writing-plans`
- **Trigger:** Trigger: `writing-plans` / 'create plan'
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: Before any multi-file feature or database migration.
- **Example Prompt:** `Prompt: 'Write a step-by-step implementation plan with verification checkpoints for migrating from openpyxl to xlsxwriter.'`

#### `requesting-code-review`
- **Trigger:** Trigger: `requesting-code-review` / 'code review'
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: Prior to staging a change; verifies against AGENTS.md, solid design, and ponytail ladder.
- **Example Prompt:** `Prompt: 'Perform a code review on git diff against CIP plain-English header and minimal code rules.'`

#### `using-git-worktrees`
- **Trigger:** Trigger: `using-git-worktrees`
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: Starting experimental feature work in complete isolation from the live working tree.
- **Example Prompt:** `Prompt: 'Set up an isolated git worktree for testing the DuckDB analytical cube integration.'`

#### `verification-before-completion`
- **Trigger:** Trigger: `verification-before-completion`
- **Compatibility:** Both (Claude + Gemini via superpowers)
- **When to use:** When to use: Before claiming any bug fix or task is complete.
- **Example Prompt:** `Prompt: 'Run .venv/bin/pytest tests/ and npm run build before reporting task complete.'`

#### `ce-simplify-code`
- **Trigger:** Trigger: `/ce-simplify-code`
- **Compatibility:** Both (Claude + Gemini via compound-engineering)
- **When to use:** When to use: After finishing an implementation pass; deletes single-use wrappers and redundant abstractions.
- **Example Prompt:** `Prompt: '/ce-simplify-code on api/main.py and etl/ to prune dead code per the ponytail ladder.'`

#### `codebase-design`
- **Trigger:** Trigger: `codebase-design`
- **Compatibility:** Both (Claude + Gemini via compound-engineering)
- **When to use:** When to use: Designing module interfaces following John Ousterhout's deep-module philosophy.
- **Example Prompt:** `Prompt: 'Redesign etl/forsta_client.py so its public interface is 2 functions hiding all HTTP and retry complexity.'`

#### `sharp-edges`
- **Trigger:** Trigger: `sharp-edges`
- **Compatibility:** Both (Claude + Gemini via trailofbits)
- **When to use:** When to use: Auditing FastAPI schemas in `api/` for footguns and insecure defaults.
- **Example Prompt:** `Prompt: 'Audit api/schemas.py for sharp edges, ensuring all query limits have strict upper bounds.'`

#### `semgrep-rule-creator`
- **Trigger:** Trigger: `semgrep-rule-creator`
- **Compatibility:** Both (Claude + Gemini via trailofbits)
- **When to use:** When to use: Writing static analysis rules to block un-parameterized SQL queries.
- **Example Prompt:** `Prompt: 'Create a Semgrep rule that flags any raw SQL string interpolation in api/ and etl/.'`

#### `supply-chain-risk-auditor`
- **Trigger:** Trigger: `supply-chain-risk-auditor`
- **Compatibility:** Both (Claude + Gemini via trailofbits)
- **When to use:** When to use: Auditing `requirements.txt` and `frontend/package.json`.
- **Example Prompt:** `Prompt: 'Audit requirements.txt for single-maintainer risks, pinned CVEs, and abandoned packages.'`

#### `differential-review`
- **Trigger:** Trigger: `differential-review`
- **Compatibility:** Both (Claude + Gemini via trailofbits)
- **When to use:** When to use: Security-focused diff review assessing blast radius before staging.
- **Example Prompt:** `Prompt: 'Review git diff for security regressions, token leakage, or unauthenticated route exposure.'`

#### `git-guardrails-claude-code`
- **Trigger:** Trigger: `git-guardrails-claude-code`
- **Compatibility:** Claude (hook)
- **When to use:** When to use: Continuous background hook enforcing HARD RULE: 'NEVER COMMIT OR PUSH'.
- **Example Prompt:** `Prompt: 'Verify git guardrail hooks are active to block any git push or git commit.'`

#### `claude-api`
- **Trigger:** Trigger: `claude-api`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: In `api/assistant.py` (Ask CIP) for managing Anthropic client, prompt caching, and structured output.
- **Example Prompt:** `Prompt: 'Configure prompt caching in api/assistant.py on SYSTEM message to cut token costs by 90%.'`

#### `health`
- **Trigger:** Trigger: `/health`
- **Compatibility:** Both (Claude + Gemini via gstack)
- **When to use:** When to use: Periodic codebase health check on CIP code quality, test passes, and cyclomatic complexity.
- **Example Prompt:** `Prompt: '/health audit CIP code quality and test coverage dashboard.'`

#### `qa`
- **Trigger:** Trigger: `/qa`
- **Compatibility:** Both (Claude + Gemini via gstack)
- **When to use:** When to use: Running automated full-stack QA checks on Next.js frontend + FastAPI backend.
- **Example Prompt:** `Prompt: '/qa test all survey wave filters and report downloads on localhost:3000.'`

#### `qa-only`
- **Trigger:** Trigger: `/qa-only`
- **Compatibility:** Both (Claude + Gemini via gstack)
- **When to use:** When to use: Running non-destructive read-only QA audit on staging.
- **Example Prompt:** `Prompt: '/qa-only audit staging portal endpoints without modifying database state.'`

### Frontend & UI Engineering (KEEP-CIP)

#### `frontend-design`
- **Trigger:** Trigger: `frontend-design`
- **Compatibility:** Both (Claude + Gemini via anthropic-skills)
- **When to use:** When to use: In `frontend/src/screens/` when building or reshaping dashboard UI components.
- **Example Prompt:** `Prompt: 'Apply frontend design guidelines to the survey question matrix: high contrast typography, accessible focus states, zero AI slop.'`

#### `web-artifacts-builder`
- **Trigger:** Trigger: `web-artifacts-builder`
- **Compatibility:** Both (Claude + Gemini via anthropic-skills)
- **When to use:** When to use: Generating multi-component React/Tailwind analytics widgets for Next.js 16.
- **Example Prompt:** `Prompt: 'Build an interactive demographic breakdown card using React 19 and Tailwind CSS variables.'`

#### `webapp-testing`
- **Trigger:** Trigger: `webapp-testing`
- **Compatibility:** Both (Claude + Gemini via anthropic-skills)
- **When to use:** When to use: End-to-end browser automation testing for Next.js screens.
- **Example Prompt:** `Prompt: 'Run Playwright assertions verifying that clicking survey question S1 renders the chart within 80ms.'`

### Instagram & Short-Form Video Creation (KEEP-GENERAL)

#### `ig-reel`
- **Trigger:** Trigger: `/ig-reel <topic>`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Drafting a Reel from 26 scored hook formulas with timed beat sheet.
- **Example Prompt:** `Prompt: '/ig-reel Showcasing DuckDB as a sub-millisecond in-process analytics engine'`

#### `ig-viral`
- **Trigger:** Trigger: `/ig-viral <niche>`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Finding outlier reels in tech/developer niche ranked by multiple over median.
- **Example Prompt:** `Prompt: '/ig-viral analyze developer tools and AI agent coding reels'`

#### `ig-caption`
- **Trigger:** Trigger: `/ig-caption <draft>`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Linting caption to ensure the hook fits in the 125 characters before the '...more' truncation.
- **Example Prompt:** `Prompt: '/ig-caption Write a 125-character high-conversion caption for the DuckDB reel.'`

#### `ig-human`
- **Trigger:** Trigger: `/ig-human <script>`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Stripping AI slop words, em dashes, and invisible watermark characters from drafts.
- **Example Prompt:** `Prompt: '/ig-human clean this script through slop.json and detect.py heuristics.'`

#### `ig-carousel`
- **Trigger:** Trigger: `/ig-carousel <topic>`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Designing swipe-based multi-slide educational carousels.
- **Example Prompt:** `Prompt: '/ig-carousel 5 tips to eliminate FastAPI database connection drops on Azure MySQL'`

#### `edit-video`
- **Trigger:** Trigger: `edit-video`
- **Compatibility:** Both (Claude + Gemini)
- **When to use:** When to use: Editing Reels, TikToks, and Shorts with event-matched audio and safe areas.
- **Example Prompt:** `Prompt: 'Edit short-form video brief with synchronized captions and adaptive glass styling.'`

---

## Section 4: Removal Plan & Space Savings (Step 5 - Pending User Approval)

> [!IMPORTANT]
> **SAFETY GATE:** In strict adherence to STEP 5, NO files have been deleted or moved. The following removal plan is staged and waiting for explicit user confirmation (`Proceed` or `Yes`).

### Space Reclamation Breakdown

| Target Category | Path | Action | Space Recovered |
| :--- | :--- | :--- | :---: | |
| **Unused Marketplace Clone** | `~/.claude/plugins/marketplaces/understand-anything` | Move to trash/removal (contains 445MB `node_modules`, 0 installed plugins) | **526.33 MB** |
| **Unused Marketplace Clone** | `~/.claude/plugins/marketplaces/ruflo` | Move to trash/removal (heavy duplicate agent repo) | **232.89 MB** |
| **Redundant Diagram References** | `~/.codex/skills/excalidraw-diagram-skill` | Remove (135MB reference assets; duplicated by `diagram`) | **135.30 MB** |
| **Duplicate Session Sync Buckets** | `~/.claude/skills/synced` | Remove duplicate remote cache buckets | **22.09 MB** |
| **Redundant UI Package** | `~/.claude/skills/impeccable` | Remove (18.6MB duplicated by `frontend-design` & `21st-ui`) | **18.60 MB** |
| **Legacy Architecture Tool** | `~/.claude/skills/archify` | Remove (10.7MB legacy tool; replaced by `codebase-design`) | **10.73 MB** |
| **Deleted Trash Cache** | `~/.claude/skills/.trash` | Clear literal deleted files cache | **4.23 MB** |
| **Static Markdown Archive** | `~/.claude/skills/awesome-design-md` | Remove (2.85MB static archive; superseded by `frontend-design`) | **2.85 MB** |
| **AWS Skills (23 skills)** | `~/.claude/skills/aws-*`, `~/.agents/skills/aws-*` | Remove (CIP runs on Azure App Service & Azure MySQL; AWS unused) | **3.25 MB** |
| **Physical Directory Duplicates (80 skills)** | Duplicate copies across `~/.claude/skills` & `~/.gemini/config/skills` | Consolidate to single canonical symlink pointing to source | **35.10 MB** |
| **Specialized Genomics Tools (Scientific)** | `anndata`, `scikit-bio`, `imaging-data-commons`, etc. | Remove specialized clinical/bio tools irrelevant to consumer research | **18.50 MB** |
| **Redundant GSD Phases (67 skills)** | `gsd-*` across `.claude/skills` & `.gemini/config/skills` | Remove (duplicates `superpowers` & `compound-engineering`) | **0.28 MB** |
| **TOTAL RECLAIMABLE DISK SPACE** | | | **2,163.77 MB (~2.11 GB)** |

### Staged Move Protocol (Executed after User Approval)

```bash
# Protocol to be run upon approval:
DATE=$(date +%Y%m%d)
DEST=~/skills-removed-$DATE
mkdir -p "$DEST"

# 1. Move uninstalled heavy marketplaces
mv ~/.claude/plugins/marketplaces/understand-anything "$DEST/"
mv ~/.claude/plugins/marketplaces/ruflo "$DEST/"

# 2. Clear deleted trash and sync buckets
mv ~/.claude/skills/.trash "$DEST/"
mv ~/.claude/skills/synced "$DEST/"

# 3. Move large duplicate skill trees
mv ~/.codex/skills/excalidraw-diagram-skill "$DEST/"
mv ~/.claude/skills/impeccable "$DEST/"
mv ~/.claude/skills/archify "$DEST/"
mv ~/.claude/skills/awesome-design-md "$DEST/"

# 4. Remove unused AWS and iOS clusters from all 4 skill directories
# 5. Consolidate remaining 80 duplicate physical folders into clean symlinks
```

---

## Section 5: Verification Checklist (Post-Approval State)

Once approved, the following commands will be run and appended with raw outputs:
1. `du -sh` on all five directories before and after.
2. `find -L ~/.claude/skills ~/.gemini/skills ~/.gemini/config/skills ~/.agents/skills -type l` (asserting broken links = **0**).
3. CLI check verifying Claude and Gemini both still launch and list installed skills cleanly.
