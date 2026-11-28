# Ask CIP rebuild, part 5: the series the wording-join fix changed (Phase 1, 27 Nov 2026)

What this is: every Ask CIP question entry whose surveys changed when api/ask_index.py wording_groups stopped joining
wordings that share half their words. It now joins two wordings of one code only when they have the same meaning words
(a year, a lead-in such as "Looking back,", the answer instructions, a bracketed example and grammar words set aside) and
most of the same answers. Built from staging's database published read-only on 27 Nov 2026 (case-sensitive copy),
comparing the old and new index, entries matched by wording. Who reads it: anyone checking a trend Ask showed before
27 Nov 2026, and Phase 5's comparison.

172 entries changed: 89 lost surveys of another question (372 surveys in all), 106 gained their own, 38 are new entries split off, 2 merged into another.

| Entry | Wording | Surveys before → after | Surveys that left | Surveys that joined |
|---|---|---|---|---|
| CSI-US/tracker/DP1 | Have you purchased any products from a department store in the past three months (whether online or in-store)? | 54 → 19 | 2022-09-05, 2022-10-31, 2022-11-07, 2022-11-28, 2022-12-12, 2023-01-23 … (+30) | 2024-11-18 |
| CSI-US/tracker/Q7_1#3 | Which categories are you currently purchasing less than before the start of the coronavirus outbreak? Select a | 3 → 32 |  | 2021-04-12, 2021-04-19, 2021-04-26, 2021-06-01, 2021-06-08, 2021-06-14 … (+23) |
| CSI-US/tracker/DS2#2 | Which drugstore/pharmacy retailers have you purchased products from in the past three months (whether in-store | 33 → 18 | 2022-09-05, 2022-09-12, 2022-11-28, 2023-02-20, 2023-02-27, 2023-03-06 … (+14) | 2022-08-08, 2022-10-31, 2023-01-23, 2023-09-11, 2023-11-27 |
| CSI-US/tracker/BT1 | Have you purchased any beauty products (whether for men or women) in the past three months? | 22 → 19 | 2022-08-08, 2022-08-15, 2022-10-31, 2023-01-09, 2023-01-23, 2023-09-11 … (+7) | 2022-09-05, 2022-11-28, 2023-07-24, 2023-10-09, 2023-12-26, 2023-12-26 … (+4) |
| CSI-US/tracker/HI5 | How much did you spend on home-improvement/DIY/garden products in the past three months? | 39 → 18 | 2022-08-29, 2022-09-05, 2022-09-12, 2022-11-21, 2022-11-28, 2023-01-02 … (+15) |  |
| CSI-US/tracker/FW6 | How much did you spend on footwear in the past three months? | 25 → 10 | 2022-01-31, 2022-04-25, 2022-07-18, 2022-08-29, 2022-10-31, 2022-11-21 … (+11) | 2024-04-29, 2024-07-22 |
| CSI-US/tracker/EC1 | Have you purchased any products online in the past three months? | 10 → 22 | 2022-02-21, 2022-05-16 | 2022-08-15, 2022-11-07, 2023-01-30, 2023-04-17, 2023-07-03, 2023-09-18 … (+8) |
| CSI-US/tracker/FW2 | Which retailers have you purchased footwear from in the past three months? | 24 → 20 | 2022-01-31, 2022-02-07, 2022-04-25, 2022-05-03, 2022-07-18, 2022-07-25 … (+4) | 2022-08-08, 2022-10-31, 2023-01-23, 2023-09-11, 2024-02-12, 2024-10-21 |
| CSI-US/tracker/Q2_2#1 | Are you currently purchasing any products more because of the coronavirus outbreak? | 0 → 15 |  | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |
| CSI-US/tracker/Q3_1#1 | Which categories are you currently purchasing more due to the coronavirus outbreak? Select all that apply. | 0 → 15 |  | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |
| CSI-US/tracker/Q4_1#1 | And are you currently purchasing any products less because of the coronavirus outbreak? | 0 → 15 |  | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |
| CSI-US/tracker/Q4_2#2 | Are you currently purchasing any products more than before the start of the coronavirus outbreak? | 47 → 32 | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |  |
| CSI-US/tracker/Q5_1#1 | Which categories are you currently purchasing less due to the coronavirus outbreak? Select all that apply. | 0 → 15 |  | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |
| CSI-US/tracker/Q5_1#3 | Which categories are you currently purchasing more than before the start of the coronavirus outbreak? Select a | 47 → 32 | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |  |
| CSI-US/tracker/Q6_1#3 | And are you currently purchasing any products less than before the start of the coronavirus outbreak? | 47 → 32 | 2020-12-28, 2021-01-04, 2021-01-11, 2021-01-18, 2021-01-25, 2021-02-01 … (+9) |  |
| CSI-US/tracker/TF5#1 | Have you changed, or do you anticipate changing, your shopping behavior to avoid the effects of tariffs? | 4 → 12 | 2025-05-12, 2025-07-07, 2025-08-04 | 2025-09-29, 2025-10-27, 2025-11-24, 2025-12-22, 2026-01-19, 2026-02-16 … (+5) |
| CSI-US/tracker/DS5#1 | How much did you spend at drug stores in the past three months? | 20 → 17 | 2023-02-13, 2023-10-02, 2024-01-29, 2024-04-15, 2024-04-29, 2024-07-08 … (+2) | 2022-08-08, 2022-10-31, 2023-01-23, 2023-09-11, 2023-11-27 |
| CSI-US/tracker/O2 | Which of the following off-price retailers have you purchased from in the past three months? | 6 → 18 |  | 2022-01-31, 2022-04-25, 2022-07-18, 2023-01-02, 2023-03-27, 2023-06-12 … (+6) |
| CSI-US/tracker/O5 | How much did you spend at off-price retailers in the past three months? | 6 → 18 |  | 2022-01-31, 2022-04-25, 2022-07-18, 2023-01-02, 2023-03-27, 2023-06-12 … (+6) |
| CSI-US/tracker/BT15 | How much did you spend on beauty products in the past three months? | 23 → 20 | 2023-11-27, 2023-12-16, 2023-12-18, 2024-01-29, 2024-03-04, 2024-04-15 … (+1) | 2022-09-05, 2022-11-28, 2023-02-20, 2023-07-24 |
| CSI-US/tracker/BT7 | Which of the following types of beauty products have you purchased in the past three months. | 18 → 17 | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13, 2024-09-30 | 2023-05-15, 2024-03-11, 2024-06-03, 2024-08-26, 2025-02-17 |
| CSI-US/tracker/DS1#1 | Have you purchased from a dollar store retailer in the past three months? | 7 → 18 |  | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13, 2025-09-01 … (+5) |
| CSI-US/tracker/DS1#2 | Have you purchased from a drug store or pharmacy in the past three months? | 29 → 18 | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13, 2025-09-01 … (+5) |  |
| CSI-US/tracker/FW1 | Have you purchased any footwear in the past three months? | 10 → 21 |  | 2022-02-21, 2022-05-16, 2022-08-08, 2022-10-31, 2023-01-23, 2023-04-10 … (+5) |
| CSI-US/tracker/FW4 | What categories of footwear have you purchased in the past three months? | 31 → 20 | 2022-08-29, 2022-11-21, 2023-01-02, 2023-01-09, 2023-03-27, 2023-05-01 … (+5) |  |
| CSI-US/tracker/HI2 | Which, if any, of the following retailers have you purchased home-improvement/DIY/garden products from in the  | 9 → 18 | 2024-11-25 | 2022-12-12, 2023-03-06, 2023-05-22, 2023-08-07, 2023-10-23, 2024-01-08 … (+4) |
| CSI-US/tracker/LX1 | Have you purchased any luxury products in the past three months? | 8 → 17 | 2023-05-15 | 2022-08-29, 2022-11-21, 2023-02-13, 2023-05-01, 2023-07-17, 2023-10-02 … (+4) |
| CSI-US/tracker/LX7 | How much did you spend on luxury goods in the past three months? | 8 → 17 | 2022-08-08 | 2022-08-29, 2022-11-21, 2023-02-13, 2023-05-01, 2023-07-17, 2023-10-02 … (+4) |
| CSI-US/tracker/TF5#2 | Have you changed your shopping behavior to avoid the effects of tariffs? | 15 → 4 | 2025-09-29, 2025-10-27, 2025-11-24, 2025-12-22, 2026-01-19, 2026-02-16 … (+5) |  |
| CSI-US/tracker/DS3#1 | Which types of products have you purchased from a dollar store in the past three months? | 9 → 18 |  | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13, 2024-01-29 … (+3) |
| CSI-US/tracker/DS4#1 | How much did you spend at dollar stores in the past three months? | 9 → 18 |  | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13, 2024-01-29 … (+3) |
| CSI-US/tracker/HI1 | Have you purchased any home-improvement/DIY products or garden-improvement products in the past three months? | 9 → 18 |  | 2023-03-06, 2023-05-22, 2023-08-07, 2023-10-23, 2024-01-08, 2024-03-25 … (+3) |
| CSI-US/tracker/HF2 | Which, if any, of the following retailers have you purchased home-furnishing/décor products from in the past t | 7 → 15 |  | 2022-09-12, 2023-02-27, 2023-05-15, 2023-07-31, 2023-10-16, 2024-01-02 … (+2) |
| CSI-US/tracker/HF3 | Which home-furnishing/décor products have you bought in the past three months? Select all that apply. | 7 → 15 |  | 2022-09-12, 2023-02-27, 2023-05-15, 2023-07-31, 2023-10-16, 2024-01-02 … (+2) |
| CSI-US/tracker/Q6#2 | Have you purchased any home-furnishing/d&eacute;cor products in the past three months? | 1 → 9 |  | 2022-09-12, 2023-02-27, 2023-05-15, 2023-07-31, 2023-10-16, 2024-01-02 … (+2) |
| CSI-US/tracker/DS2#1 | Which dollar stores have you purchased from in the past three months? | 15 → 18 | 2023-12-16, 2023-12-18 | 2023-01-02, 2023-03-27, 2023-06-12, 2023-08-28, 2023-11-13 |
| CSI-US/tracker/AP3 | Which retailers have you purchased clothing or apparel accessories from in the past three months? | 20 → 20 | 2022-08-08, 2024-02-12, 2024-10-21 | 2022-02-07, 2022-05-03, 2022-07-25 |
| CSI-US/tracker/HI3 | Which home-improvement/DIY/garden products have you bought in the past three months? | 22 → 18 | 2022-09-12, 2023-02-27, 2023-05-15, 2023-07-31, 2023-10-16 | 2022-12-12 |
| CSI-US/tracker/Q6#22 | Did you make any holiday purchases in the last seven days? | 1 → 7 |  | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |
| CSI-US/tracker/Q6#23 | Did you make any holiday purchases in the last days before the holiday? | 7 → 1 | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |  |
| CSI-US/tracker/Q7#21 | Which, if any, of these categories did you buy for the holidays in the final days? | 7 → 1 | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |  |
| CSI-US/tracker/Q8#48 | From which, if any, of the following retailers did you make holiday-related purchases in the final days? Selec | 7 → 1 | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |  |
| CSI-US/tracker/SC7 | And thinking specifically about buying on TikTok, what types of new products have you purchased on TikTok in t | 15 → 9 | 2023-02-13, 2023-10-02, 2024-03-11, 2024-06-03, 2024-08-26, 2025-02-17 |  |
| CSI-US/tracker/XM1A | Which, if any, of these categories did you buy for the holidays in the last seven days? | 22 → 28 |  | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |
| CSI-US/tracker/XM2 | From which, if any, of the following retailers did you make holiday-related purchases in the last seven days? | 23 → 29 |  | 2024-10-07, 2024-11-04, 2024-11-18, 2024-11-25, 2024-12-02, 2024-12-16 |
| CSI-US/tracker/AP1 | Have you purchased any clothing or apparel accessories in the past three months? | 15 → 20 |  | 2023-01-09, 2023-04-03, 2023-06-19, 2023-09-04, 2023-11-20 |
| CSI-US/tracker/BT13 | Which, if any, of the following retailers or platforms have you purchased beauty products from in the past thr | 17 → 18 | 2022-08-08, 2023-11-27 | 2022-09-05, 2022-11-28, 2024-11-25 |
| CSI-US/tracker/D10#1 | Did the Federal government shutdown impact your holiday shopping plans? | 0 → 5 |  | 2025-10-20, 2025-10-27, 2025-11-03, 2025-11-10, 2025-11-17 |
| CSI-US/tracker/D10#2 | Did the Federal government shutdown impact your holiday shopping? | 7 → 2 | 2025-10-20, 2025-10-27, 2025-11-03, 2025-11-10, 2025-11-17 |  |
| CSI-US/tracker/HF5 | How much did you spend on home-furnishing/décor products in the past three months? | 7 → 12 |  | 2022-09-12, 2023-02-27, 2023-05-15, 2023-07-31, 2023-10-16 |
| CSI-US/tracker/M1#1 | Have you purchased from any of these mass merchandisers/warehouse clubs in the past three months? | 12 → 17 |  | 2023-01-16, 2023-04-03, 2023-06-19, 2023-09-04, 2023-11-20 |
| CSI-US/tracker/M4 | How much did you spend at mass merchandisers or warehouse clubs in the past three months? | 13 → 8 | 2023-01-16, 2023-04-03, 2023-06-19, 2023-09-04, 2023-11-20 |  |
| CSI-US/tracker/AP5 | Now thinking about brands: Which, if any, clothing or apparel accessories brands have you purchased in the pas | 7 → 11 |  | 2023-01-09, 2023-11-20, 2024-04-22, 2025-03-24 |
| CSI-US/tracker/BT5 | How do you feel when you use beauty products? | 12 → 16 |  | 2023-07-24, 2023-10-09, 2023-12-26, 2023-12-26 |
| CSI-US/tracker/BT8 | Which beauty products have you bought in the past three months? | 19 → 19 | 2022-08-08, 2022-12-12 | 2022-09-05, 2022-11-28 |
| CSI-US/tracker/CS1 | Considering your discretionary income (what is left over after all your monthly bills are paid), do you think  | 73 → 77 |  | 2023-10-02, 2023-10-09, 2023-10-16, 2023-10-23 |
| CSI-US/tracker/DP3 | What type of product/s did you purchase at department stores in the past three months? | 15 → 19 |  | 2022-08-29, 2022-11-21, 2023-05-01, 2023-07-17 |
| CSI-US/tracker/DP8 | How much did you spend at department stores in the past three months? | 13 → 11 | 2023-02-20, 2023-07-24, 2024-09-30 | 2024-03-04 |
| CSI-US/tracker/DS3#2 | Which products have you bought from a drugstore/pharmacy in the past three months? | 20 → 18 | 2024-01-02, 2024-03-18, 2024-09-03 | 2022-08-08 |
| CSI-US/tracker/Q19#34 | Which of the following are most important to you when selecting the hair care products you buy? (select up to  | 4 → 8 |  | 2022-09-05, 2023-02-20, 2023-07-24, 2024-11-25 |
| CSI-US/tracker/q009 | Now looking forward over the next 12 months... Considering your discretionary income (what is left over after  | 72 → 68 | 2023-10-02, 2023-10-09, 2023-10-16, 2023-10-23 |  |
| CSI-US/tracker/AP9 | How much did you spend on clothing or apparel accessories in the past three months? | 14 → 11 | 2023-12-16, 2023-12-18, 2024-02-12 |  |
| CSI-US/tracker/BD1#3 | Did you purchase anything on Amazon.com during the Big Deal Days 2025 promotion last year (October 2025)? | 4 → 1 | 2025-08-18, 2025-10-13, 2026-08-10 |  |
| CSI-US/tracker/BD2#1 | Do you expect to purchase from or browse Prime Big Deal Days promotion on Amazon.com this year? | 0 → 3 |  | 2024-08-12, 2025-08-18, 2026-08-10 |
| CSI-US/tracker/BD5 | Do you have membership to Amazon Prime or access to Amazon Prime through membership of someone else in your ho | 11 → 14 |  | 2023-04-24, 2024-05-20, 2024-07-22 |
| CSI-US/tracker/DS7#1 | Which, if any, of the following factors would enhance your shopping experience at dollar stores? | 7 → 10 |  | 2024-01-29, 2024-04-15, 2024-07-08 |
| CSI-US/tracker/EC4 | And which, if any, of these categories have you purchased online in the past three months? | 25 → 22 | 2022-10-31, 2023-01-23, 2023-09-11 |  |
| CSI-US/tracker/EC6 | Do you have an Amazon Prime membership/access to Prime membership? | 25 → 22 | 2023-04-24, 2024-05-20, 2024-07-22 |  |
| CSI-US/tracker/FW3 | Now thinking about brands: Which, if any, footwear brands have you purchased in the past three months? | 7 → 10 |  | 2022-10-31, 2023-01-23, 2023-09-11 |
| CSI-US/tracker/G1 | On a different topic, have you heard of artificial intelligence or AI? | 23 → 22 | 2023-07-31, 2023-08-21 | 2023-06-19 |
| CSI-US/tracker/HW3#1 | What is the main reason you expect to spend more this Halloween? | 1 → 4 |  | 2023-08-14, 2025-09-29, 2026-09-14 |
| CSI-US/tracker/HW3#2 | What is the main reason you spent more this Halloween? | 6 → 3 | 2023-08-14, 2025-09-29, 2026-09-14 |  |
| CSI-US/tracker/HW5#1 | How, if at all, will you celebrate Halloween this year? | 0 → 3 |  | 2021-09-20, 2025-09-29, 2026-09-14 |
| CSI-US/tracker/HW5#2 | How, if at all, did you celebrate Halloween this year? | 6 → 3 | 2023-08-14, 2025-09-29, 2026-09-14 |  |
| CSI-US/tracker/Q11_2#19 | How do you expect your spending for the 2021 holiday season to compare to last year? Please think about total  | 0 → 3 |  | 2021-07-12, 2021-08-16, 2021-09-13 |
| CSI-US/tracker/Q11_2#27 | How did your spending for the 2021 holiday season compare to 2020? Please think about total spending, not just | 4 → 1 | 2021-07-12, 2021-08-16, 2021-09-13 |  |
| CSI-US/tracker/Q12#12 | Now thinking about brands: Which, if any, footwear brands have you purchased in the past three months? Select  | 13 → 10 | 2022-02-07, 2022-05-03, 2022-07-25 |  |
| CSI-US/tracker/Q18#35 | Which of the following are most important to you when selecting the skin care products you buy? (select up to  | 5 → 8 |  | 2023-05-15, 2023-07-24, 2024-11-25 |
| CSI-US/tracker/Q19#70 | Which of the following technologies in physical retail stores would enhance your shopping experience? Select a | 4 → 1 | 2024-01-29, 2024-04-15, 2024-07-08 |  |
| CSI-US/tracker/Q20#3 | Now thinking about brands: Which, if any, clothing or apparel accessories brands have you purchased in the pas | 6 → 9 |  | 2022-02-07, 2022-05-03, 2022-07-25 |
| CSI-US/tracker/SD2#1 | Do you expect to purchase from or browse retailers' Single's Day promotions this year (whether online or in-st | 1 → 4 |  | 2023-08-07, 2025-08-11, 2026-08-17 |
| CSI-US/tracker/T3#1 | Which, if any, of the following are your greatest concerns about adding new tariffs? Select up to three or “No | 0 → 3 |  | 2025-05-12, 2025-07-07, 2025-08-04 |
| CSI-US/tracker/T4#1 | Which, if any, of the following do you think would be the greatest benefits of adding new tariffs? Select up t | 0 → 3 |  | 2025-05-12, 2025-07-07, 2025-08-04 |
| CSI-US/tracker/T5#1 | Have you changed, or do you anticipate changing, your shopping behavior to avoid the effects of the new tariff | 0 → 3 |  | 2025-05-12, 2025-07-07, 2025-08-04 |
| CSI-US/tracker/T6#1 | How have, or will, you change your shopping behavior to avoid the impact of new tariffs? Select all that apply | 0 → 3 |  | 2025-05-12, 2025-07-07, 2025-08-04 |
| CSI-US/tracker/T6#2 | How have, or will, you change your shopping behavior to avoid the impact of tariffs? | 4 → 1 | 2025-05-12, 2025-07-07, 2025-08-04 |  |
| CSI-US/tracker/TF3 | Which, if any, of the following are your greatest concerns about tariffs? Select up to three or “None of these | 19 → 16 | 2025-05-12, 2025-07-07, 2025-08-04 |  |
| CSI-US/tracker/TF4 | Which, if any, of the following do you think are the greatest benefits of tariffs? Select up to three or “None | 19 → 16 | 2025-05-12, 2025-07-07, 2025-08-04 |  |
| CSI-US/tracker/BD1#1 | Did you purchase anything on Amazon.com during the Big Deal Days promotion last October? | 1 → 3 |  | 2025-08-18, 2026-08-10 |
| CSI-US/tracker/BD2#2 | Did you browse or purchase anything during the Prime Big Deal Days promotion back in October of 2024? | 3 → 1 | 2025-08-18, 2026-08-10 |  |
| CSI-US/tracker/BD3#1 | What categories do you expect to purchase from or browse Prime Big Deal Days promotion on Amazon.com this year | 0 → 2 |  | 2025-08-18, 2026-08-10 |
| CSI-US/tracker/BD3#2 | What categories did you purchase from or browse during Prime Big Deal Days promotion on Amazon.com this year? | 3 → 1 | 2025-08-18, 2026-08-10 |  |
| CSI-US/tracker/BD4#1 | Do you expect to browse or purchase on Amazon.com on Prime Big Deal Days for holiday purchases? | 1 → 3 |  | 2025-08-18, 2026-08-10 |
| CSI-US/tracker/BD4#2 | Did you make holiday gift purchases from the Prime Big Deal Days promotion on Amazon.com? | 4 → 2 | 2025-08-18, 2026-08-10 |  |
| CSI-US/tracker/BT9 | Which of the following are most important to you when selecting the skin care products you buy? | 12 → 10 | 2022-09-05, 2023-02-20 |  |
| CSI-US/tracker/D11#4 | Were you aware of the Federal government shut down that ended last month? | 3 → 1 | 2025-11-17, 2025-11-24 |  |
| CSI-US/tracker/HF7 | Which, if any, of these statements about shopping for home furnishings, do you agree with? | 9 → 9 | 2024-01-08 | 2023-10-16 |
| CSI-US/tracker/HOLR2 | Which, if any, of these statements do you agree with? | 4 → 4 | 2021-02-15 | 2024-01-08 |
| CSI-US/tracker/HW2#1 | How do you expect your Halloween 2026 spending to compare to last year? Think about all spending, including on | 0 → 2 |  | 2025-09-29, 2026-09-14 |
| CSI-US/tracker/HW2#2 | How did your Halloween 2026 spending to compare to last year? Think about all spending, including on candy, gi | 4 → 2 | 2025-09-29, 2026-09-14 |  |
| CSI-US/tracker/LX3 | Which luxury brand/s did you purchase in the past three months? | 15 → 17 |  | 2023-02-13, 2023-10-02 |
| CSI-US/tracker/Q11#49 | On a different topic, have you heard of generative AI? | 13 → 15 |  | 2023-07-31, 2023-08-21 |
| CSI-US/tracker/Q20#20 | Do you expect your personal financial situation to be better or worse for holiday 2023 than holiday 2022? | 0 → 2 |  | 2023-02-27, 2023-08-28 |
| CSI-US/tracker/Q20#32 | Was your personal financial situation better or worse for July 4th 2023 than July 4th 2022? | 3 → 1 | 2023-02-27, 2023-08-28 |  |
| CSI-US/tracker/Q21#28 | Which of the following are most important to you when selecting the fragrance products you buy? (select up to  | 6 → 8 |  | 2022-09-05, 2023-02-20 |
| CSI-US/tracker/SD2#2 | Did you purchase from or browse retailers' Single's Day promotions this year (whether online or in-store)? | 4 → 2 | 2025-08-11, 2026-08-17 |  |
| CSI-US/tracker/SD3#1 | What categories do you expect to purchase from or browse from Single's Day promotions this year? | 0 → 2 |  | 2025-08-11, 2026-08-17 |
| CSI-US/tracker/SD3#2 | What categories did you purchase from or browse during Single's Day promotions this year? | 4 → 2 | 2025-08-11, 2026-08-17 |  |
| CSI-US/tracker/SD4#1 | How much do you expect to spend on Single's Day promotions this year? | 2 → 4 |  | 2025-08-11, 2026-08-17 |
| CSI-US/tracker/SD4#2 | How much did you spend on Single's Day promotions this year? | 5 → 3 | 2025-08-11, 2026-08-17 |  |
| BACK_TO_SCHOOL/adhoc/Q4#2 | Do you expect to spend more, less or about the same on back-to-school shopping this year compared to last year | 1 → 2 |  | 2023-06-07 |
| BACK_TO_SCHOOL/adhoc/Q6#2 | Compared to last year, how are you approaching your back-to-school shopping trips? | 2 → 1 | 2023-06-07 |  |
| CSI-US/tracker/CMR5 | Which, if any, of these retailers did you buy from on Cyber Monday, either in a store or online? | 4 → 3 | 2022-12-05 |  |
| CSI-US/tracker/D11#2 | Were you aware of the Federal government shut down that ended last week? | 0 → 1 |  | 2025-11-17 |
| CSI-US/tracker/D11#3 | Were you aware of the Federal government shut down that ended a couple of weeks ago? | 0 → 1 |  | 2025-11-24 |
| CSI-US/tracker/D29 | In the last two weeks, did you use AI for work, for yourself, or both? | 33 → 32 | 2026-04-13 |  |
| CSI-US/tracker/E2#1 | How do you expect your Easter 2026 spending to compare to last year? Think about all spending, including on fo | 0 → 1 |  | 2026-01-26 |
| CSI-US/tracker/E2#2 | How did your Easter 2026 spending to compare to last year? Think about all spending, including on food, gifts, | 2 → 1 | 2026-01-26 |  |
| CSI-US/tracker/E3#1 | What is the main reason you expect to spend more this Easter? | 2 → 3 |  | 2026-01-26 |
| CSI-US/tracker/E3#2 | What is the main reason you spent more this Easter? | 5 → 4 | 2026-01-26 |  |
| CSI-US/tracker/E5#1 | How, if at all, will you celebrate Easter this year? | 2 → 3 |  | 2026-01-26 |
| CSI-US/tracker/E5#2 | How, if at all, did you celebrate Easter this year? | 2 → 1 | 2026-01-26 |  |
| CSI-US/tracker/G4 | Which of the following have you heard of? | 21 → 22 |  | 2023-06-19 |
| CSI-US/tracker/GU2#1 | Did you use AI for work, for yourself, or both? | 0 → 1 |  | 2026-04-13 |
| CSI-US/tracker/HF6 | Which factors are most important to you when choosing which retailers to purchase from for home furnishings? | 4 → 5 |  | 2023-10-16 |
| CSI-US/tracker/HI7 | Which, if any, of these statements about shopping for home improvement, do you agree with? | 6 → 5 | 2023-10-16 |  |
| CSI-US/tracker/HX5#1 | Do you expect your personal financial situation to be better or worse for holiday 2026 than holiday 2025? | 12 → 11 | 2025-12-15 |  |
| CSI-US/tracker/HX5#2 | Do you find your personal financial situation to be better or worse for holiday 2025 than holiday 2024? | 0 → 1 |  | 2025-12-15 |
| CSI-US/tracker/M3#1 | What is the main reason you expect to spend more this Memorial Day? | 4 → 5 |  | 2023-06-12 |
| CSI-US/tracker/M5#1 | How, if at all, will you celebrate Memorial Day this year? | 0 → 1 |  | 2026-03-09 |
| CSI-US/tracker/M5#2 | How, if at all, did you celebrate Memorial Day this year? | 2 → 1 | 2026-03-09 |  |
| CSI-US/tracker/M6#1 | Where do you expect to buy products for Memorial Day? | 0 → 1 |  | 2026-03-09 |
| CSI-US/tracker/M6#2 | Where did you buy products for Memorial Day? | 2 → 1 | 2026-03-09 |  |
| CSI-US/tracker/M7#1 | Which type of retailer do you expect to shop at for Memorial Day products? | 0 → 1 |  | 2026-03-09 |
| CSI-US/tracker/M7#2 | Which type of retailer did you shop for Memorial Day products? | 2 → 1 | 2026-03-09 |  |
| CSI-US/tracker/M8#1 | Do you expect your personal financial situation to be better or worse for Memorial Day 2026 than Memorial Day  | 0 → 1 |  | 2026-03-09 |
| CSI-US/tracker/M8#2 | Was your personal financial situation better or worse for Memorial Day 2026 than Memorial Day 2025? | 2 → 1 | 2026-03-09 |  |
| CSI-US/tracker/MDR1 | Did you spend on or celebrate Mother's Day this year? Think about all spending, including on food, gifts, trav | 2 → 1 | 2023-05-15 |  |
| CSI-US/tracker/Q10#19 | Which, if any, of the following online platforms have you purchased beauty products from in the past three mon | 0 → 1 |  | 2023-02-20 |
| CSI-US/tracker/Q11#28 | Which of the following waistline styles have you bought in the last twelve months? Select all that apply | 0 → 1 |  | 2023-06-05 |
| CSI-US/tracker/Q11#51 | Have you bought any denim products in the last twelve months? | 2 → 1 | 2023-06-05 |  |
| CSI-US/tracker/Q12#39 | Which factors are most important to you when choosing which retailers to purchase from for home improvement? S | 2 → 1 | 2023-10-16 |  |
| CSI-US/tracker/Q13#38 | Do you expect your personal financial situation to be better or worse for Halloween 2023 than Halloween 2022? | 0 → 1 |  | 2023-08-14 |
| CSI-US/tracker/Q13#44 | Was your personal financial situation better or worse for Halloween 2023 than Halloween 2022? | 2 → 1 | 2023-08-14 |  |
| CSI-US/tracker/Q13#56 | How do you expect your Father's Day 2024 spending to compare to last year? Think about all spending, including | 2 → 1 | 2023-03-13 |  |
| CSI-US/tracker/Q13#58 | Do you expect to purchase from or browse the Prime Big Deal Days promotion on Amazon.com this year? | 1 → 0 | 2024-08-12 |  |
| CSI-US/tracker/Q13#69 | What categories do you expect to purchase or browse during Single's Day promotions this year? Select all that  | 2 → 1 | 2023-08-07 |  |
| CSI-US/tracker/Q13#72 | How did your Labor Day 2024 spending compare to last year? Think about all spending, including on food, gifts, | 2 → 1 | 2024-06-17 |  |
| CSI-US/tracker/Q14#58 | What products or services do you expect to spend on, related to watching Olympic events? | 0 → 1 |  | 2024-05-20 |
| CSI-US/tracker/Q14#63 | How, if at all, will you celebrate Halloween this year? Select all that apply or "No plans to celebrate" | 1 → 2 |  | 2023-08-14 |
| CSI-US/tracker/Q14#68 | How much did you spend on products/services related to watching the Olympics? | 2 → 1 | 2024-05-20 |  |
| CSI-US/tracker/Q14_1#15 | Thinking about shopping for the holiday season this year, which, if any, of these statements do you agree with | 4 → 3 | 2021-03-01 |  |
| CSI-US/tracker/Q14_1#16 | How, if at all, will you celebrate Halloween this year? Select all that apply. | 1 → 0 | 2021-09-20 |  |
| CSI-US/tracker/Q14_1#3 | Which, if any, of the following statements about CBD/hemp do you agree with? Select all that apply or "None of | 0 → 1 |  | 2021-02-15 |
| CSI-US/tracker/Q14_1#4 | Thinking about returning unwanted items after the 2020 holiday season, which, if any, of these statements do y | 0 → 1 |  | 2021-03-01 |
| CSI-US/tracker/Q17#13 | Which, if any, of these retailers did you buy from on Cyber Monday? Select all that apply or None of these. | 0 → 1 |  | 2022-12-05 |
| CSI-US/tracker/Q18#32 | Have you heard of Web 3? | 2 → 1 | 2023-06-19 |  |
| CSI-US/tracker/Q18#61 | What is the main reason you spent more this Memorial Day? | 3 → 2 | 2023-06-12 |  |
| CSI-US/tracker/Q19#28 | How did your Memorial Day 2023 spending compare to last year? Think about all spending, including on food, gif | 2 → 1 | 2023-03-27 |  |
| CSI-US/tracker/Q20#10 | Thinking specifically about drugstore and pharmacy purchases, how (if at all) have you changed, or how do you  | 0 → 1 |  | 2022-10-31 |
| CSI-US/tracker/Q22#12 | Did you watch the Super Bowl this past weekend? | 0 → 1 |  | 2023-02-13 |
| CSI-US/tracker/Q22#50 | Did you watch the Super Bowl this year? | 2 → 1 | 2023-02-13 |  |
| CSI-US/tracker/Q23#6 | Which of the following technologies did you notice within the store during this store visit? Select all that a | 1 → 2 |  | 2022-11-21 |
| CSI-US/tracker/Q26#25 | How did your Mother's Day 2024 spending to compare to last year? Think about all spending, including on food,  | 2 → 1 | 2024-03-04 |  |
| CSI-US/tracker/Q26#31 | Will you spend on or celebrate Memorial Day this year? Think about all spending, including on food, gifts, tra | 2 → 3 |  | 2023-03-27 |
| CSI-US/tracker/Q26#5 | How many items did you intend to purchase when you started this shopping trip to the store? | 1 → 2 |  | 2022-11-21 |
| CSI-US/tracker/Q9#13 | Which, if any, of the following retailers have you purchased beauty products from in the past three months (wh | 0 → 1 |  | 2023-02-20 |
| CSI-US/tracker/Q9#20 | Which of the following categories have you bought in the last twelve months? Select all that apply | 0 → 1 |  | 2023-06-05 |
| CSI-US/tracker/Q9#24 | How do you expect your Halloween 2023 spending to compare to last year? Think about all spending, including on | 0 → 1 |  | 2023-08-14 |
| CSI-US/tracker/Q9#27 | How did your Halloween 2023 spending compare to last year? Think about all spending, including on candy, gifts | 2 → 1 | 2023-08-14 |  |
| CSI-US/tracker/R1#1 | Have you returned any apparel (clothing items) purchased online in the past 12 months? | 0 → 1 |  | 2026-02-23 |
| CSI-US/tracker/R1#2 | Now thinking specifically about online clothes shopping, have you returned any apparel (clothing items) purcha | 2 → 1 | 2026-02-23 |  |
