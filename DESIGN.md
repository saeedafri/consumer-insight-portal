---
name: Consumer Insight Portal
description: Coresight Research survey analytics design system (Research Desk)
colors:
  primary: "#D62E2F"
  primary-hover: "#BF2627"
  primary-wash: "#FBEAEA"
  ink: "#2D2A29"
  ink-secondary: "#5F5C5B"
  paper: "#FAFAFA"
  surface: "#FFFFFF"
  desk: "#EEF0F3"
  blue: "#005F8F"
  sky: "#A3C0CE"
  rose: "#D07676"
  grey: "#7F7F7F"
  silver: "#B2B2B2"
  mist: "#E5E5E5"
  up-sig: "#166B41"
  down-sig: "#A61F20"
  warn: "#8A5A00"
  warn-wash: "#FFF4D6"
  fill: "#F2F1F0"
  rail: "#2D2A29"
typography:
  display:
    fontFamily: "Montserrat Variable, Montserrat, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Montserrat Variable, Montserrat, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "normal"
  title:
    fontFamily: "Montserrat Variable, Montserrat, system-ui, sans-serif"
    fontSize: "15.5px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "Montserrat Variable, Montserrat, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Montserrat Variable, Montserrat, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.02em"
rounded:
  sm: "4px"
  md: "8px"
  lg: "10px"
  full: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "7px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "7px 14px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "18px 20px"
  chip-significant:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.down-sig}"
    rounded: "{rounded.full}"
    padding: "2px 9px"
  chip-neutral:
    backgroundColor: "{colors.fill}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.full}"
    padding: "2px 9px"
---

## Overview

Consumer Insight Portal (CIP) follows the **Research Desk (Option C)** design paradigm. The interface is purposefully designed for market researchers, retail executives, and quantitative analysts who examine weekly consumer tracking surveys.

The system is founded on the conviction that **survey data is sample evidence, not a deterministic financial ledger**. Visual authority is communicated through restraint, structured typographic hierarchy, explicit respondent base annotations ($N$), statistical significance encoding, and clean data density.

## Colors

Coresight 2026 Brand Palette is applied with strict intentionality:

- **Brand Primary (`#D62E2F`)**: Used exclusively for brand identity (the CIP logo badge), active navigation rail indicators, the primary page-level action button, and the left heading accent bar. It is never used as generic decorative background wallpaper or casual text coloring.
- **Ink & Neutral Hierarchy**:
  - `ink` (`#2D2A29` in Light, `#FAFAFA` in Dark): High-contrast primary reading text.
  - `ink-secondary` (`#5F5C5B` in Light, `#C9C5C3` in Dark): Metadata, respondent base counts, footnotes, and inactive labels ($\ge 6.6:1$ contrast ratio).
- **Backgrounds & Surfaces**:
  - `paper` (`#FAFAFA` / `#1B1918`): The main application background canvas.
  - `surface` (`#FFFFFF` / `#2D2A29`): White content cards with a hairline border (`#E5E5E5`).
  - `fill` (`#F2F1F0` / `#3A3634`): Segmented controls, chips, and table row hover states.
- **Data Series & Significance Scale**:
  - `blue` (`#005F8F` / `#A3C0CE`): Standard data series for bar and column charts.
  - `sky` (`#A3C0CE`): Default categorical bar fill.
  - `up-sig` (`#166B41`) / `down-sig` (`#A61F20`): Statistically significant shifts ($p < 0.05$, $z \ge 1.96$). Non-significant shifts remain muted grey (`#7F7F7F`).
  - `warn` (`#8A5A00` on `#FFF4D6`): Small base warning ($N < 50$), question routing breaks, and non-comparable wave shifts.

## Typography

- **Primary Typeface**: Montserrat Variable (`@fontsource-variable/montserrat`) with system-ui fallback.
- **Numeric Discipline**: All data tables, percentages, base counts, and delta chips enforce `font-variant-numeric: tabular-nums` to ensure exact column alignment and instant vertical comparison.
- **Scale**:
  - Page Headings: `28px` / Weight 600 / Line-height 1.2.
  - Block/Question Titles: `21px` / Weight 600 / Line-height 1.35.
  - Card Headings: `15.5px` / Weight 600.
  - Data / Body Text: `14px` / Weight 400.
  - Metadata, Bases, Notes: `12px` / Weight 500 or 600.
  - Large Hero Figures: `34px` / Weight 700.
- **Tone & Case**: Sentence case across all titles, buttons, and badges. No all-caps text.

## Layout

- **Frame Architecture**:
  - **Left Sticky Rail (248px)**: Dark brand rail displaying the Coresight logo, portal navigation links (Overview, Changes, Questions, Cross-tabs, Trends, Survey, Library), and dataset wave statistics.
  - **Top Sticky Bar**: Compact header containing survey wave selector, wave date, respondent count context, global question search shortcut (`Cmd+K`), and Light/Dark mode switcher.
  - **Main Canvas**: Centered container with max-width `1440px` and responsive gutters (`28px` on desktop, `16px` on tablet/mobile).
- **Responsive Grid**:
  - Flexible CSS grid (`.g2`, `.g3`, `.g4`, `.g5`) collapsing to 2 columns on tablet ($\le 1180\text{px}$) and 1 column on mobile ($\le 900\text{px}$).
  - Split views: Dual-pane layout (`340px` question navigator + fluid analysis canvas) collapsing gracefully into single stacked view on narrow viewports.

## Elevation & Depth

- CIP adopts a **flat, tonal layering model** rather than heavy drop shadows:
  - Surfaces are separated by crisp 1px borders (`#E5E5E5`) and micro-tonal contrast (`#FAFAFA` canvas vs `#FFFFFF` card surface).
  - Subtle grounding shadow (`0 1px 2px rgba(45, 42, 41, 0.06), 0 4px 16px rgba(45, 42, 41, 0.05)`) provides depth for floating tooltips, dropdowns, and cards without visual noise.

## Shapes

- **Radius Hierarchy**:
  - Content Cards & Modals: `10px` (`--radius`).
  - Buttons, Inputs, Select Fields: `8px`.
  - Base Indicators & Badges: `6px`.
  - Significance & Status Chips: `999px` (pill radius).
- **Visual Rhythm**: Standard 8px grid (spacing multiples of 4px, 8px, 16px, 24px).

## Components

### 1. KPI & Databank Tiles (`.kpi`)
- Displays metric percentage (`34px` bold in brand red for focal metrics or ink for standard metrics).
- Label placed clearly at top with fixed minimum height for vertical rhythm.
- Explicit footnote indicating respondent base ($N$) and wave comparison.
- Interactive cards provide hover outlines (`1px solid var(--red)`) signaling drill-down capability.

### 2. Status & Significance Chips (`.chip`)
- Pill badges (`border-radius: 999px`) indicating delta direction and statistical significance.
- `.chip.sig`: Light red wash (`#FBEAEA`) with deep red text (`#A61F20`) for significant movements.
- `.chip.flat`: Neutral grey fill (`#F2F1F0`) with muted text for non-significant fluctuations.
- `.chip.warn`: Light amber wash with warning text for small bases or method changes.

### 3. Data Tables (`table.data`)
- Sticky dark table header (`#2D2A29` with `#FFFFFF` text) anchoring long tabular views.
- Strict right-alignment for all numeric columns.
- Cross-tab heat mapping using blue opacity ombre (`rgba(0, 95, 143, alpha)`) calibrated for readable text contrast.

### 4. Question Header (`.qhead` & `.qtext`)
- Question code pill (e.g. `Q1`, `XM1`) in solid brand red with bold white text.
- Respondent wording rendered prominently in `21px` weight 600.
- Context line specifying question type (Single choice, Multi-select, Matrix), base condition, and sample count.

## Do's and Don'ts

### Do:
- Always pair every metric and percentage with its sample base ($N$).
- Use tabular numbers (`font-variant-numeric: tabular-nums`) in all numeric displays.
- Highlight changes in green/red **only** when statistically significant ($p < 0.05$).
- Preserve dark mode parity across all components, charts, and tables.
- Clearly annotate missing waves, routing changes, and sample suppression.

### Don't:
- Don't use brand red as a decorative background, border clutter, or non-essential text.
- Don't nest cards inside cards (anti-pattern: keep hierarchy flat and clean).
- Don't hide respondent bases or make claims of trend without significance indicators.
- Don't use pure black (`#000000`) or harsh un-tinted greys.
- Don't use screaming all-caps in headings, table columns, or buttons.

