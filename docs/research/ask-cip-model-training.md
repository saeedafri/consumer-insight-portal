# Ask CIP: the whole story, explained simply

**What this is:** the full record of how we made Ask CIP (the "Ask Coresight" box in the portal) accurate, fast and
cheap, including how we trained our own small AI model. It is written for someone who has never worked with AI or code.
Every technical word is explained with an everyday comparison the first time it appears. The technical details are kept
for the very end (Appendix), for engineers.

**Started:** 12 November 2026 · **Kept up to date:** every new step is added to the Log (Part 15).

> [!TIP]
> **How to read this.** Part 1 is the whole story on one page. Parts 2 to 9 explain each piece slowly, with pictures
> made of boxes. Part 13 answers the questions a manager usually asks. You can stop after Part 1 and still know what
> happened.

---

## Contents

1. [The whole story on one page](#part-1-the-whole-story-on-one-page)
2. [What Ask CIP is: a very fast librarian](#part-2-what-ask-cip-is-a-very-fast-librarian)
3. [What was wrong when we started](#part-3-what-was-wrong-when-we-started)
4. [How we measured: the exam](#part-4-how-we-measured-the-exam)
5. [The fixes that needed no AI at all](#part-5-the-fixes-that-needed-no-ai-at-all)
6. [Every new survey, handled automatically](#part-6-every-new-survey-handled-automatically)
7. [AI from zero: the ideas you need](#part-7-ai-from-zero-the-ideas-you-need)
8. [Why we trained our own model](#part-8-why-we-trained-our-own-model)
9. [The training, round by round](#part-9-the-training-round-by-round)
10. [How the big AI companies do it, and what we copied](#part-10-how-the-big-ai-companies-do-it-and-what-we-copied)
11. [The "which did you mean?" safety check](#part-11-the-which-did-you-mean-safety-check)
12. [Cost, speed, memory, and where things run](#part-12-cost-speed-memory-and-where-things-run)
13. [Questions a manager usually asks](#part-13-questions-a-manager-usually-asks)
14. [What happens next](#part-14-what-happens-next)
15. [Log](#part-15-log)
16. [Glossary in plain words](#part-16-glossary-in-plain-words)
17. [13 November: what the live test showed, and what changed](#part-17-13-november-what-the-live-test-showed-and-what-changed)
18. [13 November, later: is 99.99% reachable, where the time goes, and the one notebook left (v5)](#part-18-13-november-later-is-9999-reachable-where-the-time-goes-and-the-one-notebook-left-v5)
19. [Appendix for engineers](#appendix-for-engineers)

---

## Part 1. The whole story on one page

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  THE GOAL                                                                                     │
│  Anyone (analyst, colleague, client) types a question in their own words and gets the right  │
│  number from OUR surveys, with a chart, in a blink, at almost no cost, and the same answer   │
│  however they word it.                                                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  WHAT WE FOUND (12 Nov 2026)                                                                  │
│  • Real questions got wrong answers (US questions answered from the China survey, etc.)      │
│  • Nobody could say how accurate it really was                                                │
│  • Each new survey needed a person to run a step by hand                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  WHAT WE DID                                                                                  │
│  1. Wrote an exam of ~40,000-50,000 questions with known answers, to MEASURE accuracy         │
│  2. Fixed the causes of mistakes one by one (71% → 92% on the same exam)                      │
│  3. Gave every survey question its "nicknames", so analyst wording is recognised (99.3% right)│
│  4. Made every new survey get named, checked and reported AUTOMATICALLY                        │
│  5. Added a safety check: when unsure, Ask asks "which did you mean?" instead of guessing      │
│  6. Studied how ChatGPT, Gemini and the big companies do it                                    │
│  7. Trained our own small AI model on Google Colab (3 rounds so far; each taught us something) │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  WHERE WE ARE                                                                                 │
│  • Of the answers Ask gives, 97.6% to 99.3% are right (depending on the kind of question)     │
│  • Answers take about 10 thousandths of a second on our server                                │
│  • No AI cost for most questions; about $0.0002 only when Ask is unsure                        │
│  • Ask NEVER invents a number: every figure is calculated from the survey                     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **The one sentence to remember:** Ask CIP does not let AI make up numbers. AI only helps it understand *which survey
> question* someone means; the number itself is always counted from our own survey data.

---

## Part 2. What Ask CIP is: a very fast librarian

Think of our surveys as a **library**: about **3,000 survey questions** (books), each asked in many weekly waves, each
with its answers counted.

Someone walks up to the desk and asks: *"What share of Gen Z bought from Amazon in October?"*

A good librarian does four things:

```
  The question: "What share of Gen Z bought from Amazon in October?"
        │
        ▼
 ┌───────────────────────┐   Picks out the details:
 │ 1. LISTEN              │   • which country? the US      • when? October
 │    (rules, 0.001 s)    │   • which group? Gen Z         • what? a share (a percentage)
 └───────────────────────┘
        │
        ▼
 ┌───────────────────────┐   Finds the right book:
 │ 2. FIND THE QUESTION   │   "Which of these retailers have you bought from in the past two weeks?"
 │    (0.005 s)           │   (by its nickname, by its words, or by its meaning)
 └───────────────────────┘
        │
        ▼
 ┌───────────────────────┐   Counts, from the survey itself:
 │ 3. COUNT               │   Gen Z respondents in October's waves who chose Amazon,
 │    (0.005 s)           │   out of all Gen Z respondents asked → exact percentage
 └───────────────────────┘
        │
        ▼
 ┌───────────────────────┐   Says it clearly:
 │ 4. ANSWER              │   a sentence, a chart, a table, the source, and the number of people
 └───────────────────────┘
```

> [!NOTE]
> Steps 1, 3 and 4 have always worked well: they follow fixed rules and arithmetic. **Step 2, finding the right
> question, is where almost all mistakes happen.** Almost everything in this document is about step 2.

---

## Part 3. What was wrong when we started

| What someone asked | What Ask did | Why it was wrong |
|---|---|---|
| "How do US consumers feel about the economy?" | answered from the **China** survey | the China survey had just been added and Ask did not know questions belong to one country |
| "Which retailers do Gen Z shop at most?" | answered from a question asked **once, to 26 people** | it did not prefer the question asked every week to 400 people |
| "Will people spend more this holiday than last year?" | answered "the main reason you expect to spend more" | right topic, wrong question |
| "Are people cutting back on dining out because of tariffs?" | said no survey asks this | the survey does ask it |

> [!WARNING]
> The bigger problem: **nobody could say how accurate Ask really was**, because the test questions were few and were
> written by the same people who built it.

First fixes: one country per question, a warning when fewer than 50 people answered, correct holiday periods, and
refusing questions that have nothing to do with our surveys. Result on the hand-written test: **84%**.

---

## Part 4. How we measured: the exam

You cannot improve what you cannot measure. So we wrote **an exam with an answer key**.

```
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │  THE BIG EXAM ("question bank")         ~40,000 to 50,000 questions                  │
 │  For each of the ~3,000 survey questions, we wrote the questions people might ask:   │
 │    • the latest figure           "Amazon Prime membership: latest wave"              │
 │    • over time                   "Amazon Prime membership trend since 2022"          │
 │    • by group                    "Amazon Prime membership by generation"             │
 │    • compared                    "Amazon Prime membership, 2025 vs 2026"             │
 │    • top answers, one answer, a season, a client's decision, a casual question       │
 │  Because each was written FROM a survey question, the right answer is known.         │
 └─────────────────────────────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │  THE FINAL EXAM ("golden set")          161 questions written by people               │
 │  Real-sounding questions in people's own words, with the right answer marked.         │
 │  Never used to teach anything: only to test.                                          │
 └─────────────────────────────────────────────────────────────────────────────────────┘
```

We also asked: **who uses the portal, and how do they ask?** (from how Morning Consult, YouGov, NIQ and others describe
their users, and research-practice writing):

| Who | What they want | How they ask |
|---|---|---|
| Analyst | the exact figure, how many people, a group, a change | short and precise: "Tariff concerns by generation" |
| Colleague (sales, editorial, events) | a number to quote, a chart to paste | plain words: "What do consumers say about Amazon Prime?" |
| Client (retailer, brand, investor) | a decision | "Which generation over-indexes on Temu?" |

**First score on the big exam: 45%.** That number started everything that follows.

---

## Part 5. The fixes that needed no AI at all

### 5.1 Nicknames for every survey question

Survey questions are written formally: *"Do you have membership to Amazon Prime or access to Amazon Prime through
membership of someone else in your household?"* Nobody types that. They type *"Amazon Prime membership"*.

So every survey question got **nicknames** (we call them names and aliases), written once by a small AI model:

```
  Survey question (formal)                              Nicknames people actually use
  ─────────────────────────────────────────────────     ─────────────────────────────────
  "Do you have membership to Amazon Prime or…"     →    "Amazon Prime membership status"
                                                         "Prime membership", "Amazon Prime access"
  "Which, if any, of these retailers have you      →    "Retailers bought from in past two weeks"
   bought any NONFOOD products from…"                    "Nonfood retailers", "Where people shop"
```

When a question uses a nickname, Ask goes straight to that survey question. We call those answers **Verified**.

> [!TIP]
> **Result:** of 29,838 exam questions answered through a nickname, **99.3% were right**. This is the same idea the big
> data companies use (Snowflake calls it "verified queries", Databricks "trusted assets").

### 5.2 Small reading mistakes, fixed at the root

| The mistake | Example | The fix |
|---|---|---|
| Survey wording read as a date | "used in **the past month**" made Ask look only at last month | "past month" is the survey's own words, not a period; "last month" still is |
| "Since" misread | "since **Aug 2025**" meant only August | now means August 2025 onwards |
| Groups not recognised | "**Which generation**…", "**women or men**…", "**South vs West**" | all read as "split by this group" |
| More vs less mixed up | "spend **more**" and "spend **less**" looked the same | direction words kept |
| A quoted answer taken as the topic | "chose **"Yes"**" found the tax-return question | a quoted answer is an answer, not a topic |

### 5.3 The score, climbing

Each fix was tested on **the same 5,000 exam questions**, so we know exactly what each one bought:

```
  71.3%  ███████████████████████████████████▋               start (with nicknames)
  75.4%  █████████████████████████████████████▋             survey wording, periods, quoted answers
  79.0%  ███████████████████████████████████████▌           "which generation", "women or men" as groups
  82.0%  █████████████████████████████████████████          more vs less; a study that has the group asked for
  91.5%  █████████████████████████████████████████████▊     shared nicknames handled; "rising or falling" = trend
```

---

## Part 6. Every new survey, handled automatically

A new survey arrives every week. Before, a person had to remember to run a step for its questions to get nicknames.
Now it is an **assembly line** that runs by itself every time data is published:

```
  New survey published
        │
        ▼
 ┌──────────────────────┐   A small AI model gives each new question its nicknames
 │ 1. NAME               │   and 8 example questions.  Cost: about $0.002 per survey
 └──────────────────────┘
        │
        ▼
 ┌──────────────────────┐   If two different questions got the same nickname, each gets its own
 │ 2. SPLIT LOOK-ALIKES  │   ("Economic outlook" was given to both "the economy" and "price rises")
 └──────────────────────┘
        │
        ▼
 ┌──────────────────────┐   Every question an analyst might ask about the new survey is asked,
 │ 3. CHECK              │   and the answers are marked right or wrong.  About 6 seconds per survey
 └──────────────────────┘
        │
        ▼
 ┌──────────────────────┐   On the Logs page, one row per survey: how many questions,
 │ 4. REPORT             │   how many right, and the misses to look at
 └──────────────────────┘
```

> [!NOTE]
> On the four newest weekly surveys, **99.1% to 99.6%** of all questions analysts might ask were answered right.

---

## Part 7. AI from zero: the ideas you need

These are the only AI ideas needed to follow the rest. Each has an everyday comparison.

### 7.1 What is an AI "model"?

> [!NOTE]
> **A model is a recipe with millions of adjustable dials.** Text goes in, the recipe runs, a result comes out.
> **Training** means turning the dials, a tiny bit at a time, until the results are good.

Our search model has about **33 million dials**. ChatGPT-class models have **hundreds of billions**. Ours is small on
purpose: small means fast and cheap, and it only has to understand questions about our surveys.

### 7.2 Tokens: cutting words into pieces

Before a model can read, text is cut into pieces called **tokens**, like cutting a sentence into Lego bricks:

```
  "Which retailers do Gen Z prefer?"
     │
     ▼
  [which] [retail] [##ers] [do] [gen] [z] [prefer] [?]      ← each brick is just a number to the model
```

Our model knows about 30,000 different bricks. ChatGPT's newest models know about 200,000.

### 7.3 Embeddings: a map of meaning

> [!TIP]
> **Imagine a giant map where every question is a pin.** Questions that mean the same thing are pinned close together,
> even if they use completely different words. That map is what AI people call **embeddings**.

```
                     (a tiny corner of the map)

        • "Amazon Prime membership"
        • "Do you have Prime?"              ← close together: same meaning
        • "Share with an Amazon Prime account"

                                                    • "Holiday spending plans"
                                                    • "How much for Christmas?"   ← another neighbourhood

    • "Tariff worries"
    • "Are people concerned about tariffs?"
```

Each pin's position is written as **384 numbers** (like GPS coordinates, but with 384 directions instead of 2). Nobody
places the pins by hand: the model learns where they go.

### 7.4 Search by meaning

When someone asks a question, Ask:
1. puts a pin for the new question on the map (about 0.0015 seconds),
2. looks for the nearest survey-question pins (about 0.001 seconds),
3. takes the closest.

This is how Ask understands *"Do people have Prime?"* even though no survey question uses those exact words.

> [!NOTE]
> **Do we need a "vector database"?** No. Those are for maps with millions or billions of pins. Ours has about 25,000,
> which a normal computer checks in a thousandth of a second, using no extra software or cost.

### 7.5 The transformer: how the model reads

The model reads a sentence the way a careful person does: **every word looks at every other word** to work out what it
means here. In *"Which stores do people **shop** at"*, "shop" leans on "stores" and "people". This mechanism is called a
**transformer**. It is the "T" in ChatGPT (Generative Pre-trained **Transformer**), and our small model uses the same idea.

### 7.6 Training: learning with flashcards

> [!TIP]
> **Training is like studying with flashcards.** On the front: a question someone might type. On the back: the survey
> question it means. The model guesses, sees the right card, and adjusts its dials so the next guess is better.

```
   FRONT (what someone types)                 BACK (the right survey question)
  ┌───────────────────────────────────┐      ┌───────────────────────────────────────────────┐
  │ "Which dollar stores do people     │  →   │ "Which of these dollar store retailers have   │
  │  buy from?"                        │      │  you purchased from in the past three months?"│
  └───────────────────────────────────┘      └───────────────────────────────────────────────┘
```

- We showed the model **about 30,000 to 80,000 flashcards**.
- It studies them **in groups of 128** (a "batch"). In each group, every question must pick its own card out of the
  128 on the table, which forces it to notice differences.
- Going through the whole pile once is called an **epoch**. We did 1 to 5 epochs.
- Each time it picks wrong, a "mistake score" (the **loss**) tells it how wrong, and the dials move a little. Lowering that
  score over thousands of rounds *is* the learning.

### 7.7 Trick questions, and the twins problem

**Trick questions ("hard negatives").** Easy wrong answers teach little. The model learns most from *look-alikes*:

```
  Question: "WHICH dollar stores do people buy from?"   (wants a LIST of stores)
     ✔ right:  "Which of these dollar store retailers have you purchased from?"
     ✘ trick:  "HAVE YOU purchased from a dollar store?"            (a YES/NO question: same topic, wrong kind)
```

**The twins problem ("false negatives").** Our catalogue has the **same question asked by several studies in slightly
different words** (for example, the beauty-products question appears in three studies). If the model is taught that twin
#2 is a *wrong* answer for twin #1, it learns to separate things that are actually the same, and becomes **confidently
wrong**. We found 395 such twin groups.

> [!WARNING]
> This is exactly the mistake our first training round made (Part 9), and the big companies warn about it in their
> research (Baidu's RocketQA, NVIDIA's NV-Retriever).

### 7.8 Practice test and final exam

> [!TIP]
> **A student who memorises the practice test gets 100% on it and fails the real exam.** That is called
> **overfitting**. So we always keep some questions hidden from training and test on those only.

```
   Each survey question has 8 example questions:
   ┌──┬──┬──┬──┬──┬──┐ ┌──┬──┐
   │1 │2 │3 │4 │5 │6 │ │7 │8 │        + the 161 hand-written "final exam" questions
   └──┴──┴──┴──┴──┴──┘ └──┴──┘
     used to TEACH       HIDDEN: used only to TEST
```

### 7.9 Teacher and student

> [!TIP]
> **A teacher is a big, slow, very good reader. A student is a small, fast one.** The teacher grades every flashcard
> pair ("how well does this question match this survey question, from 0 to 10?"), and the student learns to give the
> same grades. Then only the small student works on our server: fast, but with some of the teacher's judgement.

This is called **distillation** (making something small that keeps the strength of something big).

### 7.10 Each thermometer has its own scale

Different models give "closeness" scores on different scales, like one thermometer showing Celsius and another
Fahrenheit. So the rules "this is too far to be related" and "this is sure enough to answer" are **measured for each
model** and stored with it (a small file called `calibration.json`).

### 7.11 Making the model small: like compressing a photo

A trained model is a big file. We store its 33 million dials with less precision (**8-bit instead of 32-bit**), like
saving a photo as a smaller JPEG that looks the same. Result: **half the size of today's model file (34 MB vs 66 MB), faster**, and the
same choices within half a percentage point. The file format is **ONNX**, a standard way to save a trained model, like
a PDF is for documents.

---

## Part 8. Why we trained our own model

### 8.1 The evidence

On wording it had never seen, the general off-the-shelf model found the right survey question only **39%** of the time.
We read 80 of its misses by hand:

```
   ┌──────────────────────────────── 80 misses, read one by one ───────────────────────────────┐
   │ 45%    ████████████████████  PLAINLY WRONG   "Why do people shop at Publix?" → department   │
   │                                              stores question; "gift ideas" → IT staffing    │
   │ 27.5%  ████████████          EQUALLY RIGHT   another study asked the same question          │
   │ 27.5%  ████████████          NO ONE ANSWER   "How does interest vary by income?" (interest   │
   │                                              in what?)                                       │
   └────────────────────────────────────────────────────────────────────────────────────────────┘
```

The plainly wrong ones come from a model that has **never seen our world**: it does not know Publix, BNPL, Prime Big
Deal Days, or what "over-indexes" means. Every big company tunes its search to its own data. Ours already had the study
material: nicknames and example questions for every survey question.

### 8.2 Why not just send every question to ChatGPT?

| | Send every question to ChatGPT | Train our own small model |
|---|---|---|
| Speed | about 1 second per question | about 0.0015 seconds |
| Cost | paid per question, grows with every user | one-off training (a few Colab units), then free |
| Numbers | outside our control | always counted from our data |
| Data | each question sent to an outside company | stays on our server |
| Works when the internet or the AI service is down | no | yes |

> [!IMPORTANT]
> **Training is a one-time effort that keeps paying back.** New surveys do not need new training: the model learns how
> people ask about retail and consumers, so it already understands questions about next week's survey. Retraining is
> only needed now and then, when the automatic checks show accuracy slipping.

### 8.3 Where the training happens

```
   ┌────────────────────────────── GOOGLE COLAB (our Google AI Pro) ───────────────────────────────┐
   │  A powerful rented graphics card (NVIDIA A100 or L4), used for ~10-50 minutes per round.        │
   │  In: the catalogue of survey questions (wording only: no respondents, no figures).              │
   │  Out: one 34 MB model file.                                                                     │
   └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                  │  download the file
                                                  ▼
   ┌────────────────────────────── OUR LAPTOP (testing) ───────────────────────────────────────────┐
   │  The new model is tested INSIDE Ask, on the big exam and the final exam, against today's model. │
   │  Only a clear winner moves on.                                                                  │
   └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                  │  replace two files
                                                  ▼
   ┌────────────────────────────── OUR SERVER (staging, then production) ──────────────────────────┐
   │  Runs the small model on an ordinary processor. No graphics card, no AI subscription needed.    │
   └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 9. The training, round by round

Each round is a full study session, followed by both exams. A round only "wins" if Ask **with** the new model beats Ask
**today** on the final exam, with the safety check on.

### Round 1 (v1): first try

| | Today's model | v1 |
|---|---|---|
| Unseen wording (inside Ask) | 39% | **48%** |
| Final exam, 161 questions | **138** right | 134 right |

> [!WARNING]
> **Lesson 1:** testing the model on its own showed +12 points; inside Ask it was almost no better. **Always test the
> whole system, not one part.**
> **Lesson 2:** the new model used a different "thermometer scale" (Part 7.10). Fixed by measuring each model's own
> settings.
> **Lesson 3 (the big one):** the twins problem (Part 7.7). v1 was taught that twins were wrong answers, so it became
> confidently wrong, and the safety check could not catch its mistakes.
> **Decision: not used.**

### Round 2 (v2): twins fixed, frequent questions weighted

What changed: the 395 twin groups were treated as one question each, and questions asked every week (which analysts ask
most) got up to 3 times more flashcards than one-off studies.

| | Today's model | v2 |
|---|---|---|
| Unseen wording (inside Ask) | 39% | **48%** |
| Final exam, always answering | **86%** | 84% |
| Final exam, answers given with the safety check | **97.6%** | ~88% |

What we found when we read its mistakes:

```
  Asked:  "WHICH dollar stores do people buy from?"
  v2 picked:  "HAVE YOU bought from a dollar store?"       ← right TOPIC, wrong KIND of question
  Asked:  "HOW MANY people take GLP-1 drugs?"
  v2 picked:  "WHY are you taking a GLP-1 drug?"            ← right TOPIC, wrong KIND of question
```

> [!WARNING]
> **Lesson 4:** the model learned *topics* very well, but not *what kind of answer* is wanted (a list, yes/no, a
> reason, an amount). Its flashcards mostly mentioned the topic.
> **Decision: not used.** Today's model stays, with the safety check.

### Round 3 (v3): the three techniques of the big labs

| Technique | In plain words | What it fixes |
|---|---|---|
| **AI-written practice questions** | A free, open AI model (Qwen2.5-7B, by Alibaba, free to use commercially) writes 12 new flashcards for every survey question, keeping the *kind* of question: "which…" for lists, "how many / do people…" for yes/no, "why…" for reasons | the "right topic, wrong kind" mistakes |
| **Trick questions checked by a teacher** | Look-alikes from the same topic are used as wrong answers, but only after a teacher confirms they are clearly wrong (so twins are never used) | fine distinctions, without the twins problem |
| **A teacher model** | A big reader (BAAI's bge-reranker-v2-m3, free) grades every pair; our small model learns its grades | makes the small model's confidence trustworthy, so the safety check works |

> [!NOTE]
> The notebook first checks whether the teacher is actually better than today's model on our questions. If it is not,
> it skips that part instead of wasting time. No paid AI service is used: only the Colab graphics card we already pay for.

**What happened (13 November 2026).** The free AI model wrote **36,570 practice questions** (all 3,076 survey questions
covered, and they kept the kind of question: "Which home products have you bought on social media?" for a list question).
The teacher check **passed**: on the final exam, today's model picks right 58.3%, the teacher reordering its top 20
picks 70.2%. Two models were trained (v3a without the teacher's grades, v3b with them), about 11 minutes each.

| Inside Ask | Today's model | v3a | v3b (teacher) |
|---|---|---|---|
| Final exam, always answering | **136** right | 134 | 129 |
| Final exam, answers given with the safety check | **97.6%** right (52% answered) | 88.2% (79% answered) | 87.6% (75% answered) |
| Unseen wording (big exam) | 38.9% | **46.1%** | 37.6% |

We also tested **letting both models vote** (answer only when today's model and v3a agree): 97.4% right on 48% answered,
no better than today's model alone, so it is not worth the extra memory.

> [!IMPORTANT]
> **Conclusion after three rounds.** Training clearly helps with new wording (+7 to +9 points), but the trained models
> are more often *confidently* wrong, so the safety check cannot lift them past about 89% on people's own wording, while
> today's model reaches 97.6%. **Today's model with the safety check stays.** What moves accuracy further now is not more
> training but: (1) the automatic renaming of shared nicknames on staging (for example "Economic outlook"), (2) real
> analyst questions saved as verified answers, and (3) a human review of four final-exam answers that look too strict
> (for example "Satisfaction with shopping in AI platforms" was answered from "How satisfied were you with your AI tool
> shopping experience?", which is right).
>
> We also tested one change to Ask's own rules (letting meaning beat a shared nickname): +1 on the final exam but 128
> wrong answers on the big exam, so it was undone. Every change is measured before it is kept.

---

## Part 10. How the big AI companies do it, and what we copied

### 10.1 How ChatGPT, Claude, Gemini and Grok work, in one picture

```
  Your message
     │
     ▼  cut into tokens (Part 7.2)
     ▼  each token becomes numbers (Part 7.3)
     ▼  a giant transformer (Part 7.5) with hundreds of billions of dials reads them
     ▼  it WRITES the reply one word at a time (that is why they take seconds)
     ▼  for facts, they often SEARCH documents first and read them ("RAG": retrieve, then generate)
  The reply
```

| | ChatGPT (OpenAI) | Claude (Anthropic) | Gemini (Google) | Grok (xAI) |
|---|---|---|---|---|
| Brick vocabulary (tokens) | ~200,000 | not published | ~256,000 (reported) | 131,072 |
| Published design details | few | few | few | the older Grok-1 is fully published: 314 billion dials, "8 experts, 2 at a time" |

> [!IMPORTANT]
> **Why Ask can be faster than all of them:** they *write* answers word by word. Ask does not need to write: its
> sentences, chart and table are filled from numbers it has counted, in about **0.01 seconds**. And it cannot invent
> a number, which a writing model can.

### 10.2 What the big companies do when they answer questions about their own data

| Company | What they built | The lesson for us |
|---|---|---|
| Snowflake | "verified queries": approved answers to common questions | our Verified nicknames |
| Databricks | "trusted" label on approved answers; tests with 2-4 wordings of each question | our Verified label; our exam |
| Uber | first decide the business area, then search inside it | our country and topic narrowing |
| Pinterest, LinkedIn | good descriptions of each table matter more than the AI model | our nicknames and example questions |
| Anthropic | search by words AND meaning together, plus a re-reader | our nicknames + words + meaning |

### 10.3 How the big labs train search models (the five techniques)

| # | Technique | Who | Simple comparison | Status at Coresight |
|---|---|---|---|---|
| 1 | AI-written practice questions | Microsoft, Google | a tutor writes extra practice questions | Round 3 |
| 2 | Never teach a right answer as wrong | Baidu, NVIDIA | do not mark a twin's answer as a mistake | Round 2 (twins) + Round 3 (teacher check) |
| 3 | Teacher and student | GPL, BAAI | the student copies the expert's grades | Round 3 |
| 4 | Words and meaning together | BAAI, Anthropic | the librarian checks the title and the summary | Done |
| 5 | Measure the whole system | everyone | test the whole car, not one part | Done (both exams, every survey) |

---

## Part 11. The "which did you mean?" safety check

> [!TIP]
> **A good waiter does not guess.** If you say "a coffee" and they have three kinds, they ask "which one?". Ask now does
> the same.

How it works: when Ask finds a question by meaning, it measures **how much better the best match is than the next
*different* question** (twins do not count as different). If the lead is too small, Ask shows the 2-3 closest survey
questions as buttons: *"Choose one"*. Where the AI check is switched on, the AI settles it automatically in about a
second.

An illustration (the scores are made up to show the idea):

```
  "Gym visits by generation"
        │
        ▼
  best match:   "Which of these have you done in the past two weeks?"   (includes "visited a gym")  0.71
  next match:   "Do you have access to a gym?"                                                       0.70
        │
        ▼  too close to call
  Ask shows:  Choose one   [ Activities in past two weeks ]  [ Access to a gym ]
```

| Today's model | Answered right away | Of those, right |
|---|---|---|
| Big exam, without the check | 96% | 93.9% |
| **Big exam, with the check** | **83%** | **98.7%** |
| Final exam, without the check | 98% | 86.0% |
| **Final exam, with the check** | **52%** | **97.6%** |

> [!NOTE]
> The trade-off: more "which did you mean?" questions, in exchange for almost never giving a wrong answer. A
> better-trained model (Round 3) should answer more questions right away at the same accuracy.

---

## Part 12. Cost, speed, memory, and where things run

### 12.1 On our server (staging), measured

| What | Amount | Plain meaning |
|---|---|---|
| Time per new question | **~0.01 seconds** of one processor | about 100 new questions a second |
| Time per repeated question | **~0** | remembered from the last 500 answers |
| Memory used by Ask | **~375 MB** of the server's 4 GB | under a tenth of the machine |
| Database use | **none** for answers | only a one-line note per question in the audit log |
| Stored file | 14.6 MB | the map of meaning, saved so it loads in 0.1 seconds |
| From India | ~0.23 seconds | the distance to the US data centre, not our code |

### 12.2 Money

| What | Cost |
|---|---|
| Most questions (Verified or sure) | **$0** |
| Unsure questions, if the AI check is on | ~$0.0002 each, capped at **$0.50 a month** |
| Naming a new survey's questions | ~$0.002 per survey |
| A training round on Colab | 1 to 7 "compute units" from the Google AI Pro plan (no extra bill) |

### 12.3 What leaves the company

| Where | What is sent | What is never sent |
|---|---|---|
| Google Colab (our company account) | survey question wording, nicknames, example questions | respondents, answers, figures |
| OpenAI (existing key, small model) | new survey question wording (naming); unsure questions (AI check, optional) | respondents, figures |

---

## Part 13. Questions a manager usually asks

**Will Ask ever be 100% accurate?**
For questions our surveys asked, the answers it *gives* can be pushed very close: 97.6% to 99.3% today, depending on the
kind of question. No system in the world is 100% on every possible wording, because some questions have no single
right answer ("How does interest vary by income?"). The honest promise is: **every answer shown is right, and when Ask
is unsure, it asks.**

**What if someone asks about something our surveys never asked?**
Ask says so: "None of the surveys asks this." It never makes up an answer. Example: "What is the stock price of Nvidia?"

**Do two people asking the same thing in different words get the same number?**
Yes: once Ask has found the survey question, the number is counted the same way, from the same data. The work in this
document is about making sure different wordings find the same survey question.

**Do we need to train again every week?**
No. The model learns how people ask about retail and consumer topics, so it understands next week's survey questions
without retraining. New questions get their nicknames automatically after each publish. Retraining happens only now and
then, when the automatic checks show a drop.

**Why not use ChatGPT for everything?**
Slower (about 1 second), a cost per question that grows with use, numbers outside our control, and our questions sent to
an outside company. Our way: fast, nearly free, and the numbers always come from our data.

**How do we know it works?**
Two exams with answer keys (about 40,000 to 50,000 questions, and 161 written by people), run after every change. And
every new survey is checked automatically after it is published, with the result on the Logs page.

**What did this cost?**
Engineering time; under $1 of AI usage; a few Colab compute units per training round, inside the Google AI Pro plan.

**Is any respondent data sent outside?**
No. Only the wording of the survey questions; never who answered or what they answered.

**What happens if the AI services are down?**
Ask keeps answering: its search model runs on our own server. Only the optional AI check for unsure questions would
pause, and Ask would show "Choose one" instead.

---

## Part 14. What happens next

1. **Shared nicknames renamed** automatically at staging's next publish (fixes questions like "Economic outlook").
2. **Ask learns from every AI check (built 13 Nov):** when the AI settles a question, its reading is kept, and the same or a
   close question is then answered from it at once, with no AI call, for everyone. AI use falls as people use Ask
   (the "Cache & Distil" pattern from ACL 2024: the small model takes over what the large one has already settled).
3. **Deploy** the safety check and the automatic survey checks to staging (waiting for the next push).

---

## Part 15. Log

| Date | Step | Result |
|---|---|---|
| 12 Nov 2026 | Staging problems fixed (country, small groups, periods, off-topic) | final exam 84% |
| 12 Nov 2026 | The big exam written (10,707 → ~50,000 questions); first score | 45%; 71% once nicknames were used |
| 12 Nov 2026 | Root-cause reading fixes; automatic per-survey workflow; Verified vs Best match | Verified 99.3%; newest surveys 99.1-99.6% |
| 12 Nov 2026 | Research: how ChatGPT, Gemini, Claude, Grok and data companies work | the structure is right; meaning search and a safety check were missing |
| 12 Nov 2026 | 80 misses read by hand | 45% wrong, 27.5% equally right, 27.5% no single answer |
| 12 Nov 2026 | Training round 1 (v1) on Colab | unseen wording +8 pts; final exam 134 vs 138; not used |
| 12 Nov 2026 | "Which did you mean?" safety check; per-model settings | final exam: 97.6% of answers given are right |
| 12 Nov 2026 | Training round 2 (v2): twins as one question, frequent questions weighted | unseen +9 pts; right topic, wrong kind; not used |
| 13 Nov 2026 | Training round 3 (v3): 36,570 practice questions by Qwen2.5-7B, teacher check passed (58.3% → 70.2%), v3a and v3b trained | inside Ask: v3a 134 vs 136, safety check 88.2% vs 97.6%; not used |
| 13 Nov 2026 | Two-model vote tested; "meaning beats shared nickname" rule tested | vote 97.4% on 48% (no gain); rule +1 final exam, −128 big exam: undone |
| 13 Nov 2026 | Decision | today's model + safety check stays; next: renaming on staging, verified real questions, review 4 final-exam answers |
| 13 Nov 2026 | Live test on staging after the deploy: 52% right at once, 91% after the AI check, the AI called for 80% of questions; memory 500 MB → 1.1 GB and a 7-minute wait during a one-off vector rebuild | causes found and fixed (Part 17) |
| 13 Nov 2026 | Instant answers again; Ask learns from AI checks; rebuilds in a separate process; number-first headlines; v4 reranker notebook | waiting for deploy / Colab run |
| 13 Nov 2026 | Whole-app debug: time per stage, accuracy by kind, every remaining miss read; learned answers were saved by a code 115 codes share: fixed (saved by the question's own key); v5 notebook | second ask 81% → 88% with no AI; v5 ready (Part 18) |

---

## Part 17. 13 November: what the live test showed, and what changed

**What you saw on staging** (and why):

| What | Why | Fixed by |
|---|---|---|
| CPU at ~54% and memory at 833 MB-1.1 GB right after the deploy | the saved "map of meaning" file was renamed (one file per model), so the server re-drew all 18,394 pins on its single CPU for 7 minutes, and kept the memory it used | re-drawing now happens in a separate helper program that gives its memory back when it finishes (measured: +341 MB instead of +1,086 MB) |
| One question took 7 minutes | the AI check waited for a lock the re-drawing held the whole time | the lock is held only while reading or writing the file |
| Answers felt slow | the "which did you mean?" check sent half of all questions to the AI (live: 79 of 161) | the best answer shows at once; the AI confirms or corrects it a second later |
| The AI was used for 80% of questions | each unsure question asked the AI again, even if asked before | every AI decision is kept; the same or a close question is answered from it at once |

**How the big systems keep AI use low** (research): a small fast model answers what it is sure of, a large model only
the rest, and every large-model decision is stored and used to train the small model ("Cache & Distil", ACL 2024;
semantic caching). The best search systems use two stages: a fast search, then a small "re-reader" that reads the
question with each of the top few candidates (our test: 58% → 70% with a large re-reader). The v4 Colab notebook trains a
small re-reader (22 million dials, a few milliseconds) from the large one, on far more and more varied practice
questions, including "this one, not that look-alike" questions.

**How answers are written** (research: Pew Research Center's headlines, Perplexity): the finding first, with its number
and who was asked; then the evidence; the source one click away. Ask's first sentence now reads: *"53.0% answered 'I have
an Amazon Prime membership myself' in 12 Oct 2026, the latest (214 of 404 respondents)."*

## Part 18. 13 November, later: is 99.99% reachable, where the time goes, and the one notebook left (v5)

Method: the whole app taken apart and measured, not guessed: the network from India to the server (curl's timing of each
step, and one kept-open connection as a browser uses), the server stage by stage (a profiler over the 161 final-exam
questions), the page's code bundle (REA's JavaScript analysis of `frontend/out`, evidence
`ev_66a5b01823d638442eb3a5536dc13d563813271c7820b495f35d0e1d5157fa81`), and every question still wrong, one by one.

### The one number: right answers

**Right answers** = of the questions people ask, the share where the answer Ask finally shows is the correct one (the right
survey question, period, group and kind; or "not in the surveys" when that is true). Measured on the 161 hand-written
questions (the final exam), the way the page asks: the instant answer, then the AI check where Ask is unsure.

| When | Right answers |
|---|---|
| Staging, 12 Nov (old code) | 91% |
| 13 Nov, learned answers kept by key, today's AI check (gpt-4o-mini) | 91.3% |
| 13 Nov, rules fixed, each survey question shown to the AI once, answers it names first | 93.8% |
| The same, with gpt-4.1 as the AI check (a setting, no code) | **96.3%** (155 of 161) |
| Goal | 99% |

What 99% needs, from what is still wrong (6 of 161 with gpt-4.1):

| Still wrong | Why | What fixes it |
|---|---|---|
| "How do Chinese consumers feel about the economy?" | this laptop has no China surveys | right on staging, which has them (to confirm after deploy) |
| "Economic outlook by generation" | the alias "Economic outlook" was given to an inflation question | the per-publish renaming on staging (to confirm) |
| "Which retailers do Gen Z prefer?" | "prefer" fits both the feelings question and the shopping lists | a judgement call: the answer key's choice (shopping lists) to be confirmed by an analyst |
| "walmrt shoppers" | a typo hides "Walmart" from the retailer rule; the AI picked the mass-merchants question | v5 (it learns typos from practice questions) |
| "What share of women started holiday shopping" | "started" fits "when do you expect to start" better in words than "status of your holiday shopping" | v5 (contrast practice questions) |
| "Are people cutting back on dining out because of tariffs?" | no survey asks it; the AI still answers from the nearest tariff question | v5's "none of these" score |

**Why no notebook alone reaches 99%:** a model can only choose among the candidates the search found (the right one is
among the nearest 10 for 95.4%, 20 for 97.4%, 30 for 98.7%), and a stronger AI alone did not help (gpt-4.1 90.7% vs
gpt-4o-mini 91.3% before the fixes): the misses were mostly *our own rules overruling a right pick* (below), and answer
keys, and judgement calls. v5 is the last notebook to design; after it, the same notebook re-runs monthly on real
questions.

### 13 November, deeper debug: the AI picked right, and our rules overruled it

The AI's own pick was compared with the final answer for every question it read (128 of 161):

| | gpt-4.1 | gpt-4o-mini |
|---|---|---|
| AI right, final right | 108 | 106 |
| **AI right, final wrong (a rule overruled it)** | **7** | **5** |
| AI wrong, final right (a rule rescued it) | 5 | 8 |

So the rules rescued about as many as they broke: removing them would not help; fixing the ones that broke did. Fixed, each
checked on the final exam and the 38,316-question bank (bank with no AI: 77.8% → 80.7%; 1,122 questions fixed, 26 worse):

| Rule | What went wrong | Now |
|---|---|---|
| A retailer named → the long-running retailer list | "How do people feel about Target?" answered from the purchases list | not when the pick shares more of the question's words |
| Few waves → the same answers asked over more waves | "your finances" answered from "the economy" (both much better … much worse); "Don’t know" with a curly apostrophe was not seen as generic | a 5-point scale must also match in wording |
| A trend → the first question with history | "online grocery trend" answered from grocery categories (3 waves) | the one with history that names most of the question |
| Not asked in the period → only a retailer's other list | "online last month" said "not asked" | the same question in another study too |
| The AI's list | one question filled 4 of 14 places; answers cut to 6 × 20 letters ("movie theater" was 13th) | each question once; the answers the question names first, 32 letters |
| A learned answer | saved by a code 115 codes share: 13 of 161 came back from the wrong study | saved by the question's key |
| A top list for one group | "Top 5 in 9 Nov" for Gen Z alone read as everyone's | "Top 5 among Gen Z" |

Two answer keys were wrong (Ask was right): "Satisfaction with shopping in AI platforms" (*How satisfied were you with the
shopping experience in the GenAI platform?*) and "How has weight loss medication changed apparel purchases?" (AP11).

**v4, tested inside Ask:** with today's search model and the confidence check, 85 of 161 are answered at once and 98.8%
of those are right; with v4's reranker, at no threshold were 98% of those answered at once right (best 97.3%, on 73), and it
added 44 ms and 93 MB. v4 is not used. The reason is in its design: it learned only the order of candidates, from a teacher
right 70% of the time, so its scores do not say how sure it is. v5 changes exactly that.

### Where the time goes (one question, from India)

| Step | Time | Who pays it |
|---|---|---|
| Opening the connection (first question of a visit) | ~460 ms | once per visit |
| The trip to the server in Central US and back | ~230 ms | every question, from India (~30-60 ms from the US) |
| The server: read, search, compute the figures, write the answer | **20 ms** typical, 39 ms at worst (95th), 63 ms max | every question |
| The AI check, when the question is new | 1-3.4 s, *after* the answer is already on screen | new, unsure questions only; then learned |
| The chart library (197 KB) | ~1.9 s, first visit only | cached for a year after |
| The Ask page itself | an 11 KB file | once |

Measured on staging over one kept-open connection: **235-310 ms per question**, of which ~230 ms is distance. The 790 ms
measured earlier included opening a new connection for every question, which a browser does not do. The 7-minute
question was the lock fixed in Part 17. **The server is already milliseconds; what is left is the distance to Central
US**, which only hosting near the people asking would remove.

### Why the answers read like a list, and the professional format

What Ask shows today, for *"Economy better or worse, every 4 weeks"*:

> 24.8% answered "About the same" in 19 Oct 2026 – 9 Nov 2026, the latest (399 of 1,611 respondents).
> • 29 periods, every four weeks, 25 Mar 2024 – 1 Apr 2024 to 19 Oct 2026 – 9 Nov 2026:
> • "About the same": 31.2% (25 Mar 2024 – 1 Apr 2024) → 24.8% (…), -6.4 pts. Highest 31.4% (22 Jul 2024), lowest 15.8% …
> • (four more lines like it)

Five problems: the headline is the *middle* answer, not the finding; "answered" is used for every question; dates are
ranges where a reader expects "4 weeks to 9 Nov 2026"; a scale (worse … better) is never added up into worse vs better;
and each line packs six numbers. How professional research is written (Pew Research Center, Gallup, Morning Consult;
Perplexity and ChatGPT for answers): **one sentence with the finding, then 2-4 key figures, the chart titled with what
it shows, two short "what stands out" points, and the source and base in one line underneath.**

The same answer, written that way (figures from the same data):

> **Economic outlook, next 12 months**
> **41.4% of US adults expect the economy to get worse over the next 12 months; 27.2% expect it to get better** (4 weeks to 9 Nov 2026).
>
> | Worse | Better | About the same |
> |---|---|---|
> | **41.4%** · −2.4 pts | **27.2%** · +3.0 pts | **24.8%** · −0.5 pts |
> | vs the previous 4 weeks | | |
>
> *(line chart: worse vs better, Mar 2024 to Nov 2026)*
>
> **What stands out:** "Much worse" peaked at 21.4% (May 2026) and is at 18.0% now; the latest changes are not significant.
>
> Source: Coresight Research US Consumer Tracker, CS2 "And thinking about the economy overall over the next 12 months…",
> 84 waves, Mar 2024 – Nov 2026, latest base 1,611 · unweighted · Open in Trends →

And *"Top beauty retailers"*:

> **Where people bought beauty products, past three months**
> **Walmart leads: 42.8% bought beauty products there, ahead of Amazon.com (32.2%) and Bath & Body Works (16.7%)** (week of 28 Sep 2026, 264 respondents).

What makes this possible without an AI call per question: each survey question needs a **chart title** and a
**headline pattern** ("{share} bought beauty products from {answer}"), and for a scale which answers count as positive
or negative. v5 has Qwen write and check them once for all 3,076 questions (free, on Colab); each new survey's questions
get theirs at publish (the naming step that already runs, ~$0.001 a survey). The server fills in the numbers.

### v5: one notebook, everything the analysis asked for

`scripts/colab/train_search_model_v5.ipynb` (A100, ~80 minutes, ~15-20 compute units; ~25 minutes less with v4's
`synthetic-v4.json` uploaded):

| Step | Why (the measurement behind it) |
|---|---|
| 1. Today's search: is the right question in the top 1 / 5 / 10 / 20? | the re-reader can only pick what the search found |
| 2. Qwen writes off-topic questions, and a chart title and headline pattern for every survey question (checked: one {share}, no numbers) | "not in the surveys" needs examples; the professional format needs the patterns |
| 3. Round-trip check: a practice question is kept only if Qwen, shown its survey question among the 4 closest others, picks it; Qwen's own accuracy is printed, and its rejections are used only if it is right ≥ 80% on the final exam | v1-v3 learned from practice questions that fit two survey questions equally: confident and wrong |
| 4. The search model trained to *find* (right one in the top 20); twins never in one batch; kept only if it finds more than today's | 8 misses were 3rd-10th |
| 5. The large re-reader scores the nearest 20 for 60,000 practice questions | the teacher |
| 6. The small re-reader (22M dials) learns the teacher's order **and** a yes/no per candidate, with off-topic questions all no | v4 learns only the order: its score cannot say "none of these" or how sure it is |
| 7. Depth (5, 10 or 20), the gate (the lead needed to be right 99% of the time on unseen wording) and the floor (under it: "not in the surveys"), measured | thresholds belong to the model (Part 11) |
| 8. Both shrunk to 8-bit, checked with the server's own code, timed on one CPU thread | memory and speed on the 1-CPU server |
| 6, after v4: learns mostly from the known right answer (80%), the teacher's order 20% | v4's student copied its 70%-right teacher |
| 6: a "wrong" candidate the teacher rates as good as the right one is not taught as wrong | the same thing asked another way (NVIDIA's NV-Retriever) |
| 6-7: the epochs' weights averaged ("model soup"), kept if better on held-out wording | Qwen3 Embedding and Gemini Embedding both do this |

How the large labs train, and what v5 takes from each (their published reports): Qwen3 Embedding trains first on ~150
million pairs written by a large model, then on ~12 million kept by a quality filter, then averages checkpoints; Gemini
Embedding has Gemini remove wrong examples and pick the hard "looks right but is not" examples; NVIDIA's NV-Retriever drops
"wrong" examples scored nearly as high as the right one; Llama 3 is trained in six rounds, each adding the best of many
answers chosen by a judge model. v5 is the same recipe at our size: practice questions written by Qwen, kept only if a
judge agrees, hard look-alikes, near-equals not taught as wrong, checkpoints averaged, and a fixed exam it must beat.

**The first run's checks (13 Nov, on an L4):** two of Qwen's outputs failed and were replaced before training.
Qwen2.5-7B as the round-trip judge was right on only 67% of the final exam, so (as designed) its rejections were not
used; and 948 of its 2,131 "off-topic" questions were ones a survey can answer ("What percentage of consumers read
reviews before buying online?"), which would have taught the re-reader to refuse real questions. Done instead, on the Mac
with the server's own search model: gpt-4.1 marked the answerable "off-topic" ones (1,111 truly off-topic kept, $0.09),
and gpt-4.1-mini was the round-trip judge (right on 85% of the exam, names a wrong question 7.6% of the time, mostly the
same question from another study; gpt-4.1 agreed with 74% of its rejections on a 300 sample). It removed 19,085 of the
65,099 hard practice questions (29%, $8.57): mostly real labelling mistakes, such as "What is the main reason you have an
Amazon Prime membership?" written for "Do you have Prime?". Every survey question keeps at least 5. The checked file is
uploaded as `qwen-v5.json`, so a re-run skips Qwen (scratchpad `check_off.py`, `roundtrip.py`).

Re-running monthly: upload staging's `logs/ask-learned.json` as `learned.json`; real questions count three times.

**Before v5 goes live** (after its zip comes back, as with every round): tested inside Ask on the final exam and the
big exam; the server reads the depth, gate and floor from the re-reader's `calibration.json`, retrieves 20 candidates
(today 14), and applies the retailer-list rule only when the re-reader is unsure. Memory: the 8-bit search model is
about half today's file (34 vs 66 MB), the re-reader about 23 MB; together about what Ask uses today (~375 MB in one
process). CPU: the re-reader adds ~20-40 ms to an unsure question, on the server's one CPU.

**v5 tested inside Ask, 14 Nov 2026: not shipped.** No OpenAI at all (the key removed, any call raises); every question
answered with its margin kept (scratchpad `v5_test.py`, `v5_gate.py`). In Colab v5 found more (right one in the top 20:
86% → 92% of the final exam) and its re-reader picked better than v4's (76% vs 72%), but inside Ask, where names, rules
and retailer lists already decide much, it changed little:

| Right answers, no AI, always answering | Final exam (161, people's wording) | Big exam (3,000 sampled) | Peak memory |
|---|---|---|---|
| Today (bge-small, no re-reader) | 86.3% | 83.1% | 463 MB |
| v5 search alone | 82.6% | 84.5% | 475 MB |
| v5 search + v5 re-reader (10) | 87.0% | 84.3% | 629 MB |
| Today's search + v5 re-reader (5) | 87.0% | 84.2% | 519 MB |

Answered at once (no AI) at the same accuracy, v5 is no better: today 53% of the final exam at 98.8% right (gate 0.04);
today's search with v5's re-reader 48% at 97.4% (lead 0.5). Its own calibration says the same: to be right 99% of the
time on unseen wording it needs a lead of 0.98, which 1.6% of questions reach. Why: a student copies its teacher, and
the teacher (bge-reranker-v2-m3) is right on 77% of the final exam, below Ask's own 86%. On the big exam the errors are
mostly in answers by name (81% of its questions, 91% right), which no search model changes. A better local model needs a
better teacher: a large open model on Colab, measured on the final exam in Ask's own format before any training.

**The teacher test, 14 Nov 2026** (`scripts/colab/test_teacher.ipynb`; scratchpad `teacher_ask.py`): the 128 requests
Ask sends its AI for the final exam were saved on the Mac (nothing sent), answered on a Colab A100 by Qwen3-32B (4-bit,
5 minutes), and its replies given back to Ask in the AI's place, no OpenAI. Right answers: **153 of 161 (95.0%)**, against
139 with no AI, 151 with gpt-4o-mini and 155 with gpt-4.1. All 128 replies were valid JSON; 20 used "week" for the
grain, which OpenAI's strict format would not allow, scored the same read as "wave" or "auto". It shares 4 misses with
gpt-4.1, gets "walmrt shoppers" and "Gen Z prefer" right where gpt-4.1 does not, and misses 4 gpt-4.1 gets (dining-out
trend, personal-finance outlook, tariff cut-backs, gas-price trend). Qwen2.5-32B did not load (neither copy). So an open
model on Colab is good enough to teach the next round (v6); running it in Ask itself would need a GPU server.

### v6: Ask picks on its own, no AI API (built and run 14 Nov 2026; results below)

**Where the no-AI answers go wrong** (scratchpad `decompose.py`, no OpenAI): of the final exam's 22 misses, 19 are the
*choice* (the right survey question is among the 10 candidates, the wrong one is picked), 2 are "not in the surveys"
answered anyway, 1 is China (no China data on the Mac); none is the search (at 10 candidates the right one is always
there) and none is the reading (period, group, kind). And Qwen3-32B's *pick alone*, the rules doing the rest, scored 154
of 161 (one more than its full reply). So v6 has one job: pick the right candidate, or "none of these".

**What v6 is** (`scripts/ask_v6.py export` on the Mac, then `scripts/colab/train_search_model_v6.ipynb`, ~2½-3 hours on
an A100, then `scripts/ask_v6.py score` on the Mac): Ask builds the request it would send its AI for 12,281 practice
questions (the analysts' asks, the checked practice questions, 602 off-topic; the golden set and the whole big exam kept
out); Qwen3-32B (AWQ, on vLLM, its reply held to Ask's own JSON schema) picks for each; the hard ones are read again
with thinking, only if thinking does better on the tests; a small cross-encoder (MiniLM L6 and L12, both trained) learns
the picks from exactly the line the AI reads (waves, years, name, wording, answers: v5's never saw waves, and 3 of
Qwen's 7 misses turn on them), with "none of these" as one of its choices. Both come back as 8-bit server files with
their picks for the tests, scored inside Ask with no AI.

**What it can reach, honestly.** The research (RankGPT: a 440M student trained on ChatGPT's rankings beat a 3B model;
Microsoft's TnT-LLM: small classifiers trained on GPT-4's labels about equal GPT-4) says a student lands about at its
teacher. The teacher here is 154 of 161 (95.7%); v6 at its best is about that, against 139 (86.3%) with no AI today.
99% on the final exam means at most one miss, and the 7 the teacher misses are not all a model's to fix: China needs
the China data (staging has it), "Economic outlook" a stored name, and three are one-off studies picked over the weekly
tracker that asks the same thing. Ask stays answering either way: below its confidence it shows the closest questions.
To be used, the server needs a small change (the re-reader reads the AI's line and its pick is final with no AI): made
only if v6 beats today on the final exam and the big exam.

**The run (14 Nov 2026, ask-v6.zip, scored on the Mac with `scripts/ask_v6.py score`, no OpenAI).** Right answers inside
Ask, the gate off:

| In the AI's place | Final exam (161) | Big exam (3,000) | Against the rules, final · big | ms a question (Mac, 1 thread) |
|---|---|---|---|---|
| Nothing (today's rules) | 139 (86.3%) | 2,493 (83.1%) | | |
| Qwen3-32B, the teacher | 155 (96.3%) | 2,495 (83.2%) | +17 −1 · +71 −69 | (a GPU) |
| v6 L6 (Colab's picks · the Mac's) | 152 · 151 (94.4% · 93.8%) | 2,479 · 2,482 | +15 −2 · +71 −85 | 71 (95th 102), 23 MB, ~230 MB with its runtime |
| v6 L12 (Colab's · the Mac's) | 150 · 152 | 2,493 · 2,493 | +15 −4 · +74 −74 | 141 (95th 195), 34 MB |

- **The final exam (hand-checked) gains 12-13 answers; the big exam does not move.** Its key names one question where a
  near-twin is as good an answer, so its wins and losses are mostly noise: of L6's 85 losses, 53 are as good an answer by
  hand (the same question another year, a near-twin wording, "brands" asked and the key wanting "retailers"), 32 real; of
  its 71 wins, 35 real. Real: +35 −32, about even. 8 of the 32 real losses are "none of these" where the key exists.
- **What v6 still misses** (L6, 9): China (no China data on the Mac) and "Economic outlook" (the stored name): data, not
  the model; dining out by quarter and dining out over tariffs (the teacher misses them too); a typo ("walmrt shoppers",
  read as "none of these"); 4 close picks.
- **The same 8-bit file picks differently on the Mac (Arm) and on Colab (x86)**: 26 of 746 test picks for L6, 53 for L12,
  some at 0.9-1.0 (8-bit arithmetic differs by processor), worth ±1-2 on the final exam. A server must be scored on its own
  processor.
- **Thinking did not run**: all 746 thinking replies were unreadable (2,048 tokens is too few for Qwen3 to think and then
  answer), so no hard question was read again. The students agree with the teacher on 71-72% of held-out practice
  questions: the room left is there, not in the teacher.
- Not used yet: the server change (the re-reader's pick replacing the rules' choice when there is no AI) waits for a yes.

**v6 in Ask (14 Nov 2026, same day).** L6 became Ask's own reader (`models/ask-reader`, `api/ask_model.py read_pick`):
it reads every candidate's line (`describe_candidate`, the one the AI reads) and picks, or says "none of these", in ~70 ms. Its lead
over the next choice (logits; "none" = 0) decides whether the AI is asked: from a lead of 2 (`calibration.json` "sure")
its pick is final. That line was set on the notebook's 900 held-out practice questions, not on the tests: there a lead of
2 or more is 51% of questions, 90% agreeing with the teacher (6 or more: 11%, 99%); on the final exam it was 52% at 98.5%.
Without a key the reader's pick always stands; the quick answer shows it at once and asks for the AI check only when it
is unsure. Fixed on the way, each a general rule: the alias "Economic outlook" was on a 2023 inflation question and a 2022
one-off, now on the weekly economy question CS2 (84 waves) (`config/ask_semantic.json`); a misspelt retailer or brand is
put right (`ask_index.py correct_spelling`: only toward the answers of long-running retailer, brand or store lists; correcting
every unknown word changed "having" to "behaving" in the bank, this changes 6 words of 38,477 questions); a trend's
question with history counts a word no candidate uses by its synonyms ("dining out" → "Gone to a restaurant").

Live in Ask on the Mac (`scripts/ask_v6.py score … --reader`; the teacher's recorded replies stand in for the AI, as
OpenAI was not used):

| | Final exam (161) | Big exam (3,000) | AI asked |
|---|---|---|---|
| Rules only (today without a key) | 139 (86.3%) | 2,493 (83.1%) | none |
| Ask's reader, no AI | 154 (95.7%) | 2,482 (82.7%) | none |
| Ask's reader, the AI where it is unsure | 156 (96.9%) | 2,503 (83.4%) | 61 of 161 (38%) · 381 of 3,000 (13%) |

Quick answer on the Mac: median 13 → 76 ms, 95th 28 → 109 ms; memory +78 MB. Today's AI reads ~80% of questions.

**Second run (14 Nov 2026, afternoon; `ask-v6 (1).zip`), now in `models/ask-reader`.** `teacher-v6.json` was uploaded,
so the teacher was not run again (its thinking check still unreadable): the same labels, the students trained again.
The new L6, live in Ask on the Mac as above:

| | Final exam (161) | Big exam (3,000) | AI asked |
|---|---|---|---|
| Ask's reader, no AI | 154 (95.7%) | 2,495 (83.2%) | none |
| Ask's reader, the AI where it is unsure | 158 (98.1%) | 2,503 (83.4%) | 54 of 161 (34%) · 380 of 3,000 (13%) |

- Calibration holds: a lead of 2 is 52% of the held-out practice questions at 90.1% agreement. The "sure" line, swept
  inside Ask with the teacher as the AI: 1.0 → 157 · 2,505, AI 17% · 7%; 1.5 → 157 · 2,504; 2.0 → 158 · 2,503, AI 34% ·
  13%; 2.5 → 157 · 2,501; 3.0 → 157 · 2,498, AI 52% · 15%. 2.0 stays; 1.0 halves the AI's calls for one final-exam answer.
- Arm (Mac) and x86 (Colab, as staging) pick differently on 2 of 128 final-exam and 23 of 618 big-exam requests, all at
  a lead under 0.5: never where the reader is sure.
- L12: 153 · 2,498 alone, 156 · 2,502 with the AI, at twice the time: not used.
- Cost, measured again back to back (old and new reader, the same): median 13 → 75 ms, 95th 26 → ~110 ms; peak memory
  +~125 MB (the +78 MB above was one run).
- `train_search_model_v6.ipynb` now reads the thinking check again when an uploaded `teacher-v6.json` has it unreadable,
  keeping the plain picks (the long part).

**What 99% needs** (at most 1 miss of 161). The China question is right on staging (China Consumer Survey Q9, 149 waves;
the Mac has no China waves), so 159 of 161 there (98.8%) with the second run. Left:

| Miss | Why | Fix |
|---|---|---|
| "Amazon in 2025 vs 2026" | the reader is right but unsure (lead 1.67); the AI changed it to Prime membership | a better AI on the unsure third (gpt-4.1 scored 155 vs gpt-4o-mini's 151 on the whole set), or a reader sure of it |
| "Are people cutting back on dining out because of tariffs?" | no survey asks it; reader and AI answer from a tariff question | a "none of these" the AI and reader both learn (the thinking check) |

Fixed by the second run: "What share of women started holiday shopping" (the reader is now sure and right) and "Why buy
on social media instead of a store?" (now unsure, so the AI reads it, and is right).

**Third run (14 Nov 2026, evening; `ask-v6 (2).zip`), not used.** The fixed notebook read the thinking check again
with 4,096 tokens: all 746 replies unreadable again, so `teacher-v6.json` came back unchanged and the students were
only trained again on the same labels. Its L6: 155 · 2,485 alone, 157 · 2,501 with the AI, the AI asked for 64 of 161;
L12: 151 · 2,487, 156 · 2,506. Neither beats the second run. Why thinking fails is not in the files (the run's printed
lines would show it); no further Colab run is planned.

**"Amazon in 2025 vs 2026", fixed by a rule** (`api/assistant.py`, the retailer rule): a pick with the retailer in its
wording (Prime membership) stood whenever the AI or the reader made it; now only when the question asks more than the
retailer and a time (its subject, `plan["about"]`, has another word: "How many have Amazon Prime?" keeps Prime). The
model was told this rule and broke it. Live on the Mac with the second run's reader: final exam 154 alone, **159 of 161
(98.8%) with the AI on the unsure ones**; big exam 2,495 and 2,503, unchanged. On staging, with the China question,
**160 of 161 (99.4%)**; the one left is dining out over tariffs (should be "none of these").

**Staging, the same night (build 93d5104a: the second run's reader and the retailer rule), golden through the MCP
connector: 154 of 161 (95.7%), not 160.** The projection assumed an AI as good as Qwen3-32B and no learned answers; staging
has gpt-4o-mini and its learned answers (`logs/ask-learned.json`: every question the AI settled, reused for the same or a
close question ahead of the reader). Of the 7 misses, 5 were learned answers ("Which foods do GLP-1 users eat more or
less?" took the answer learned for "Do GLP-1 users eat less?", over a reader sure at a lead of 7; the AI-shopping and Gen Z
retailer questions kept gpt-4o-mini's picks), 2 were the reader unsure with no AI to check it (holiday inflation, social
media); dining out is among the 5. No live AI ran: staging's AI calls fail (the OpenAI account has no credit; the health
page still says on, and a check left its paid-call count at 479), so the reader's pick stood. The 2 reader errors staging
got right (personal finances by income, retail subscriptions) were saved answers from earlier in the month. Fixed in code: a learned answer is used only
where the AI would be asked, so a sure reader's pick stands (`api/assistant.py answer`, test
`test_a_learned_answer_gives_way_to_a_sure_reader_and_stands_for_an_unsure_one`). Lesson: the Mac harness turns learned
answers off (`scripts/ask_v6.py without_api`), so a staging run is the only real test.

**v7: better lessons, checked by Claude in the build session (14 Nov 2026, night; no API key, no credit).** Both AI
accounts were out of credit, and more runs on Qwen's labels gave no gain (three runs, Part 18), so the labels were fixed
instead. Of the 12,281 practice questions, the 1,000 where Qwen's pick is likeliest wrong (it differs from the survey
question the practice question was written from, that question among the candidates, the reader siding with it first,
then the most unsure; or Qwen's reply was unreadable; or an off-topic question got a pick) were labelled again by five
Claude helpers in parallel, each reading only the question and its candidate lines with Ask's own rules, never Qwen's pick
or the source (~2 million tokens in all, on the Claude Code plan). Added: 238 questions no survey answers (300 written: a
surveyed topic with a reason no survey asks, company facts, opinions never asked; tariffs left out so the golden set's
dining-out question stays a fair test; the 62 Ask's rules already answer "none" dropped). 40 hidden controls (Qwen, the
reader and the source agreeing, the reader sure): the helpers agree on 39 (97.5%). They changed 725 of the 1,000 labels
(the written-from question chosen in 429 of 769 where it was listed; the other picks more specific, e.g. the restaurant
technology question for a restaurant question), kept 39, and labelled 228 of the 238 new questions "none" (10 do have a
question). `v7-train.json` (12,519 practice questions with their labels; the helpers' labels in `v7-labels/`) is in
`Downloads/cip-colab`; `scripts/colab/train_search_model_v7.ipynb` trains MiniLM L6 and the smaller L4 on it with no
teacher (an L4 GPU, ~1-1½ hours), scored on the Mac inside Ask as before.

**v7's run (14 Nov 2026, night; `ask-v7.zip`): no gain, not used.** Inside Ask on the Mac (golden · big exam; the AI
column with Qwen's recorded replies standing in; today's reader with the retailer and learned-answer fixes for comparison):

| Reader | No AI | AI where unsure | AI asked (golden · big exam) | Quick answer, median · 95th |
|---|---|---|---|---|
| v6 second run (installed) | 154 · 2,495 | 159 · 2,503 | 54 · 380 | 75 · 110 ms |
| v7 L6 | 154 · 2,499 | 158 · 2,503 | 65 · 354 | (same size) |
| v7 L4 | 154 · 2,504 | 157 · 2,503 | 71 · 364 | 56 · 77 ms |

Held out, the students agree with the new labels 74.8% (L6) and 72.4% (L4); a lead of 2 is ~50% of questions at 93-94%.
Each still misses 7 golden questions with no AI, but different ones: L6 fixed the AI-assistants question and broke
"Warehouse club shoppers"; L4 fixed four and broke four, among them "Walmart in October 2026" read as "none of these".
Dining out over tariffs is still answered from TF5 (the no-answer lessons left tariffs out on purpose). Better labels on
1,000 hard practice questions did not lift the final exam: at ~154-155 of 161 without AI, the small reader is at its
ceiling for this data; L4 saves ~20 ms a question, which the ~1 s network trip from India hides, and its new mistakes are
on plain retailer questions, so it is not swapped in either.

**The fresh test: the questions people really type (14 Nov 2026, night).** Staging's audit log (65,688 asks since
23 Oct) is mostly the 10 Nov load test (51 accounts, 13 fixed questions and numbered variants); real people are 4
accounts, with 55 distinct questions outside the golden set. 50 of them (four near-repeats and the hand-fixed "Economic
outlook" left out), each answer written by reading its candidates, are `scripts/ask_fresh.yml`
(`python scripts/ask_golden.py --questions scripts/ask_fresh.yml`). With no AI, Ask's own model answered **41 of 50
(82%)**: golden's 95.7% flatters it, as golden has been tuned on. Three general fixes from its misses, **43 of 50 (86%)**
after: an event question (now also Labor Day, Memorial Day, Super Bowl, Presidents' Day, the Fourth of July, New Year,
Singles' Day, Christmas) answers only a question naming the event (`assistant.py EVENT`; "personal finances better or
worse quarterly" was the Labor Day question); "the all wave" reads as every wave (`ask_reader.py`); four event-spending
questions lost the alias "Holiday spending" (`config/ask_semantic.json`). Golden with no AI stays 154, the big exam 2,495
→ 2,496. (The replayed-AI scores moved because the event fix changed 2 golden and 40 big-exam requests, which then had no
recorded reply: not a measure.) Still wrong with no AI: "holiday spending" (the stored name step), "Ama Prime", holiday
groceries, two "bought Amazon Prime" (read as Amazon's retailer share), Prime "in all Waves" (none), tariff worry over 6
months. Eight common questions people asked are now verified answers (`config/ask_verified.yml`, by key: these codes are
reused by other studies); three more were dropped as they would answer golden questions. The fresh set has now been used
for these fixes: real questions added later, unseen, keep it honest.

**Ready for an AI key.** Saved AI answers carry the model that made them and are reused only while it is the AI
(`ask_index.py load_verified`), so a new model starts clean. The scratchpad's `openai_all.sh` tests gpt-6-luna,
gpt-4o-mini, gpt-4.1-mini, gpt-6.1-terra and gpt-4.1 in turn (each's cheapest accepted settings probed first) on golden and
the fresh set, only the reader's unsure questions sent, $1 cap in all; `claude_golden.py` does Haiku, Sonnet and Opus 5.5
($1.50 cap) once the Anthropic account has credit. A new survey needs no step: a publish rebuilds Ask's index, the vectors
of new questions are computed and kept on /home (`logs/`), after_publish names the new questions (with a working key; the
backlog is named on the next publish once it has one) and checks each new survey (Logs page), and the reader reads any new
question as it is, with no retraining. Everything saved (learned and verified answers, readings, vectors, spend, quality)
lives in `logs/`, which is /home/cip/logs on Azure (`deploy/start.sh`), on disk, not in memory.

**Would a vector database, a fuller RAG pipeline or more training help? Where the answers are lost (14 Nov 2026, night;
scratchpad `rag_test.py`, no AI).** Ask is already retrieval-augmented: the question's vector against every survey
question's and its analysts' asks', joined with a keyword ranking, a little for long-running questions and the question's
area; then the reader picks; then the figures are computed from the survey cells, never written by a model.

| | Golden | Fresh (real) | Big exam |
|---|---|---|---|
| Right answers, no AI | 154 of 161 | 43 of 50 | 2,500 of 3,000 |
| Right one first, by vectors alone (what any vector database returns with these embeddings) | 57% | 51% | 63% |
| ... in the first 10, vectors alone | 83% | 74% | 91% |
| Right one first, Ask's hybrid retrieval | 80% | 57% | 62% |
| Right one in the reader's list (≤14) | 97% | 91% | 97% |
| The reader's pick when it is in the list | 97% | 84% | 85% |

- **A vector database would not raise accuracy**: it returns at best the exact nearest vectors, which here rank the right
  question first 51-63% of the time against the hybrid's 57-80%. Speed: the exact search over today's 3,076 vectors (4.7 MB
  in memory) takes 0.07 ms; 100,000 would take 3 ms and 1,000,000 59 ms on this Mac, so a database (with its network hop,
  service and cost) pays only past a million vectors. Embedding a question: 3.3 ms.
- **Retrieval loses 3-9%** (the right question not among the 14: golden 4, fresh 4, big exam 98). Perfect retrieval would
  add at most ~4 golden, ~3 fresh and ~2.8 points of the big exam (at the reader's pick rate); a larger embedding model
  (bge-base/large, e5, gte: 2-4 times slower, +100-400 MB) is the only lever there.
- **The pick loses most**: 15-16% of real and big-exam questions whose right answer is in the list are picked wrong. Bigger
  readers (L12) and better labels (v7) did not move it; the AI on unsure questions and verified answers do.
- **Tokenization is no limit**: the reader's inputs are 74 tokens at the median and 128 at most (8,037 measured): none is
  cut at 192.
- **Generation** (an LLM writing the answer, the "G" of RAG) is left out on purpose: every figure is computed from the
  survey data, so no number can be invented; a model could only reword the text, at a cost.

**v8: bigger search models and bigger readers, on our own questions (14 Nov 2026, night; ready to run).** What the
field says (searched 14 Nov): under 1B parameters, Qwen3-Embedding-0.6B leads MTEB English v2 (~70.5, Apache 2.0) and
EmbeddingGemma-300M leads under 500M (gated licence, not tried); IBM Granite Embedding R2 (149M, ModernBERT, Apache 2.0)
and the bge family are the small open ones. For readers, Granite's reranker R2 and Alibaba's GTE ModernBERT reranker
(149M each, ~55 BEIR nDCG@10) are the newest small cross-encoders; a 2026 study (arXiv 2603.04816) finds reranking
quality follows a power law in model size (17M to 1B, the Ettin series) with diminishing returns. Products that answer
data questions in plain words reach high accuracy the way Ask's verified answers do: Snowflake Cortex Analyst's
verified query repository (and, since Oct 2025, suggestions from users' own questions) and Databricks Genie's trusted
assets; both keep their benchmark questions apart from what guides the answers (a verified query is ground truth or a
guide, not both), as `scripts/ask_fresh.yml` is kept apart from `config/ask_verified.yml`.

`scripts/colab/train_search_model_v8.ipynb` (A100, ~2-2½ hours; data: `python scripts/ask_v6.py export-search
~/Downloads/cip-colab` writes `v8-search.json`, 3,076 survey questions with 24,608 asks, 11,427 labelled practice
questions, the three tests; and `v8-tests.json`, the requests the reader reads; with `v7-train.json`) scores 12 search
models as Ask ranks (each model read as its card says; the asks' weight chosen per model on 2,000 practice questions
that are not word for word an embedded ask: 6,517 of 11,427 are, and would match themselves), fine-tunes the best two
small ones with hard negatives, trains three bigger readers on v7's labels against L6 retrained the same way, and
exports the winners as Ask loads them, with a `calibration.json` (pooling, prefixes, the asks' weight, and today's
thresholds mapped to the model's scale: absolute ones by the same share of tuning questions, added ones by its spread).
Checked on the Mac before spending units: its score gives Ask's own numbers with bge-small (golden right one first 78.8%,
in the first 14 98.0%; fresh 59.6%, 91.5%; big exam 64.9%, 96.4%), its copy of the server's embed gives Ask's vectors
(cosine 1.0), and the mapping maps bge-small's scale onto itself (near floor 0.64 → 0.640).

Made ready in Ask for it (today's models behave as before: golden 154, fresh 43, big exam 2,496): `api/ask_model.py`
reads a search model's pooling (cls, mean, last), prefixes, kept dims, length and pad token from its calibration.json,
and `api/ask_index.py` its thresholds (verified_near, ask_weight, standing, area_boost; near_floor and gate already);
the reader feeds only the inputs its model has (ModernBERT readers take no token type ids) and pads with its own token.
Verified answers when a new survey arrives: a saved or verified answer keeps its survey question's wording and is found
again when a publish renumbers a reused code (EC6 → EC6#1); `etl/ask_quality.py check_verified` asks every verified
question again after each publish (`logs/ask-verified-check.json`, warnings in the publish log). Its first run found one
wrong: "Categories purchased online in the latest survey" (verified: the weekly q3, 219 waves) was answered from EC4
(8 waves) because its words are EC4's stored name, and the name step ran before the verified ones; a verified answer
now wins over a stored name (an AI-saved one does not): 37 of 37.

Sources: [Qwen3/EmbeddingGemma on MTEB](https://www.cognee.ai/best-embedding-models),
[EmbeddingGemma](https://arxiv.org/pdf/2509.20354), [Granite Embedding R2](https://arxiv.org/pdf/2508.21085),
[Granite reranker R2](https://huggingface.co/ibm-granite/granite-embedding-reranker-english-r2),
[Scaling laws for cross-encoder reranking](https://arxiv.org/pdf/2603.04816),
[Cortex Analyst verified queries](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository),
[verified query suggestions](https://docs.snowflake.com/release-notes/2025/other/2025-10-09-verified-query-suggestions),
[Genie best practices](https://learn.microsoft.com/azure/databricks/genie/best-practices),
[hard negatives for domain fine-tuning](https://tianpan.co/blog/2026-05-05-embedding-fine-tuning-gap-domain-specific-relevance).

Even then, 99% on 161 questions is ±1.5 points: these fixes were found on the final exam, so it no longer measures new
questions fairly. A fresh set of analysts' questions, never looked at, is the honest test of 99%.

## Part 16. Glossary in plain words

| Word | Plain meaning | Everyday comparison |
|---|---|---|
| Ask CIP | the "ask a question" box in the portal | a librarian |
| Survey question | one question as the survey asked it, over all the weeks it ran | a book in the library |
| Nickname (name, alias) | the short way people refer to a survey question | a book's common title |
| Verified answer | found through a nickname: right 99.3% of the time | the librarian knows the book by name |
| Best match | found by meaning; shown with its source to check | the librarian's best guess, with the book shown |
| AI model | a recipe with millions of adjustable dials | a recipe |
| Training | turning the dials using examples until results are good | studying |
| Token | a piece of a word | a Lego brick |
| Embedding | the position of a question on the map of meaning | GPS coordinates |
| Transformer | the reading method where every word looks at every other | careful reading |
| Flashcard (training pair) | a question someone types + the survey question it means | a flashcard |
| Batch / epoch | 128 flashcards at a time / one pass through the whole pile | a study session / reading the whole book once |
| Loss | the mistake score the model tries to lower | marks lost on a test |
| Hard negative | a wrong answer that looks right | a trick question |
| False negative (twin) | a "wrong" answer that is actually right | marking a correct answer as wrong |
| Overfitting | memorising instead of understanding | memorising the practice test |
| Held-out test | questions hidden during training, used only to test | the real exam |
| Teacher / student (distillation) | a big model grades; a small one learns its grades | a student copying an expert's judgement |
| Calibration | measuring each model's own settings | each thermometer's scale |
| Quantization | storing the model more compactly | saving a photo as a smaller JPEG |
| ONNX | the standard file for a trained model | a PDF for models |
| Google Colab | rented powerful computers by the hour, in our Google plan | renting a workshop with heavy tools |
| Compute unit | Colab's measure of how much of that computer we used | hours on a meter |
| Safety check (gate) | "which did you mean?" when two answers are too close | a waiter asking which coffee |

---

## Appendix for engineers

### A.1 The pipeline

`api/ask_reader.py` (rules: country, periods, cuts, kind) → `api/ask_index.py` (stored names `named`, keyword index
`find`, vectors `retrieve`) → `api/assistant.py` (choice, margin, gate, sentences) → `api/ask_figures.py` (pooled exact
figures, numpy). Model: `api/ask_model.py` (`encoder`, `embed`, `calibration`, per-model `VECTORS`). Settings per model:
`models/<model>/calibration.json` (`near_floor`, `gate`); defaults for bge-small as shipped: 0.64 and 0.04.

### A.2 Per-survey workflow

`etl/publish.py publish` → `etl/ask_quality.py after_publish` → `etl/ask_semantic.py name_new`, `rename_shared` →
`check_surveys` → `logs/ask-quality.json` → `GET /api/v1/admin/ask/quality` → Logs page.

### A.3 Training

Notebooks: `scripts/colab/train_search_model_v1.ipynb`, `_v2.ipynb`, `_v3.ipynb`. Base model `BAAI/bge-small-en-v1.5`
(33M parameters, 384 dimensions, CLS pooling). Loss: in-batch InfoNCE (MultipleNegativesRankingLoss, scale 20), batch
128, AdamW lr 3e-5, linear warm-up 10%, 3 epochs; v2 one near-twin group per batch and long-running questions weighted
up to 3x; v3 adds Qwen2.5-7B-Instruct synthetic queries (type-faithful), positive-aware hard negatives (teacher
probability < 95% of the positive's, NV-Retriever), MarginMSE distillation from `BAAI/bge-reranker-v2-m3`. Export:
`torch.onnx.export` (opset 17, classic exporter), `onnxruntime.quantization.quantize_dynamic` (QInt8), verified with the
server's encode path.

The training step (v2):

```python
def train(epochs, with_hard, lr=3e-5, batch=128, scale=20.0):
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=DEVICE)
    ...                                                                      # batches: one near-twin group each
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    for step in steps:
        a = emb([typed question for each pair])                              # 128 typed questions → vectors
        targets = [right survey question for each pair] (+ look-alikes)
        loss = cross_entropy(a @ emb(targets).T * scale, arange(len(step)))  # each must pick its own
        loss.backward(); opt.step(); sched.step(); opt.zero_grad()
```

### A.4 Results in numbers

| Model | Search alone, unseen / golden | Ask: bank / unseen / golden | Golden with gate (answered / right) |
|---|---|---|---|
| bge-small as shipped | 39.0% / 58.3% | 91.6% / 39.3% / 138 | 52% / 97.6% (gate 0.04) |
| v1 (3 epochs) | 50.8% / 66.9% | 92.5% / 47.6% / 134 | 63% / 89.2% (gate 0.08) |
| v2a (twins, weighted) | 56.4% / 65.6% | 92.2% / 48.3% / 133 | 77% / 87.9% (gate 0.04) |
| v2b (+ look-alikes) | 57.1% / ~64% | 92.0% / 46.7% / 128 | 81% / 87.8% (gate 0.04) |

### A.5 Files

| What | Where |
|---|---|
| Ask's code | `api/ask_reader.py`, `api/ask_index.py`, `api/assistant.py`, `api/ask_figures.py`, `api/ask_model.py` |
| Per-survey workflow | `etl/ask_semantic.py`, `etl/ask_quality.py`, `etl/publish.py` |
| Tests | `tests/test_assistant.py`, `tests/test_ask_quality.py`, `tests/test_ask_semantic.py`, `scripts/ask_golden.py` |
| Research | `docs/research/ask-architecture.md`, `docs/research/ask-question-bank.md` |
| Training notebooks | `scripts/colab/` |
| Trained models (local only, not deployed) | `models/bge-cip-v1`, `models/bge-cip-v2a`, `models/bge-cip-v2b` |
| Status | `status/README.md` |

### A.6 Sources

Anthropic, Contextual Retrieval · Uber, QueryGPT · Snowflake, Cortex Analyst evaluations and Verified Query Repository ·
Databricks, Genie benchmarks and trusted assets · Pinterest, text-to-SQL · LinkedIn, SQL Bot · BGE M3-Embedding
(arXiv 2402.03216) · E5 (arXiv 2212.03533) · Improving Text Embeddings with LLMs (arXiv 2401.00368) · RocketQA
(arXiv 2010.08191) · GPL (arXiv 2112.07577) · NV-Retriever (arXiv 2407.15831) · Grok-1 open weights · OpenAI tiktoken ·
explainers on embeddings as a map of meaning and on overfitting as memorising the practice test. Links in
`docs/research/ask-architecture.md`.
