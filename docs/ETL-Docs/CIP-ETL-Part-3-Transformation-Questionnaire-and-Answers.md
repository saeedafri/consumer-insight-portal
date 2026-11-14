# CIP ETL Series, Part 3: Transformation, Questionnaire and Answers

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the first half of the "T" of ETL. How Forsta's questionnaire description (the datamap) becomes clean questions, rows, answer options and fields, and how each respondent's raw record becomes one respondent row and many answer rows
Previous part: Part 2, Extraction. Next part: Part 4, Transformation (Business Logic)

Everything in this document is taken from the project's code (folder `cip-stg`), mainly `etl/forsta_api.py`, `etl/records.py`, `etl/loaders.py`, `etl/forsta_etl.py`, `etl/survey_map.py`, `config/survey_map.yml` and the table definitions in `sql/001_schema.sql`. The worked examples use the question shapes from the project's own tests, which copy the shapes of real Forsta datamaps.

---

## 1. Where we are in the pipeline

At the end of extraction (Part 2), the pipeline holds two things for one wave:

1. **The datamap:** Forsta's description of the questionnaire, in memory.
2. **The snapshot:** every respondent's raw record, in a private file on disk. Values are codes and strings, for example `"status": 3`, `"q1r1": 1`, `"D5": 2`.

Raw codes mean nothing to a reader. "D5 = 2" only becomes "$25,000 to $49,999" if the pipeline knows the questionnaire. So transformation happens in two steps, in this order:

| Step | Input | Output | Code |
|---|---|---|---|
| **A. Questionnaire** | The datamap | Questions, rows (items), answer options and fields, each with a type and flags | `etl/forsta_api.py` `questions_from_datamap`, then `etl/loaders.py` `load_definitions` |
| **B. Answers** | The snapshot records + the fields from step A | One respondent row per record, and one answer row per filled value | `etl/forsta_etl.py` `_respondent`, `_answer_values`, `_write` |

Business rules on top of this (demographics, bands, generations, concepts, cohorts) come in Part 4.

## 2. The target shape: "long" storage

Before the details, it helps to see what the data must look like at the end, and why.

A Forsta export is **wide**: one row per respondent, one column per question variable. The weekly wave of 21 September 2026 had 375 columns, and the columns change every week as modules rotate in and out.

CIP stores data **long**: one row per respondent per answer. The table `cip_answer` has the same few columns whatever the questionnaire is:

| respondent_id | field_id | value_code | value_label | value_number | value_text |
|---|---|---|---|---|---|

The schema's own comment gives the reason: the questionnaire changes every wave, so a new question becomes new rows, never a change to the database's structure. A wave with 375 columns and 500 respondents becomes about 150,000 answer rows (the table's comment: about 151,000 per wave).

To make long rows meaningful, every answer row points to a **field**, every field points to its **question** (and, for a list or grid, its **item**), and every code can be looked up in the question's **options**. Step A builds exactly that dictionary.

## 3. The four definition tables

| Table | One row per | Example | Key columns |
|---|---|---|---|
| `cip_question` | Question, as an analyst names it | `q1`, `DP7`, `CS1`, `HX6` | code, wording, short wording, type, min and max code, technical flag, virtual flag, multi flag, topic, base, order |
| `cip_item` | Row of a list or grid | `q1r1`, `DP7r3`, `HX6r2` | code, label, short label, "None of these" flag, "Other" flag, left and right statement (bipolar), order |
| `cip_option` | Answer code of a question | `D5`: 1 = "under $25,000", 2 = "$25,000 - $49,999" | code, label, non-response flag, order |
| `cip_field` | Column in Forsta's export | `q1r1`, `D5`, `HX6r1` | exact column name, its question, its item (if any), value type |

There is also **`cip_topic`**, the editorial grouping (Shopping and Spending, Department Stores, BNPL, Consumer Sentiment, Demographics and so on), which every question is placed in.

## 4. Step A: reading the datamap

### 4.1 What a datamap question looks like

Each question in the datamap has:

- `qlabel`: its code, for example `D5`
- `qtitle`: its wording
- `type`: `single`, `multiple`, `number`, `float`, `text`, `textarea` or `date`
- `flags`: optional, `t` (technical) and/or `v` (virtual, meaning derived by Forsta, not asked)
- `variables`: one per export column, each with a `label` (the column name, for example `q1r1`), and for rows a `rowTitle` and sometimes a `colTitle`
- `values`: the answer codes and their titles (labels), for example `{value: 1, title: "under $25,000"}`

One Forsta question can produce several export columns. CIP keeps **one question per Forsta question**, not one per column. The columns become items and fields under it.

### 4.2 Cleaning every piece of text

Every wording and label passes through two cleaning steps before it is used:

1. **HTML codes become characters.** Forsta writes some text with HTML codes, for example `&amp;` for "&" or `&#39;` for an apostrophe. These are converted to the real characters.
2. **Whitespace is normalised.** Every run of spaces, tabs, line breaks and non-breaking spaces becomes one ordinary space, and leading and trailing spaces are removed.

The code explains why this matters: Forsta's datamap writes some labels with non-breaking spaces ("Spent\xa0a lot less…") while the data export uses ordinary ones. Compared as they are, the label lookup missed and the answer loaded with no code. Cleaning every label the same way prevents that.

### 4.3 Personal fields are removed first

These names are never turned into questions or fields, whatever the datamap says:

| Name | What it is |
|---|---|
| `userAgent` | The respondent's browser string |
| `url` | The link they used |
| `session` | Their session ID |
| `dcua` | A device fingerprint |
| `ipAddress` | Their IP address |
| `RID` | The panel's ID for the person (kept only as a one-way hash, Section 8) |

If a whole question has one of these codes, it is skipped. If a question contains one of these as a variable, that variable is removed. If a question has no variables left, it is skipped.

### 4.4 Finding the answer labels

The answer codes and titles are normally on the question (`values`). The code notes that in about a third of real datamaps they are only on the question's variables. So the rule is: take the question's `values`; if there are none, take them from the first variable that has some. Only whole-number codes are kept (negative codes are allowed). Each title is cleaned (Section 4.2).

### 4.5 "Other, please specify" boxes become their own questions

Many questions have a free-text box for "Other". In the datamap this is a `text` variable inside a non-text question, for example `q1r2oe` inside multi-select `q1`, or `vosr15oe` inside `vos`.

**Rule:** a text variable inside a non-text question is taken out of that question and becomes **its own text question**:

- its code is the variable's name (`q1r2oe`);
- its wording is the parent question's wording, then " — ", then the row's title (or "Other"), then " (please specify)";
- it keeps the parent's flags.

So the "Other" box is never treated as a row of a list or a point on a scale. The tick for "Other" stays in the parent question; the typed words go into the new text question.

### 4.6 Technical and virtual flags

| Flag | Meaning | Examples | Effect |
|---|---|---|---|
| `t` | Technical | `qtime` (interview time), `conditions`, `start_date`, `status` | Stored, never reported |
| `v` | Virtual (derived by Forsta) | `vos` (operating system), `vbrowser`, `vlist` | Stored, never reported |
| title ends "- NORMALIZED" | Forsta's normalised copy of a grid | `HX6_norm` | Treated as virtual |

"Stored, never reported" means the question and its answers are in the database (they are part of the record of the fieldwork), but they are left out of the topics people browse, the concepts, the cube and every chart.

### 4.7 Deciding the question type

This is the central rule of step A. First, two facts are worked out for each question:

- **rows:** each remaining variable (after removing personal and "Other" text variables) with its label. The row label is the variable's `rowTitle` and `colTitle` joined by " — ", or its `title`, or its name.
- **named apart:** true if there is more than one row, or if the single row's name differs from the question's code. (For a plain single-choice question, Forsta names its one column the same as the question, for example `D5`.)

Then:

| Forsta type | Condition | CIP type (`qtype`) | Rows kept? | Options | Min/max code |
|---|---|---|---|---|---|
| `multiple` | always | `multi` | yes, one item per row | the question's values, if any | 0 and 1 |
| `single` | not named apart | `single` | no | the answer list | lowest and highest code |
| `single` | named apart | `grid_single` | yes, one item per row | the answer list | lowest and highest code |
| `single` | named apart, and every answer title is blank | `grid_single`, **bipolar** | yes | replaced by 1 = "Left statement", 2 = "Right statement" | 1 and 2 |
| `number`, `float` | | `numeric` | yes if named apart | none | |
| `text`, `textarea` | | `text` | yes if named apart | none | |
| `date` | | `datetime` | yes if named apart | none | |
| anything else | | `text` | yes if named apart | none | |

A question is marked **multi** (`is_multi = 1`) when it has rows and its codes run from 0 to 1, which is the multi-select shape.

### 4.8 Bipolar grids

Some grids ask the respondent to pick between two statements per row, for example "I start holiday shopping early" versus "I leave holiday shopping late". In the datamap these grids have answer codes 1 and 2 with **blank titles** (a title of only `&nbsp;` counts as blank after cleaning). Without special handling, the answers would be meaningless numbers.

Forsta also creates a "- NORMALIZED" copy of such a grid (for example `HX6_norm`), whose variables carry each row's left statement (`…_l`) and right statement (`…_r`).

**Rule:**

- The grid's options become 1 = "Left statement", 2 = "Right statement".
- For each row, the **left statement** is the row's own title, and the **right statement** is the title of the matching `{question}_norm{row}_r` variable from the NORMALIZED copy.
- Both are stored on the item (`left_label`, `right_label`), so a chart can say what code 1 and code 2 mean for each row.
- The NORMALIZED copy itself becomes a virtual question: stored, never reported.

### 4.9 A worked example, from the shapes in the project's tests

| Datamap question | What CIP makes of it |
|---|---|
| `vos` "Operating System", type single, flags v and t, values Windows (1) … Other (15); variables `vos` and text `vosr15oe` | Question `vos`, type `single`, virtual and technical. Separate text question `vosr15oe` "Operating System — Other (please specify)", also virtual and technical |
| `q1` "Which, if any, of these have you done?", type multiple; variables `q1r1` "Met up with friends", `q1r2` "Other (please specify)", text `q1r2oe` | Question `q1`, type `multi`, items `q1r1` and `q1r2`. Separate text question `q1r2oe` |
| `D5` "What was your total household income last year?", type single, one variable `D5`, values only on the variable | Question `D5`, type `single`, options 1 "under $25,000", 2 "$25,000 - $49,999" (taken from the variable) |
| `HX6` "Please choose the statement from each row.", type single, rows `HX6r1`, `HX6r2`, values 1 and 2 with blank titles | Question `HX6`, type `grid_single`, bipolar. Options 1 "Left statement", 2 "Right statement". Item `HX6r1`: left "I start holiday shopping early", right "I leave holiday shopping late". Item `HX6r2`: left "I set a budget first", right "I just spend" |
| `HX6_norm` "… - NORMALIZED" | Virtual question, stored, never reported |
| `qtime` "Total Interview Time", type float, flag t | Question `qtime`, type `numeric`, technical |
| `q9` "Anything else?", type text | Question `q9`, type `text` |

## 5. Step A, continued: placing each question in a topic

Every question gets a topic from **`config/survey_map.yml`**. Rules are tried from the lowest priority number upward, and the first rule that matches wins. A rule can test the question's code (a pattern) or its wording, and can apply to one family or to every survey (`*`).

### 5.1 The rules for the US weekly tracker (family CSI-US)

| Priority | Code pattern | Topic |
|---|---|---|
| 10 | `q1` to `q6` | Shopping and Spending |
| 20 | starts `DP` + digit | Department Stores |
| 30 | starts `DJ` + digit | Diamonds and Fine Jewelry |
| 40 | starts `BN` + digit | Buy Now, Pay Later |
| 50 | `D28` to `D35` | AI and GenAI Shopping |
| 60 | starts `GP` + digit | GLP-1 Impact |
| 70 | starts `CS` + digit | Consumer Sentiment |
| 80 | `D12` to `D15` | Macro and Gas Prices |
| 90 | `D1` to `D8` | Demographics |
| 100 | starts `XM` + digit | Holiday Shopping Tracker |
| 110 | starts `HX` + digit | Holiday Spending Outlook |
| 120 | starts `BT` + digit | Beauty |
| 130 | starts `TF` + digit | Tariffs |
| 140 | starts `IN` + digit | Inflation and Prices |

### 5.2 Rules for the China tracker (family CSI-CN)

`S1` to `S5` Demographics; `Q1` to `Q6` Shopping; `Q7` to `Q9` Sentiment.

### 5.3 Rules for every survey

| Priority | Test | Topic |
|---|---|---|
| 900 | code is one of record, uuid, date, markers, status, source, session, url, list, decLang, userAgent, dcua, RID, start_date, conditions | Technical |
| 910 | code starts with qtime, vlist, vos, vbrowser, vmobile, vdropout, vterm, vq, voq | Technical |
| 950 | wording mentions gender, age, income, ethnicity, marital, relationship status, state, region or zip | Demographics |
| no match | | **Unclassified** |

### 5.4 What the topic decides

- A question in the **Technical** topic is marked technical (`is_technical = 1`), in addition to any question with Forsta's `t` flag.
- If a rule names a topic the database has never seen, the topic is **created on the spot** (its name made from its code, placed after the standard topics), so a new module never blocks a load.
- An unmatched question is still loaded, in "Unclassified". The config file's own header states the principle: nothing in these rules is required; they only make the portal tidier. A new module in a future wave is a config edit, not a code change.

## 6. Step A, continued: writing the definitions

`load_definitions()` writes everything in one database transaction, with a fixed small number of statements per wave, whatever the number of questions (each round trip from India to Azure costs about 250 milliseconds).

### 6.1 Questions (`cip_question`)

One row per question, in questionnaire order:

| Column | Rule |
|---|---|
| `qcode` | The code, cut to 50 characters |
| `qtext` | The cleaned wording |
| `qtext_short` | The wording shortened to 120 characters with "…" if longer (chart titles) |
| `qtype` | Section 4.7 |
| `value_min`, `value_max` | Section 4.7 |
| `topic_id` | Section 5 |
| `is_technical` | Technical topic or flag `t` |
| `is_virtual` | Flag `v` (including NORMALIZED copies) |
| `is_multi` | Has rows and codes 0 to 1 |
| `sort_order` | Position in the questionnaire |

### 6.2 Answer options (`cip_option`)

One row per answer code of each question, in the datamap's order. Label cut to 500 characters. One flag is set from the label:

- **Non-response** (`is_nonresponse = 1`) when the label contains "don't know", "dont know", "not sure" or "prefer not to say". These answers can be left out of summary measures such as top-two-box.

### 6.3 Items (`cip_item`)

One row per row of a list or grid, in order. Label cut to 1,000 characters; a short label of up to 80 characters for chart axes. Flags:

- **Exclusive** (`is_exclusive = 1`) when the label starts with "None of these". These are dropped from rankings.
- **Other** (`is_other = 1`) when the item's code ends in `oe`.
- **Left and right statements** for bipolar rows (Section 4.8).

### 6.4 Fields (`cip_field`)

One row per export column. This table is the loader's map from Forsta's column names to CIP's meaning.

- A question **with items** gets one field per item, named exactly like the item (`q1r1`, `HX6r2`).
- A question **without items** gets one field named like the question (`D5`, `q9`).

Each field gets a **value type** that decides how its values are stored (Section 9):

| Question type | Field value type |
|---|---|
| `numeric` | `numeric` |
| `text` | `text` |
| everything else (`single`, `multi`, `grid_single`, `datetime`) | `code` |

### 6.5 Reloads update in place, nothing is duplicated

Every write is an "insert, or update if it already exists", keyed on Forsta's own names: the question code within the wave, the item code within the question, the answer code within the question, the field name within the wave. Reloading the same wave updates rows in place.

**Removing rows that disappeared.** Updating in place never removes a row. So after a wave's answers are written and verified, a separate step (`drop_unlisted_items`) deletes any item that the questionnaire no longer lists **and that nobody chose**. An item anyone chose (any code other than 0, any number, any text) is always kept. The code records the case that caused this rule: a corrected question 7 list in survey 97 left a second, empty "YouTube" row next to the real one. Only questions in the current load are looked at.

## 7. Step B: turning records into respondents and answers

With the dictionary in place, each record from the snapshot becomes one respondent row and many answer rows. This happens inside **one database transaction** (Part 5 explains why that matters).

## 8. One respondent row per record

Each record becomes one row in **`cip_respondent`**:

| Column | From the record | Rule |
|---|---|---|
| `record_no` | `record` | Whole number, 0 if missing |
| `forsta_uuid` | `uuid` | Up to 64 characters. Forsta's unique ID for the interview |
| `status_code` | `status` | 1, 2, 3 or 4 |
| `status_label` | | 1 Terminated, 2 Overquota, 3 Qualified, 4 Partial |
| `is_qualified` | | 1 when status is 3, else 0. **The base of every portal percentage** |
| `completed_at` | `date` | Read as a date and time (formats such as `09/29/2026 01:10`) |
| `interview_secs` | `qtime` | Whole seconds |
| `markers` | `markers` | Quota buckets, up to 1,000 characters |
| `device`, `os`, `browser` | `vmobiledevice`, `vos`, `vbrowser` | Up to 50 characters each |
| `dropout_qcode` | `vdropout` | Where a partial respondent stopped |
| `panel_source` | `vlist`, or `list` | Up to 100 characters |
| `respondent_key` | `RID` | **A one-way keyed hash, never the ID itself** |
| `load_id` | | The audit-log row of this load |

**How the respondent key is made.** The panel's ID for the person (`RID`) is first turned into a SHA-256 fingerprint, and that fingerprint is then hashed again with a secret key (HMAC-SHA256, key `CIP_RESPONDENT_SALT`). Without the secret, a list of panel IDs cannot be matched against the stored keys. The key still lets CIP spot the same panelist qualifying twice in one wave (an integrity check in Part 5). The raw ID is never stored anywhere.

**Respondents who disappeared from Forsta.** Each record is matched to an existing row by wave and record number, so a reload updates the same person. After writing, any respondent stored from an earlier load whose `uuid` is no longer in Forsta's data is deleted, together with their demographic profile and cohort memberships. The database always mirrors Forsta exactly.

## 9. Answer rows: the exact rule for each value

For every record, every key in the record that matches a field becomes at most one row in **`cip_answer`**. Keys that are not fields (the personal ones, for example) are ignored. The rule depends on the field's value type:

| Value | Field value type | What is stored | Example |
|---|---|---|---|
| Missing, null or only spaces | any | **Nothing.** No row | Question not shown to this person |
| A whole number, written as `3`, `"3"`, `3.0` or `"3.0"` | `code` | `value_code` = 3 | `D5: 2` → code 2 |
| `0` on a multi-select item | `code` | `value_code` = 0 | `q1r1: 0` → shown, not chosen |
| `1` on a multi-select item | `code` | `value_code` = 1 | `q1r1: 1` → chosen |
| Something that is not a whole number | `code` | `value_label` = the raw value (up to 500 characters); no code invented | A date answer such as `09/29/2026` |
| A number | `numeric` | `value_number`, rounded to 4 decimals | `qtime: 612.4` → 612.4 |
| A number that is not finite, or 100 trillion or more | `numeric` | Nothing (see the safety note below) | |
| Not a number | `numeric` | Nothing (see the safety note below) | |
| Any text | `text` | `value_text`, exactly as typed | `q9: "More discounts please"` |

### 9.1 Why "no row" means "not asked" and a 0 is kept

This is the most important business rule at this stage.

- A **blank** value means the respondent was not shown the question (survey routing skipped them). No row is stored. So "no answer" is the **absence** of a row.
- On a multi-select question, Forsta writes **0** for every item that was **shown but not ticked**. These 0 rows **are** stored.

Together, this gives every question its correct **base**: the people who were actually asked it. A multi-select question's base is everyone with any row for it (0 or 1), and an item's percentage is the 1s divided by that base. Part 4 shows how bases are counted, and why routing makes this essential: in this survey many questions are asked only of a subgroup (department-store questions only of department-store buyers, BNPL questions only of BNPL users), and dividing by the whole wave would understate them two to six times.

### 9.2 Labels are not repeated on every answer

For single-choice and grid answers, only the code is stored. The label already lives once in `cip_option` and is joined back when read. For multi-select answers, the item label is kept on the answer only if the question also has its own 0/1 option labels; otherwise a "Yes"/"No" option label could win over the real item name when displayed. The code notes that repeating a label on every one of about 26 million answer rows would cost about 860 MB, so labels are stored once and looked up.

### 9.3 Why numbers are rounded before upload

`value_number` holds up to 4 decimals. MySQL would round a longer number itself, but it would also raise a warning, and the bulk upload treats **any** warning as a failure of the whole wave (Part 5). So the pipeline rounds to 4 decimals itself, before upload.

### 9.4 A safety effect worth knowing

If a value cannot be stored under its field's rule (for example text in a numeric field, or an impossibly large number), no answer row is written for it. But verification (Part 5) counts, for every field, how many non-blank values Forsta sent and how many answers were stored. The two counts would then differ, and **the wave fails** instead of loading with a silently missing value. Nothing is dropped quietly.

## 10. Speed: how the answers are written

A weekly wave is about 150,000 answer rows. The pipeline writes them without holding them all in memory:

1. Respondents are written in batches of 512 rows per statement.
2. The wave's existing answers are deleted (inside the same transaction).
3. Answer rows are generated one record at a time from the snapshot and written to a temporary tab-separated file.
4. That file is sent to MySQL in **one** `LOAD DATA LOCAL INFILE` command, a compact bulk upload. If the server refuses that command, the same file is sent as batched inserts of 5,000 rows instead.

The code records why: from India, the network round trips cost far more than the server's work (13,000 rows took 18 seconds as ordinary inserts).

## 11. How the China and history sources differ at this stage

The Forsta API gives **codes**. The China files and the old Excel exports give **labels**. These sources use an older, shared path (`replace_respondents` in `etl/wave_loader.py`) with a label convention:

- A ticked multi-select item holds its label; an unticked one holds "NO TO: " followed by the label. The first becomes code 1, the second code 0.
- A single-choice cell holds a label such as "Yes". The label is looked up in the question's options (case-insensitive, after cleaning) to get its code. The code's comment explains the danger this avoids: treating every answered single-choice cell as code 1 once made "BNPL users" 404 people instead of 133.
- Respondents are matched on record number rather than `uuid`.

The China questionnaire comes from `config/china_codebook.yml` rather than a datamap: every Chinese wording maps to the analysts' English, and an answer's code is its place in its list (new answers are always added at the end, so existing codes keep their meaning).

From here on, every source follows the same steps: profiles, bases, concepts, cube, serving.

## 12. What this stage produces, in numbers

From the data dictionary of the live database (approximate row counts):

| Table | Rows |
|---|---|
| `cip_question` | about 8,300 |
| `cip_item` | about 50,300 |
| `cip_option` | about 29,000 |
| `cip_field` | about 56,500 |
| `cip_respondent` | about 176,500 |
| `cip_answer` | about 23.3 million |

The project's documentation also records how often each datamap shape appeared across 1,416 Forsta questions: 693 single-choice with one variable, 491 multi-select, 73 single-choice grids, 53 single-choice with an "Other" text box, 43 single-choice with rows and one variable, 32 numeric and 23 text.

## 13. Summary

Transformation starts by turning Forsta's questionnaire description into a dictionary. Every question gets one clean row with its type (single, multi-select, grid, bipolar grid, numeric, text or date), its topic and its flags. Every list or grid row becomes an item, every answer code an option, every export column a field. Personal fields are removed before anything is stored. "Other, please specify" boxes become their own text questions. Technical and Forsta-derived questions are kept but never reported. Then each respondent's record becomes one respondent row, with the qualified flag that every percentage depends on and the panel ID replaced by a secret one-way hash, and many answer rows, one per value that was filled. A blank means "not asked" and is not stored; a 0 on a list means "shown, not chosen" and is stored, which gives every question its true base. Any value that cannot be stored correctly makes the wave fail at verification, so nothing goes missing silently.

**Part 4** applies Coresight's business logic on top of these rows: demographic profiles, age bands and generations, income midpoints, census regions, question bases, and the concepts that link a question across waves and platforms.
