# Ask CIP rebuild, part 1: the manager's template as a complete behaviour spec (27 Nov 2026)

What this is: the manager's template (`ask-cip-in-platform-v4.html`, one beauty-purchases answer) taken apart element by
element, then widened to every kind of question Ask CIP gets, then compared with what Ask does today, with the
smallest change for each gap. The meeting notes (newer than the template) win wherever the two disagree.
Who reads it: whoever builds the rebuild (frontend/src/screens/Ask.tsx, api/assistant.py and friends), and the manager
for the open questions in section 6. Nothing in the repo was changed to write it.

How it was made: the template was served locally and driven with REA (`capture_browser_scenario`) in light mode, dark
mode and at phone width; every element, state and interaction was clicked through. The current code was read
(file:line below). Claims about real figures were checked against `data/published/current` (the 10 Nov 2026 publish,
US only) and two read-only questions to staging's Ask (the `cip-stg` connector). No data left Coresight systems.

| Capture | REA evidence ID | What it covers |
|---|---|---|
| Light, 1280 px, 5 steps | `ev_4f88a22fe057e889e7737f473cb1144e53e0fc128060398d06eecd5bb2f60a78` | load, Since 2022 range, every-result table opened, Analyst view |
| Dark, 1280 px, 10 steps | `ev_9886998bb114f613176657893c8011e00bdd5c608450c0116941da163a012bfb` | theme switch, History open/close, dot tooltip, empty Ask, chip, filled Ask, New question |
| Phone, 390 px | `ev_5d266158c24afeecb19faa1339835784b0b1f6316e8a35afc070045520a9af9a` | stacked layout and the accessibility tree |

Screenshots (temporary, scratchpad): `/private/tmp/claude-501/-Users-mohdsaeedafri-All-Code-Base-cip-test/005d6eac-65c9-4dd6-abbd-892864090ebc/scratchpad/shots/`
(`light-step1.png`, `light-step4.png`, `dark-step3.png`, `dark-dot.png`, `dark-composer.png`, `mobile.png`).

---

## 0. Read this first: what changes the plan

1. **The template's own chart is wrong data, and so is Ask today.** The beauty trend joins five different survey
   questions that once shared the code Q10. Only one of the template's 15 points before 2025 is the beauty question:
   - "Since Aug 2022 +10.7 pts, from 54.8%": 8 Aug 2022 asked *"Have you purchased any footwear in the past three months?"*
   - "Unusual high 88.8% (Nov 2024)": 4 Nov 2024 asked *"Have you purchased any products online in the past three months?"*
   - 15 Aug 2022 (77.8%) was the online question too; 21 Oct 2024 (62.0%) footwear; 18 Nov 2024 (59.9%) department stores.
   - The real beauty series (same wording, Q10 then B1 then BT1): 25 Nov 2024 68.2%, 12 May 2025 69.9%, 4 Aug 2025 74.4%,
     27 Oct 2025 68.4%, 19 Jan 2026 62.5%, 13 Apr 2026 63.9%, 6 Jul 2026 63.6%, 28 Sep 2026 65.5% (264 of 403).
   - **Correction (27 Nov 2026, Phase M):** the same wording goes back further. The BT1 question file's waves borrowed
     from Q8 and Q6 (`borrowed`, exact wording) and each wave's book show it from 5 Sep 2022 (68.9%): 18 readings
     (two surveys on 26 Dec 2023 added together). So "Since 2022" is a real range; only the template's figures were
     wrong. The first-to-latest change (68.9% to 65.5%) could be chance. `mockups/build_samples.py` reads it.
   - Staging's Ask returns exactly the template's series today ("asked in 22 waves, 8 Aug 2022 – 28 Sep 2026 ... Highest
     88.8% (4 Nov 2024) ... Includes the same question asked under 2 earlier codes (Q10, B1, BT1)").
   - Root cause: `api/ask_index.py:191-208` `wording_groups` joins a wording to a group when it shares half its words
     with the group's *last* member (`SAME_WORDING = 0.5`, line 60). "Have you purchased any footwear / products online /
     products from a department store / beauty products in the past three months?" chain into one series. Across all
     2,666 published question files, 12 joined groups (151 waves) hold a pair of wordings under the 0.5 threshold
     (certain chaining); a wider check (wordings that differ by a sector, channel or holiday word) finds about 64
     groups (401 waves). The same groups join "How much did you spend on footwear / at off-price retailers / at drug
     stores" (Q10, Q11, Q14).
   - So the honest headline for the template's question is: *"In the latest survey (28 Sep 2026), 65.5% of US adults
     said they bought beauty products in the past three months, about the same as in November 2024 (68.2%)."* The
     "+10.7" card, the "Unusual high" label and the "Why was Nov 2024 so high?" chip all disappear. **Fix the join
     first (gap G14); the template must not be used as test data except its latest figure.**
2. **"Gen X highest at 72.4%" is a tie.** Real figures for 28 Sep 2026: Gen X 72.4%, Millennials 72.1%, Gen Z 70.5%,
   Boomers 51.2%. The plain answer is "Gen Z, Millennials and Gen X about the same (70.5% to 72.4%); Boomers lowest
   (51.2%)". Ask's tiles today also pick a single "Highest" (`api/assistant.py:593-617`).
3. **The chart rule flips a decision made today.** The user asked on 27 Nov 2026 for the chart only on request
   (`Ask.tsx:26` `ASKS_CHART`, status/README.md line 42, "Waiting for deploy"). The manager's layout puts a chart in
   every answer. The meeting notes win; the user should confirm before the toggle is removed.
4. **"Omit the base" collides with small-sample honesty.** The template's hint says "Check the sample size before
   quoting a figure" while the meeting removes the sample size. Ask must carry the warning itself, in words (4.3).
5. **There is no market concept yet.** The API has no market input (`api/main.py:836-840`); a question naming no
   country is US (`api/ask_reader.py:253`). China's survey (staging: weekly since 6 Feb 2023, about 550 a wave)
   asks only its fixed Q1-Q9 plus S1-S5, so "both markets" only ever arises for a handful of twin questions.

---

## 1. Decisions that win (meeting notes)

| # | Decision | Effect on the template |
|---|---|---|
| D1 | One view, no Client view / Analyst view | The segmented control and the whole "Analyst detail" block go; significance is said in words |
| D2 | Market selector: US, China, Both; default Both. Both + results in both markets: Ask asks which survey's results. Every answer names the country | New control in the header tools (where the view toggle was); ask-back card (type T13) |
| D3 | Order: direct answer, three summary cards, a suitable chart, then supporting evidence/source. Plain words | Same order as the template, minus Analyst detail |
| D4 | Chart fits the question: vertical bars to compare categories, a line for trends | Line for T2; vertical columns for groups (T3) |
| D5 | Period options follow how often the question is asked | Range/grain buttons depend on the question's cadence (4.3) |
| D6 | Keep dig deeper / follow-ups, Excel export of chart and numbers, Copy the full answer; New question opens a fresh chat, the earlier one stays in History | Chips, Export (Excel with a chart), Copy, New question, History |
| D7 | Placeholder "Ask a question in your own words"; remove "Answers come from survey data." | Composer placeholder; subtitle and hint lines trimmed |
| D8 | Keep the question asked and the source/evidence; omit question code, base, latest-data metadata | Trust block keeps the wording and survey/date; drops "403 US adults", "22 surveys since", codes |

---

## 2. Part A: template inventory

Template facts used below: viewport 1280 px; content column max 1000 px; Figtree font; tokens on `:root` with a full
dark set under `[data-theme="dark"]`; breakpoints at 960, 760 and 640 px. All interactions are plain JS in one IIFE.

### 2.1 Page header and tools

| Element | Shows | States and interactions (observed) | Data it needs | Fate |
|---|---|---|---|---|
| Page title | "What would you like to understand?" (30 px, 800) | none | none | Keep |
| Subtitle | "Ask a question in your own words. Answers come from Coresight survey data." | none | none | Keep first sentence only (D7) |
| View toggle | Client view / Analyst view, `aria-pressed`, red outline on the pressed one | Click toggles `body.analyst`, showing `.analyst-only` blocks | none | Remove (D1); replaced by the Market selector |
| History button | "History (15)" with clock icon, `aria-expanded` | Click opens a 340 px popover; click outside closes; no Escape | count of this person's questions | Keep |
| History popover | Up to 4 recent questions, current one highlighted (`aria-current`), "Show all 15" | Items are `<a href="#">` (do nothing) | `[{question, asked_at}]`, the current thread's question | Keep; items re-ask in a fresh thread; add Escape to close; items as buttons |
| New question | Red primary button "+ New question" | Clears the input, changes the placeholder to "Ask anything about the surveys", focuses the box; the thread stays | none | Keep, but it must clear the thread (D6); placeholder stays "Ask a question in your own words" |
| Market selector | not in template | | `market` US / CN / both, remembered per browser | Add (D2) |

### 2.2 Thread

| Element | Shows | States and interactions | Data it needs | Fate |
|---|---|---|---|---|
| Question bubble | The question as typed, right-aligned, navy | none | question text (or `asked_as` for a follow-up) | Keep |
| Collapsed earlier answer | One line: "**Gen X highest at 72.4%,** Boomers lowest at 51.2% (28 Sep 2026)." + "Show full answer" | Button does nothing in the template | a one-line summary: first two cards' label and value + date | Keep; summary from the cards; button expands and collapses (`aria-expanded`) |
| Order | Oldest at the top, newest at the bottom, composer docked below | Thread is `aria-live="polite"` | | Keep |

### 2.3 Answer card

| Element | Shows | States and interactions | Data it needs | Fate |
|---|---|---|---|---|
| Card header | Red mark, "**Ask CIP** Coresight US Consumer Survey" | none | the survey's display name, which names the country | Keep; the survey name is the country label for the whole card |
| Copy | Button with icon | No handler in the template | the full answer as text (4.5) | Keep (D6) |
| Export | Button with icon | No handler | Excel workbook with the chart and the numbers (4.5) | Keep (D6) |
| Headline | "In the latest survey, **65.5%** of US adults reported buying beauty products in the past three months. This is 10.7 percentage points higher than in August 2022 (54.8%), and the share has remained stable throughout 2026." The key figure in red (`em`) | none | latest share, latest date; first share and month; change in points and whether it is real; stability verdict and its window; a plain phrase for what people did ("bought beauty products in the past three months"); country noun ("US adults") | Keep the pattern (T2); the example's numbers are wrong (section 0) |
| Card 1 (main, red tint) | "Latest survey / 65.5% / 28 Sep 2026" | none | latest share, latest date | Keep |
| Card 2 | "Since Aug 2022 / ↑ +10.7 pts (green) / From 54.8%" | none | first month-year, change, direction, first share, whether real | Keep; arrow colour neutral (6, C14) |
| Card 3 | "During 2026 / Steady / Between 63.5% and 65.5%" | none | the window (this year), its verdict, its lowest and highest | Keep; real 2026 range is 62.5% to 65.5% |
| Chart card title | "Bought beauty products in the past three months" / "% of respondents in each survey" | none | the plain phrase; the unit line | Keep |
| Range buttons | "Last 12 months" (pressed) / "Since 2022" | Click redraws: Last 12 months = monthly-quarter ticks and a value label on every dot; Since 2022 = year ticks, no labels, an "Unusual high" label | the series with ISO dates; first year asked | Keep, generalised by cadence (4.3) |
| Line chart (SVG 860x260) | Y axis 0-100% fixed, gridlines at 25s; a red line; a dot per survey; the latest dot larger with a red pill "65.5%" | Dots are focusable (`tabindex=0`); hover or focus shows a tooltip; leave or blur hides it | `[{date, share}]` per survey | Keep |
| Gap joins | Dashed grey line between surveys more than 120 days apart | Recomputed per range | dates | Keep |
| "Unusual high" label | "Unusual high: 88.8% (Nov 2024)" on Since 2022 | Highest point of the range, always labelled | the series max | Keep only under a rule (4.3); in this example it is the data error |
| Tooltip | "**64.0%** bought beauty products / 19 Jan 2026 / [403 respondents]" (respondents only when known) | | share, date, base | Keep share and date; drop respondents (D8) |
| Chart foot | Last 12 months: "Each dot is one survey. Hover a dot for its date and sample size." Since 2022: "... Dashed lines join surveys more than four months apart. The November 2024 reading is much higher than any other, so treat it with care." | Changes with the range | which notes apply | Keep; drop "and sample size" |
| Analyst detail | Three tiles: "Base, latest survey 403 / 264 said yes", "Change since Aug 2022 +10.7 pts / Significant rise", "Since last survey +1.9 pts / Not significant" | Only in Analyst view | base, people, tests | Remove (D1, D8); the tests become words in headline and cards |
| Question asked | "Question asked: “Have you purchased any beauty products (whether for men or women) in the past three months?”" | none | the survey wording(s) | Keep (D8) |
| Based on | "403 US adults surveyed on 28 Sep 2026. Coresight US Consumer Survey, 22 surveys since 8 Aug 2022, unweighted." | none | base, date, survey, count, weighting | Keep only "Coresight US Consumer Survey, 28 Sep 2026" (D8); label "Source" |
| Question code | "BT1 Recent beauty product purchases. Also asked as Q10 and B1." (Analyst only) | link | codes | Remove (D8) |
| See every survey result | Disclosure; table Survey date / Yes / No, newest first, "65.5% (403 respondents)" | Opens and closes; table scrolls at 280 px with a sticky header | every survey's figures | Keep; no respondents column (D8) |
| Not what you meant? | "Pick a different survey question" link | `href="#"` | the close alternative questions | Keep when alternatives exist (C7) |
| Dig deeper | Heading + 5 pill chips: By generation, By household income, By gender, Which products?, Why was Nov 2024 so high? | Click puts the chip's full question (`data-q`) in the box and focuses it; it does not send | each chip: short label, full question, source key | Keep; chips ask at once (today's behaviour); never a "Why" chip (T15) |

### 2.4 Composer (docked at the bottom)

| Element | Shows | States and interactions | Fate |
|---|---|---|---|
| Text box | Placeholder "Ask a follow-up or a new question"; red focus ring | Enter sends; typing clears an error | Placeholder "Ask a question in your own words" (D7) |
| Voice button | Microphone icon, `aria-label="Ask by voice"` | no handler | Keep (exists today: `MicButton`) |
| Ask button | Red "Ask →" | Empty: hint turns red "Type a question or pick one above first."; filled: "In the live product, the answer appears below as a new card in this thread." | Keep; empty send shows the error, not a disabled button |
| Hint line | "Answers use Coresight survey data only. Check the sample size before quoting a figure." | | Remove both sentences (D7, C4); the line is used only for the empty-send error |

### 2.5 Look, dark mode, phone, accessibility

- Dark mode: every token has a dark value (surface `#1B1E23`, red `#F0505E`, navy `#6FA8D8`); the capture shows all text
  readable, the latest-value pill keeps white on red, the History popover and tooltip switch correctly.
- Phone (390 px): nav hidden, cards stack, header tools wrap. The chart scales its whole SVG, so its 11 px labels render
  at about 5 px and are unreadable; the rebuild's chart must lay out again at phone width (ECharts does).
- Accessibility gaps in the template: History has no Escape; history items are dead links; "Show full answer" has no
  `aria-expanded`; the chart's accessible name does not say the figures (the tree reads only tick text). Good: dots
  are keyboard-focusable and show the tooltip on focus; reduced motion is honoured.

### 2.6 Which template figures are real

| Template | Published data | Verdict |
|---|---|---|
| Latest 65.5%, 28 Sep 2026, 403 | BT1: 264 of 403 = 65.5% | Real |
| First point 54.8%, 8 Aug 2022 | Q10 that week asked about footwear | Wrong question |
| 88.8%, Nov 2024 ("Unusual high") | Q10 on 4 Nov 2024 asked about buying anything online | Wrong question |
| "During 2026 between 63.5% and 65.5%" | 62.5%, 63.9%, 63.6%, 65.5% | Approximate (template says "values read approximately") |
| "22 surveys since 8 Aug 2022" | 8 surveys with this wording since 25 Nov 2024 | Wrong (the join) |
| "Since last survey +1.9 pts, not significant" | 63.6% → 65.5%, not significant | Real |
| "Gen X highest at 72.4%, Boomers lowest at 51.2%" | Gen X 72.4 (105), Millennials 72.1 (111), Gen Z 70.5 (61), Boomers 51.2 (125) | Figures real, "highest" misleading |

---

## 3. What kinds of question the data holds (quick check)

- Question types in the published wave books (374 US waves: 271 weekly tracker, 79 ad hoc, 24 annual): single choice
  5,757 question-asks, multi choice 4,434, grids (rate or rank each item) 248. No open numeric answers: amounts are
  always asked in bands ("How much did you spend on footwear in the past three months?"); 28 "How much, in dollars"
  questions without amounts are already left out of the index (`api/ask_index.py` UNIT_ONLY). Ranking grids exist
  ("Please rank the following store checkout methods").
- China: not in the local publish; staging has the weekly China tracker (Q9 asked in 181 waves since 6 Feb 2023,
  550 a wave). Its cuts: gender, age (18-25, 26-41, 42-57, 57-76, 77+), monthly income in RMB bands, city tier
  (`config/countries.yml`). No generation, no region, no Census weighting (`config/weighting.yml` is US only).
- How often US tracker questions are asked (median gap between their surveys, per question file):

| Cadence | Questions | Still asked since Aug 2026 | Example |
|---|---|---|---|
| Every week | 90 | 40 | q3 online categories (196 waves since 2020) |
| Every 2-4 weeks | 48 | 28 | TF1 tariffs, G4 GenAI awareness |
| Every 5-10 weeks | 31 | 27 | DS5 dollar-store reasons |
| About quarterly (sector modules, every 12 weeks) | 92 | 92 | BT10 hair care, FW6 footwear spend |
| Twice a year or less | 8 | 7 | LDR6 Labor Day finances |
| One or two surveys | 334 | 60 | event and one-off questions |
| Annual studies | 24 waves in their own families | | Holiday shopping, Back-to-school |

---

## 4. Part B: the behaviour spec for every answer

### 4.1 The fixed anatomy of an answer

1. **Question bubble**: the words typed (a follow-up also shows a small "Read as: ..." line in plain words).
2. **Card header**: "Ask CIP" + the survey's name, which names the market ("Coresight US Consumer Survey",
   "Coresight China Consumer Survey", or an annual study's name "Coresight Holiday Shopping Survey 2025, US"); Copy; Export.
3. **Direct answer**: one or two sentences, the key figure in red, the country noun in the first sentence.
4. **Three cards**: the first tinted (the main figure); cards 2 and 3 by answer type (4.4).
5. **Chart**: title = the plain phrase; unit line ("% of adults in each survey"); controls only where 4.3 allows;
   a foot line with the notes that apply (each dot one survey; dashed joins; unusual reading; small samples;
   "people could choose more than one").
6. **Evidence**: "Question asked" (the wording in quotes; two wordings when two questions were used); "Source"
   (survey name and date or date range); "See every survey result" (the table); "Not what you meant? Pick a
   different survey question" when other close questions exist.
7. **Dig deeper**: up to 5 chips (4.4 per type).

Never shown: question codes, bases or "n=", the number of surveys, "unweighted", how Ask understood the question
("Best match by meaning"), "Analyst" content, p-values. Shown only when it changes the figures: "Census-weighted
figures" (the Weighted switch is on).

### 4.2 Wording rules (every type)

- Country noun: US "US adults"; China "adults in China"; a group "Gen Z adults in the US", "adults in China aged
  26-41". When the market is Both, every headline names its country even if obvious.
- Dates: a survey "28 Sep 2026"; a month "August 2022"; a quarter "Q3 2026"; a year "2026 (so far)" when incomplete.
- Shares one decimal with "%"; changes "percentage points" in the headline, "pts" in cards.
- Plain phrase for what people did, made from the survey wording by rule ("Have you purchased any beauty products ...
  in the past three months?" → "bought beauty products in the past three months"); when no rule fits, "said “Yes” to
  “{wording}”". One phrase per question, used in the headline, the chart title and the tooltip.
- A change or gap is "higher/lower" or "up/down" only when the 95% test says it is real (two-proportion test,
  30+ people each side, `api/dashboards.py:86`); otherwise "about the same" or "the gap could be chance". Never
  "statistically significant", never "p =".
- Ties: groups or answers not reliably different from the top one are named together ("Gen Z, Millennials and Gen X
  are about the same, 70.5% to 72.4%").
- Say what the survey measures when the question asks more ("a lot", "how often", "why"): "The survey asks whether
  people bought beauty products in the past three months, not how much."
- An old question (last asked over a year before the newest survey) opens "When last asked (12 May 2025), ..." instead
  of "In the latest survey".

### 4.3 Shared rules

**Significance.** As above; computed on unweighted figures even when weighted figures are shown (exists).

**Small samples.** Under 50 people: the figure is marked on the chart (hollow dot or hatched bar) and the foot says
"Fewer than 50 people answered here: read with caution." Under 30: shown in the table only, never in the headline,
cards or a test. In group comparisons, groups under 50 are left out of highest/lowest and the foot says "Groups with
fewer than 50 people are not compared". The number of people is never printed (D8).

**Periods follow the question's cadence (D5).** The cadence is the median gap between the surveys that asked the
question (the index already holds each question's dates).

| Cadence | Grain buttons offered | Range buttons | Default |
|---|---|---|---|
| Weekly or every 2-4 weeks | Each survey (only when the range holds 26 surveys or fewer), Monthly, Quarterly, Yearly | Last 12 months, Since {first year} | Last 12 months, monthly |
| Every 5-14 weeks (sector modules) | Each survey (= roughly quarterly), Yearly | Last 12 months, Since {first year} | Since {first year}, each survey |
| Twice a year or less, annual studies | Each survey (= yearly) | none | all |
| One or two surveys | none (no trend; T1) | none | |

A pooled period counts everyone asked in its surveys (the existing pooling in `api/ask_figures.py`). A partial year
says "2026 so far". "Since 2022" in the template becomes "Since {the first year this wording was asked}".

**Line chart.** Real time axis (spacing by date), 0-100% axis for shares, one red line per series (at most 5 lines),
a dot per reading, the latest dot larger with a value pill, value labels on every dot when 12 or fewer are shown,
dashed grey join where two readings are more than 120 days apart, no join across a different wording (there must be
none after G14).

**Unusual readings.** A reading is labelled "Unusual high/low: x% (Mon YYYY)" only when it differs, by the 95% test, from
both the readings before and after in the same direction and lies 10+ points from the series median (both numbers
in config). Before labelling, Ask checks that reading's wording equals the series wording; if not, the reading is
left out and the join is a bug. The foot says "treat it with care"; never a reason.

**Colour.** One brand red for the series and the key figure; direction arrows in ink, not green or red (up is not
always good: "worried about tariffs" up). See C14.

### 4.4 Answer types

Each row lists: when Ask uses it; the headline pattern (with a real example where the data allowed); the three cards;
the chart and its controls; evidence lines beyond 4.1; dig-deeper chips. Copy and Excel follow 4.5 unless noted.

**T1. Single latest value** (asked once or twice, or "latest" asked)
- Headline: "In the latest survey ({date}), {x}% of {country noun} {phrase}." + "That is about the same as / up N
  percentage points from {previous date} ({y}%)." when asked before. Example: "In the latest survey (28 Sep 2026),
  65.5% of US adults said they bought beauty products in the past three months, about the same as on 6 Jul 2026 (63.6%)."
- Cards: Latest survey (x%, date) | Since {previous date} (change or "About the same", from y%) | for yes/no "Said no"
  (100-x); for a list the runner-up answer; when not asked before, "First time asked".
- Chart: one-question single choice: vertical columns of every answer in the survey's own answer order; a list: bars
  ranked (T4). No range buttons.
- Chips: By generation, By household income, By gender, Over time (when asked 3+ times), related question.

**T2. Trend over time** (asked 3+ times, no period named, or "over time / trend / since")
- Headline: "In the latest survey ({date}), {x}% of {country noun} {phrase}. This is {N} percentage points
  {higher/lower} than in {first month year} ({y}%) / about the same as in {first month year} ({y}%), and the share
  {has stayed steady / has risen / has fallen / has gone up and down} {during {year} / over the last 12 months}."
  Real example (after G14): "In the latest survey (28 Sep 2026), 65.5% of US adults said they bought beauty products in
  the past three months, about the same as in November 2024 (68.2%). The share has stayed between 62.5% and 65.5% during 2026."
- Cards: Latest survey (x%, date) | Since {first month year} (change with arrow, "from y%"; "About the same" when not
  real) | During {year} (or "Last 12 months" when this year has fewer than 3 readings): Steady / Rising / Falling /
  Up and down, "Between a% and b%".
- Verdict rule (config): Steady when the window's highest minus lowest is 5 points or less and no step is real;
  Rising / Falling when first-to-last in the window is real and no real step goes the other way; else Up and down.
- Chart: line (4.3) with range and grain buttons by cadence; unusual label by rule.
- Evidence: the wording; "Source: Coresight US Consumer Survey, {first date} to {latest date}".
- Chips: By generation, By household income, By gender, {First month year} vs latest, related question; Same in China
  when a twin exists (T13).

**T3. Compare demographic groups** ("by generation", "which generation ...")
- Headline: "In the latest survey ({date}), {top group(s)} were the most likely to {phrase} ({x}%), and {bottom group}
  the least likely ({y}%), a real gap of N points / a gap that could be chance." Real example: "In the latest survey
  (28 Sep 2026), Gen Z, Millennials and Gen X were about equally likely to have bought beauty products in the past
  three months (70.5% to 72.4%); Boomers were the least likely (51.2%)."
- Cards: Highest ({group}, x%; note names the tied groups) | Lowest ({group}, y%) | Difference (N pts, "a real gap"
  or "could be chance").
- Chart: vertical columns, one per group in the config order (Gen Z, Millennials, Gen X, Boomers; income low to high),
  value on each column, small groups marked. Controls: "Latest survey" / "Last 12 months" (pooled, steadier for small
  groups) when the question is asked weekly or every 2-4 weeks. Trend by group (asked "over time by generation"):
  one line per group, same controls as T2.
- Chips: the other cuts (household income, gender, age group, region, city or rural), Over time by {cut}.

**T4. Rank the answers of one question** ("which retailers", "top products")
- Headline: "{A} was the most common answer: {x}% of {country noun} {phrase with A} in the latest survey ({date}),
  ahead of {B} ({y}%) and {C} ({z}%)." Ties: "{A} and {B} were about level ({x}% and {y}%)". "Top N" honoured.
- Cards: Top answer | Second | Gap between them (real or chance).
- Chart: bars biggest first, top 10 (or N). Vertical when 6 or fewer short labels, horizontal for longer lists or
  labels (C17). Multi choice: foot "People could choose more than one, so shares add up to more than 100%"; "None of
  these" and "Other" never ranked but kept in the table.
- Chips: By generation, By household income, {A} over time, related question.

**T5. Two periods compared** ("October vs September", "first and latest")
- Headline: "In {period 2}, {x}% of {country noun} {phrase}, up/down N percentage points from {period 1} ({y}%)" or
  "about the same as in {period 1} ({y}%)".
- Cards: {Period 1} (y%) | {Period 2} (x%) | Change (real or chance).
- Chart: vertical paired columns per answer (period 1 lighter, period 2 strong), up to 8 answers. Replaces today's
  dumbbell (C17).
- Chips: Over time, By generation in {period 2}.

**T6. One group within another question** ("among GLP-1 users, what share bought footwear")
- Headline: "Among {country noun} who {group phrase}, {x}% {phrase} in {period}, compared with {y}% of all {country
  noun}" (+ "a real difference" / "about the same").
- Cards: Among {group} | All {country noun} | Difference.
- Chart: two vertical columns (group, everyone), or grouped columns per answer when the counted question is a list.
- Evidence: both wordings; "{Group}: people who answered “{answer}” to “{wording}”", same survey(s).
- Small samples are common here: 4.3 applies; pooled weeks named ("the four surveys from 19 Oct to 9 Nov 2026").
- Chips: the group over time, the counted question for everyone, by another group.

**T7. Two answers combined** ("bought from both Walmart and Target", "either")
- Headline: "{x}% of {country noun} {did both / did either} in {period}."
- Cards: Both (or Either) | {A} | {B}.
- Chart: vertical columns A, B, Both/Either.
- Evidence: "Counted person by person from each survey's answers."
- Chips: Each over time, Both by generation.

**T8. Amounts asked in bands** ("how much did people spend", "average", "median")
- Headline: "The middle answer was {band}; the average was about ${m} (worked out from the ranges people chose)" +
  the period and country. China in RMB.
- Cards: Middle answer | Average (estimate) | Most chosen range (x%).
- Chart: vertical columns per band in band order (never ranked); over time, a line of the average.
- Foot: "Spending was asked in ranges, so the average is an estimate; the top range counts at its lower end."
- Chips: By household income, Over time, By generation.

**T9. Grids** ("how do you feel about each retailer", "rate each category", "rank")
- Headline: "{Item} had the most {positive side} views ({x}% {side words}) and {item} the fewest ({y}%) in {survey}."
  Ranking grids: "{Item} was ranked first most often ({x}%)".
- Cards: Highest item | Lowest item | Difference.
- Chart: horizontal bars, one per item, of the positive side (top two answers) or "ranked first"; the full grid
  (items x answers) in the evidence table.
- Chips: one item over time, By generation for the top item.

**T10. Single choice vs multi choice (applies inside T1-T5)**
- Single choice: shares add to 100%; scales keep their own order (Much better ... Much worse); 6 or fewer answers drawn
  as vertical columns in answer order (replaces today's segmented "split" bar and donut).
- Multi choice: ranked, the "more than one" foot, "None of these" listed last.

**T11. Scales: nets and top-two box** (better/worse, likely/unlikely)
- Headline: "More {country noun} expected {subject} to get worse ({x}%) than better ({y}%) in the latest survey
  ({date})" or "Views are split: ...".
- Cards: {Positive side} (sum of its answers) | {Negative side} | Net ({+/-N}, positive minus negative). Over time:
  Net latest | Net change since {first} | During {year} verdict.
- Chart: one period, vertical columns in scale order with the two sides shaded; over time, two lines (positive and
  negative side).
- Side words from `config/weekly_report.yml net_words` and `config/ask_nets.yml` (exist).

**T12. China**
- Same types; the noun "adults in China", the survey "Coresight China Consumer Survey"; cuts gender, age group,
  monthly income (RMB), city tier. A generation question is answered by age group and says so: "The China survey
  records age groups, not generations." Example shape: "In the latest China survey (9 Nov 2026), 56.0% of adults in
  China expected the economy to be positive over the next 12 months, about the same as on 26 Oct 2026 (57.1%)."
- A wording's own time words ("over the next 12 months") are part of the question, not a period: staging today
  answers this as a two-wave comparison (dumbbell), not a trend (gap G33).
- Chips: By age group, By city tier, By monthly income, Same in the US (when a twin exists).

**T13. Market = Both, results in both (the ask-back)**
- When the best match has a twin in the other market with figures this person may see, Ask answers with a short card
  and no figures: "Both the US and China surveys ask this. Which results do you want?" Buttons: "US results (latest
  {date})", "China results (latest {date})". One click answers in that market; the thread remembers the choice for
  follow-ups. Never one pooled figure across countries (`config/countries.yml` rule).
- Only one market asks it: answer that market, its name in the header and headline.
- The question names a country ("Chinese consumers"): that country, whatever the selector (C15).
- Twins live in config (rules belong in config/*.yml), for example US q1 ↔ CN Q4 (activities in the past two weeks),
  q2 ↔ Q5 (bought in store), q3 ↔ Q6 (bought online), CS2 ↔ Q9 (economy over the next 12 months); personal finances and
  next-two-weeks spending to be confirmed with the research team. Answer lists differ between markets.

**T14. Typed follow-up in a thread** ("What about Gen Z?", "and by income?", "how about China?")
- Read with the previous question and its survey question (exists: `follow_on`); the answer shows "Read as: beauty
  purchases among Gen Z, latest survey". Keeps the market chosen in T13. A follow-up with its own subject is a new
  question in the same thread. "How about China?" switches market and uses the twin.

**T15. "Why" questions and unusual readings**
- Ask never gives a reason the surveys do not record. Headline: "The surveys record what people did and said, not
  why." then the facts it can give: "In {month}, {x}% {phrase}; the surveys before and after were {a}% ({date}) and
  {b}% ({date})", and whether that survey asked the same wording of a similar number of people (said as "the same
  question, asked the same way" or "a different question was asked that week").
- Cards: That reading | Survey before | Survey after.
- When a survey question asks people's own reasons ("What is the main reason you expect to spend more this
  Halloween?"), answer from it as "the reasons people gave".
- Chips: Compare {month} with the surveys either side; reasons question when one exists. Never "Why was ... so high?"
- News events (`config/news_events.yml`) are not offered as causes.

**T16. Ambiguous question** (two different survey questions about equally close)
- Ask-back card: "This could be one of two survey questions. Which did you mean?" with each option as its plain name
  or wording, its survey and when last asked; no codes. One click answers.
- When Ask answered its best match instead, "Not what you meant? Pick a different survey question" opens the same list.

**T17. No survey asks it**
- "None of our surveys asks about {subject}. These are the closest questions we have:" up to 4 chips (plain name,
  survey, last asked). No figures.

**T18. Small samples** (applies everywhere; 4.3). A whole answer resting on under 30 people (a narrow "among" group in one
week) says so first: "Too few people answered for a reliable figure in one survey; here are the four surveys from
{date} to {date} together" (the existing 4-week pool).

**T19. A period the survey did not run**
- "The {US/China} survey did not ask this in {period}. It was asked from {first} to {last}; the nearest surveys were
  {before} and {after}." Chips: those dates and "Latest". China before February 2023: "The China survey started in
  February 2023." "Last month" on a question not asked then: the latest figures, said up front (exists).

**T20. Two kinds of group at once** ("Gen Z women"): pooled over 4 surveys and said so; cards: the group | everyone |
difference; the T3 chart for the combination's siblings.

### 4.5 Copy, Export, thread, History, composer

**Copy (one button, the full answer as plain text):**

```
Q: Recent beauty product purchases over time
In the latest survey (28 Sep 2026), 65.5% of US adults said they bought beauty products in the past three months, about the same as in November 2024 (68.2%). The share has stayed between 62.5% and 65.5% during 2026.
Latest survey: 65.5% (28 Sep 2026)
Since Nov 2024: about the same (from 68.2%)
During 2026: steady, between 62.5% and 65.5%
Question asked: “Have you purchased any beauty products (whether for men or women) in the past three months?”
Source: Coresight US Consumer Survey, 25 Nov 2024 to 28 Sep 2026.
```

Notes that apply (small samples, unusual reading, weighted) follow as lines. No codes, no bases.

**Export (Excel, D6):** one workbook. Sheet "Answer": the question asked, the direct answer, the three cards, the chart's
numbers as a table (dates down, answers across; or groups across), a native Excel chart of the same kind next to it
(line or columns), then notes: question wording, survey and dates, country, "Figures are the % of adults surveyed who
gave each answer", small-sample marks. Sheet "Every survey result": the evidence table. CSV, PowerPoint and PNG may stay
in the menu (C18). Bases in Excel: open (C20).

**Thread:** oldest first, newest at the bottom, the composer docked below; a new answer is appended and scrolled into view;
the previous answers collapse to one line (the first two cards and the date) with "Show full answer". Loading: the
question bubble appears at once, the card shows "Finding the answer…"; errors (busy, too many questions) appear as a
plain line in the thread.

**New question:** clears the thread and the box, focuses the box; the old thread's questions stay in History.

**History:** "History (N)" button; popover with the 4 newest and "Show all N"; the current one highlighted; closes on a
click outside or Escape; choosing one asks it again in a fresh thread (questions are stored as read, so a follow-up
comes back whole: `api/main.py:809`).

**Composer:** placeholder "Ask a question in your own words"; Enter or Ask sends; empty send shows "Type a question first."
under the box; voice button; suggestions while typing stay (today's `suggestAsk`, not in the template, not in conflict).
Empty page (no thread): today's example chips stay.

### 4.6 The data each answer needs (existing vs new)

| Field | Today | Needed for |
|---|---|---|
| `headline`, `tiles[{label,value,note}]`, `chart{type,categories,series}`, `table`, `sources[].question`, `next[]`, `suggestions[]`, `scope.country`, `asked_as`, `notes`, `mode` | exists (`api/assistant.py:1949-1962`, `frontend/src/api.ts:280-298`) | direct answer, cards, chart, evidence, chips |
| request `market` (US, CN, both) | none | D2, T13 |
| `survey` display name with country | none (FAMILY names "Weekly US consumer tracker", `assistant.py:95`) | card header, Source line |
| `tiles[].tone` (main, up, down, same) | none | card styling without parsing text |
| `chart.dates` (ISO per reading), `chart.unusual`, `chart.small`, `chart.grains`, `chart.cadence` | labels only | time axis, dashed joins, labels, controls |
| `next[].label` (short chip text) | full sentence only | chips |
| `suggestions[].country` and `last_asked` | qcode and text | ask-back cards (T13, T16, T17) |
| collapsed summary | none | derived on the page from the first two tiles and the date; no API field needed |

---

## 5. Part C: gap list (today vs required, smallest change)

| # | Part | Today (file:line) | Required | Smallest change |
|---|---|---|---|---|
| G1 | One view | Client/Analyst toggle and saved choice `Ask.tsx:27-29, 306, 312, 396-399`; analyst-only content `Ask.tsx:196, 252-256, 265, 278` | One view | Delete the audience state and toggle; keep what Client view shows; drop the "how it was understood" line and analyst points |
| G2 | Market selector | none; API body has no market `main.py:836-840`; `assistant.ask` `assistant.py:1983`; US default `ask_reader.py:253` | US / China / Both, default Both, remembered | `market` in the body passed to `answer`, which already filters `visible` by country (`assistant.py:1528-1531`); a seg control saved in localStorage like today's view choice; MCP keeps its current behaviour by default |
| G3 | Ask-back for both markets | none | T13 | Twin pairs in `config/countries.yml`; when market is both and the pick has a twin with figures, return `mode: "choose"` with two country choices (reuses the existing choose card) |
| G4 | Country named | Source line "United States · period · N survey waves · N respondents · Unweighted · Source BT1" `Ask.tsx:246-251`; headline noun "US adults surveyed" `assistant.py:279` | Survey name in the header; "US adults" / "adults in China" in the headline | Rename FAMILY values to survey names and show them in the header; drop the source line |
| G5 | Direct answer wording | Takeaway or `in_words` with "(264 of 403, 28 Sep 2026)" `assistant.py:270-313`; "Last asked …" appended `assistant.py:1946-1947`; p-values in combined answers `ask_plan.py:404-416` | 4.2 patterns, no counts, no p, "When last asked" first | Drop the "(people of base," part; move "Last asked" to the front; replace the p-value clauses with the plain words |
| G6 | Key figure in red | Every figure bold `Ask.tsx:31-34` | One red key figure | Colour the first figure of the headline |
| G7 | Cards | `brief` `assistant.py:545-700`: trend = latest / change since first / latest change; groups = highest / lowest / gap without ties; one period = top three answers | 4.4 per type; "During {year}: Steady" card; ties; tone | Replace the trend's third tile with the window verdict (one small helper, thresholds in config, one test); add the tie rule to the group tiles; add `tone` |
| G8 | Chart always shown | Hidden until asked: `ASKS_CHART` `Ask.tsx:26, 189, 266-267` | Shown in every answer that has one (C9) | Delete the toggle and the regex |
| G9 | Chart type switcher | Line/Columns/Table/Donut/... `Ask.tsx:36-52, 268-269` | The one chart that fits | Delete the switcher; the table lives in the evidence |
| G10 | Chart forms | Horizontal bars by default for groups and lists `Ask.tsx:89-95`; types grouped/stacked/heatmap/split/dumbbell `assistant.py:372-412` | Line for trends; vertical columns for groups, scales, bands, two periods; horizontal only for long ranked lists | Draw `grouped`, `split`, `stacked`, `dumbbell` as the existing `column` view; heatmap data to the evidence table |
| G11 | Time axis, gaps, latest pill | Category axis of labels with null gaps `Ask.tsx:83-88` | Real dates, dashed joins over 120 days, latest value pill, labels when 12 or fewer | Add ISO dates to the chart payload (periods carry `from`/`to`); ECharts time axis; a dashed join series |
| G12 | Range and grain buttons | none; periods only from words | 4.3 by cadence | Return allowed grains from the question's dates (index `dates`); buttons re-ask with the source key and words ("by quarter", "since 2024"), as follow-ups already do |
| G13 | Unusual reading | none | 4.3 rule, label, foot, wording check | One helper over the series (two thresholds in config, one test) |
| G14 | **Wrong series (blocker)** | `wording_groups` chains to the group's last member at 0.5 shared words `ask_index.py:60, 191-208`; "Includes the same question asked under N earlier codes" `assistant.py:483` | A series holds one wording (or wordings proven alike) | Join a wording only when alike to every member, and never when the differing words name a subject (sector, channel, product); a test on Q10's footwear/online/beauty wordings; drop the codes sentence |
| G15 | Evidence block | "Figures and sample sizes" with n= `Ask.tsx:165-182, 278-280`; source link labelled with the code `Ask.tsx:250`; notes list `Ask.tsx:275-277`; "What this tells us" `Ask.tsx:274` | Question asked, Source, See every survey result, Not what you meant | Reuse `Figures` without the n cells; one Source line; notes into the chart foot; drop the takeaway block (it is the headline) |
| G16 | Not what you meant | Tags "qcode: text" when unsure `Ask.tsx:205, 260-262, 287-291` | A link opening plain names | Same data (`suggestions`), labels without codes |
| G17 | Dig deeper | Up to 3 sentences "Continue the analysis" `assistant.py:703-724` (cuts `FOLLOW_CUTS` line 86: generation, income), `Ask.tsx:282-286` | Up to 5 short chips: cuts incl. gender, over time / first vs latest, related question, other market, unusual compare | Add gender to `FOLLOW_CUTS`, a `label` per chip, related questions from `suggestions` asked in the same survey, the twin chip |
| G18 | Copy | "For an email" / "For a slide" with code, waves, respondents, weighting `Ask.tsx:136-158, 235-238` | One Copy, full answer, 4.5 | Keep `writeUp` email form, drop code/base/waves, one button |
| G19 | Export | CSV/Excel/PowerPoint/PNG `Ask.tsx:221-229, 239-240`, `components/bits.tsx:250-273`; Excel is a table only `api/exports.py:62-73` (the chart is PowerPoint only, `exports.py:189`); notes carry the source line with the code `Ask.tsx:217` | Excel with the chart and numbers | When the spec carries a chart type, `build_xlsx` adds an openpyxl line or column chart (already installed); notes without codes |
| G20 | Thread order | Newest first, prepended under the box `Ask.tsx:298, 335, 380-413` | Oldest first, composer docked, older answers collapsed | Append instead of prepend; sticky composer; a collapsed state per reply |
| G21 | New question | none; clearing the box clears the answers `Ask.tsx:384-390` | Button that starts a fresh chat | A button that does what clearing does today |
| G22 | History | "Your recent questions (N)" details of tags `Ask.tsx:310-311, 410-411`; data from `main.py:796-813` | "History (N)" popover, 4 + Show all, Escape | Same data, popover markup |
| G23 | Placeholder, title, subtitle | "e.g. How are higher gasoline prices…" `Ask.tsx:392`; "Ask CIP" and a long lede `Ask.tsx:375-378` | D7 and the template title | Text changes |
| G24 | Empty send | Ask disabled under 3 characters `Ask.tsx:394` | Error line "Type a question first." | Keep the guard, show the line |
| G25 | Typed follow-up | Exists: `follow_on` `assistant.py:193-224`, sent from `Ask.tsx:327-330`, shown `Ask.tsx:234` | T14 plus market carried | Pass the thread's market with `previous` |
| G26 | Ambiguous | Asks back only when no AI check follows `assistant.py:1726-1737`; otherwise best guess + unsure tags | T16 | Keep the 12 Nov choice (best match first, then check) and show the options up front as plain names (C24) |
| G27 | No survey asks it | Exists `assistant.py:1595-1597, 1659-1662, 1740-1753`; page shows "qcode: text" `Ask.tsx:288-290` | T17 wording, no codes | Text and labels |
| G28 | Period not run | Exists `assistant.py:1803-1814`; message shows the code | T19 with nearest dates as chips | Drop the code; add the two nearest dates from `fig["asked"]` |
| G29 | Why questions | Only "did X cause" (`assistant.py:1493-1506`) | T15 | A "why / what made / what caused" rule returning the facts around the date and any reasons question |
| G30 | Small samples | "Note: small base, as few as N respondents" `assistant.py:476-479`; groups under 50 left out of tiles (exists) | 4.3 without numbers; under 30 kept out of the headline and tests | Reword the note; one guard for under 30 in `brief` |
| G31 | Combined answers | `ask_plan.answer` has no tiles or chips `ask_plan.py:458-463` | Cards and chips like every answer | Build tiles from its rows (T6, T7) |
| G32 | China | Generation cut not available returns "unavailable group" `assistant.py:1855` (two groups at once: 1360); "over the next 12 months" read as a period (staging answer for Q9) | T12 | Map generation to age group for CN with a note; leave a wording's own time words out of the period reading |
| G33 | Weighting line | "Census-weighted · / Unweighted ·" in the source line `Ask.tsx:249` | Say only when weighted (C2) | Keep the weighted note, drop "Unweighted" |
| G34 | Docs | | What's new, CHANGELOG, API.md and the API guide in the same words when `market` is added (tests/test_docs.py) | Same change |

---

## 6. Part D: conflicts between the template and the meeting notes

| # | Template | Meeting note / other rule | Winner | Still unclear |
|---|---|---|---|---|
| C1 | Client view / Analyst view | One view | Meeting | Does the admin-only "Save as verified" (`Ask.tsx:255-256`) stay, somewhere quieter? |
| C2 | "Based on 403 US adults surveyed on 28 Sep 2026 … 22 surveys since 8 Aug 2022, unweighted" | Omit base and latest-data metadata | Meeting: "Source: Coresight US Consumer Survey, 28 Sep 2026" | Is "unweighted" metadata? Proposed: say only "Census-weighted" when it applies |
| C3 | Tooltip "403 respondents", table "(403 respondents)", foot "Hover a dot for its date and sample size" | Omit base | Meeting | none |
| C4 | Hint "Check the sample size before quoting a figure" | Omit base; remove the data line | Meeting; Ask warns about small samples in words itself | Confirm the wording "Fewer than 50 people answered here" (no number) is acceptable |
| C5 | "Answers come from Coresight survey data." / "Answers use Coresight survey data only." | Remove | Meeting | none |
| C6 | Placeholder "Ask a follow-up or a new question" (and "Ask anything about the surveys" after New question) | "Ask a question in your own words" | Meeting | none |
| C7 | "Not what you meant? Pick a different survey question" always shown | Keep question and evidence; plain | Keep it, but only when other close questions exist, as plain names | Does the manager want it on every answer? |
| C8 | Voice button | Not mentioned | Keep (exists today) | none |
| C9 | Chart in every answer | The user's 27 Nov "chart only when asked" (`Ask.tsx:26`, status line 42) | Meeting (chart always) | The user should confirm; the status line will be undone |
| C10 | Chip "Why was Nov 2024 so high?" | Never invent a reason | Rule: no "why" chip | none; and the Nov 2024 reading was another question (section 0) |
| C11 | "Since Aug 2022 +10.7 pts" and "22 surveys" | Data integrity | The first point is the first survey with the same wording | none |
| C12 | "Gen X highest at 72.4%" | Plain, honest wording | Tie rule (4.2) | none |
| C13 | "Since 2022" fixed | Frequency matches the data | "Since {first year}" plus cadence grains | Is a weekly view wanted for weekly questions? The notes list monthly, quarterly, yearly |
| C14 | Green up-arrow on "+10.7 pts" | Plain | Proposed neutral ink arrows | Manager to confirm |
| C15 | not covered | Market Both, the question names a country | Proposed: the named country wins | Confirm |
| C16 | not covered | Both + results in both: ask which | Two buttons, US and China | Is a third "Both, side by side" (two cards, never pooled) wanted? |
| C17 | Line only | Vertical bars to compare categories | Vertical for groups, scales, bands, periods | Long ranked lists (retailers, products) read better as horizontal bars: confirm |
| C18 | One "Export" button | Excel with chart and numbers | Excel first | Keep CSV, PowerPoint, PNG in the menu? |
| C19 | One "Copy" | Copy the full answer | One Copy (drops today's email/slide choice) | none |
| C20 | not covered | Omit base | | Does the Excel file keep a "people asked" column for analysts? |
| C21 | Chips fill the box | Dig deeper | Chips ask at once (today) | none |
| C22 | not covered | Omit base | "How many people" questions answered as a share | Confirm counts of respondents never appear |
| C23 | New question keeps the thread | New question opens a fresh chat | Meeting | none |
| C24 | not covered | Ambiguous: ask back | Today shows the best match at once and offers the others (asking first made half of questions wait, 12 Nov) | Ask back always, or only when no AI check follows? |

---

## 7. Checks to leave behind (one per calculation, as CLAUDE.md asks)

- The wording join: Q10's footwear, online, department-store and beauty wordings are four series; BT1 + B1 + Q10 (25 Nov
  2024) stay one; the 28 Sep 2026 figure stays 65.5% (264 of 403).
- The window verdict: the real 2026 beauty readings give "Steady, between 62.5% and 65.5%".
- The tie rule: 28 Sep 2026 by generation names Gen Z, Millennials and Gen X together and Boomers lowest.
- The unusual-reading rule fires on a synthetic spike and not on the fixed beauty series.
- Cadence: q3 is weekly, BT1 about quarterly; the grains offered match the 4.3 table.
- The market ask-back: a twin question with Both returns two country choices; a US-only question answers at once.
