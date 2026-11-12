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
17. [Appendix for engineers](#appendix-for-engineers)

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
2. **Real questions as verified answers (built 13 Nov):** the Logs page lists every question people typed, most asked
   first. An admin presses **Check**, sees Ask's answer, and presses **Right: save as verified** or picks the right survey
   question. That question, and every later one worded like it, is then answered exactly and instantly. On staging the list
   already shows the real top questions (for example "How worried are people about tariffs?", asked 25 times by 3 people).
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
| 13 Nov 2026 | Admin review screen for real questions (Logs page): Check, Save as verified, or pick the right question | built; waiting for deploy |

---

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
