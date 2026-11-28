# Ask CIP: sample questions and expected answers (awaiting analyst check)

Status: **checked by the user, all correct (27 Nov 2026).** Written 27 Nov 2026 by `build_samples.py` from the published files of 27 Nov 2026
(`data/published/preview/current`). The mock-ups (`index.html`) draw the same answers. Every sentence comes from a fixed
pattern per answer type, every figure from one survey's file. Keep these questions out of every tuning set and out of
`config/ask_verified.yml`.

Rule used for “higher / lower / up / down”: the 95% two-proportion test of `api/dashboards.py` significant; otherwise
“about the same” or “could be chance”. The number of people asked is not shown in the answers (the meeting's decision);
it is in each file named below.

## S1. Did people buy beauty products recently?

- Level: Easy. Answer type: T1 Latest value. Market: US.
- Expected answer: In the latest survey (28 Sep 2026), **65.5%** of US adults said they bought beauty products in the past three months, about the same as on 6 Jul 2026 (63.6%).
  - Cards: Latest survey: 65.5% (28 Sep 2026) | Since 6 Jul 2026: About the same (From 63.6%) | Said no: 34.5% (28 Sep 2026)
  - Chart: columns, “Bought beauty products in the past three months”.

## S2. How have beauty purchases changed over time?

- Level: Easy. Answer type: T2 Trend over time. Market: US.
- Expected answer: In the latest survey (28 Sep 2026), **65.5%** of US adults said they bought beauty products in the past three months, about the same as in September 2022 (68.9%). The share has stayed between 62.5% and 65.5% during 2026.
  - Cards: Latest survey: 65.5% (28 Sep 2026) | Since Sep 2022: About the same (From 68.9%) | During 2026: Steady (Between 62.5% and 65.5%)
  - Chart: line, “Bought beauty products in the past three months”.

## S3. Which generation buys the most beauty products?

- Level: Easy. Answer type: T3 Compare groups. Market: US.
- Expected answer: In the latest survey (28 Sep 2026), Gen Z, Millennials and Gen X were about equally likely to have bought beauty products in the past three months (**70.5% to 72.4%**); Boomers were the least likely (51.2%).
  - Cards: Highest: 72.4% (Gen X; about the same as Gen Z and Millennials) | Lowest: 51.2% (Boomers) | Difference: 21.2 pts (A real gap)
  - Chart: columns, “Bought beauty products in the past three months, by generation”.

## S4. And by household income?

- Level: Hard. Answer type: T14 Follow-up (by income). Market: US.
- Follow-up of S3. Read as: Beauty purchases by household income, latest survey (28 Sep 2026).
- Expected answer: In the latest survey (28 Sep 2026), US adults in households earning $50k-$99k and $100k+ were about equally likely to have bought beauty products in the past three months (**72.5% to 76.8%**); US adults in households earning under $50k were the least likely (57.1%).
  - Cards: Highest: 76.8% (Household income $100k+; about the same as $50k-$99k) | Lowest: 57.1% (Household income Under $50k) | Difference: 19.7 pts (A real gap)
  - Chart: columns, “Bought beauty products in the past three months, by household income”.

## S5. Where do people buy beauty products?

- Level: Hard. Answer type: T4 Ranked answers (long list). Market: US.
- Expected answer: Walmart was the most common place: **42.8%** of US adults bought beauty products there in the past three months, in the latest survey (28 Sep 2026), ahead of Amazon.com (32.2%) and Bath & Body Works (16.7%).
  - Cards: Top answer: 42.8% (Walmart) | Second: 32.2% (Amazon.com) | Gap between them: 10.6 pts (A real gap)
  - Chart: both-bars, “Where people bought beauty products in the past three months (top 10)”.

## S6. How much do people spend on beauty products?

- Level: Hard. Answer type: T8 Amounts in ranges. Market: US.
- Expected answer: In the latest survey (28 Sep 2026), the middle answer among US adults was **$51 - $75** spent on beauty products in the past three months; the average was about $84 (worked out from the ranges people chose).
  - Cards: Middle answer: $51 - $75 (Half spent less, half more) | Average (estimate): $84 (From the ranges people chose) | Most chosen range: 19.3% ($26 - $50)
  - Chart: columns, “Spent on beauty products in the past three months”.

## S7. Do people think tariffs are hurting them?

- Level: Hard. Answer type: T2 + T11 Monthly trend of a scale. Market: US.
- Expected answer: In the latest survey (23 Nov 2026), **50.7%** of US adults said tariffs have a negative impact on them personally, about the same as in September 2025 (53.0%). During 2026 the share has gone up and down between 43.7% and 60.3%; 20.3% now say tariffs help them.
  - Cards: Latest survey: 50.7% (Negative impact, 23 Nov 2026) | Since Sep 2025: About the same (From 53.0%) | During 2026: Up and down (Between 43.7% and 60.3%)
  - Chart: line, “Say tariffs have a negative or positive impact on them personally”.

## S8. What do consumers expect for the economy over the next year?

- Level: Complex. Answer type: T13 Both markets: ask back. Market: both.
- Market Both: Ask asks back: “Both the US and China surveys ask this. Which results do you want?” (US results (latest 23 Nov 2026) / China results (latest 9 Nov 2026)).
- If US: More US adults expect the economy to get worse over the next 12 months (**38.4%**) than better (27.5%), in the latest survey (23 Nov 2026).
  - Cards: Expect worse: 38.4% (Much or somewhat worse) | Expect better: 27.5% (Much or somewhat better) | Net: -10.9 pts (Better minus worse)
- If CN: In the latest China survey (9 Nov 2026), **56.0%** of adults in China expected the economy to be positive over the next 12 months; 13.6% expected it to be negative.
  - Cards: Positive: 56.0% (9 Nov 2026) | Negative: 13.6% (9 Nov 2026) | Net: +42.4 pts (Positive minus negative)

## S9. Which generation in China is most positive about the economy?

- Level: Complex. Answer type: T12 China, by age group. Market: CN.
- Expected answer: The China survey records age groups, not generations. In the latest China survey (9 Nov 2026), adults in China aged 18-25, 26-41 and 42-57 were about equally likely to expect the economy to be positive over the next 12 months (**47.5% to 59.0%**); the differences could be chance.
  - Cards: Highest: 59.0% (Aged 26-41; about the same as 18-25 and 42-57) | Lowest: 47.5% (Aged 42-57) | Difference: 11.5 pts (Could be chance)
  - Chart: columns, “Expect the economy to be positive over the next 12 months, by age group”.

## S10. Why did beauty purchases drop at the start of 2026?

- Level: Hard. Answer type: T15 Why question. Market: US.
- Expected answer: The surveys record what people did and said, not why. On 19 Jan 2026, **62.5%** of US adults said they bought beauty products in the past three months; the surveys before and after were 68.4% (27 Oct 2025) and 63.9% (13 Apr 2026). The fall from October could be chance, and it was the same question, asked the same way.
  - Cards: That reading: 62.5% (19 Jan 2026) | Survey before: 68.4% (27 Oct 2025) | Survey after: 63.9% (13 Apr 2026)
  - Chart: line, “Bought beauty products in the past three months”.

## S11. How many Americans own an electric car?

- Level: Hard. Answer type: T17 No survey asks this. Market: US.
- Expected answer: None of our surveys asks whether people own an electric car. These are the closest questions we have: Categories people planned to buy during the Presidents' Day weekend, which include automobiles (Coresight US Consumer Survey, 12 Jan 2026); Holiday purchases in the last seven days (Coresight US Consumer Survey, 23 Nov 2026); What impact tariffs have on you personally (Coresight US Consumer Survey, 23 Nov 2026). No figures.

## S12. Are more people using AI tools like ChatGPT and Gemini than a year ago?

- Level: Hard. Answer type: T5 Two periods compared. Market: US.
- Expected answer: Among US adults who have heard of at least one AI tool, use of Gemini rose from 34.6% (3 Nov 2025) to **45.2%** (2 Nov 2026); ChatGPT, Copilot, Perplexity, Grok and Deep Seek were about the same a year apart (ChatGPT 57.8% then, 63.3% now).
  - Cards: Gemini, 2 Nov 2026: 45.2% (Of those who have heard of an AI tool) | Gemini, 3 Nov 2025: 34.6% (A year earlier) | Change: +10.6 pts (A real rise)
  - Chart: paired, “AI tools people have used”.

## S13. Among people who say tariffs hurt them, how many have changed how they shop?

- Level: Complex. Answer type: T6 One group within another question. Market: US.
- Expected answer: Among US adults who say tariffs have a negative impact on them, **53.2%** said they had changed their shopping to avoid the effects of tariffs in the latest survey (23 Nov 2026), compared with 42.6% of all US adults and 31.7% of everyone else, a real difference.
  - Cards: Say tariffs hurt them: 53.2% (Changed how they shop) | All US adults: 42.6% (Changed how they shop) | Difference: 21.5 pts (A real difference vs everyone else)
  - Chart: columns, “Changed their shopping to avoid the effects of tariffs”.

## Where every figure comes from

| Figure | Value | Survey date | File |
|---|---|---|---|
| Bought beauty products, latest | 65.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, survey before | 63.6% | 6 Jul 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, first survey with this wording | 68.9% | 5 Sep 2022 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 73.3% | 28 Nov 2022 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 73.2% | 20 Feb 2023 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 75.6% | 24 Jul 2023 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 72.2% | 9 Oct 2023 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 63.2% | 26 Dec 2023 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 77.1% | 11 Mar 2024 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 57.2% | 3 Jun 2024 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 71.6% | 26 Aug 2024 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 68.2% | 25 Nov 2024 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 68.5% | 17 Feb 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 69.9% | 12 May 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 74.4% | 4 Aug 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 68.4% | 27 Oct 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 62.5% | 19 Jan 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 63.9% | 13 Apr 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products (trend reading) | 63.6% | 6 Jul 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, Gen Z | 70.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, Millennials | 72.1% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, Gen X | 72.4% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, Boomers | 51.2% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, income Under $50k | 57.1% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, income $50k-$99k | 72.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products, income $100k+ | 76.8% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT1.json.gz` |
| Bought beauty products from Walmart | 42.8% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Amazon.com | 32.2% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Bath & Body Works | 16.7% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Walgreens | 14.0% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Sephora (excluding at Kohl's) | 12.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Dollar store retailer | 12.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from CVS | 12.1% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Target (excluding Ulta at Target) | 11.0% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from TikTok | 11.0% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Bought beauty products from Supermarket/grocery store | 11.0% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT13.json.gz` |
| Spent Less than $10 on beauty products | 6.8% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $10 - $25 on beauty products | 15.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $26 - $50 on beauty products | 19.3% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $51 - $75 on beauty products | 18.6% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $76 - $99 on beauty products | 11.4% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $100 - $199 on beauty products | 15.5% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $200 - $299 on beauty products | 5.3% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Spent $300 or more on beauty products | 4.2% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/BT15.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 53.0% | 1 Sep 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 43.0% | 29 Sep 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 52.7% | 27 Oct 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 50.1% | 24 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 51.6% | 22 Dec 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 46.2% | 19 Jan 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 46.8% | 16 Feb 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 55.7% | 16 Mar 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 51.5% | 13 Apr 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 56.1% | 11 May 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 52.0% | 8 Jun 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 48.1% | 6 Jul 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 48.6% | 3 Aug 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 60.3% | 31 Aug 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 43.7% | 28 Sep 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs hurt them personally (very or somewhat negative) | 50.7% | 23 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Say tariffs help them personally (very or somewhat positive) | 20.3% | 23 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF1.json.gz` |
| Expect the economy to get better (much or somewhat) | 27.5% | 23 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/CS2.json.gz` |
| Expect the economy to get worse (much or somewhat) | 38.4% | 23 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/CS2.json.gz` |
| Expect the economy to be positive (China) | 56.0% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Expect the economy to be negative (China) | 13.6% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Expect the economy to be positive, aged 18-25 (China) | 53.0% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Expect the economy to be positive, aged 26-41 (China) | 59.0% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Expect the economy to be positive, aged 42-57 (China) | 47.5% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Expect the economy to be positive, aged 57-76 (China) | 50.0% | 9 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-CN/tracker/Q9.json.gz` |
| Used ChatGPT (of those who have heard of an AI tool) | 63.3% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used ChatGPT (of those who have heard of an AI tool) | 57.8% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Gemini (of those who have heard of an AI tool) | 45.2% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Gemini (of those who have heard of an AI tool) | 34.6% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Copilot (of those who have heard of an AI tool) | 17.6% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Copilot (of those who have heard of an AI tool) | 18.6% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Perplexity (of those who have heard of an AI tool) | 7.3% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Perplexity (of those who have heard of an AI tool) | 8.1% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Grok (of those who have heard of an AI tool) | 7.0% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Grok (of those who have heard of an AI tool) | 7.6% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Deep Seek (of those who have heard of an AI tool) | 6.2% | 2 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Used Deep Seek (of those who have heard of an AI tool) | 6.1% | 3 Nov 2025 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/G5.json.gz` |
| Changed how they shop, among those who say tariffs hurt them | 53.2% | 23 Nov 2026 | `data/published/preview/current/api/v1/waves/725/people.json.gz` |
| Changed how they shop, everyone else | 31.7% | 23 Nov 2026 | `data/published/preview/current/api/v1/waves/725/people.json.gz` |
| Changed how they shop, all US adults | 42.6% | 23 Nov 2026 | `data/published/preview/current/api/v1/questions/CSI-US/tracker/TF5.json.gz` |

## Open questions for the manager (built with the default until answered)

1. Show the word “unweighted” on answers? **Default:** No. Say “Census-weighted figures” only when the weighted switch is on.
2. Keep the number of people asked in the Excel export? **Default:** No.
3. Long ranked lists (retailers, products): vertical or horizontal bars? **Default:** Vertical, as decided; the retailer mock-up shows both so you can choose.
4. A weekly view for questions asked every week? **Default:** No: monthly, quarterly and yearly only.
5. A side-by-side option when both markets ask a question? **Default:** No: two buttons, US results and China results.
6. Does a country named in the question override the market selector? **Default:** Yes: “Chinese consumers” answers from China whatever the selector says.
7. Neutral or green/red arrows on changes? **Default:** Neutral ink arrows: up is not always good (“worried about tariffs” up).
8. When two survey questions fit about equally: ask back first, or answer the best match and offer the other? **Default:** Answer the best match and offer the others under “Not what you meant?” (today's behaviour).
9. How to warn about small samples without showing the number of people? **Default:** “Fewer than 50 people answered here: read with caution.” Under 30, the figure is kept out of the headline and cards.
10. A market ask-back and a question ask-back in the same answer? **Default:** Ask the market only, then answer the best match and offer the others.
11. The selected market does not ask the question at all (China selected, a US-only question)? **Default:** Answer from the market that asks it and say so at the top of the answer.
