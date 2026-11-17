# How a Forsta Survey Becomes a Number on the CIP Platform: A Plain-English Guide

**Consumer Intelligence Platform (CIP), Coresight Research**
For: analysts, research managers, the business team and anyone who reads CIP numbers but does not work on the system
Companion to: the six-part CIP ETL series in this folder (Parts 1 to 6) and its videos. Each section below names the part that covers the same ground in technical detail.
Checked against the system as it runs on 15 November 2026.

---

## How to read this guide

This guide follows one survey wave from the moment fieldwork ends in Forsta to the moment its numbers appear on a CIP screen, in a report or in the team's email. It uses the words the research team already uses (wave, fieldwork, completes, base, quota, cross-tab, verbatims) and explains every other word the first time it appears. Every example is a real CIP survey, question or date.

The guide has eleven sections:

1. The words used in this guide
2. The whole journey on one page
3. Why the process is built this way
4. The weekly rhythm: when things happen
5. Stage 1: collecting the data from Forsta
6. Stage 2: turning the questionnaire into a clean list of questions
7. Stage 3: turning each interview into clean answers
8. Stage 4: applying Coresight's research rules
9. Stage 5: saving the wave and proving it is right
10. Stage 6: preparing every result in advance, and delivering it
11. Questions people often ask

---

## 1. The words used in this guide

| Word | What it means in CIP |
|---|---|
| **Forsta** | Forsta Surveys, the platform (formerly called Decipher) on which Coresight builds and fields its surveys. CIP only ever reads from Forsta; it never changes anything there. |
| **CIP data pipeline** | The automatic process that takes survey data out of Forsta, cleans it, applies Coresight's rules, checks it and puts it on the portal. The industry name for this kind of process is **ETL**: **E**xtract (collect the data), **T**ransform (clean it and apply the rules), **L**oad (save it). The six-part series is named after these three steps. |
| **Survey** | One questionnaire in Forsta. Each has its own Forsta address, for example `selfserve/58f/260907`. |
| **Wave** | One fielding of a study. The US weekly tracker fields a new Forsta survey every week, so each week is one wave. |
| **Wave date** | The Monday of the week in which the first qualified respondent completed the survey. The wave whose first complete came on Tuesday 29 September 2026 is the wave of 28 September 2026. This is how the data team always named weekly waves in their Excel files. |
| **Tracker, annual study, ad hoc study** | The three kinds of study CIP knows. The **tracker** is the weekly US Consumer Sentiment and Shopping survey ("Shopping and Spending - inc …"); the China Consumer Survey is a weekly tracker too. An **annual** study is a yearly study such as Holiday Shopping, Online Grocery, Back-to-School or Apparel. An **ad hoc** study is a one-off or client study. |
| **Study family** | The waves of one study that are trended together. All US weekly tracker waves form the family `CSI-US`; the China tracker is `CSI-CN`; all years of the Holiday Shopping study form `HOLIDAY_SHOPPING`, even though the study's title changed from year to year. |
| **Respondent status** | How an interview ended, as Forsta records it: **qualified** (a complete that counts), **terminated** (screened out), **over quota** (their quota group was already full) or **partial** (dropped out before the end). |
| **Qualified complete** | A respondent with the qualified status. Every percentage on the portal is based on qualified completes only. |
| **Quota cell** | A target number of completes for one group, for example "Midwest: 85". Forsta groups cells into quota sheets (Gender, Region and so on). |
| **Questionnaire map** | Forsta's description of the questionnaire: every question's code (such as D5), wording, type, rows and answer codes with their labels. Forsta calls it the **datamap**. |
| **Base** | The number of qualified respondents who were asked a question and answered it. Every CIP percentage is "of those asked", not "of everyone in the wave". |
| **Routing** | The survey logic that shows a question only to some people (for example, department-store questions only to department-store buyers). Also called skip logic. |
| **Cut** | A demographic breakdown of a result: by gender, age band, generation, household income, Census region or area (urban, suburban, rural). |
| **Concept** | CIP's record that two questions in different waves are the same question, even if their code or exact wording changed. Concepts make trends possible. |
| **Cohort** | A named group of respondents defined by an analyst's rule and applied to every wave, for example "Beauty shoppers". |
| **Verified** | The status a wave receives only after CIP has proven that everything Forsta sent was saved. Only verified waves appear on the portal. |
| **Published files** | The ready-made results for every standard screen, prepared in advance so a screen opens without waiting. |
| **Failure list** | The private internal email list that receives problem reports. Problem emails never go to the wider team list. |

---

## 2. The whole journey on one page

Take the US weekly tracker wave of 28 September 2026 as the example. Here is everything that happens to it, in order:

1. **Fieldwork runs in Forsta.** The wave launches on Monday at about 18:00 India time (IST). Respondents from the panel take the survey overnight, US time.
2. **CIP watches.** From 17:30 IST on Monday, CIP checks Forsta every 30 minutes.
3. **Fieldwork is effectively over.** As soon as 400 people have qualified, or every quota cell is full, or 9 hours have passed since launch (about 03:00 IST on Tuesday), CIP treats the fieldwork as over, even if Forsta still shows the survey as live.
4. **Collect.** CIP downloads the questionnaire map and the record of every person who started the survey: qualified completes, screen-outs, over-quotas and drop-outs.
5. **Clean the questionnaire.** Every question is given a clear type (single choice, multi-select, grid and so on), a topic (Shopping and Spending, Beauty, Tariffs and so on) and a tidy wording. Personal data is removed.
6. **Clean the answers.** Every interview becomes one respondent record and a set of answers. A question the person was never shown leaves no answer at all; an item they saw but did not tick is kept as "not chosen".
7. **Apply Coresight's rules.** Each respondent gets an age band, a generation, an income band midpoint and a Census region. Each question gets its true base. Each question is linked to the same question in earlier waves.
8. **Save and prove.** The wave is saved while hidden from everyone. CIP then proves that every respondent, every question and every answer Forsta sent was saved. Only then does the wave become visible.
9. **Prepare every result in advance.** Every answer is counted for every demographic cut; percentages are worked out; last week's and last year's figures are attached; significant changes are marked.
10. **Check again.** CIP downloads the wave from Forsta a second time and compares every saved answer with Forsta's, one by one.
11. **Publish.** The ready-made results for every screen are written as a complete new version, checked, and switched on in one step.
12. **Tell people.** The team receives one email (and a Teams post) with who answered, the three biggest significant changes and the usual workbooks: Cross Tabs, Holiday Inflation Cross Tabs when that week's questionnaire can fill them, Raw Data and the Weekly Line-By-Line file.
13. **Final reload.** When Forsta formally closes the wave (often a day or two later), CIP loads it once more. This reload is the final version and replaces the early one. The team receives a second email.

The rest of this guide explains each of these steps.

---

## 3. Why the process is built this way

Four business reasons shaped every part of the system (Part 1, section 2).

**Reason 1: no manual work, no manual errors.** Before CIP, the data team downloaded each week's results from Forsta as Excel files, cleaned them by hand and pasted them into master workbooks, including the Weekly Line-By-Line file. CIP rebuilds the same output automatically. When CIP's rebuilt line-by-line rows were compared with the team's hand-made file week by week, the comparison found errors in the hand-made file. Automation removes that kind of error.

**Reason 2: Forsta does not keep data forever.** Forsta puts a survey to sleep ("hibernates" it) after 90 days with no new respondents and no one opening it. A hibernated survey cannot be read until someone wakes it in the Forsta portal. A hibernated survey can then be archived, and an archived survey is erased 12 months later. After that, Coresight's own database is the only copy. This is why CIP loads every wave as soon as its fieldwork ends, keeps every respondent (not only completes), and also keeps Forsta's own fieldwork record for each survey.

**Reason 3: speed for the reader.** All counting and percentage work is done once per wave, when the wave arrives, not each time someone opens a screen. When an analyst opens the portal, the numbers are already prepared and are simply sent to the screen.

**Reason 4: trust.** A wave appears on the portal only after CIP has proven that every respondent, every question and every answer Forsta sent was saved. Then, in the same run, every saved answer is compared with Forsta a second time. If anything does not match, the failure list is told at once.

---

## 4. The weekly rhythm: when things happen

All times below are India time (IST). The system itself keeps its clock in UTC, which is 5 hours 30 minutes behind IST (Part 1, section 7).

### Launch Monday

| Time (IST) | What happens |
|---|---|
| Monday 17:30 | CIP starts its **launch watch**. If the data team's launch plan has a launch today, CIP posts a Teams message naming the sector and topics launching and saying that CIP will check every 30 minutes. |
| About 18:00 | The wave launches in Forsta. CIP sees it as "live, still fielding" and waits. While it is live, CIP also reads its quota cells, so the portal's Launch Schedule page can show how full each cell is. |
| Every 30 minutes | CIP checks Forsta again. |
| When fieldwork is effectively over | CIP loads the wave (section 5.3 explains the rule). The portal marks it **"in field"**, because it is not the final version yet. |
| When Forsta closes the wave | Forsta's close date appears. CIP notices it at the next check and reloads the wave. This reload is final. |
| Wednesday 23:30 at the latest | The watch ends once the week's wave is both loaded and closed, or after 54 hours. If 54 hours pass first, CIP posts a Teams warning, and the regular checks keep looking. |

A real example from the system's records: wave 261002 was loaded early on the night of 26 October 2026 with 401 qualified completes, while still live in Forsta, and was reloaded as final when Forsta closed it on 2 November with 404.

### Every day

| When | What happens |
|---|---|
| Every 30 minutes, day and night | One check of Forsta. Anything that has closed is loaded within 30 minutes. This check is also the safety net: if a system update interrupts the Monday watch, a closed wave still loads within 30 minutes. |
| 09:00, Tuesday to Sunday | A daily run that does the same as the 30-minute check, as a second chance. |
| Every hour | A watchdog checks that the last run finished. If a run stopped without finishing, or if no check has been heard from for too long, the failure list is emailed. |
| Every 10 minutes | Once Coresight IT has given CIP access to the China survey's SharePoint folder, CIP looks there for new China weeks. |

### Friday

Once every Friday, the first check that finds nothing new also runs the **full health check** of the whole database and re-checks every number Coresight has already published (section 9.6 and 9.7). On other quiet runs these checks are skipped, because nothing has changed.

### Annual and ad hoc studies

Annual and ad hoc studies field for days (Holiday 2025 fielded for 8 days). They are never loaded while still in field: Coresight's rule is that a study is never published half-fielded. They load within 30 minutes of Forsta closing them.

---

## 5. Stage 1: collecting the data from Forsta

This stage is the "E" (Extract) of ETL. It is covered in detail in Part 2.

### 5.1 CIP only reads

Every request CIP sends to Forsta asks for information; none can change anything. Forsta also offers actions that do change surveys (launching, closing, editing data, sharing links). CIP's own rules allow only three exceptions, all of which make Forsta calculate something without changing the survey: running a cross-tab, running a report the team saved, and exporting that saved report as Excel, PDF or PowerPoint. CIP uses these only to keep Forsta's fieldwork record (section 5.6). After using them, CIP reads the survey's "last edited" time again to prove nothing changed. This was checked live on survey 261003 on 7 November 2026: the survey's last-edit time and its audit history did not change.

If Forsta is busy or briefly unavailable, CIP waits a few seconds and asks again (up to 4 tries in total, waiting 2, then 4, then 8 seconds). If Forsta refuses CIP's access key, the run stops straight away and the failure list is emailed, instead of failing every survey one by one.

### 5.2 The list of every survey, and a status for each

Each run starts by asking Forsta for its full list of surveys. CIP keeps its own register of every survey it has ever seen, and gives each one a status:

| Status | Meaning | What CIP does |
|---|---|---|
| **Waiting** (Forsta testing, or live and still fielding) | Fieldwork is still running | Waits |
| **Ready to load** | Forsta has closed it, or (weekly tracker only) its fieldwork is effectively over, and it is not loaded yet | Loads it in this run |
| **Loaded** | Already on the portal | Nothing, unless Forsta reopens or closes it again |
| **Asleep** (hibernated) | Forsta has hibernated it before CIP could load it | Cannot read it. Someone must wake it in the Forsta portal; the next run then loads it |
| **Failed** | The last attempt did not succeed | Tries again (section 9.5) |

CIP also notices when a survey is **reopened**. If Forsta's close date changes, or the total number of respondents changes, the survey counts as reopened and is loaded again. Two examples:

- A weekly wave was loaded early on Tuesday morning while still live. On Wednesday Forsta closes it, so its close date appears. CIP sees the change and reloads it. That reload is the final version.
- An annual study was loaded last month. Someone reopened it in Forsta and collected 50 more respondents. While it is collecting, the portal keeps last month's version. When Forsta closes it again, CIP sees the new close date and reloads it with the extra respondents.

Every closed, readable survey is loaded, however few people answered it.

### 5.3 When is weekly fieldwork "effectively over"?

Forsta often keeps a weekly wave open after enough people have answered. Waiting for Forsta to close it would delay the data. So, for weekly tracker waves only, CIP decides for itself that fieldwork is over as soon as **any one** of these is true:

| Test | Rule | Why |
|---|---|---|
| Time | 9 hours since launch | The data team's window: launch about 18:00 IST, fieldwork over by about 03:00 IST |
| Completes | 400 or more qualified completes | The plan's target for each weekly wave (the Forsta weekly waves on record finished with 400 to 414) |
| All quota cells full | Every quota cell has reached its target | No group needs more people |
| One quota sheet full | Qualified completes have reached the total target of one whole quota sheet | One complete quota dimension is satisfied |

The 400 rule exists because of a real case: on 19 October 2026, Forsta stopped a wave at 400 completes with the Midwest cell at 80 of its 85. Not every cell was full, but fieldwork was clearly over, and the 400 rule loaded the wave on time.

Loading early changes nothing in Forsta; the survey stays open there. The portal marks the wave "in field" until Forsta closes it and CIP loads the final version.

### 5.4 What is collected for each wave

For each wave, CIP downloads two things:

1. **The questionnaire map**: every question's code (for example D5), its wording ("What was your total household income last year?"), its type, its rows, and its answer codes with their labels (1 = "under $25,000", 2 = "$25,000 - $49,999" and so on).
2. **Every respondent record**: one record per person who started the survey, with a value for each question they saw. Values arrive as codes, not labels: "D5 = 2" rather than "$25,000 - $49,999".

**Every respondent is collected, not only the completes.** Screen-outs, over-quotas and drop-outs are the record of how fieldwork went, and Forsta will erase archived surveys one day. Asking Forsta for qualified completes only would make the download smaller (for survey 261003, 2.0 MB instead of 5.1 MB), but no one waits on this download, so completeness wins. The portal's percentages still use qualified completes only.

CIP checks the download as it arrives. If it is cut off halfway or damaged in any way, the wave fails for this run with a clear message, and the next run downloads it again from the beginning. CIP never tries to continue a half-received download, because that could count some respondents twice.

### 5.5 Which wave is this, and which study does it belong to?

Before anything is saved, CIP decides where the wave belongs:

- **The wave date** is the Monday of the week in which the first qualified respondent completed it (section 1). If a wave is reloaded later, it keeps the date and the identity it was given the first time, so a reload never creates a second copy of the same wave.
- **The study family** is `CSI-US` for every US weekly tracker wave. For annual studies, a list kept by the team ties together the years of the same study even when the title changed ("Holiday 2021 Shopping and Spending", "Holiday Shopping and Spending 2025", "Holiday Shopping 2026" are all `HOLIDAY_SHOPPING`). Without that list, each renamed year would become a study of its own and lose its year-on-year comparison. A study not on the list takes its title without the year.

### 5.6 Forsta's own fieldwork record

Respondent answers are only part of what Forsta knows. Forsta also holds the respondent funnel, drop-outs by page, quota progress, screen-out rules, warnings, the team's saved cross-tab reports, the questionnaire's programming file, and Forsta's schedule for archiving and erasing each survey. All of that disappears when Forsta erases a survey, so CIP keeps a copy of it for the surveys it has loaded. CIP also asks Forsta to run its own cross-tab of every question and compares it with CIP's figures. These records feed the portal's Fieldwork and Forsta admin screens and each wave's question-logic preview. CIP never wakes a hibernated survey to read this record, because waking it changes Forsta and is a paid action.

### 5.7 The China Consumer Survey

The China survey is fielded on Baidu QSS, which cannot be reached from outside China. Each week an analyst downloads two files from Baidu and places them in a SharePoint folder (year, then month, then one folder per survey week, for example "2026 / October / Survey of Oct 26"):

- the **raw export**, one row per respondent, in Chinese;
- the **topline**, Baidu's own summary of each question's answer counts and base.

The same two files can also be uploaded by hand on the portal's Upload Survey page.

Before saving anything, CIP checks the files strictly:

- every Chinese question and answer wording is translated using the analysts' own English codebook; a wording the codebook does not know stops the load and is named, so nothing untranslated reaches the screens;
- every count CIP calculates from the raw rows (each question's base and each answer's count) must equal Baidu's topline exactly; a single count off stops the load.

The analysts name a China survey after the week before the one in which it was answered ("Survey of Oct 26" was fielded on 3 November). CIP uses the folder name as the wave date, and logs a warning if the folder name is more than 21 days away from when the answers were actually given. A corrected file placed in the same folder is picked up automatically.

### 5.8 History: Qualtrics and SurveyMonkey

Before Forsta, Coresight fielded on SurveyMonkey (2018 to July 2022) and Qualtrics (August 2022 to May 2025). Those years were copied into CIP once, from Coresight's old data warehouse, plus one Qualtrics Excel export for the May 2025 wave that the warehouse did not hold. The weekly process never reads the old warehouse again. On 15 November 2026 the database held 523 verified waves: 374 US and other studies going back to 18 January 2018 (87 from Forsta, 142 from Qualtrics, 145 from SurveyMonkey) and 149 China weeks.

---

## 6. Stage 2: turning the questionnaire into a clean list of questions

This is the first half of the "T" (Transform) of ETL. It is covered in detail in Part 3.

### 6.1 Why a clean list of questions is needed

Raw answers mean nothing on their own. "D5 = 2" only becomes "$25,000 - $49,999" if CIP knows the questionnaire. So CIP first turns Forsta's questionnaire map into its own clean list of every question, every list row and every answer option, and only then reads the answers.

Forsta's data file has one row per respondent and one column per question variable; the weekly wave of 21 September 2026 had 375 columns, and the columns change every week as modules rotate in and out. CIP instead saves one entry per answer, so a new module in next week's questionnaire simply adds new entries and never requires any change to the database.

### 6.2 Tidying every wording

Every wording and label is tidied the same way: special characters that Forsta writes in coded form (such as "&amp;" for "&") are turned back into normal characters, and stray spaces, line breaks and invisible "non-breaking" spaces are turned into ordinary single spaces. This matters: Forsta's questionnaire map wrote some answer labels with invisible spaces ("Spent a lot less…") while the data file used ordinary spaces. Before this tidying, the two did not match and the answer was saved without its code.

### 6.3 Personal data is removed first

Six items Forsta collects about each respondent are never kept: the browser description, the survey link they used, their session number, a device fingerprint, their IP address, and the panel's ID for them. The panel ID is replaced by a scrambled code that cannot be turned back into the ID (section 7.2).

### 6.4 Question types

CIP gives every question one clear type from the questionnaire map:

| Type | What it is | CIP example |
|---|---|---|
| **Single choice** | One answer from a list | D5 "What was your total household income last year?" |
| **Multi-select** | Tick all that apply; each row is a separate yes/no | q1 "Which, if any, of these have you done?" with rows such as "Met up with friends" |
| **Grid** | Several rows, each answered on the same scale | A grid of statements, each rated on the same answer list |
| **Bipolar grid** | Each row asks the person to choose between two statements | HX6 "Please choose the statement from each row": "I start holiday shopping early" versus "I leave holiday shopping late" |
| **Numeric** | A number | Total interview time |
| **Open-ended** | Typed words | q9 "Anything else?" |
| **Date** | A date | A date the respondent entered |

**Bipolar grids** need special care. In the questionnaire map their answer codes 1 and 2 have blank labels, so the answers would show as meaningless numbers. CIP labels them "Left statement" and "Right statement" and stores, for each row, which statement is on the left and which on the right, so a chart can show what 1 and 2 mean on every row. It takes the right-hand statements from a second, "normalized" copy of the grid that Forsta creates automatically.

### 6.5 "Other, please specify"

Many questions have a box where the respondent types an "Other" answer. CIP turns each such box into a separate open-ended question, worded as the parent question followed by "Other (please specify)". The tick for "Other" stays in the original question, where it is counted with the other answers; the typed words go to the new open-ended question, where they can be coded into themes (section 10.6). An "Other" box is therefore never mistaken for a point on a scale.

### 6.6 Questions kept but never reported

Some questions in the questionnaire map are not real survey questions: the interview length, Forsta's routing conditions, the respondent's operating system or browser, which panel they came from, and Forsta's own derived copies of questions. CIP keeps them, because they are part of the fieldwork record, but leaves them out of every chart, table, trend and topic list.

### 6.7 Topics

Every question is placed in an editorial topic so people can browse the portal by subject. For the US weekly tracker, the question code decides the topic:

| Question codes | Topic |
|---|---|
| q1 to q6 | Shopping and Spending |
| DP… | Department Stores |
| DJ… | Diamonds and Fine Jewelry |
| BN… | Buy Now, Pay Later |
| D28 to D35 | AI and GenAI Shopping |
| GP… | GLP-1 Impact |
| CS… | Consumer Sentiment |
| D12 to D15 | Macro and Gas Prices |
| D1 to D8 | Demographics |
| XM… | Holiday Shopping Tracker |
| HX… | Holiday Spending Outlook |
| BT… | Beauty |
| TF… | Tariffs |
| IN… | Inflation and Prices |

For the China tracker, S1 to S5 are Demographics, Q1 to Q6 Shopping and Spending, and Q7 to Q9 Consumer Sentiment. In any other survey, a question whose wording mentions gender, age, income, state, region and similar words goes to Demographics. A question no rule recognises goes to "Unclassified" and still loads. These rules are kept in a settings file the team can edit, so a new module in a future wave is a settings change, not a programming job.

### 6.8 Reloads never create duplicates

When a wave is reloaded, every question, row and answer option is matched to the one already saved by its Forsta code and updated in place. A list row that the corrected questionnaire no longer has, and that nobody chose, is removed. This rule came from a real case: a corrected question 7 list in survey 97 had left a second, empty "YouTube" row next to the real one.

---

## 7. Stage 3: turning each interview into clean answers

This is still the "T" of ETL. It is covered in Part 3, sections 7 to 10.

### 7.1 One respondent record per interview

Every interview becomes one respondent record holding: Forsta's record number and unique interview ID, the status (qualified, terminated, over quota or partial), the completion time, the interview length, the quota cells the person counted in, their device, operating system and browser, the question where a drop-out stopped, and the panel source. Most importantly, it holds a **qualified** marker, which is "yes" only for qualified completes. That marker decides who counts in every percentage on the portal.

### 7.2 The panel ID is never kept

The panel's ID for each person is scrambled into a code that cannot be turned back into the ID, and the ID itself is not kept. The scrambled code still lets CIP spot the same panellist qualifying twice in one wave, which the health check reports (section 9.6).

### 7.3 "Not asked" versus "shown but not ticked"

This is the most important rule at this stage.

- **A blank means "not asked".** When routing skipped a person past a question, Forsta leaves that question blank for them. CIP saves no answer at all. So "no answer saved" always means "this person was not asked".
- **A 0 on a multi-select row means "shown, not ticked".** Forsta writes 0 for every row the person saw and did not tick. CIP keeps these 0s.

Together, this gives every question its true **base**: the qualified people who were asked it. On a multi-select question, the base is everyone who saw the list, and a row's percentage is the people who ticked it divided by everyone who saw it.

Why it matters, with real CIP numbers from one weekly wave of 404 qualified completes: department-store question DP2 was asked of 222 people (department-store buyers only), Buy Now, Pay Later question BN2 of 133 (BNPL users only) and GLP-1 question GP8 of 71 (GLP-1 users only). Dividing any of these by all 404 would make the result look two to six times smaller than it is. So every CIP percentage is "of those asked".

### 7.4 Labels are stored once

For single-choice and grid answers, CIP saves only the answer code; the label ("$25,000 - $49,999") is stored once with the question and looked up when shown. This keeps the answer store small: repeating labels on every one of more than 23 million saved answers would take about 860 MB.

### 7.5 Nothing is dropped quietly

If a value cannot be saved correctly (for example, text where a number is expected), CIP saves nothing for it. The proof step (section 9.3) then finds that the number of answers saved is one short of what Forsta sent, and the whole wave fails instead of appearing with a silently missing answer.

### 7.6 China and history are read the same way

The China files and the old Qualtrics Excel export give answer labels ("Yes") instead of codes. CIP looks up each label in the question's answer list to find its code. This rule matters: an earlier shortcut that counted every filled single-choice cell as "yes" once made "BNPL users" 404 people instead of 133. From here on, every source (Forsta, China and the history) follows the same rules.

---

## 8. Stage 4: applying Coresight's research rules

This is the second half of the "T" of ETL: Coresight's business rules. It is covered in Part 4.

### 8.1 One demographic profile per respondent

Demographic answers (gender, age, income, state and so on) are ordinary answers, and their question codes differ between studies and platforms. To make demographic filters fast and consistent, CIP gives each respondent one **profile**: gender, age, age band, generation, relationship status, ethnicity, household income band, area (urban, suburban, rural; city tier in China), political view, state, Census region, and their outlook on their own finances and on the economy.

For each wave, CIP decides which question supplies each demographic:

1. For the US weekly tracker, the team's settings name the questions: D1 gender, D2 age, D3 relationship status, D4 ethnicity, D5 household income, D6 area, D7 political view, D8 state, CS1 outlook on own finances, CS2 outlook on the economy. The China tracker uses S1 gender, S2 age, S3 income, S4 city tier, Q8 and Q9 for the two outlooks.
2. For any demographic still missing, CIP looks for a question whose wording asks it, for example "What is your gender" or "Which state is your primary residence".
3. If no question supplies it, that demographic is left empty for that wave and the portal hides that filter instead of showing an empty one.

Two of these wording searches were tightened after real mistakes: the income search once picked a December 2022 question about "monthly household income" for debt, and the state search once picked "Which state did you move from?".

### 8.2 Age bands and generations

| Age band | Ages | | Generation | Ages |
|---|---|---|---|---|
| 18-29 | 18 to 29 | | GenZ | 18 to 28 |
| 30-44 | 30 to 44 | | Millennial | 29 to 44 |
| 45-60 | 45 to 60 | | GenX | 45 to 60 |
| Over 60 | 61 and over | | Boomer | 61 and over |

Note that a 29-year-old is in age band 18-29 but is a Millennial, not GenZ.

Rules that keep these cuts honest:

- **"Under 18" is outside every cut.** It is not counted as 18. This rule came from a real case: counting one under-age respondent as 18 put GenZ at 62 in the 28 September 2026 wave, while Forsta's own table said 61.
- **An age range only gets a band if it fits wholly inside one.** Some older studies asked age in ranges. A range of "26-41" spans GenZ and Millennials, so it gets neither, rather than being forced into one.
- **Average age** uses the analysts' own midpoints: 23.5 for 18-29, 37 for 30-44, 52.5 for 45-60 and 67 for Over 60. China's bands have their own: 21.5, 33.5, 49.5, 66.5 and 80.

### 8.3 Household income midpoints

To compute an average income for a group (for example, a retailer's shoppers), each income band has a midpoint, in thousands of dollars, taken from the analysts' own workbooks:

| Income band | Midpoint ($000) |
|---|---|
| under $25,000 | 13 |
| $25,000 - $49,999 | 37.4995 |
| $50,000 - $99,999 | 74.9995 |
| $100,000 - $149,999 | 124.9995 |
| $150,000 - $199,999 | 174.9995 |
| $200,000 or greater | 225 |

### 8.4 Census regions

The state answer is turned into one of the four US Census regions: Northeast, Midwest, South and West. Both two-letter state codes ("CT") and full names ("Connecticut") are recognised, because different waves give different forms; accepting only one would leave the region filter silently empty. For the SurveyMonkey years, the panel's Census division is turned into its region.

### 8.5 Every question carries its own base

For every question in every wave, CIP counts its base: the qualified respondents who were asked it and answered (section 7.3). The base travels with the question, so every percentage the portal shows is "of those asked".

### 8.6 The survey calendar: what each wave was about

Weekly tracker titles follow one pattern: "Shopping and Spending - inc <part> + <part> + …". CIP reads each part:

- **Sectors** (Drugstore, eCommerce, Luxury, Department stores, Beauty, Home furnishings, Home improvement, Social commerce, Off-price/dollar, Apparel, Mass/warehouse, Footwear). When the first part is a sector, it is the wave's **lead sector**. The 12 sectors rotate, so each lead sector returns about every 12 weeks (give or take a week around holidays).
- **Recurring topics** (Tariffs and inflation, GLP-1, GenAI, Financial health, MidEast gas price shock).
- **The holiday tracker**, recognised from the title or from the wave itself asking the holiday shopping status question. The second check matters: the 28 September 2026 wave's title said only "Holiday", yet it carried the holiday tracker.
- **Events** (Prime Day, Labor Day and others).

A **season** runs from July to June, so September 2026 and January 2027 are both in season 2026. Seasonal and annual waves are numbered in launch order within their season, which is what lets the portal compare "holiday tracker wave 2 this year" with "wave 2 last year".

### 8.7 The same question across many waves

Trends and "this week versus last year" need the same question in different waves. Matching on the question code alone would be wrong:

- **Codes get reused for different questions.** Q13 asked about footwear one week and about Cyber Monday the next. DS1 to DS3 ask about drugstores in drugstore weeks and about dollar stores in off-price weeks.
- **The same question gets different codes**, especially across SurveyMonkey, Qualtrics and Forsta.
- **Wording drifts slightly**: a different apostrophe, an added "Select all that apply".

So CIP links each question to a **concept**, its permanent identity, by comparing wordings after tidying away such small differences:

| What CIP finds | What happens |
|---|---|
| The same wording, with no new answers | Linked at once; the trend continues |
| The same wording, but with new answers added | Proposed, waits for an analyst to review |
| Wording at least 85 % similar | Proposed, waits for an analyst to review |
| Nothing close | A new concept is started |

Why 85 %: the most similar pair of unrelated questions in the 21 and 28 September 2026 waves scored 79.6 %, so the bar sits above that. A wave can never link two of its own questions to the same concept, or their answers would be counted twice. Nothing uncertain is trended until a person has looked.

When CIP finds last week's or last year's figure for an answer, it uses the concept when both waves have one. Without a concept, it compares only questions with the same code **and** the same wording; a matching code with different wording is marked "wording changed" and not compared. A reused code therefore starts a new trend instead of joining two different questions.

### 8.8 Cohorts: named groups of respondents

A cohort is an analyst's rule for a group of respondents, written once and applied to every wave. Rules are written over concepts, not question codes, so a cohort means the same thing in a 2023 Qualtrics wave and a 2026 Forsta wave. Only qualified respondents can belong to a cohort.

The cohort in use today is **Beauty shoppers**: everyone in a wave that asked the beauty purchase question ("Have you purchased any beauty products … in the past three months?") who did not answer "No". It is the analysts' own rule, matched respondent by respondent against their "Beauty Shopper Profiles" workbook (1,200 shoppers; average age 44.94375; average income 93.1132 thousand dollars).

### 8.9 Weighting: an optional view

Every portal percentage is **unweighted** by default: each qualified respondent counts once, exactly as in Forsta and the team's Excel files. The portal can also show Census-weighted figures, which adjust each wave to US adult shares on three measures at once:

| Measure | Target shares |
|---|---|
| Gender | Male 49.0 %, Female 51.0 % |
| Age band | 18-29: 20.5 %, 30-44: 25.5 %, 45-60: 25.0 %, Over 60: 29.0 % |
| Census region | Northeast 17.3 %, Midwest 20.6 %, South 38.4 %, West 23.7 % |

The targets come from the US Census Bureau's American Community Survey 2023 (adults 18 and over), and should be checked against the latest release before weighted figures are quoted to clients. The weights use the standard raking method, and no respondent is allowed to count more than 5 times or less than 0.2 times the average. **Significance is always tested on unweighted figures.**

---

## 9. Stage 5: saving the wave and proving it is right

This is the "L" (Load) of ETL, and the proof that comes with it. It is covered in Part 5.

### 9.1 Hidden until proven

The moment CIP starts saving a wave, it marks the wave **"loading"**. A loading wave is invisible on the portal. It becomes **"verified"**, and visible, only after every step below has succeeded. When a wave that is already on the portal is reloaded, the portal keeps showing the previous version until the new one is published.

### 9.2 All or nothing

A wave's respondents and answers are replaced together, in a single step: either every answer is replaced, or none is. A wave can therefore never be left half old and half new. The saving step also refuses any value the database would have to alter to store (shortening a long text, rounding a number, turning a bad value into zero). If the database reports even one such alteration, nothing from this attempt is kept and the wave's previous answers stay exactly as they were.

### 9.3 The proof: three checks before anyone can see the wave

| Check | What must be true | Example of a failure |
|---|---|---|
| Every respondent saved | Respondents saved = respondents Forsta sent | "498 saved, 500 sent" |
| Every question understood | Every question variable in the questionnaire map has a place in CIP | A question Forsta added that CIP did not recognise |
| Every answer saved | For every question variable, the answers saved = the answers Forsta sent | "D5: 400 sent, 399 saved" |

If any check fails, the wave fails and stays hidden, and the failure list is emailed.

### 9.4 A second, independent check against Forsta

The three checks prove that every answer arrived; they cannot prove that every answer is right (a wrong code would still be counted). So, after each run that loaded a wave, CIP downloads the wave from Forsta again and compares every saved answer with Forsta's, one by one: codes, labels, numbers and typed words. If anything differs, or if Forsta can no longer be read (for example, because it has hibernated the survey), the failure list is told; a check that could compare nothing is never counted as a pass. The project records a full comparison on 8 October 2026: 31 Forsta waves, 4,476,153 answers, no differences.

### 9.5 When something goes wrong

What happens to the portal depends on how far the attempt got:

| What went wrong | What the portal shows afterwards |
|---|---|
| The download from Forsta failed, and the wave was on the portal before | The previous version, unchanged |
| The save failed before the answers were replaced, and the wave was on the portal before | The previous version's answers, unchanged |
| A first load failed | Nothing for this wave yet |
| The proof found a difference, or a later step failed after the answers were replaced | The wave is hidden until a successful load |

Then:

- **The failure list is emailed**, with the reason. The same problem is emailed at most once every 6 hours, because checks run every 30 minutes; a new kind of problem is emailed at once.
- **CIP tries again**: at every run (every 30 minutes) up to 3 failures in a row; after that, once every 6 hours, so a broken survey is not downloaded in full every 30 minutes. A weekly wave that failed while still live is also tried again as soon as Forsta closes it, because its final data can be read from then. Each failure email says when the next try will be and how to load the wave at once by hand.
- **Reloading is always safe.** Every respondent and answer is matched to what is already saved by Forsta's own identifiers, so running a load again never creates duplicates. Respondents who have been removed from Forsta are removed from CIP too, so CIP always mirrors Forsta.

### 9.6 The health check: does the whole database still add up?

After every run that loaded or failed a wave, and once every Friday, CIP checks the whole database. Problems fall into two groups:

- **Things CIP can safely rebuild by itself**, because they are worked out from the saved answers: for example a verified wave missing its prepared counts, or a search entry pointing at a deleted question. CIP rebuilds them (up to 20 waves per check per run), checks again, and reports anything still wrong.
- **Things only a person should decide**, because they concern the collected data itself: the same Forsta interview saved twice in one wave, the same panellist qualifying twice in one wave, a wave stuck in "loading", a verified wave with no qualified respondents, a closed survey still not loaded after 3 days, or a planned weekly wave not on the portal 4 days after its Monday. CIP never changes these; it emails the failure list so someone can look.

CIP also watches for surveys it cannot fetch by itself: a closed survey that Forsta hibernated before CIP loaded it, a weekly wave loaded early that Forsta hibernated before its final reload (the portal keeps the early version), and a survey that disappeared from Forsta's list before it was loaded. Each needs someone to act in Forsta.

### 9.7 Numbers Coresight has already published

Coresight's reports quote CIP numbers. A published set of numbers is frozen in CIP as a "publication": which question, which waves, which group, which cut, and the figures it gave on the day. After every run that loaded a wave, and every Friday, CIP works out every publication again from today's data and compares each figure. Figures must agree to within 0.0005 for percentages and averages, and exactly for counts. If any published figure would now come out differently, the failure list is emailed. This replaces the analysts' manual "Cross-Check" tab.

---

## 10. Stage 6: preparing every result in advance, and delivering it

This is covered in Part 6.

### 10.1 Everything is counted once, when the wave arrives

The data changes once a week; people open the portal many times a day. So CIP counts every answer once per wave and saves the finished results. A standard screen then reads a few dozen ready-made figures instead of going through a wave's roughly 150,000 saved answers.

For every answer to every single-choice question, grid row and multi-select row, CIP counts how many qualified people gave it and how many answered the question, for the total and for every standard cut:

| Cut | Values |
|---|---|
| Total | Everyone |
| Gender | As answered |
| Age band | 18-29, 30-44, 45-60, Over 60 |
| Generation | GenZ, Millennial, GenX, Boomer |
| Household income | As answered |
| Census region | Northeast, Midwest, South, West |
| Area | Urban, suburban, rural (city tier in China) |

(China uses its own age bands, 18-25, 26-41, 42-57, 57-76 and 77+, and has no generation or Census region.)

The same counts are made again for each cohort, such as Beauty shoppers. Each count also carries the age and income midpoints of the people in it, so the average age and average income of any answer's group are ready too. Numeric and open-ended answers have no percentages.

### 10.2 The percentage

Percentage = people who gave the answer ÷ base × 100. Every verified wave is shown, however few people answered it; a small base is marked, never hidden. A group that was asked a question but in which nobody chose an answer shows 0 %, not a blank.

### 10.3 Last week and last year

| Comparison | Which wave is used |
|---|---|
| **Prior week** (weekly trackers only) | The latest verified wave of the same study family dated 1 to 14 days earlier |
| **Last year**, weekly tracker | The verified wave of the same family dated within 3 days of exactly 52 weeks earlier (the same weekday a year ago) |
| **Last year**, annual or ad hoc study | The family's latest verified wave 300 to 430 days earlier, because annual studies do not field in the same week each year |

If there is no last-year wave because a Forsta survey from that week was never loaded (for example, it hibernated first), the portal says so instead of quietly using a different week.

The matching answer in the other wave is found through the concept (section 8.7) or, without one, by the same question code with the same wording. When a question's wording changed, the comparison is dropped and marked "wording changed".

### 10.4 Warning marks on a result

| Mark | When | Why |
|---|---|---|
| **Small base** | Base under 50 | The figure is shown but faded, as less reliable |
| **Wording changed** | Same question code, different question | Unlike questions are not compared |
| **Routing changed** | The share of qualified respondents who answered the question moved by more than 10 percentage points between the two waves | The two percentages describe different groups of people |
| **Significant change** | The change passes the significance test below | Highlights real movement |

### 10.5 Which changes are real: significance testing

A weekly wave has hundreds of answers, and every one moves a little from week to week by chance. CIP marks a change as significant only when it is very unlikely to be chance.

- **The test** is the industry-standard two-proportion test, comparing this wave's percentage with the prior (or last-year) wave's percentage for the same answer.
- **Which results are tested**: only the total (not the demographic cuts); only when both bases are at least 30; only when routing did not change; and never for filler answers such as "None of these", "None of the above", "Other" and "Prefer not to say".
- **The correction for testing many answers at once.** Testing hundreds of answers at the usual 95 % confidence level would flag about 1 in 20 unchanged answers as "significant" by chance alone. So CIP applies the standard correction for many tests at once (the Benjamini–Hochberg method), which keeps false alarms to at most 5 in every 100 changes it flags. Prior-week and last-year changes are corrected separately.

The same marks are used by the portal's screens, the topic dashboards' tiles and lists, and the team's weekly email, so they always agree. The weekly report applies the same test and correction to its own one-week and three-month comparisons.

### 10.6 Other things prepared for each wave

- **The Weekly Line-By-Line file.** For every US weekly tracker wave, CIP rebuilds the rows of the team's "Weekly Line-By-Line Survey Data" workbook: one row per qualified respondent, in order of completion, with the team's own columns and column order (month, date, the five multi-select lists q1 to q5, household and economic situation, gender, age, relationship status, ethnicity, household income, primary residence, state, start date, age range and generation) and the team's own spellings ("over 60", "Millenial"). D7 and the panel session ID are left out, as the team always did.
- **Open-ended answers coded into themes.** After each weekly Forsta load, the typed answers to "Other, please specify" and open questions are grouped into themes so they can be charted: by an AI model (Claude), which names up to 8 themes; or, without it, by frequency, merging near-identical answers and making any answer given by two or more people a theme. The portal then shows the share of those who wrote something, by theme, for the total, gender and generation. The typed answers themselves never leave CIP's coding file.
- **Topic dashboards.** The business team's databank tiles (single figures, ranked lists such as top retailers, and segments), each with its prior and last-year comparison and a small-base mark at 50, are rebuilt for the modules the new wave carries.
- **Metric alerts.** Alerts that team members set on the portal are checked after every load, and checked again when an early load is replaced by the final one. An alert fires at most once per wave, with a Teams message and an email to the person who set it.

### 10.7 Publishing: switching on the new results safely

The finished results for every standard screen are written as files, so a screen opens almost instantly without asking the database. To keep this safe:

1. The new version is built completely, apart from the live one. Waves that did not change are reused from the live version, so only what changed is rebuilt.
2. The new version must pass quality checks: it lists exactly as many waves as CIP holds; every wave has its complete set of results; and no wave has lost more than a tenth of its questions compared with the live version (a big drop means something went wrong, not a real change).
3. Only then is the new version switched on, in one step, so a reader sees either the old version or the new one, never a mix.
4. If any check fails, the new version is thrown away, the previous version stays live, and the failure list is told.
5. The last three versions are kept, so the portal can be turned back to the previous one at once.

After a system update, the portal restores the latest saved version within seconds, and adds any wave loaded since that version was saved.

### 10.8 Reports and databanks built from the results

These are prepared at the same time and shown on their screens as they are:

| View | What it reproduces | How it was checked |
|---|---|---|
| **Weekly "US Consumer Survey Insights" report** | The weekly PDF report: "Three Data Points To Watch"; net better (better minus worse) for personal finances and the economy, weekly, four-week average and by income group; 13-week retailer, category and activity tables with one-week and three-month changes; shopper profiles by retailer; respondents per week and margin of error | Against the 3 November 2026 report. The same engine builds the China report. A week whose question wording differs from today's is treated as not asked, so a report never mixes two questions |
| **Databank sector tables** | One column per survey the sector ran (back to 2022), the purchase rate, and tables of retailers, brands and categories | Against the Databank page of 6 November 2026 (Department stores). Reused codes are told apart by wording (DS1 to DS3 for drugstores versus dollar stores) |
| **Retailer databank** | Every retailer and sector week by week, with shoppers split by gender, generation, income, region and area | Built from the same counts, so any choice of weeks can be added up on screen |
| **Expected vs actual** | For each retail event (Halloween, Black Friday and others): what people expected beforehand versus what they did afterwards, this year and last year, with significance | Against the 7 October 2026 seasonal report |
| **Public home page facts** | Counts and dates only (number of waves and responses, the latest weekly wave's date and topics) | No survey answer is public |

### 10.9 The email to the team

After the dashboards and screens are live, CIP sends one email per loaded survey to the team list (with a copy to the data-automation mailbox) and posts a headline in Teams:

- who answered;
- the **three biggest significant changes** against the prior wave, using the same significance marks as the portal, one per question, leaving out the demographic questions D1 to D9 (annual and ad hoc studies have no prior wave, so their email says no answer changed significantly);
- the team's usual workbooks: **Cross Tabs** and **Holiday Inflation Cross Tabs** (in the layout of the team's Forsta exports, with `*` marking bases under 100 and `**` bases under 30), each only when that week's questionnaire can fill it, and otherwise named in the email with the reason; **Raw Data**, Forsta's own labelled export; and, for US weekly tracker waves, the **Weekly Line-By-Line** file.

A weekly wave loaded early is emailed twice: once at the early load and once at the final reload.

---

## 11. Questions people often ask

**Why does this week's wave say "in field"?**
Because CIP loaded it as soon as fieldwork was effectively over (400 qualified completes, full quotas, or 9 hours after launch), before Forsta formally closed it. When Forsta closes it, CIP reloads it and the mark goes away. The final numbers can differ slightly from the early ones if a few more respondents completed in between.

**Why did a number change between Tuesday and Wednesday?**
Most likely because the Tuesday figure came from the early load and the Wednesday figure from the final reload, which can include a few more completes (wave 261002 went from 401 to 404 qualified). The team receives an email for each.

**Why is the base for a question not 400?**
Because the base is only the people who were asked that question. Routing shows many questions only to a subgroup: in one wave of 404 completes, DP2 went to 222 department-store buyers, BN2 to 133 BNPL users and GP8 to 71 GLP-1 users.

**Why is a percentage faded?**
Its base is under 50, so it is less reliable. It is still shown, never hidden.

**Why is there no "vs last year" figure?**
Either no wave of the same study ran within the rule's window a year earlier (section 10.3), or a Forsta survey from that week was never loaded (for example, it hibernated first), in which case the portal says so. A comparison is also dropped when the question's wording changed.

**Why is a large change not marked significant?**
The test may not apply: one of the two bases is under 30, the question's routing changed by more than 10 points, the answer is a filler such as "None of these", or the change is in a demographic cut rather than the total. Or the change did not pass the correction for testing many answers at once.

**Can CIP change or delete anything in Forsta?**
No. CIP only reads from Forsta. Its three permitted calculation requests (running a cross-tab, running and exporting a saved report) change nothing, and CIP proves this after each one by checking the survey's last-edited time.

**What happens if Forsta is down on a launch night?**
CIP retries each request a few times, then fails the wave for that run and emails the failure list. It tries again at every 30-minute check, and after 3 failures in a row every 6 hours, and once more as soon as Forsta closes the wave. The previous week's data stays on the portal throughout.

**What if a survey is hibernated before CIP loads it?**
CIP cannot read it, and the health check warns about it. Someone needs to wake it in the Forsta portal; the next check then loads it.

**Does CIP keep screen-outs and drop-outs?**
Yes. Every respondent of every status is kept, as the record of the fieldwork. Only qualified completes count in percentages.

**Are portal percentages weighted?**
No, not by default. They are unweighted, as in Forsta and the team's Excel files. A Census-weighted view is available as an option; significance is always tested on unweighted figures.

**Is any personal information kept?**
No. The browser description, survey link, session number, device fingerprint and IP address are never kept, and the panel ID is replaced by a scrambled code that cannot be turned back into the ID.
