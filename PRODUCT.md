# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are Coresight Research analysts, research directors, retail strategy consultants, and enterprise client subscribers (retail brand executives, merchandising leads, and market research teams). They operate in high-stakes analytical situations where they must evaluate consumer sentiment, track weekly retail spending intentions, verify statistical significance across demographic cohorts, and prepare data-driven client presentations and research reports.

## Product Purpose

The Consumer Insight Portal (CIP) aggregates, harmonizes, and visualizes weekly consumer survey tracker data (spanning from 2018 to the present across 144+ survey waves and over 71,000 qualified respondents). It replaces manual, error-prone spreadsheets with an interactive, research-grade portal that lets analysts and enterprise clients instantly explore survey questions, compare wave-over-wave changes, evaluate two-cut cross-tabulations, and track longitudinal trends with guaranteed mathematical and statistical accuracy.

## Positioning

CIP is a research-grade analytical desk—not a generic SaaS metrics dashboard. Unlike generic dashboards that treat metrics as simple continuous counters, CIP treats every metric as a sample estimate derived from survey respondents:
1. Every figure explicitly displays its respondent base ($N$).
2. The exact question text is presented in respondents' words rather than abstracted metrics.
3. Longitudinal shifts are highlighted with colour *only* when statistically significant at 95% confidence (two-proportion $z$-test).
4. Methodological breaks (such as questionnaire routing changes) and sample limitations ($N < 50$) are explicitly surfaced as "Not comparable" or "Small base" states rather than disguised as drops or spikes.

## Operating Context

- Used during weekly survey wave releases (every Monday when the Forsta survey wave closes).
- Analysts pull insights, cross-tabulations, and chart exports directly into Coresight weekly reports, PowerPoint decks, and client briefings.
- Dual-surface architecture:
  - **Client & Analyst Web Portal** (`web/`): A high-performance React 19 + Vite application providing instant exploration of Overview, Questions, Cross-tabs, Trends, Changes, Survey Simulation, and Library.
  - **Internal Operations & Data Health** (`app/pages/`): Streamlit administrative interface for wave loading, harmonization mapping review, and publication drift cross-checking.

## Capabilities and Constraints

- **Historical Depth**: Spans 144+ waves from 2018 to present across Qualtrics, SurveyMonkey, and Forsta Surveys.
- **Harmonization Engine**: Questions linked to 828+ canonical concepts across waves, resolving rotating weekly modules.
- **Pre-computed Multi-dimensional Cube**: Sub-second queries (P95 < 0.35 s) over multi-million row datasets.
- **Dual Themes**: Complete light and dark mode support honoring brand guidelines.
- **Zero-Friction Client Access**: Read-only fast serving with static publishing and responsive data tables designed for 10+ banner columns.
- **No Data Fabrication**: Never extrapolate, invent sample responses, or smooth out survey breaks without methodological footnotes.

## Brand Commitments

- **Brand Authority**: Coresight Research 2026 Style Guide.
- **Brand Palette**:
  - Primary Brand Red (`#D62E2F`): Reserved strictly for identity, logo, active navigation markers, and primary call-to-action buttons. Never used casually as text or decorative wallpaper.
  - Ink (`#2D2A29` / `#1A1A2E`): Deep charcoal text for high contrast readability.
  - Desk & Paper (`#EEF0F3` / `#FAFAFA` / `#FFFFFF`): Clean, intentional surfaces.
  - Data Series Blue (`#005F8F` / `#A3C0CE`): Controlled opacity ombre for categorical options.
- **Typography**: Montserrat for headings and Roboto for body text, as on coresight.com, with tabular numbers (`tabular-nums`) across all data displays. Sentence case exclusively—no screaming uppercase headers.
- **Brand Motifs**: Clean red vertical bar prefix on major page headings (reproducing the authoritative Coresight Research PDF report style).

## Evidence on Hand

- Verified database staging environment (`cip_stg`) with 10.4M+ respondent answer rows reconciled 100% against source workbooks.
- Comprehensive UI architecture specifications and benchmark reports in `docs/Ui-Design-Claude/` (including Option C "Research Desk" system design, competitor teardowns, and load benchmarks).
- Interactive mockups and goldens in `docs/Ui-Design-Claude/ui/`.
- Production React codebase in `web/src/` with live TypeScript and statistical verification suites (`stats.check.ts`).

## Product Principles

1. **Truth Before Aesthetics**: Never prioritize a pretty visual trend over sample validity, respondent base clarity, or statistical significance.
2. **Scanability with Depth**: Deliver immediate takeaway insights at a glance (executive takeaway line and KPI tiles), but allow immediate click-through to question wording, cross-tabs, and raw percentages.
3. **Restraint Over Clutter**: Color carries quantitative meaning (statistical significance or scale sentiment). Neutralize secondary elements so significant signals stand out instantly.
4. **Resilience Across Breakpoints**: Provide compact, dense table views (such as condensing 10+ banner columns) that adapt cleanly to laptops, tablets, and desktop workstations.

## Accessibility & Inclusion

- Target WCAG AA compliance (contrast ratio $\ge 4.5:1$ for normal text, $\ge 3:1$ for large text and UI components).
- Accessible data visualization: Ensure data charts provide tooltips, data tables, and color scales distinguishable for red-green and blue-yellow color vision deficiencies.
- Full keyboard navigation and visible focus rings (`:focus-visible` with 2px brand outline).
- Respect `prefers-reduced-motion` across all micro-interactions and transitions.

