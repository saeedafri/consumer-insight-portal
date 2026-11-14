# CIP ETL Series, Part 4: Transformation, Business Logic

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the second half of the "T" of ETL. The Coresight business rules applied on top of the clean questions and answers: demographic profiles, age bands, generations, income midpoints, census regions, question bases, the survey calendar, concepts that link a question across waves, cohorts, and Census weighting
Previous part: Part 3, Transformation (Questionnaire and Answers). Next part: Part 5, Loading and Verification

Everything in this document is taken from the project's code (folder `cip-stg`), mainly `etl/wave_loader.py`, `etl/survey_map.py`, `config/survey_map.yml`, `etl/survey_calendar.py`, `config/survey_calendar.yml`, `etl/harmonise.py`, `etl/cohorts.py`, `config/cohorts.yml`, `etl/weighting.py` and `config/weighting.yml`. Where an example shows an age or income result, it was produced by running the project's own functions.

---

## 1. Where we are in the pipeline

After Part 3, one wave's data is in the database as clean rows: questions, items, options, fields, respondents and answers. A row says "respondent 81,204 gave code 2 to D5". That is correct, but it is not yet useful for analysis. An analyst wants to ask "what share of Millennials in the South with income over $100,000 bought online?", and wants this week's number set against last week's and last year's.

This part explains the steps that make that possible. In the load sequence of one wave (Part 1, Section 9) they run right after verification:

| Order | Step | Function | Output table |
|---|---|---|---|
| 1 | Demographic profile per respondent | `rebuild_profiles` | `cip_profile`, `cip_profile_map` |
| 2 | Each question's own base | `rebuild_question_bases` | `cip_question.base_n` |
| 3 | Link questions to concepts | `harmonise_survey` | `cip_concept`, `cip_concept_option`, `cip_concept_map` |
| 4 | Cohort membership (inside the cube step) | `cohorts.derive` | `cip_respondent_cohort` |
| After the load | Survey calendar | `survey_calendar.rebuild` | `cip_wave_module` |
| When screens are built | Census weights (optional view) | `weighting.wave_weights` | used in published files |

## 2. The demographic profile

### 2.1 Why a profile table exists

Demographic answers (gender, age, income, state and so on) are ordinary answers in `cip_answer`. Filtering by them there would mean looking up eight or more answers per person for every chart. So the pipeline copies each respondent's demographics into **one row** of **`cip_profile`**. A demographic filter then becomes one fast lookup. The table's own comment: "flattened … so a filter is one indexed join rather than eight lookups".

### 2.2 Which question supplies which demographic

Question codes differ between studies and platforms, so the pipeline decides **per wave** which question feeds each demographic. The rule, in order of preference:

1. **An explicit entry for the wave's family** in `config/survey_map.yml`, if that question exists in the wave.
2. **Detection from the question wording**, for each demographic still missing. The first question whose wording matches wins.
3. **Nothing.** The demographic is left empty for that wave, and the portal hides that filter instead of failing.

**Explicit entries:**

| Demographic | US weekly tracker (CSI-US) | China tracker (CSI-CN) |
|---|---|---|
| Gender | D1 | S1 |
| Age | D2 | S2 |
| Relationship status | D3 | |
| Ethnicity | D4 | |
| Household income | D5 | S3 |
| Area (urban, suburban, rural; city tier in China) | D6 | S4 |
| Political view | D7 | |
| State | D8 | |
| Outlook on own discretionary income | CS1 | Q8 |
| Outlook on the economy | CS2 | Q9 |

**Wording detection, for every other study** (case-insensitive):

| Demographic | Wording looked for |
|---|---|
| Gender | "what is your gender" |
| Age | "what is your age" |
| Relationship | "relationship status" or "marital status" |
| Ethnicity | "ethnicity", "racial" or "race do you" |
| Income | "your total household income", "your total annual household income" or "total income" |
| Area | "area where your primary residence" or "area where you live" |
| Political | "political philosophy" or "political party" |
| State | "which state is your primary residence", "which state do you (currently) live/reside", "state is your primary residence" |
| Income outlook | "discretionary income" |
| Economy outlook | "economy overall" |

Two of these patterns were tightened after real mistakes, as the config notes. The income pattern avoids a December 2022 debt question about "…your monthly household income". The state pattern avoids "Which statement…" and "Which state did you move from?".

### 2.3 The decision is recorded

For every wave, the decision is written to **`cip_profile_map`**: one row per demographic, naming the question used and whether it came from the config (`config`) or from wording (`detected`). This makes the choice visible, auditable and correctable per wave without changing code.

### 2.4 What goes into a profile row

For each respondent, the pipeline reads the label of their answer to each mapped question (the option's label, or the item's label), then fills:

| Profile column | Rule |
|---|---|
| `gender`, `relationship`, `ethnicity`, `income_band`, `urbanicity`, `political`, `state_name`, `outlook_income`, `outlook_economy` | The answer's label, as given |
| `age_years`, `age_band`, `generation`, `age_mid` | From the age answer, Section 3 |
| `income_mid_k` | From the income label, Section 4 |
| `census_region` | From the state, Section 5 |
| `weight` | Reserved, always 1 (waves are unweighted; Section 11 explains the optional weighted view) |

Only respondents who answered at least one mapped question get a profile row. History from SurveyMonkey also takes age, gender, income and Census division from the panel provider where no question supplied them, without overwriting a respondent's own answer (Part 2).

## 3. Age: years, bands, generations and midpoints

### 3.1 The standard cuts

From `config/survey_map.yml`:

| Age band | Ages |
|---|---|
| 18-29 | 18 to 29 |
| 30-44 | 30 to 44 |
| 45-60 | 45 to 60 |
| Over 60 | 61 and over |

| Generation | Ages |
|---|---|
| GenZ | 18 to 28 |
| Millennial | 29 to 44 |
| GenX | 45 to 60 |
| Boomer | 61 and over |

Note that age bands and generations do not share every boundary: a 29-year-old is in band 18-29 but is a Millennial, not GenZ.

### 3.2 The rules, in order

The US tracker asks age in single years and exports the label ("34"). Other studies ask in ranges. One function (`classify_age`) handles every form:

1. **A range** ("26-41", "over 60", "70 or more", "under 50") has no single age. It gets a band or a generation **only if it lies wholly inside one**. "26-41" spans GenZ and Millennials, so it gets neither.
2. **"Under 18"** is below 18, not at 18. It is outside every cut. The code records why: read as 18, one under-age respondent in the 28 September wave put GenZ at 62, while Forsta's published table said 61.
3. **A named band** the analysts use that is not a plain range (China's "26-41 years old") gets its own band.
4. **A single number** gives the age, its band, its generation and its midpoint (the age itself).

**Midpoints** are used to compute average age. For the standard bands they are the analysts' own: 18-29 = 23.5, 30-44 = 37, 45-60 = 52.5, Over 60 = 67. For China's bands: 18-25 = 21.5, 26-41 = 33.5, 42-57 = 49.5, 57-76 = 66.5, 77+ = 80. A plain "a - b" range gets (a + b) / 2. An open range ("70 or more", "under 50") gets no midpoint.

### 3.3 Results from the project's own functions

| Age answer | Age | Band | Generation | Midpoint |
|---|---|---|---|---|
| "34" | 34 | 30-44 | Millennial | 34 |
| "28" | 28 | 18-29 | GenZ | 28 |
| "29" | 29 | 18-29 | Millennial | 29 |
| "60" | 60 | 45-60 | GenX | 60 |
| "61" | 61 | Over 60 | Boomer | 61 |
| "Under 18" | 17 | none | none | 17 |
| "70 or more" | none | Over 60 | Boomer | none |
| "Over 60" | none | Over 60 | Boomer | 67 |
| "18-29" | none | 18-29 | none | 23.5 |
| "26-41" (US history) | none | none | none | 33.5 |
| "26-41 years old" (China) | none | 26-41 | none | 33.5 |

## 4. Household income midpoints

Income is asked in bands. To compute an average income for a group (for example a retailer's shoppers), each band gets a midpoint, in thousands of dollars. The table is the analysts' own, from `config/survey_map.yml`:

| Income band | Midpoint ($000) |
|---|---|
| under $25,000 | 13 |
| $25,000 - $49,999 | 37.4995 |
| $50,000 - $99,999 | 74.9995 |
| $100,000 - $149,999 | 124.9995 |
| $150,000 - $199,999 | 174.9995 |
| $200,000 or greater (also "$200,000+") | 225 |

Any other closed range written as "$low - $high" gets (low + high) / 2 / 1,000, the same convention (for example "$30,000 - $39,999" gives 34.9995). This also covers SurveyMonkey's spellings without spaces. The open top band takes 225, the same $25,000 step above $200,000 that the band below uses from its bottom.

## 5. Census region

The state answer is turned into one of the four US Census regions:

| Region | States |
|---|---|
| Northeast | Connecticut, Maine, Massachusetts, New Hampshire, Rhode Island, Vermont, New Jersey, New York, Pennsylvania |
| Midwest | Illinois, Indiana, Michigan, Ohio, Wisconsin, Iowa, Kansas, Minnesota, Missouri, Nebraska, North Dakota, South Dakota |
| South | Delaware, Florida, Georgia, Maryland, North Carolina, South Carolina, Virginia, West Virginia, District of Columbia, Alabama, Kentucky, Mississippi, Tennessee, Arkansas, Louisiana, Oklahoma, Texas |
| West | Arizona, Colorado, Idaho, Montana, Nevada, New Mexico, Utah, Wyoming, Alaska, California, Hawaii, Oregon, Washington |

The lookup accepts both two-letter codes and full names, in any case ("CT" and "connecticut" both give Northeast). The code explains why: the 21 September export gave codes, another wave or country may give names, and accepting only one would leave the region filter silently empty. A value that is not a listed state (for example "PR") gets no region. For SurveyMonkey history, the panel's Census division is mapped to its region (New England and Middle Atlantic are Northeast, and so on).

## 6. Question bases: who was actually asked

### 6.1 The rule

For every question in the wave, the pipeline counts its **base**: the number of **qualified** respondents with at least one stored answer to it (a code, a label, a number or a text). The count is saved on the question (`cip_question.base_n`).

Because Part 3 stores no row when a question was not shown, and stores a 0 when a list item was shown but not ticked, this count is exactly "qualified people who were asked this question".

### 6.2 Why it matters

The survey routes heavily. The schema's comment gives real numbers from one wave: department-store question DP2 was asked of 222 of 404 qualified respondents (department-store buyers only), BNPL question BN2 of 133 (BNPL users only), GLP-1 question GP8 of 71 (GLP-1 users only). Dividing any of them by the full wave of 404 would understate the result two to six times. So the base travels **with each question**, and every percentage the portal shows is "of those asked".

The cube (Part 6) applies the same idea per answer: a single-choice question or a grid row is based on who answered that question or row; a multi-select item is based on everyone who answered the question at all ("Total Answering"), so an item a person saw and did not tick counts as not chosen.

## 7. The survey calendar: what each survey was about

The register knows every Forsta survey, but not what each one covered. The calendar (`cip_wave_module`) gives every survey one row per **module**, rebuilt after every discovery and every load. It drives sector tables, seasonal comparisons and the launch schedule.

### 7.1 Reading the weekly tracker's title

Tracker titles follow one grammar: `Shopping and Spending - inc <part> + <part> + …`. Each part after "inc" is matched against `config/survey_calendar.yml`:

| Kind | How it is found | Codes |
|---|---|---|
| **Sector** | A part matches a sector's pattern. The **first** part is the **lead sector** | Drugstore, eCommerce, Luxury, Department stores, Beauty, Home furnishings, Home improvement, Social commerce, Off-price/dollar, Apparel, Mass/warehouse, Footwear |
| **Topic** | A part matches a recurring add-on | Tariffs + inflation, GLP-1, GenAI, Financial health, MidEast gas price shock |
| **Seasonal** | A part matches "holiday track…", **or** the loaded wave asks "current status of your holiday shopping" | Holiday tracker |
| **Event** | Any other part | Its own code, for example Prime Day, Labor Day |

The seasonal rule uses the wave's own questions once loaded, because titles can miss it: the code notes that the 28 September 2026 wave's title says only "Holiday", yet it carries the holiday tracker.

### 7.2 Other surveys

A survey that is not a tracker is matched against the annual studies (Holiday shopping, Amazon apparel, Online grocery, Back-to-school). Anything else is an ad hoc study, named from its title without the year.

### 7.3 Seasons and wave numbers

A season runs **July to June**: September 2026 and January 2027 are both season 2026. Seasonal and annual surveys are numbered within their season in launch order. That is what lets the portal compare "holiday tracker wave 2 this year" with "wave 2 last year".

### 7.4 The 12-week rotation

The 12 sectors rotate in a fixed order, so each lead sector returns every 12 weeks (the project measured gaps of 12 weeks, plus or minus one around holidays). The calendar can therefore list the next 12 expected lead sectors.

## 8. Harmonisation: one question across many waves

### 8.1 The problem

Trends and "this week versus last year" need the **same question** in different waves. Matching on question code alone is wrong:

- **Codes get reused for different questions.** The code records that Q13 asked about footwear one week and Cyber Monday the next, and that DS1 to DS3 ask about drugstores in drugstore weeks and dollar stores in off-price weeks.
- **The same question gets different codes**, especially across platforms (SurveyMonkey, Qualtrics, Forsta).
- **Wording drifts slightly**: a different apostrophe, an extra "Select all that apply", a non-breaking space.

So CIP links each question to a **concept**: one stable identity for "the same question", with its own list of **concept options** ("the same answer"). This is `etl/harmonise.py`.

### 8.2 Normalising wording before comparing

Two wordings are compared only after this cleaning:

1. Non-breaking spaces become spaces; a stray "Â" (an encoding artefact) is removed; curly quotes become straight quotes.
2. Every run of whitespace becomes one space; everything is lower-cased.
3. A trailing instruction after the question's punctuation is removed: "? Select all that apply", ". Please select one", "(Select up to …)". The removal stops at " - ", so a suffix like "- Other (please specify)" survives. Wording that merely **starts** with "Please select your age" is kept as it is.
4. Leading and trailing spaces and the punctuation ". ? : ;" are trimmed.

Examples:

| Original | Normalised |
|---|---|
| "Which of these have you done? Select all that apply" | "which of these have you done" |
| "Which of these have you done?  (Select all that apply.)" | "which of these have you done" |
| "What is your age? Please select one - Other (please specify)" | "what is your age - other (please specify)" |
| "Please select your age" | "please select your age" |

### 8.3 What gets a concept: units

Only questions that are neither technical nor virtual are harmonised. Each is broken into **units**:

| Question type | Unit | Its answers |
|---|---|---|
| Grid | **Each row** is its own unit; its wording is "question :: row". Rows of one grid share a concept group | The grid's options |
| Multi-select | The whole question | Its items |
| Single, numeric, text | The whole question | Its options |

### 8.4 The decision for each unit

Each unit is compared only with concepts of the **same question type**, and not with a concept this wave already uses for another question (one wave, one question per concept, or its answers would count twice).

| Result | Condition | Status | Effect |
|---|---|---|---|
| **exact** | Same normalised wording, and every answer it offers is already a concept option | `confirmed` | Linked at once; trends immediately |
| **changed** | Same normalised wording, but it offers answers the concept lacks | `proposed` | Waits for review. Evidence lists the added answers |
| **similar** | No exact wording match, but wording is at least **85 %** similar | `proposed` | Waits for review. Evidence: "x % similar wording to <concept>" |
| **new** | Nothing close | `confirmed` | A new concept is created |

**Why 85 %.** The code records that the highest similarity score between two unrelated questions in the 21 September and 28 September waves was 0.796. The threshold sits above that.

**Tie-breaks.** If several concepts share the exact wording, the one that already has every answer wins; otherwise the one this wave adds the fewest answers to; on a further tie, the newest concept, because it is the latest decision (for example an analyst's "keep separate").

**Two passes.** Every unit is decided first against the concepts that existed before this wave; then the new concepts, options and links are written in batches. Otherwise a concept created for one question in the wave could wrongly capture its sibling.

### 8.5 What is written

- **New concepts** (`cip_concept`): a code made from the question code plus a short fingerprint of its type and wording (for example `BT1_A88981`), its name (the wording), its group (for grid rows), its topic, its type and its normalised wording.
- **Concept options** (`cip_concept_option`): every answer of an exact or new unit becomes an option of the concept if it is not one already, matched on normalised label, with a short code made from the label.
- **Links** (`cip_concept_map`): one row for the unit itself (status, method `exact_text` or `similar_text`, confidence, evidence), and, **only for confirmed units**, one row per answer linking it to its concept option.

A proposal writes only its unit-level link. Its answers are linked only when someone confirms it. The code's principle: nothing trends before someone has looked.

**The wording a concept was first confirmed on is the reference.** Later waves are matched against that earliest confirmed wording.

**Safe to re-run.** A unit that already has a link (confirmed, proposed or rejected) is left alone, so reloading a wave never overrides a decision.

### 8.6 Reviewing proposals

- **Confirm** (`harmonise.confirm`, which the code's comments call the Mappings page): accept the proposed concept, or choose another. It refuses if that concept is already used by another question in the same wave. A conditional update guarantees that two people deciding at the same moment cannot both settle the same unit.
- **Automatic confirmation of the safe part** (`python -m etl.harmonise --confirm-same-wording --apply`): proposals with exactly the concept's wording that only add answers are confirmed without a person, unless the wave already uses that concept. Proposals made on similar wording always stay for a person.
- **After any decision,** cohort memberships for that wave are re-derived, the cube cells of any cohort that changed are rebuilt, and the wave's serving rows, plus those of waves that compare with it, are rebuilt. Most decisions touch no cohort, and then nothing else is rebuilt.

### 8.7 Scale

From the live database's data dictionary: about 1,769 concepts, 11,670 concept options and 66,766 links.

### 8.8 How concepts are used

When the serving step (Part 6) looks for "the same answer" in last week's or last year's wave, it uses the concept option when both waves have one. If not, it falls back to the same question code and the same answer label, but only if the two questions have the same normalised wording. A matching code with different wording is flagged "wording changed" and not compared. A reused code therefore starts a new series instead of joining two different questions.

## 9. Cohorts: named respondent groups

### 9.1 What a cohort is

A cohort is an analyst's rule for a group of respondents, stored once and applied to every wave: for example "Beauty shoppers". Rules are written over **concepts**, not question codes, so a cohort means the same thing in a 2023 Qualtrics wave and a 2026 Forsta wave.

### 9.2 The rule language

A rule combines conditions with "all" (and), "any" (or) and "not". Each condition is one of:

| Condition | Meaning |
|---|---|
| `option` | The respondent gave that answer (single, grid) or ticked that item (multi) |
| `answered` | The respondent answered any question linked to the concept |
| `asked` | The respondent's **wave** has (or has not) the question |

Only confirmed links count. The rule is checked when defined (a rule naming a concept or option that does not exist is refused), then turned into one database condition, so a wave's members are found in one statement inside MySQL. Only **qualified** respondents can be members.

### 9.3 The cohort in use today

From `config/cohorts.yml`:

**BEAUTY_SHOPPER, "Beauty shoppers":** everyone in a wave that asked the beauty purchase question (concept `BT1_A88981`, "Have you purchased any beauty products … in the past three months?") who did **not** answer "No". Respondents the survey routed past the question count as shoppers. Waves that never asked are not counted.

The config notes that this is the analysts' rule, proven against their "Beauty Shopper Profiles" workbook respondent by respondent: it reproduces 1,200 shoppers, age bands 255 / 353 / 330 / 262, average age 44.94375 and average income 93.1132 exactly.

### 9.4 Versions

Editing a rule creates a new version. The old version stops being read, and its members and cube cells are deleted so nothing can read it by mistake. Cohorts are applied to every wave with `python -m etl.cohorts --sync`, and re-derived for each new wave during its load (inside the cube step). Each cohort then gets its own pre-counted cells in the cube (Part 6).

## 10. Topics, recap

Every question is placed in an editorial topic from its code and wording (Part 3, Section 5). The topic is a business grouping for browsing (Shopping and Spending, Department Stores, BNPL, GLP-1 Impact, Consumer Sentiment, Demographics, Holiday Shopping Tracker and so on). An unknown module gets its own topic automatically, and an unmatched question goes to "Unclassified" without blocking the load.

## 11. Census weighting, an optional view

### 11.1 Default: unweighted

Every portal percentage is **unweighted** by default: each qualified respondent counts once. This matches Forsta and the data team's Excel files.

### 11.2 The weighted view

The portal can also show Census-weighted figures (`etl/weighting.py`). Each qualified respondent of a wave gets a weight so that the wave matches US adult shares on three margins at once:

| Margin | Target shares (%) |
|---|---|
| Gender | Male 49.0, Female 51.0 |
| Age band | 18-29: 20.5, 30-44: 25.5, 45-60: 25.0, Over 60: 29.0 |
| Census region | Northeast 17.3, Midwest 20.6, South 38.4, West 23.7 |

Source in the config: US Census Bureau, American Community Survey 2023 1-year estimates, adults 18+ (table S0101 for sex and age; regions summed from states). The config asks that these be checked against the latest ACS release before weighted figures are quoted to clients.

**How the weights are made (raking).** Start with every weight at 1. Adjust the weights so the gender shares match; then age; then region; repeat until nothing moves. A respondent with no value on a margin (or a value not listed, such as a non-binary gender) is left out of that margin only. A margin uses only the groups that have someone in this wave, rescaled to 100 %. Then weights are **trimmed** so no one counts more than 5 times or less than 0.2 times the average, and rescaled so they average 1, repeated until every weight is inside those bounds. Trimming comes last, so a hard-to-reach group may stay a little short of its share. The weighted base of a wave equals its respondent count.

**Significance flags are always tested on unweighted counts.**

## 12. All business rules on one page

| Rule | Value | Where it lives |
|---|---|---|
| Base of every percentage | Qualified respondents (status 3) who were asked the question | `wave_loader.rebuild_question_bases` |
| Age bands | 18-29, 30-44, 45-60, Over 60 | `config/survey_map.yml` |
| Generations | GenZ 18-28, Millennial 29-44, GenX 45-60, Boomer 61+ | `config/survey_map.yml` |
| Under 18 | Outside every cut | `survey_map.classify_age` |
| Age midpoints | 23.5, 37, 52.5, 67 (China 21.5, 33.5, 49.5, 66.5, 80) | `config/survey_map.yml` |
| Income midpoints ($000) | 13, 37.4995, 74.9995, 124.9995, 174.9995, 225 | `config/survey_map.yml` |
| Region | US Census regions from state code or name | `config/survey_map.yml` |
| Demographic source per wave | Config for the family, else wording, else none; recorded in `cip_profile_map` | `survey_map.resolve_profile_map` |
| Same question across waves | Concept: exact wording confirmed; added answers or 85 % similar proposed | `etl/harmonise.py` |
| Season | July to June | `config/survey_calendar.yml` |
| Lead sector | First part after "inc" in the tracker title; 12-week rotation | `config/survey_calendar.yml` |
| Beauty shoppers | Asked BT1 and did not answer "No" | `config/cohorts.yml` |
| Weighting | Off by default; raked to ACS 2023 on gender, age band, region; trimmed 0.2 to 5 | `config/weighting.yml` |

Most of these rules live in YAML configuration files, not in code. A change to a band, a midpoint, a topic pattern or a cohort is a config edit.

## 13. Summary

Business logic turns clean answers into analysis-ready data. Each respondent gets one demographic profile, built from whichever questions supply gender, age, income, state and the rest in that wave, with the choice recorded. Age becomes a band, a generation and a midpoint under clear rules (Under 18 is outside every cut; a range gets a band only if it fits inside one). Income bands get the analysts' midpoints, states become Census regions. Every question carries its own base, so a percentage is always "of those asked", which matters because many questions go only to subgroups. The survey calendar reads each tracker title into its lead sector, topics, seasonal trackers and events. Harmonisation links each question to a concept so trends survive code reuse, wording drift and platform changes: exact matches link at once, anything uncertain waits for a person. Cohorts such as Beauty Shoppers are written once over concepts and applied to every wave. Census weighting is available as an alternative view, never the default.

**Part 5** explains how all of this is loaded and proven: the write order, the single transaction, the bulk upload, the verification rules, what happens on failure and reload, the second check against Forsta, and the integrity checks that keep the database whole.
