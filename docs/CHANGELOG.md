# What's new in CIP

Every feature, enhancement and update, newest first: the same entries as the portal's What's new page
(`frontend/src/screens/WhatsNew.tsx`). Add each change to both; `tests/test_docs.py` fails if they differ.
The API and the MCP connector are documented in [API.md](API.md).

## 27 November 2026

### The Consumer Health dataset is now the ESP dataset

The left-menu download and its tick on the Access page are now called ESP dataset. The workbook, who may download it and its API address (/api/v1/datasets/consumer-health) are as before.

### Ask CIP: the chart only when you ask for it

An Ask CIP answer now opens with its words and key figures only. The chart waits behind a Show chart button under the figures, and opens at once when the question asks for one (a chart, graph or plot of something). Hide chart closes it again; the chart types, the PNG download and the figures with their sample sizes are as before.

### Faster screens: nginx sends the stored files itself again

Since 22 November every wave's book and weekly report, every question file, every tracker dashboard and the databank views (sectors, retailers, Home's glance, expected vs actual, the weekly topic screens) were sent by the API instead of straight from disk by nginx: a setting meant for browsers that cannot read compressed files emptied the part of the address nginx uses to find the file, so it never found one. They still opened, only slower and at more cost to the server. nginx now finds every one of them: in a test, the Activities & retailers file went from about 590 answers a second (median 33 ms) through the API to about 33,500 a second (median 1 ms) from nginx, and a tool that cannot read compressed files is still answered by the API. A test now stops the mistake coming back.

### Activities & retailers, Spending pressure and Consumer sentiment: figures built at publish, one file per screen

The three new weekly screens now get their figures from the publish instead of working them out in your browser: every publish writes one small file per screen (Activities & retailers about 320 KB, Spending pressure about 35 KB, Consumer sentiment about 60 KB, all three in under a second of the publish), with each week's and group's people and each answer's count, and the screen only divides and draws. The figures are the same as before, checked to the decimal against staging; the screens open on one request instead of two question files, and the rules (which questions, which weeks, how a net or a grid row adds up) now live in one settings file, config/weekly_topics.yml, with their own tests. Where they cut back now also lists the real answers that start with Other (Other savings or investments, Other services, Other products); only the catch-all Other is left out.

### Trackers: the chart over time keeps a headline figure the newest week did not ask

A tracker's Headline figures over time chart drew only the figures its newest week had, so a figure that week skipped lost its whole history: the GenAI tracker's week of 2 Nov 2026 asked no shopping question, and Have shopped with GenAI and Plan to shop with GenAI vanished from the chart. The chart now draws every headline figure any week of the tracker has, each line where it was asked.

### Sector databank: spend by sector, with an average spend for each survey

The Sector databank now ends with Spend by sector: every sector's newest survey side by side, with the middle buyer's spend band, the average spend estimated from the answer bands (each band's mid-point, the top band at its floor, as Ask CIP estimates an average) and its change against a year earlier and the survey before. A sector's name opens it, and beside the table the chosen sector's average spend is drawn survey by survey, its median band in the hover. A note says when to read an average with care: it jumps where a sector's answer bands changed. The table downloads as CSV or Excel, and the sector's workbook (Excel: every tab) now carries the average under the median spend.

### Consumer sentiment & outlook: a new screen for the finances and economy outlook, by group

A new screen under Core research, Consumer sentiment & outlook (Sentiment & outlook in the left menu), follows the US weekly survey's two outlook questions every week since October 2023: whether people expect their household's discretionary income (Personal finances) and the economy (Economy) to be better or worse over the next 12 months. Each tab shows net better (better less worse, in points, as the weekly report counts it), better, about the same, worse and don't know. Choosing a kind of group (gender, age band, generation, household income, region, urbanicity) shows the chosen answer for each of its groups side by side with Everyone's figure as a grey tick: the outlook by demographic group. The line chart follows the answer week by week, and the cards give this week's figure with its change, the same week a year earlier and the people asked. Home's Consumer sentiment & outlook card now opens this screen.

### Spending pressure: a new screen for how expenses changed and where people cut back

A new screen under Core research, Spending pressure, reads the US weekly survey's question on how people's expenses changed in the last twelve months (utilities, insurance, rent or mortgage; asked every week since July 2026) in three tabs: Expenses up (a notable or significant increase), Expenses down (a notable or significant decrease) and Net change (up less down, in points). A fourth tab, Where they cut back, shows where people who cut spending because of higher gas prices cut back (restaurants and bars, travel, savings…), every week since March 2026. It works like Activities & retailers: the week, the respondent group and the category; every category for the group, or the category for each group of a kind side by side with Everyone's figure as a grey tick; the category week by week; this week's figure with its change, and the people asked. It is on Home and on the Access page.

### Activities & retailers: a new screen for what people did and where they bought food and nonfood products

A new screen under Core research, Activities & retailers, follows three questions of the US weekly survey every week since December 2020: the activities people did in the past two weeks (met up with friends, went to a restaurant, a mall, a gym…), the retailers they bought food from, and the retailers they bought nonfood products from, each a tab. It works like In store vs online: pick the week, the respondent group and the activity or retailer; the bar chart ranks every answer for the group, or, with a kind of group chosen (gender, generation, income…), shows the answer for each of its groups side by side with Everyone's figure as a grey tick; the line chart follows the answer week by week over the year up to the chosen week, or between any From and To. Cards give this week's figure with its change, the same week a year earlier and the people asked. Both charts export to CSV, Excel and PowerPoint or as a picture, and the screen is on Home and on the Access page.

### In store vs online: every group of a kind side by side in the bar chart

Choosing a kind of group under Respondent group (gender, age band, generation, income…) now shows, in the bar chart, the chosen category for every group of that kind side by side: Male, Female and Non-binary for Food or beverages, or Gen Z, Millennials, Gen X and Boomers. The group chosen above (Male by default for gender, the first generation for generation) is highlighted with its percentages and Everyone's grey tick, and the line chart shows it week by week. The three stay in step: clicking a group's bar, its button over the line chart or the filter above changes all of them, and the category stays as it was. Everyone shows every category, as before.

### In store vs online: Everyone and the line chart's date range are back

Everyone is a choice under Respondent group again, and the page opens on it, as before. The line chart has its own group list (with Everyone), its From and To dates and its group buttons again, all the same choice as the filters above: picking Everyone in either shows Everyone on both charts. The line chart shows the year up to the week chosen above, so changing the Week moves it, and From and To still pick any range. The bar chart is quieter: only the chosen category shows its percentages and, when a group is chosen, Everyone's figure as a grey tick; hovering any category gives its in-store and online figures (and Everyone's). The group and the date (or the trend's dates) now sit in grey chips above each chart, so the filters applied are plain to see.

### Excel: one view at a time as well as the whole workbook, and tracker tabs named as their lists

Beside the whole workbook, the Export menu now offers the view on screen on its own, as Excel or CSV. On the Sector databank, Excel: every tab gives every tab and the median spend, Excel: this tab only gives the tab you are looking at. On each tracker, Excel: every week gives every week the tracker ran, Excel: this week only gives the chosen week: every headline figure, list answer and group split with its %, the people asked and its change in points against the week before and last year. A tracker list's tab is named as on screen (Top platforms, not top) from the next publish or deploy, not only once that tracker's next week is built, and its note says it holds each week's top answers: a blank cell is an answer outside that week's top, not one nobody gave, and every answer of the question, every week, downloads from its Trends page.

### Excel for every databank and tracker, every tab in one workbook in the Coresight style, and one look for every button filter

Every Excel download now comes in the Coresight style: the header row in Coresight red with white text, percentages shown as 61.0%, the people asked as whole numbers, weeks as dates, columns as wide as their text, the header and first column kept in view and a filter on the header. A download that covers several tables now gives them all at once, a tab each. The Sector databank gives every tab of the chosen sector (retailers, brands, categories), laid out as the Databank's own workbooks. The US and China weekly tracker pages, like any survey's overview, have an Export button for the whole survey: a tab per section, every answer with Total, gender, generation and last week's figure, and the people asked. Each tracker (Tariffs & inflation, Financial health, GenAI & AI shopping, GLP-1 impact, Gas prices & geopolitics, Holiday shopping, Holiday outlook, Social commerce) has an Export button for every week it ran: a tab for the headline figures, one per list and one per group split, an answer per row and a week per column; Holiday shopping's holds the 2025 and 2026 seasons. These workbooks come as Excel or one CSV; PowerPoint stays for single tables. The Retailer databank's sector overview, Week by week, How positive people feel and a retailer in each sector now download too, In store vs online's category table carries the people asked, the Sector databank's workbook adds the median spend, and a China weekly survey's downloads name the China Consumer Survey as their source. Expected vs actual and the Retailer databank's shopper profile show their figures as percentages. The chosen button of every button filter and tab (chart types, groups, the Sector databank's tabs) now looks the same everywhere: a red outline and red text, as In store vs online's group buttons.

### In store vs online: Everyone as a grey tick on each bar, and the line chart follows the filters

Everyone is no longer a choice under Respondent group: the page opens on the first group, for example Gender: Male, and Everyone's figure is a short grey tick across each bar, as in the Retailer databank's Who shops there, so a bar past its tick is above everyone's. Each bar's percentage is in a column on the right, red for in a store over blue for online, where a tick cannot cross it; the hover and the export give the group's figures and Everyone's. The line chart keeps only its group buttons, the same choice as the filters: its own group, From and To lists are gone, and it shows the year up to the week chosen above, so changing the Week moves it. Both charts' notes now give the group and the date, then, on a line of their own, Percentage of respondents who bought. A week of 2021-22 with no demographics still shows Everyone, as it has no groups.

### Consumer Health dataset: their history loaded, and an email when a week's answers change

The data science team's Consumer Health workbook (to 10 August 2026) is now loaded on staging, so each publish writes the download: 68,152 respondents from 4 September 2023 to 23 November 2026, the first 62,109 identical to their workbook cell for cell. Each publish also checks every newer US week against the workbook's rules and emails the pipeline's failure list when a week asks an activity the rules do not know, no longer asks one of the 12 in the same words, or has a demographic nobody answered: such a week would otherwise be counted quietly wrong. Adding the answer to config/consumer_health.yml mends every such week at the next publish. A workbook that fails to build is emailed too.

### An email for every new survey, a switch for it on My account, and New on the menus

Each new China week now sends the team the same new-survey email as a US week, whether it comes from SharePoint or the Upload survey page: who answered and the biggest changes since last week, checked against the survey's own topline. Before, a SharePoint week only posted to Teams and an uploaded one sent nothing. Anyone given Alerts can tick Email me each new survey I can open on My account, and then gets that summary after each new survey their access opens, without the team's workbooks; signing someone out everywhere stops it. The left menu marks what arrived since you last opened it: Survey library, the US and China weekly trackers, Boards (a teammate's new board), What's new and the Consumer Health dataset show a small red New until you open them. It is kept per browser, so a first visit shows none.

### Consumer Health dataset: every week since December 2020, not only since September 2023

The data science team's Consumer Health workbook now also holds every older week of the US weekly survey that CIP has, from 28 December 2020 to August 2023 (SurveyMonkey, then Qualtrics): 119 weeks and 52,435 more people, so it runs from 2020 to 2026 with 120,587 rows in all. Their own rows from 4 September 2023 are unchanged. The older weeks follow their rules: rebuilt the same way, 4,373 people of their own Qualtrics weeks came out identical in every column, with times in the US Mountain time their Qualtrics files used and their 2023 sheet's pattern codes (EM, FF, NONE). SurveyMonkey asked no demographic questions of its own, so those weeks give gender, age and income from CIP's profile of each respondent; five weeks of autumn 2022 that did not ask the activities question are left out. The Read Me's Historical gap note says so. Every publish still adds each new week.

### Consumer Health dataset: no more failed downloads after an update

After each new version of CIP, the Consumer Health download could fail for about 15 minutes, and the browser saved a broken consumer-health.json instead of the workbook: the new server started from a copy of the published files taken before the workbook existed, then rebuilt it. That copy is now refreshed once the views are rebuilt, so from the next version on the workbook is there within seconds of an update. If it is ever being rebuilt, the link says so under it (Being rebuilt after an update: ready within minutes) instead of a failed download.

## 26 November 2026

### Screens back within seconds when a new version goes live

After each new version of CIP, the Retailer databank, Sector databank, In store vs online and the other ready-made screens could show only grey placeholders for minutes. The new server had the previous figures on its disk within six seconds, but rebuilt every view first (one of them, the admins' Fieldwork record, takes over two minutes) and waited for any data load running elsewhere. It now shows the previous figures as soon as they are on disk, then rebuilds the views behind them one file at a time. In a local test the screens came back after 7 seconds instead of 192. The Consumer Health download is now replaced in one step, so it is never half-written.

### Household income in Forsta's six groups for every year, Metaverse users by gender, age and area, and no dashed lines

Household income now has the same groups in the SurveyMonkey and Qualtrics years as in Forsta's (under $25,000, $25,000 - $49,999, $50,000 - $99,999, $100,000 - $149,999, $150,000 - $199,999, $200,000 or greater, and prefer not to say), so an income trend follows one set of groups from 2018. An older band takes the name of the one group that holds its whole range ($0-$9,999 and $10,000-$24,999 both become under $25,000); the answers themselves are unchanged. 123 surveys were regrouped, the 59 SurveyMonkey weekly surveys among them, and any survey loaded or reloaded from now on is grouped the same way. Five one-off studies keep their own bands, because one of their bands spans two groups and its people cannot be split without guessing: Marijuana (Cannabis) Survey (31 Oct 2019), Shopping and social media (15 Nov 2019 and 9 Mar 2021), Shopping and livestreaming (18 Feb 2022) and Metaverse users (24 Nov 2022), whose $20,000 - $29,999 is partly under and partly over $25,000. Metaverse users now has its gender, age band and urbanicity groups, and a generation where an age range falls inside one (its 25 - 29 spans Gen Z and Millennials, so those people have none): its questions read 'Which of the following best describes your gender?' and 'Which of the following includes your age?', wording CIP did not recognise, and its age ranges were written with a long dash. Women's Health and Beauty (15 Feb 2023) was reloaded too: it asked no gender question, so it has no gender groups, and its 60 - 64 answer spans two of CIP's age bands (45-60 and over 60), so those 73 people are in no age band. The Weekly report's news-event markers, the Trends chart's gridlines and the guide line that follows the pointer on every line chart are now solid.

### In store vs online: one group for both charts, the chosen category highlighted where it ranks, PNG images and a PowerPoint line chart

Respondent group is now one group at a time, the same choice in the filters above the charts and on the line chart's own buttons: changing either changes the other and the whole page. Choosing a kind of group (gender, age, income…) opens its first group, for example under $25,000, with no All option, and the picked button is outlined in red. The bar chart shows every category for that group, biggest in store first, each bar with its percentage; the chosen category stays where it ranks, in full colour with its figures in bold, and the others are lighter. Clicking a category, or its name, opens it in the line chart, which shows it week by week over the last year, in a store in red and online in blue, both solid lines. Each line's latest figure is labelled at its end, with the gap between the two once (groceries, everyone, 23 Nov 2026: in a store 69.1%, online 28.5%, a 40.6-point gap), and the tooltip gives each week's base (n). Both chart subtitles show the group and the date in bold, and the page reads Percentage of respondents who bought each category in a store or online. Household income leaves out Prefer not to say, the fourth card is renamed Online share of the category, both charts download as a PNG image, and a trend downloaded as PowerPoint (here and on Trends) is a line chart of every week with horizontal gridlines and a % axis, instead of bars of the first 16 weeks; a bar slide's labels now carry a % sign. Where a group's lines break, the data is missing, not the export: 20 US weekly waves between 8 Jun 2021 and 24 Oct 2022 have no gender, age or income in CIP and the old warehouse they were copied from has none for them either: it lacks the panel rows of 10 SurveyMonkey weeks and the demographic answers of 6 Qualtrics weeks, and lists no demographic question for 4 more, so the original exports are asked for. The note under the chart counts the weeks without answers.

## 25 November 2026

### Consumer Health dataset: the data science team's workbook, kept up to date every week

The data science team's Consumer Health workbook (one row per US weekly respondent: when they answered, their demographics, which of the 14 activities they did in the past two weeks, and the team's counts, pairs and patterns, 73 columns) is now kept up to date by CIP. Their workbook to 10 August 2026 is kept exactly as it is, and each US weekly survey after it is added in the same sheets, columns, rules and format, from the respondents CIP already loads: 15 weeks and 6,043 people so far, to 23 November 2026. Rebuilt the same way, the 54 weeks from August 2025 to August 2026 already in their workbook came out identical, all 21,713 rows apart from the source file's name, and the 23 November week's 15 shares match CIP's own figures. Every publish writes it again. Whoever the super admin gives the Consumer Health dataset menu on the Access page downloads it from Reference in the left menu, or with an API key from GET /api/v1/datasets/consumer-health.

## 24 November 2026

### A US and China Market filter on In store vs online, the Library's cards and the databanks; the retailer cards as mocked up

In store vs online has a Market filter, United States or China. China's weekly survey (questions Q5 and Q6, every week since February 2023) gives the categories bought in a store and online, for everyone or by gender, age, household income and urbanicity: in the week of 9 Nov 2026, household essentials 44.9% in a store against 20.7% online. A change reads vs last week only when the week before had a survey, else it names that week (vs Oct 26), as on Home. Home's China card for the widest gap now opens this screen on China. In the Survey Library the Market filter also sets the cards at the top: with China chosen, the latest survey is 9 Nov 2026, with 181 weekly surveys since February 2023 and 103k respondents; All markets keeps 558 surveys, 454 weekly and 296k respondents. The Retailer and Sector databanks show the Market filter too, with China listed but not choosable, as China's weekly survey asks no retailer or sector questions. The Retailer databank's cards follow the research team's mock-ups: one retailer's name above its cards, and when comparing, a line per retailer with the name on the left and the figure on the right (Millennial · 36.5%), so a long figure no longer runs over the next line; a card's note is the share of shoppers (36.5% of shoppers), and how positive shoppers feel keeps the date it was asked (Very or somewhat positive · Nov 16, 2026).

### Next.js security update

The portal's web framework, Next.js, is updated from 16.4.2 to 16.4.6, which closes seven published security advisories (npm audit now finds none). Nothing changes on screen.

### Survey Library, In store vs online and Retailer databank: new wording and a Market filter

The Survey Library now opens with Explore 558 surveys from 2018 to 2026, spanning the US and China. Its latest survey card gives the survey's date and market (US or China), and the cards read Weekly surveys (454, since December 2020), Total respondents (296k qualified respondents across all surveys) and Search questions. A new Market filter (All markets, United States, China) sits beside the year and event filters, each survey row shows its market, and the row buttons are now Summary, What changed and All questions. In store vs online: the subtitle reads Share of people who bought each category in a store or online, the People dropdown is now Respondent group, and the first chart is All categories, this week. Retailer databank: the subtitle reads Compare retailers and sectors side by side to explore shopping activity, shopper demographics and consumer sentiment, the Market dropdown is now Sector, and with a sector chosen the first chart names the sector's shoppers and the retailers chosen (Share of department store shoppers who bought from Kohl's; dollar store shoppers when Dollar stores is chosen), while the weekly retailers keep Bought in the past two weeks. The cards above it read Market rank among department store retailers (the chosen sector's), Generation that shops the most, Income group that shops the most and Shoppers who feel positive.

### Menus given without the weekly tracker menus now work: Home, Ask, the Library, In store vs online

Turning off the US or the China weekly tracker on the Access page used to take that survey's data away with its menu, so analysts given Home, Ask CIP, the Survey library, In store vs online and the Retailer databank without them found Home without This week at a glance, a Library without the weekly surveys, Ask answering from other studies, and In store vs online failing. Each weekly tracker's tick now shows or hides only its link in the left menu (and its card on Home): the US and China surveys stay in the Library, Ask and This week at a glance. In store vs online also opens without Trends, Compare waves or Audiences, and its card on Home follows its own menu. The left menu no longer shows an empty Reference heading when neither Methodology nor What's new is given.

### This week at a glance: the US and China weekly surveys, each shown or hidden by its badge

This week at a glance on Home now covers both weekly surveys, the US and China, each in its own block of six cards under a line naming its week and how many people answered. A badge per survey above the cards, US weekly survey and China weekly survey, shows or hides its block, and this browser remembers the choice; one survey always stays shown. China's first row is the top activity (in the week of 9 Nov 2026, watching TV, short videos or livestreams, 39.3% of adults in China), the top category bought online (personal care products, 39.5%) and the spending plans for the next two weeks (net -19.1: 15.4% will spend more, 34.5% less); its second row, like the US one, is the biggest significant change in what was bought in store or online (books, music, movies and video games in store, from 9.8% on Oct 26 to 4.7% on Nov 9), the widest gap between buying in a store and online (household essentials, 44.9% against 20.7%) and the personal-finances outlook (net optimism +44.4). When a week had no survey, China's changes are against the survey before (Oct 26). A week whose weekly report has no significant change over its period now shows the biggest significant move since the survey before instead of leaving that card empty.

### This week at a glance: six cards on Home from the newest weekly survey

Home now opens with This week at a glance, always shown, so the page is never empty: six cards from the newest weekly survey, in two rows. The first row is the week's sector: its leading retailer (in the mass merchants week of 9 Nov 2026, Walmart, bought from by 72.8% of all adults in the past three months) and its top product or category, then what is new this week: a one-off or event topic such as a retro, else a monthly or seasonal tracker, else the sector's median spend. The second row is the biggest significant three-month change in the weekly report's food, nonfood, in-store and online tables, the category with the widest gap between buying in a store and online, and the personal-finances outlook against the week before, with the share who say their utility bills went up. Each card carries a badge saying where it comes from (the week's sector, New this week, Monthly topic, Weekly report, In store vs online, Consumer sentiment) and, like the at-a-glance tiles of the topic trackers, its change against the sector's survey a year earlier and the one before, or against last week. Each card opens the screen it comes from. The cards are picked when data is published, so Home is as fast as before.

### Retailer and Sector databanks open with cards, and say which weeks a figure adds up

The Retailer databank now starts with a row of cards for the weeks you chose: where the retailer ranks among its market's retailers and who leads, the generation and the household income most of its shoppers are in (set against all adults), and how positive people feel about it. Comparing retailers puts each one on its own line in every card, in its chart colour; the Sector views show the sector's leading retailer and the generation and income most of its shoppers are in. Click a card to jump to its chart. The “Bought in the past two weeks” card now carries an “Aggregate of the selected time period” badge and names the weeks, and pointing at a retailer's figure or bar shows its shoppers, its base and the weeks added together. The Sector databank opens with three cards from the sector's newest survey: its leading retailer, its top product or category (each opens its tab) and the median spend, the band the middle buyer's spend falls in, each with its change against the sector's survey before and the one a year earlier.

### In store vs online: people by kind of group, the trend's own dates, and Excel

People is now two choices: the kind of group (gender, age band, generation, household income, Census region or urbanicity), then All or one group. Only the groups the chosen week has answers from are offered, so an income band the survey no longer uses no longer leads to an empty chart. All puts the kind's groups side by side: the category for each group this week (click a group to see it alone) and each group's trend, solid for in a store and dashed for online. The category's trend has its own From and To dates (the week chosen above does not move it) and downloads as Excel, CSV or PowerPoint from Export.

## 23 November 2026

### Gemini can read the questions Ask's own reader is unsure of

Ask can now send a question its own reader is unsure of to Google's Gemini (free tier, gemini-3.5-flash-lite) to pick the survey question: set CIP_ASK_PROVIDER=gemini and GEMINI_API_KEY. Gemini sees only the question and the candidate questions' wording and answer labels, never respondent data, and never writes a figure. Measured on 23 Nov 2026: real analyst questions 202 of 232 right, up from 184 (“Are people eating out less?”, “Have consumers bought anything on TikTok Shop?”, “How has financial optimism changed this year?”); the no-answer set 57 of 60 declined, up from 55; researched 48 of 58 and fresh 48 of 50 as before; the golden set 154 of 161, down from 158. When Ask's own reader picked a question using every word of the subject (“tariffs”, “Valentine's Day spending”) and Gemini said no survey asks it, or picked one missing a word, the reader's pick now stands.

### Ask works out a median or average budget, answers month-against-month questions, and says what people reported about tariffs

“What was the median holiday spend?” and “What is the average holiday budget?” now give the middle budget band and an average worked out from the band mid-points, for everyone or by group (Gen Z: middle band $500-$749, about $854 on 7 Sep 2026); a question with no amounts asked, such as the average price of a turkey, is still declined. “Groceries online in October vs September” is answered from the weekly online-categories question, which asks every week (27.8% in September, 29.5% in October), instead of an annual study asked only in May, and the lead no longer repeats the months as what people did. “Did the tariffs cause people to spend less?” shows what people said tariffs made them change, with a note that this is their own report, not a measured cause; a question whose effect the survey does not ask, such as dining out, is still declined. Real analyst questions answered right: 166 to 184 of 232.

## 22 November 2026

### Fewer wrong refusals, and “both” keeps what was bought

Ask no longer refuses a fair question for an ordinary word: “each week of the last four”, “get worse”, “home-improvement buyers” and “18-34s” were read as subjects no survey asks. “Share using Gemini” is answered from the weekly AI-tools question instead of being refused, because Gemini is one of its answers. “Bought groceries both in a store and online” keeps “groceries” on both sides (23.5% on 16 Nov, not 77%), and “and also” reads as both. On 30 new analyst questions written after these changes and never used to tune them, Ask gets 17 right, up from 14 before the plan engine; every other test set is level or better.

### Ask answers questions that join survey questions, worked out from each week's respondents

Ask now answers questions that need several survey questions for the same people, exactly: “Among recent AI users, what share used GenAI to shop each week?” (20.6% on 16 Nov, 59 of 286), “Are GenAI shoppers more likely than other AI users to have made holiday purchases?” (57.6% against 48.9%, a gap that could be chance), “both ChatGPT and Gemini”, “did NOT also buy at Walmart”, funnels from AI-tool use to buying and satisfaction, age bands the survey does not cut by (18-34 against 55 and older) and a change tested between two weeks. Each answer shows how the question was read (what was counted, among whom, split by what, which weeks) and every figure with its base. On 132 hard analyst questions with figures worked out from the raw survey files Ask now gets 74 right, up from 57, and on 30 new questions written to test it afterwards 17, up from 15; every other question is answered as before.

### Holiday questions keep all their weeks, and Ask finds every question a combined question needs

Holiday questions whose answers change tense before and after the day (“I will spend on Halloween” before, “I spent” after) had their earlier weeks dropped from Ask's search: 282 weeks of 112 questions, such as Halloween on 14 Sep 2026, Easter and Prime Day. Each week is now checked against the newest week of its own wording, and 229 of those weeks are back; the other 53 belong to codes reused for other questions. A question that joins several survey questions (“Among GLP-1 users on 16 Nov, what share bought footwear?”) is now searched part by part, in the weeks it names: for all 126 plans in the hard test set, every survey question the plan needs is among the candidates, against 114 when searched whole. When a question names a retailer, Ask now offers the three longest-running questions that list it, not the first three it found.

### Week-by-week answers, both retailers compared, and analyst questions from ChatGPT's answer key

Tested on 40 analyst questions ChatGPT wrote with answers worked out from the last four weekly surveys: Ask now gets 12 fully right, up from 3, and 15 wrong or unanswered, down from 25. “In each of the four survey weeks” and “across the four waves” give one figure per week, not one pooled figure: “Week by week (26 Oct, 2 Nov, 9 Nov, 16 Nov 2026): 42.6%, 58.8%, 52.2%, 51.7%”. “How do Walmart and Amazon compare…” answers “Walmart is ahead of Amazon in all 4 weeks” with both series. A trend also gives the change from the week before, not only from the first week. Changes and totals are worked out from the counts before rounding: up 9.2 points, not 9.1. “Which five retailers…” and “the five most commonly purchased…” list all five. “How many respondents, and the gender breakdown?” gives 200 male, 200 female and 4 non-binary of 404. Income groups written in dollars (“below $50,000, $50,000-$99,999, $100,000 or more”) are read as three groups. “Among recent AI users” means anyone who used an AI tool, and an “among” group that is its own question's audience no longer empties the answer. “Which retailers were most used by holiday purchasers”, leaving a store without buying, recent AI-tool use and started holiday shopping now find their questions. A Census-weighted answer keeps totals such as “Started (still + finished shopping)”, and its weekly change is tested on the unweighted figures (p = 0.887, not p = 1.000). The 40-question check also found one error in ChatGPT's own key: its online grocery figures were health products. Answers still take well under a second, with no AI and no cost.

### Two groups at once, Census-weighted weekly answers, and the last wrong picks

“What share of women in the South bought from Amazon?” and “Gen Z women who shop at Walmart” now answer (23.1% and 55.4%, four weeks pooled): the weekly core questions are coded q1–q6 in each wave but Q1–Q6 in Ask's question files, and on staging the cross-tab and respondent files were not found under the capital letter, so two groups at once, Census-weighted answers and “among” filters on those questions quietly fell back or came up empty. “High income” and the other income groups now fit any wave's bands, older finer ones included, and are counted from the respondents when a small band is suppressed. “How many people use Buy Now Pay Later for holiday shopping?” says 27.1% are likely to use it (“Not likely” is never counted as likely); “How many people use rapid grocery delivery?” finds the question that asks about use; “What concerns do shoppers have about holiday shopping?” leads with inflation (41.7%), not a pick-one-of-two exercise whose 50/50 figures say nothing; and an old yes/no question gives way only to another yes/no question, so “Do high-income shoppers buy groceries online more?” answers 51.9% from the question that asked it.

### Ask picks the right survey question more often

Nine wrong picks found by a 60-question test are fixed, each checked against the golden, fresh, researched and real-question sets: “How do people feel about their personal finances?” now answers from the discretionary-income outlook, not a shutdown question; “How many people use generative AI?” counts anyone who used an AI tool (72.2% in Nov 2026), not personal-vs-work use; “How many people bought holiday gifts in the last seven days?” is the holiday purchases question (42.1%); “How is Walmart doing?” and “How is Amazon doing lately?” read the weekly retailer lists; “Top 5 nonfood retailers this week” no longer picks a 2022 study of the same name; “Millennials who bought clothing online” leads with clothing, not groceries. Questions “among” a group work for select-all answers (“among people who used ChatGPT…”), find the group's topic (“among GLP-1 users, how has apparel spending changed?”) and read an answer of the group's own question (“among holiday starters, what share have finished?”: 19.1%).

### Ask's answers read like an analyst's, in plain words

Every answer now leads with what was found, then the change in words: “Walmart: 52.9% in Q4 2026, up 5.7 points from 47.2% in Q4 2020, a significant rise”, or “about the same as on 9 Nov (65.6%)” when the change could be chance, instead of “Steady:”, “Rising:” or “Falling:”. Groups read as people (“Ages 30-44 are about twice as likely as over 60s…”, “Men are highest… a gap that could be chance”), short answers lose their quote marks, “chose” and “answered” become “said”, and a better/worse scale reads “More said worse than better: 39.2% worse, 29.3% better” (dollar bands are never treated as a scale). “GLP1” finds the GLP-1 question, “Are Chinese consumers avoiding public places?” answers “53.9% of Chinese adults surveyed are avoiding public places”, a total such as Amazon Prime own + household no longer drops older wordings, and “What about Gen Z?” on its own says it reads as a follow-up. The long list of older question codes is now one short note. Checked on 60 varied questions across the weekly US and China trackers and the annual studies: wording problems fell from 42 to 6 answers, median answer time 84 ms; the test sets are unchanged.

### Ask works out the figure you asked for, in plain English, from every survey

Asked the same 20 questions as ChatGPT given the raw files of the last 10 weekly surveys, Ask CIP now gets 19.5 right, level with ChatGPT and up from 8.5, every figure checked against the raw respondents. It now adds answers up (“bought anything online”: everyone but “None of these”; “better or worse”: both totals, and a winner only when the gap is statistically significant), reads “high, middle and low income” as three groups, answers “among GLP-1 users…” or “among people who expect the economy to worsen…” from each wave's respondents, says whether a difference is significant (“No clear difference between men and women … p = 0.074”), lists every survey week (“each of the 10 surveys”) or pools them, and reads a day (“16 Nov 2026”) as that week's survey. Answers lead in plain words: “About four in five US adults surveyed (80.0%) bought anything online in the past two weeks (323 of 404, 16 Nov 2026)”. “How many people use Amazon Prime?” counts own membership and household access, and lists every survey that asked it (weekly tracker 68.3%, Online Grocery 75.5%, Amazon Apparel 80.1% and six more). When Ask is unsure which survey question you meant, the other likely ones show right under the answer: “Not what you meant?”. A question file joined across reused codes no longer gives an empty answer (the GLP-1 chart on staging). Answers still take well under a second, with no AI and no cost.

### Ask answers more of the loosely worded questions, and refuses what no survey asks

Ask CIP was tested on 2.7 lakh answers in Colab: 91,311 loosely worded analyst questions through the whole of Ask, three ways. Neither the newly trained reader nor six times more example phrasings beat today's Ask, so neither is used. What the test found is fixed instead. Words that say how an analyst asks (“list”, “trend”, “rate”, “doing”, “commonly used”) no longer push aside the question Ask's reader picked. “High income”, “middle income” and “low income” now read as income groups ($100,000 and up, $50,000–$99,999, under $50,000). A question about “last month” on a survey question not asked then shows its latest figures, saying so, instead of no answer. A question whose only subject is a word no survey uses (“immigration”) is told no survey asks it, not answered from an unrelated question. Of 31,753 questions Ask had missed, 702 are now right; on the older 38,604-question bank 57 more are right, and 84.4% of the answers given are right (84.5% before). The test sets are unchanged: 158 of 161, 48 of 50, 48 of 58.

## 21 November 2026

### API fixes: audiences read “Gen Z”, plain clients get plain JSON, saving needs your name

Three things found in the end-to-end API test of staging. An audience sent through the API as “Gen Z” (as every screen writes it) counted nobody, because the data spells it GenZ: groups are now matched without spaces or case, and a group a wave lacks is listed under skipped instead of quietly giving zero. A program that does not accept compressed answers (Python's urllib, some tools) was sent gzip bytes it could not read from the published files: it now gets plain JSON from the API, and browsers still get the compressed file. The API guide now says that saving a view, an alert or an audience needs “by”, your name.

### Every box on the Logs page opens and closes

On the Logs page (Administration, admins only) each box, from Ask CIP survey by survey and At a glance to Raw logs and Older logs, now opens and closes from its title, so you keep only what you need in view; Expand all and Collapse all next to the time range do the whole page at once. A closed box stays closed while the page refreshes itself every minute. Every box starts open, as before.

### Ask answers with a verdict first, and how a topic is doing from its dashboard

Ask CIP now leads every answer with its verdict in plain words, worked out from the figures and never written by an AI: “How good is GLP-1 performing?” answers “GLP-1: Using a GLP-1 drug is holding steady. 15.8% of US adults are using a GLP-1 drug like Ozempic on 16 Nov 2026, down 1.9 points since 28 Jul 2025 (not a significant change). Also, 78.1% of users take it for weight loss; 60.9% of users eat less than before”, with the dashboard's other figures as lines, each linked to its survey question, and the trend as the chart; the same for every topic dashboard (tariffs, GenAI, financial health, gas prices, holiday, apparel, beauty and the others). Other answers say “Walmart leads clearly”, “Highest among GenZ, about twice the Boomer figure”, “Little real difference by income”, “Rising:”, “Falling:” or “Steady:” (tested at 95%), and an outlook scale as its net (“More negative than positive: net -6.4”). A yes/no question by group leads with yes. Ask's test sets: 158 of 161 and 48 of 50, unchanged.

### China survey history from February 2023

The China weekly tracker now starts on 6 Feb 2023 instead of 23 Oct 2023: 31 more weeks from the analysts' SharePoint folder, 180 weeks in all, each checked against its own topline (123 of 123 figures equal) before loading; and the Singles Day survey of 17 Nov 2026 as the week of 9 Nov, the newest China week. The China upload now reads 2023 files whose submit times are Excel day numbers and early-2023 answers worded with a verb (“去健身房/体育中心”). Weeks whose topline is weighted or in English (Dec 2022, Jan and 6 Mar 2023) or whose raw file lacks Baidu's first columns (31 Jul 2023) are not loaded: their counts cannot be checked.

### Weighted figures for every group, copy an answer for an email or a slide, and your questions on My account

With the Weighted switch on, Ask CIP now gives Census-weighted figures (gender, age and region) for every group, income, age, region and area type included, and for two groups at once: “Amazon by income” runs from 19.3% to 38.4% weighted. The weights come from each wave's respondents, so a pooled period counts every weighted respondent once. “Young people” is read as the 18-29 age group and “older people” as over 60. Each answer has a Copy menu: For an email gives the finding, its key figures, notes and source as text to paste, and For a slide a title, three bullets and a source line, written from the answer's own figures with no AI model. My account lists the questions you asked Ask CIP, newest first, each opening the answer again. Ask's test sets are unchanged: 158 of 161, 48 of 50 and 48 of 58.

### Ask adds the change since last week, answers for two groups at once, gives weighted figures, and keeps your questions

An answer from one survey wave now says how its main figure moved since the wave before, tested: “Walmart” leads at 51.7% … “Walmart” is down 4.9 points from 2 Nov 2026 (not a significant change). Ask CIP now answers for two kinds of group at once, such as “Do Gen Z women shop at Amazon?” (27.9%, 31 of 111, the latest 4 waves pooled) or “Amazon shoppers by generation and gender”, from the same figures as Cross-tabs, with a link to open them there. With the Weighted switch on, or when a question asks for Census-weighted figures, Ask answers with the Census-weighted shares (gender, age and region) for all respondents, gender and generation, and says when they are not available; each answer now says Census-weighted or Unweighted. Your recent questions are listed under the Ask box, each once, to ask again with one click; a follow-up is listed as the full question it was read as. Ask's test sets are unchanged: 158 of 161, 48 of 50 and 48 of 58.

### Ask answers follow-ups, compares two answers by group, and summarizes the week

Ask CIP now reads a typed follow-up with the question before it, as a chat does: after “How many people shop at Amazon?”, “What about Gen Z?” answers for Gen Z, “and by income?” by income, “how about in 2025?” for 2025, and “what about Target?” for Target, each from the same survey question; the answer shows how it was read. “Compare Walmart and Target shoppers by income” now shows both stores in every income group, with a sentence on which leads where (“Walmart” is ahead of “Target” in all 4 income groups on 9 Nov 2026, by 24.2 to 37.8 points); Walmart was missing because the store list also has Walmart+. Income bands no longer used in the period asked are no longer empty columns. “Summarize how consumers feel this week” answers with one line from each weekly tracker question the weekly report reads: the economy and personal finances outlooks as net better, then the leading food and nonfood retailers, online categories and activities, each linked to its source. Ask's test sets are unchanged: 158 of 161, 48 of 50 and 48 of 58.

### Ask reads “since last year” as last year against now

“How has consumer sentiment changed since last year?” compared 2024 with 2025. Ask CIP now compares last year with the latest wave, and does the same for “since last month” and “than last month”. “Spending last year” still means last year alone. Ask's test sets are unchanged: 158 of 161, 48 of 50 and 48 of 58.

### Ask picks the right survey question more often, and says when a question was last asked

Ask CIP now answers “Holiday progress” from the holiday shopping status question, “Inflation expectations for the holidays” from the price-increase question, “Retail subscription programs” from the subscription question, “Personal finances outlook” from the discretionary income question asked every week, and “What do people buy on TikTok?” from the TikTok purchases question instead of the beauty retailers list. “Are consumers saving more money?” now says no survey asks it, instead of answering from the gas-prices question. An answer from a question last asked more than a year ago says so in its first sentence, for example “Last asked 27 May 2020.” On Ask's test sets: 158 of 161 right (152 before), the fresh set unchanged at 48 of 50, the researched set 48 of 58 (47 before), and 44.8% of 2,000 generated test questions found the right survey question (41.9% before).

### Ask says when the surveys do not ask it, compares named groups, and reads “started” as the dashboards do

Ask CIP no longer answers a question with the nearest survey question when that question is about something else: “Fed rate cuts” was answered from the gas-prices question, and “cutting back on dining out because of tariffs” from a tariff question that never mentions dining. Now it says no survey question covers those words and lists the closest questions. A question that names two groups, such as “Do Gen Z shop on Amazon more than boomers?”, is answered by generation instead of finding nothing. “What share started holiday shopping?” is answered with Started, Still shopping plus Finished shopping (52.2% on 9 Nov 2026), the same figure as the Holiday dashboard, and “have not started” with Not yet started. Ask's test set scores 152 of 161, one more than before, and its fresh set is unchanged at 48 of 50.

### Left menu: Ask CIP at the top, the US tracker named like China's, a line of help on hover

Ask CIP is back in the left menu, second under Explore after Home, so the question box is one click away from any screen. Shopping & Spending is now called US weekly tracker, next to China weekly tracker, so the two weekly surveys read alike. Rest the pointer on Ask CIP, a tracker or a databank in Core research to read in one line what it answers. The Access page lists Ask CIP under Explore too.

### Ask answers in one sentence first, then the key figures

Ask CIP now opens each answer with the finding in one sentence, for example “Walmart” leads at 51.7%, 10.4 points ahead of “Amazon” (41.3%), instead of a long list of every figure. Under it: the country, date, number of survey waves, how many people answered, and the survey question by name; then the key figures as tiles, in Client view too; then the chart. A question with “which … most” is answered as a ranking. When a highest or lowest group leaves out groups of fewer than 50 people, the sentence says how many were left out.

## 20 November 2026

### Ask finds the weekly food, online and activities questions again

Since the 15 November change that follows a question across renumbered codes, Ask could read a weekly question under a code it held for only a few weeks, years ago: the food retailers question took the activities answers, and the weekly online purchases were left out. Each question file now names the waves it borrowed from other codes and Ask reads only a file's own waves, joining the same wording across codes itself. Questions are also told apart by their own words, not the frame many share (“Which, if any, of these ... in the past two weeks?”), and never across holidays: a Thanksgiving question no longer shows Easter's figures. On staging's data Ask answers 152 of its 161 test questions and 48 of 50 real ones, up from 141 and 39. The next publish rebuilds every question file once to add this.

### Ask uses less memory under load and answers more group questions

Ask CIP now works on at most two questions at once: with 100 people using the portal together the server held 612 MB instead of 819 MB, and pages stayed quick (95% within 75 ms instead of 417 ms) while questions waited their turn. Ask keeps one copy of each example phrasing it matches against (14 MB less) and its word search takes a quarter less time. A question about one group, such as Gen Z, that its closest match cannot answer for is answered from a near-equal question that has the group. A reviewed answer saved for one wording of a survey question still finds that wording after a publish renumbers it, instead of another question once asked under the same code.

### Ask reads dates as you say them, and safer weekly loads and deploys

Ask CIP reads "this quarter", "last quarter", "this year", "year to date", "right now", a month without a year ("October vs September") and a quarter without a year ("Q4") as calendar periods, and says when a question was not asked then. A comparison whose best match lacks one of the months uses a near-equal question that has both. An abbreviation no survey uses, such as OTT, gets the closest survey questions instead of an unrelated figure. A question about one group with no period named uses the newest wave that has that group. When a newly loaded wave's answers differ from Forsta, or the portal files fail to publish, its metric alerts and its loaded email are held and the failure email says why. Excel and PowerPoint downloads are built one at a time, so they no longer slow the rest of the portal; a second one waits a moment or asks you to retry. Every deploy now runs the full test suite first.

### Fixes from the 20 November code reviews

Choosing another matching question in Ask keeps your dates and groups. A link with a question code in other capitals opens that question, and an unknown code says so instead of showing the first question. In dark mode the second, third and other chart series have their own colours again, and the Retailer databank's trend lines their markers. The In store vs online footnote no longer says small groups are hidden: every group is shown, with its base. Behind the scenes: rolling back to an older published version keeps that version, the Forsta check catches a multi-answer stored the wrong way round, a China folder named with a month and year is not read as a day, the audiences rules file is found again, and staff never share cached answers with someone outside Coresight.

### Ask puts the finding and its survey source first

Ask CIP leads with a plain-language result, followed by the country, periods, number of survey waves, weighting and source link. It explains when a survey cannot establish what caused a change. For a request for weighted figures or for the same people across two answers, Ask explains what it can calculate and where to check next. A comparison explains when a requested group has no figures for one of the periods. If a cached data request overlaps a publication change, the API asks the caller to retry against the new version. A failed refresh of an existing published file keeps the previous file readable.

### Ask CIP shows the sample size behind each figure

Ask CIP shows each figure with its own sample size in the table and in CSV and Excel. A chart labels the group with a sample size when its figures share one base. Suggested questions keep their selected survey question, clearing the box cancels the active request, and optional AI checks can update the period or group as well as the question. The answer view shows how the question was matched. Ask explains when it lacks a requested period or demographic group.

## 17 November 2026

### The portal is now called Consumer Intelligence Platform

Consumer Intelligence Portal is renamed Consumer Intelligence Platform, still CIP for short. The new name is at the top of every page, on the public pages and their titles in search results, on the sign-in page, in the data summary emails, in the Excel downloads and in the MCP connector's description. Ask CIP keeps its name.

## 16 November 2026

### Home: one question box, then sections you open, sorted by how often the research runs

The Home page now opens with one question: “What would you like to understand?”, a box to ask it in your own words (with the microphone), and the button Ask. Everything else is a section that opens with a click and starts closed on every visit: Explore key research, This week's grocery shopping and Need to dig deeper. Explore key research now lists every survey and tracker you can open, 14 in all with Tariffs & inflation, Financial health, GLP-1, Gas prices, Social commerce, the two holiday trackers and the China weekly tracker added, each marked with how often it runs, and “Show research that runs” filters them: weekly (Shopping & Spending, In store vs online, Consumer sentiment, Retailer databank, China, Gas prices), monthly (GenAI, Tariffs & inflation, Financial health, GLP-1), quarterly (Sector databank and Social commerce, each sector every 12 weeks) and seasonal (the holiday trackers). This week's figures show groceries only, in store and online. The latest wave, with its number of adults, has moved to the bottom of the page.

### How positive people feel: every retailer its sector asks about, not only apparel

In the Retailer databank, “How positive people feel” read only the apparel module's question, which asks about 28 apparel retailers, so Costco, Dollar General, Dollar Tree, Family Dollar and most others showed “not asked”. Every sector module asks the same question about its own retailers, and the panel now reads them all: mass merchants and warehouse clubs (Walmart, Costco, Sam's Club, Target, BJ's), dollar stores (Dollar General, Dollar Tree, Family Dollar, Five Below), off-price, eCommerce, home furnishings, home improvement, department stores, luxury, footwear and apparel. Each bar names the module that asked and its date and base: on 9 November 79.6% of 294 asked felt positive about Walmart and 87.8% of 115 about Costco. The panel also shows in the Sector and Compare sectors views now. The new figures appear after the next publish.

### Who shops there: a last gender pie on its own sits in the middle

In the Retailer databank, the gender pies of “Who shops there” run four to a row; with five retailers the fifth sat alone at the left with empty space beside it. A row that is not full is now centred.

### Who shops there: generation, income, region and area as side-by-side bars

In the Retailer databank, “Who shops there” now draws generation, household income, region and area as horizontal bars, one per retailer, in every view (Retailer, Compare retailers, Sector, Compare sectors). A grey line across each group marks the share of all adults (or of the sector's shoppers), so a bar past the line means that group is over-represented among the retailer's shoppers. Each retailer's percentage is written in its colour on the right of every group. Gender stays a pie, and hovering still shows every figure.

### In store vs online now goes back to August 2022

In store vs online drew each category's trend only from January 2024, with an empty stretch before it, because the in-store and online questions were asked as Q4 and Q5 until December 2023 and the page read only q2 and q3 (which held other questions in those weeks). It now reads both, so every week from August 2022 is there: 196 weeks instead of 125, and each one can be picked in the Week list. Weeks in which q2 and q3 asked something else no longer appear in the list. The trend chart is now as tall as the category chart beside it, so its card no longer has an empty space underneath. Books, movies, music or video games now appears too: it was missing every week because the online question adds “(incl. digital purchases)” to its name.

### Retailer databank: each retailer's figure in its own small card

In the Retailer databank, “Bought in the past two weeks” (or “Bought from” in a sector) shows each chosen retailer's share in its own small card, one per retailer, like the figures on In store vs online: the short coloured line on top (red for the first retailer, light blue for the others) now sits on a card's edge instead of floating above the name.

## 15 November 2026

### Compare waves and Trends now find every wave that asked the same question

The weekly tracker renumbers its questions over the years (this week's Q1 was Q8_2 and Q10_1 in earlier waves), and Compare waves and Trends looked only under the question's own number, so about half of each question's history was missing. They now follow the question itself: every wave that asked exactly the same wording joins, under whatever number it had, as long as most of its answers are the same. A question that only shares a number (the 2022–23 Q1 about avoiding public areas) stays out, and so does the same wording over a different list. For this week's 41 questions, the waves you can compare go from 1,737 to 3,097: Q1 from 125 to 195 waves, gender from 72 to 192. The source line names the earlier numbers it joined. The questions left out are now listed once each, with how many waves asked them and when, instead of the same wording repeated for every wave, and a table compares only the answers the waves on screen gave.

### Ask CIP moves you to the new answer when you continue the analysis

Clicking a question under “Continue the analysis” now scrolls the page back up to the box, where the new answer appears, instead of leaving you looking at the previous one at the bottom.

### Speak your question to Ask CIP

Ask CIP now has a microphone button: press it and speak your question instead of typing it, and the words appear in the box for you to check and send. It uses the browser's own speech-to-text (Chrome and Edge use Google's or Microsoft's speech service, Safari Apple's), so nothing reaches CIP's servers and it costs CIP nothing; the browser asks your permission the first time and shows while it is listening. The mic is in both Ask CIP boxes: on the Home page and on the Ask CIP page. The button appears only in browsers that can do this (Chrome, Edge, Safari).

### A second check of every state: the Monday watch, Forsta retries, China uploads and deploys

A second check of the portal's state machines on staging found four slips, now fixed, and confirmed the 15 November fixes live. When another load held the lock at the moment Monday's watch checked, the watch could not see that the wave was in, and at its deadline told Teams "not in after 54 h (status: unknown)"; it now reads the wave's status at every check. A 30-minute check no longer writes over the watch's sign of life, which let the checks keep cutting in ahead of it. A Forsta wave that kept failing while live is tried again the moment Forsta closes it, when its final data is readable, not 6 hours later. A China week loaded on the Upload survey page now judges the team's metric alerts, as every other load does. And a deploy now waits until the new container has its data in place (/readyz), not only until it answers.

### Ask CIP puts misspelt words right and suggests questions as you type, at no cost

While you type a question, Ask CIP now puts misspelt words right and, after each pause, suggests up to six survey questions by their name; choose one and it answers from that question. Typing costs nothing: no AI is asked. Misspelt survey words are put right too (subcription is subscription, infaltion is inflation), and a short start of a two-word name before its second word (Ama Prime is Amazon Prime), while a real word (noted, having, marking) is left alone; an answer says when it put the spelling right. Holiday spending now answers from the holiday spending questions, not the holiday purchases one that carried the name by mistake. An AI reading kept from an older AI model is no longer reused: one had turned a right answer wrong. Ask builds its question index after each publish by itself, so the first question after a publish no longer waits several seconds. With no AI, 47 of the 50 questions people typed on staging are right (45 before); the golden set (154 of 161) and the big exam (2,496 of 3,000) are unchanged.

### Saving never holds up the portal, un-saving a view removes it for the team, and every deploy checks itself

Saving a view, alert, audience, board, pin or comment, and counting an audience, now wait for the database away from the portal's one worker, so nobody's page waits while someone else saves. Un-saving a view with its bookmark button also removes it from the team's saved views, so saving it again no longer lists it twice. Every deploy now starts the new image first and pushes it only if its API answers and Ask's search model is inside; after the switch it waits until the site reports the new build, and fails loudly if it does not within 10 minutes. A failed model download now stops the build instead of shipping an Ask that searches by words alone, and the production pipeline, which pushed a tag it never built, can deploy. A new address, /readyz, answers only once a new container has its data in place, for deployment slots and Azure Front Door.

### The Access page offers every entry of the left menu, group by group, each with its own pages

The Access page now lists the left menu itself: Explore, Core research (with a survey wave's screens under it), Trackers, Reference, Research operations, Administration and the tools on every screen, 46 menus in all, each one for a role, a client or one person to have or not. Drag a menu between On the menu and Hidden, or use its Show and Hide button, as before; each column lists its menus under the left menu's groups, a wave's screens under their own heading. New menus of their own: Survey library; Shopping & Spending and the China weekly tracker, where turning one off takes its waves out of the Library, Search, Ask and every wave screen; In store vs online; each of the eight trackers, its page and its panel on a wave's Overview; Methodology; What's new; each of the eight Forsta pages; and Upload survey and Logs, which until now only the super admin had. Home and a wave's Overview stay on for everyone, and Access stays the super admin's alone, as whoever had it could give themselves everything. Menus chosen before today lose nothing: each new menu follows the one it grew from (a tracker follows Topic dashboards, In store vs online follows Question explorer, the library and the reference pages stay on), and the admin pages stay the super admin's until given. The left menu, typed addresses, API keys and the MCP connector all follow the same choice.

### The pipeline keeps uploads open on launch Mondays, tries a failed wave again and closes every load it stops

Monday's watch now takes the pipeline's lock only while it checks Forsta, every 30 minutes, not for its 54 hours, so the Upload survey page and the China loader work during launch week; the watch starts with the 17:30 IST launch run, so its 54 hours end Wednesday 23:30 IST. A Forsta wave that fails three times in a row is tried again every 6 hours instead of never, and its failure email says when and gives the command to load it at once. A load that fails or is stopped (a deploy, a stopped container) now closes its record as failed and hides its half-loaded wave, for Forsta, China, Qualtrics and the old warehouse alike; a load killed outright no longer blocks the database upgrade, and a rollback never lands on a half-written published version. The China loader from SharePoint publishes under the same lock as every other run, emails once when a week fails to load and tries it at most three times, keeps no extra copies when another run holds the lock, and emails when it cannot reach Microsoft Graph. The watchdog no longer reports a stopped scheduler while a long run is within the time it promised, the integrity check warns when Forsta hibernates a wave before its final reload, and Friday's full integrity check runs once, not on every 30-minute check.

### Sign-in, API keys and alerts are safer, and alerts judge every wave's final data

Metric alerts are judged again on a wave's final data once Forsta closes it, fire at most once per wave, and now also follow China weeks and hand-run loads; the Library shows when an alert last fired at once. An alert is no longer sent to someone who lost access to it or its study, and what someone typed reaches Teams with no link of theirs, set by the signed-in owner's email. A session that was signed out or revoked stays out after the portal restarts; API keys no longer open admin pages or carry any of their owner's admin powers, and are always rate-limited; offboarding someone also revokes their API keys; sign-in refuses an email address the identity provider has not verified; and signing in from two browser tabs at once works in both. Ask's AI checks and Search have their own per-minute limits, so no one can spend the month's AI budget for everyone.

### Save buttons cannot be pressed twice, weighted figures carry no unweighted verdict, and Ask stays fresh

Pin, Create board, Comment, Set alert, Save for the team and Make a key grey out and say they are working until the server answers, so a double click no longer makes two boards, two alerts or a key whose secret is never shown, and they work again if the request fails. The Logs page asks for the admin token only when the server refuses access; a failed download, a server error or a lost connection says so. With weighted figures on, no answer is marked significant, as the significance tests are on the unweighted figures, and the page says so; the MCP connector's question results say so and give each comparison's base, and a wave's data no longer carries weighted figures to accounts without them. Ask CIP answers a question the AI check settled at once the next time the same person asks it, keeps no answer given before its search model is ready after a deploy, and never writes over the verified answers' file when it cannot read it.

### Ask CIP reads a full name before a part of it, gives every wave for how many in all waves, and pauses an AI that refuses its key

A name the question says in full is no longer read as a shorter answer in the retailer lists: How many people bought Amazon prime? is the Amazon Prime membership question, not Amazon's share of nonfood purchases, which Ask's own reader had picked so surely that the AI was never asked. A name that is itself an answer (Dollar General) still means its retailer list. How many people … in all waves now gives the figure for every wave, as What share … in all waves did, not one count over all of them. When OpenAI refuses the key (no credit, too many calls or a wrong key), Ask sends it nothing for 15 minutes and answers with its own model, so no question waits on a call bound to fail; the admin health report says why the AI is off and when it is tried again. With no AI, the 50 questions people typed on staging went from 43 to 45 right (these two were found among them); the golden set (154 of 161) and the big exam (2,496 of 3,000) are unchanged.

### Ask CIP leads with the headline figures, draws the chart that fits, says what it tells us and where to go next

An answer now opens with up to three headline figures, each with its base or group: the latest share, the change since the first wave and the latest change (significant or not), or the highest and lowest group and the gap between them, tested for significance. A group of fewer than 50 respondents is never called the highest or lowest, and a yes or a no is said with its question (Gas prices reducing spending: yes, 67.2%, 542 of 807 respondents). The chart is the form the figures need: a line for a trend (only the main answer for a yes or no), one segmented bar for a single choice in up to six parts, 100% stacked bars by group with each group's base (n), a heatmap for many answers by four or more groups with a Base (n) row, a dot plot for the first against the latest wave, and ranked bars otherwise. What this tells us gives the finding in one sentence, in the words people use (About two in three (67.2%) answered “Yes” to …), with dates as people say them (on 9 Nov 2026, in Nov 2026, over 9 Oct 2023 – 28 Sep 2026), and calls an answer the most common only when it leads all the answers, not just those named. Continue the analysis offers up to three follow-up questions (by generation, by income, over time, in the first and latest wave), made from templates with no extra computing and never stored; each is tied to its survey question and its survey's country, so it answers from that same question even where other surveys share the topic, and all 497 asked back in a test did. Client view shows the figures, chart, takeaway, notes and source, and when the AI is checking or has changed an answer; Analyst view adds every figure in sentences, how the question was read, Save as verified and the table of every figure and its base. All of it adds under a millisecond to an answer.

## 14 November 2026

### Ask CIP's verified answers hold when new surveys arrive, and its search and reading models can be swapped

A verified answer, checked by an analyst, now wins over a stored business name: Categories purchased online in the latest survey is the weekly online categories question again, not a quarterly one sharing its name. Saved and verified answers keep their survey question's wording, so when a new survey reuses a question code and renumbers it, the answer is found again; after every publish each verified answer is asked again and must still give its own survey question (all 37 do), and any that does not is reported. The search model and Ask's own reader are each a folder with its own settings (how it reads text, its thresholds), so a bigger model can be dropped in; a new notebook tests 12 search models and three bigger readers on our own questions.

### Ask CIP is tested on the questions people really type, and reads holidays, all waves and saved answers better

A new test (scripts/ask_fresh.yml) holds the 50 questions people typed on staging that are not in the golden set: Ask's own model, with no AI, answered 41 right (82%), and 43 (86%) after three fixes. A question about an event (Labor Day, Memorial Day, Super Bowl, Presidents' Day, the Fourth of July, New Year, Singles' Day, Christmas) now answers only a question naming it, so personal finances quarterly is no longer the Labor Day question; in the all wave reads as every wave; and four event questions lost the name Holiday spending. Eight questions people ask (Amazon shoppers, Cyber Monday, holiday spending expectations, the pace of price increases, sustainability, holiday shopping status and GLP-1 use over time) are verified answers: instant, with no model. An answer the AI settled is reused only while that AI model is in use, so changing the model starts clean.

### Ask CIP picks the survey question with its own model, and asks the AI only when that model is unsure

Ask CIP now has its own small model on our server that reads a question with the closest survey questions and picks the one that answers it, as the AI check did, in about 70 milliseconds and at no cost. It learnt from 12,281 practice questions answered by a large open model (Qwen3-32B) on Google Colab, with no OpenAI. When it is sure, its pick is final; only when it is unsure, and an AI key is set, does the AI check read the question: on the 3,000-question test the AI was asked for 13% of questions and on the 161 hand-written ones for 34%, where it used to read about 80%. With no AI key at all, right answers on the hand-written questions go from 86.3% to 95.7% (154 of 161); with a large model checking the unsure ones, 98.8% (159 of 161) on our test machine; on staging, where the AI account had run out of credit so only earlier saved AI answers were used, 95.7% (154). Also fixed: Economic outlook now means the weekly economy question (84 waves), not a 2023 inflation question; a misspelt retailer such as walmrt is read as Walmart; a question naming only a retailer and a time (Amazon in 2025 vs 2026) is answered from the weekly retailer lists, even when the AI picks a question with the retailer in its wording (Prime membership); an answer the AI settled earlier is reused only where the AI would be asked again, so when Ask's own model is sure, its pick stands (staging had answered Which foods do GLP-1 users eat more or less? from an earlier AI answer to a different question); and a trend in dining out comes from the weekly activities question (Gone to a restaurant).

## 13 November 2026

### Ask CIP no longer overrules a right pick, and says which group a top list is for

Tested on 13 November with the 161 hand-written questions and the 38,316-question bank, Ask's own rules were replacing right picks: How do people feel about Target? was answered from the purchases list (Target is one of its answers), Do people expect their finances to get better or worse? from the economy question (both use much better … much worse), and an online grocery trend from grocery categories instead of the weekly online purchases. Each rule now steps aside when the pick asks what the question asks. The AI check sees each survey question once (one had filled four of its fourteen places), the answers the question names first, and is told that a topic alone means its main question and that a thing no candidate mentions is not in the surveys. A question the AI settled is remembered by the survey question's own key, so it no longer comes back from another study that reused the code (13 of 161 had). A top list for one group says so (Top 5 among Gen Z), a question not asked in the period named is answered from the same question in another study, and Don’t know with a curly apostrophe is left out like Don't know. Right answers on the hand-written questions (two answer keys corrected): 91.3% to 93.8% with the AI check as it is (gpt-4o-mini), 90.7% to 96.3% with gpt-4.1; on the bank with no AI at all, 77.8% to 80.7%.

### Ask CIP answers at once again, learns from every AI check, and leads with the number

The best answer now shows at once; where Ask is unsure, the AI check confirms or replaces it about a second later, and “Which did you mean?” appears only when no AI check can follow (asked live on 12 November, half of the 161 test questions had waited for the AI). Every question the AI check settles is kept, and the same or a close question is then answered from it at once, with no AI call, for everyone. Answers lead with the figure: “53.0% answered ‘I have an Amazon Prime membership myself’ in 12 Oct 2026, the latest (214 of 404 respondents)”. After a deploy that changes the search model, its vectors are rebuilt in a separate, low-priority process, so the portal's memory stays where it was (it had grown from 500 MB to 1.1 GB) and no question waits behind the rebuild (one had waited 7 minutes). Ask is ready for a second-stage reader trained on our survey questions, used when its files are installed.

## 12 November 2026

### Ask CIP asks which question you meant when two are too close to call

When Ask CIP finds a survey question by meaning and another survey question asking something different comes almost as close, it no longer picks one silently: it shows the closest survey questions and asks which you meant, and with the AI check on, the AI settles it in about a second. Measured on 12 November 2026: of the answers it gives at once, 98.7% were right on 5,000 test questions and 97.6% on the 161 hand-written ones, against 93.9% and 86% when it always picked. The same question asked by several studies in slightly different words is never counted as a different question. Each search model now keeps its own thresholds and its own saved vectors, so a retrained model can be swapped in without mixing two models' figures.

### Ask CIP checks every new survey itself, and marks which answers are verified

Each time a survey is published, its new questions are named by the small AI model (what analysts call each, other ways they say it, eight example questions), and questions that share a name but ask different things are given a name each. Then every question people may ask about that survey's questions is asked and scored: its latest figure, trend, each cut its data holds (generation, income, region, gender, age, area), periods compared, top answers and one named answer. Admins see the result for each survey on the Logs page (Ask CIP, survey by survey), with the questions it got wrong. A question that uses a survey question's name is answered from it at once, with its own periods and cuts, and marked Verified; any other answer is marked Best match, with the question it used to check. Of 29,838 verified answers across the whole catalogue, 99.3% were right; on the four newest US weekly surveys, 99.1% to 99.6% of all questions were right and 99.4% to 99.9% of verified ones. Fixed along the way: in the past month (the survey's own wording) is no longer read as a period, since Aug 2025 means from August on, by household income, which generation and women or men are read as cuts, rising or falling asks for a trend, a quoted Yes no longer finds the tax-return question, and a question whose groups were never asked it gets its table instead of an error.

### The developers' speed badge is removed

The speed badge a developer could switch on with ?perf=1 timed page loads, data requests and charts in that one browser. It saved nothing on the server and no one else saw it, and Chrome's own developer tools measure the same, so it is removed: about 1,000 lines less for every page to download and run. The Logs page's monitoring dashboard (CPU, memory, bandwidth, requests per minute, server speed, the busiest pages, visitors and their city, recent errors, the cache and storage tables) stays as it is.

### Full pies with a colour each for men and women in the databanks, and donuts on the tracker pages

In the Retailer databank and the Sector databank, Who shops there shows each retailer's or sector's shoppers by gender as a full pie, men in blue and women in red: both were light blue in dark mode and read as one slice. Food, nonfood or both is a full pie too. Each tracker page (Tariffs & inflation and the others) now shows the chosen week's headline figures as donuts, the share who said it against everyone else asked, above the chart of every week.

### Trends, Compare waves and Ask CIP show each question's own answers when a question code was reused

A survey code is sometimes used again for a different question in a later week (Q22 was a facial recognition question one week and Thanksgiving spending another). Trends, Compare waves and Ask CIP read one file per code, and that file kept one name per answer number, so a week could show another question's answers: How much did you spend at drug stores? listed reasons for shopping there, Have you purchased any footwear? listed price bands, and What is your age group? listed single ages (86 codes). Each question now keeps its own answers. No figure changed: every count in all 2,666 question files is the same, and so are every weekly report and the Sector databank. Expected vs actual now names each question's own answers; for Prime Big Deal Days and Singles' Day it pairs the expectations with Yes, No and Cannot remember by answer number, which the research team should review. Ask CIP joins more weeks of the same question (Amazon Prime membership: 22 weeks, was 10) and no longer joins Halloween plans (Will you spend…) with Halloween spending (Did you spend…). The 28 questions that asked for a dollar amount whose amounts were never loaded are no longer answered as 100% answered $. Trends offers only the question's own answers to pick from. It shows after the next publish, which rebuilds every question file.

### After a deploy, screens wait for their figures instead of showing nothing, and dark-mode charts read cleanly

For about a minute after each deploy the portal restores its published figures in the background; the Sector databank, Retailer databank, Expected vs actual and weekly report lists asked in that minute got nothing and stayed empty until the page was reloaded. They now wait and ask again every 3 seconds for up to 90 seconds. Ask CIP no longer stops while it learns new survey questions after a deploy (it answered Busy for about 7 minutes on 12 Nov): it answers by the questions' words meanwhile (82% right on the golden set, against 86% once ready). Value labels on charts no longer have a light outline that smeared them in dark mode. Pickers such as Retailers and Weeks close when you click anywhere else or press Escape, as menus already did.

### The first question after a pause no longer waits for a new secure connection

Azure closes a connection left idle for about 4 minutes, and opening a new one from India takes 0.5 to 0.7 seconds before anything is asked. While a portal tab is in view, it now sends a tiny check every 2 minutes so the connection stays open: the next question or page pays only the distance, about 0.26 seconds. Hidden tabs send nothing, and the checks are left out of the Logs page's traffic.

### For admins: the Logs page refreshes in milliseconds

The Logs page's dashboard (GET /api/v1/admin/metrics) took about 2 seconds on staging: each refresh re-read seven log files, the newest 4 MB of each, from Azure's network storage, to list problems, restarts, ETL runs, sign-ins and the machine samples. The API now reads them once a minute in the background, and a refresh answers from memory: about 2 milliseconds instead of 145 on the same files on a Mac. The lists are at most a minute old, as often as the page refreshes.

### Ask CIP keeps to one country, marks small groups, and says so when no survey asks

A question is now answered only from its own country's waves: one naming China (China, Chinese) from the China survey, any other from the US surveys. Since the China history was loaded, How has consumer sentiment about the economy changed? could be answered from the China tracker. A figure resting on fewer than 50 people now says small base, read with caution, as the dashboards do. Words that are the survey's own answers are no longer read as a period: spend more this holiday season vs last year now shows the 2026 season, not 2025. Questions about nothing the surveys cover (Best pizza recipe, Translate hello into Spanish) are no longer answered from the nearest survey question. On staging's data, without the AI model as staging runs today, the first answer is right for 139 of 161 golden questions (86%), up from 132 (82%); the golden test now counts an answer from the wrong country as wrong.

### Ask CIP answers in a split second, then checks with AI, and every chart can be redrawn

Ask CIP now finds the survey question with a small search model on our own server instead of OpenAI: about 10 milliseconds and free, where each call to OpenAI took about 0.7 seconds. Every survey question also has eight questions an analyst might type to get its figures, written once by the small AI model for $0.17 in all (config/ask_semantic.json), and a question is matched against them too. The answer appears at once; when the AI model's reading may differ, it reads the question in the background (about 1.5 seconds) and the answer is replaced only if it found a differently worded question, marked updated by AI. On the 156-question golden set, the first answer is right for 132 (85%) and the checked answer for 137 (88%), up from 136 at about 2 seconds. Every chart has a switch: line or columns over time; bars, columns or a donut (when the answers add up to 100%) for one period; or the table of every figure. Other questions that match no longer lists the same wording more than once. Reusing an earlier reading of a reworded question is gone: it could repeat a wrong reading (How worried are people about tariffs? was answered from the tariff-avoidance question). Ask CIP is no longer in the left menu: ask from the box on the Home page. Answers the AI model picks out but the question does not name are no longer put first: Which retailers do Gen Z prefer? shows the retailers ranked, not one chosen at random. A reply naming several answers is no longer cut off.

### The Retailer databank: any retailer or sector, alone or side by side, over any weeks

Retailer comparison is now the Retailer databank, with four views: one retailer, retailers side by side, one sector, and two sectors with any of their retailers (for example Walmart, Target and Kohl's among clothing shoppers against Walmart among beauty shoppers). Choose one week or several: only weeks in which every chosen retailer was asked are offered, and several weeks are added together. Each view shows how many shop there, week by week, food, nonfood or both, who the shoppers are (gender, generation, household income, region, and urban, suburban or rural) next to all adults or the sector's shoppers, how positive people feel where the apparel survey asked, and for one retailer its share in every sector it is asked in. It covers the weekly tracker since July 2025 (71 weeks, 21 weekly retailers, 11 sectors), computed when data is published, so every choice is instant.

### A shorter menu: the weekly reports open from their trackers

The China weekly report and Consumer sentiment links are gone from the left menu: each was the Weekly report tab of the tracker above it (China weekly tracker, Shopping & Spending), which still opens it, as does the Home page.

## 11 November 2026

### Survey weeks loaded straight into the database appear within 30 minutes

Weeks loaded into the database outside the scheduled Forsta run (such as the China history from SharePoint) were only published at the next restart or the next Forsta load. The 30-minute check now publishes them when the database is ahead of the portal's files.

### Ask CIP finds its OpenAI key whatever case the setting is typed in

The server's OpenAI key setting is now found in any case (OPENAPI_KEY, open_api_key, OPENAI_API_KEY and the like). Staging had a key set but Ask CIP reported none and answered by rules only.

### Retailer comparison and the other prebuilt screens no longer go missing after a restart

After a deploy or restart the server brings back its prebuilt files (Retailer comparison, Sectors, Expected vs actual, the weekly reports, the public figures, Ask CIP's index) from its backup. If another data run held the lock at that moment, such as the old container's run or a data load from elsewhere, it gave up at once, and those screens showed nothing until the next wave was published; whether it happened depended on timing, which is why it came and went. The restore now waits its turn (up to 6 hours, taking the lock in the first gap), and if it still has not run, the server tries again every hour.

### China weekly report, every China week since 2023, and the analysts' calculations done by the portal

Each China week now has a weekly report like the US one, built from the analysts' monthly China CSI deck and their aggregation workbook and computed when the week is published: net optimism for the economy and personal finances (positive minus negative), weekly and as four-week rolling averages, with personal finances against a year ago; four-week tables of activities, what was bought in store and online, spending plans and places avoided, each as four-week averages or single weeks with the one-week and four-week changes; every answer of the sentiment questions over 28 weeks; and the margin of error. China weekly report, in the menu under Core research, opens the newest. On real data it reproduces the Sep 2026 deck: net economic optimism 43.7% on Aug 31 and 38.6% on Sep 28 (31.1% that week), personal finances 40.4% to 35.2% (30.9%). Checking the workbook week by week against Baidu's own counts found two faults the portal does not repeat: from Jun 2024 to Jul 2026 most rows of its activities and in-store sheets carry another answer's figures (the Watched TV row holds Played computer games), and its four-week changes still read January or July 2026 columns. The China history loads the same way as a new week: 149 weeks from Oct 2023 to Sep 2026, each equal to Baidu's crosstab. The loader now reads files re-saved with day-first dates (“26/05/25 20:06”), the 2023-24 age wording (“18-25 周岁”) and a month's extra questions in the crosstab (luxury, 618, Singles' Day, AI), which it skips. The Upload survey page needs nothing else: drop the week's two files and every figure is checked, loaded and published. Every number of the 22 monthly decks from Dec 2024 to Sep 2026 (34,198 chart points and table cells) was compared with the portal's: 95.0% are equal to the printed decimal, six decks in every number, and each of the rest is traced to a wrong label or averaging in the deck, a week the portal lacks, or a deck figure Baidu's own crosstab contradicts. The Singles' Day week of Nov 17 2025, which asks its own questions before the tracker's, now loads too. A week folder named more than three weeks away from its own answers loads as the answers' week: “2026/July/Survey of June 27” is the week of Jul 27. Data points to watch now shows every significant move up to three: each table's biggest first, then the next biggest from any table, so the week of Oct 26, when only in-store buying moved significantly, shows both of its moves (apparel +4.1 PPTs, sports products +3.9) under “Two data points to watch”; a quiet week shows fewer, never a move that is not significant.

### China survey: October loaded, the analysts' translation, and SharePoint pick-up

The four China Consumer Survey weeks of October 2026 (surveys of Oct 5, 12, 19 and 26; 539 to 574 people each) are in the portal, every figure equal to Baidu's crosstab, with week-on-week changes and cuts by gender, age, income and city tier. Their English is now the analysts' own translation, and each week is named as the analysts name it: the survey of Oct 26 was answered on 3 Nov. Once IT grants read access to the China folder on SharePoint, CIP checks the folder every 10 minutes and loads any new or replaced week by itself, with the same checks as the Upload survey page; a week whose files do not match is reported once and not loaded. China weekly tracker, in the menu under Core research, opens the newest China week; the wave switcher steps through the others. Besides the 10-minute check, a new week can now arrive within a minute: a Power Automate flow on the China folder, or Microsoft's own webhook, calls CIP when a file lands, and the timed check then runs hourly as a safety net; a flow can also upload the two files itself with an API key. A deploy no longer hides weeks loaded since the last publish: when the restored files are older than the database, the new waves are published at once. After each publish the newest China week's cross-tabs are put in the cache too, as the newest US week's always were, so the first person to open them waits about 2 ms, not 1 s.

### Ask CIP knows every survey question's business name, and is checked against 156 analyst questions

Every survey question now has a short business name, a few other ways analysts say it and a topic (Amazon Prime membership, Nonfood retailers bought from), written once by the small AI model for $0.06 in all and kept in config/ask_semantic.json; Ask CIP searches them, and only questions added later are named. Common questions an analyst has checked are answered from a verified list with no model call, and an admin can add one from any answer with Save as verified. A survey question about an event (holiday, Prime Day, Black Friday, back to school) now answers only a question that names one, so Walmart shoppers is the weekly retailer list, not the holiday one; a retailer named in a long-running list brings that list in; and a question not asked in the period you name moves to a list naming the same retailer that was. When two survey questions are equally likely, the second is offered as Did you mean. A golden set of 156 analysts' questions (scripts/ask_golden.py) is run before every release: 135 right (87%), up from 126.

### Ask CIP understands questions with a small AI model, for a fraction of a cent

Ask CIP now reads a new question with a small AI model (OpenAI gpt-4o-mini) over the survey questions found by meaning, so “How many people have subscribed to Amazon Prime?”, “Which retailers do Gen Z prefer?” or “How worried are people about tariffs?” find the right survey question. The model only picks the question and reads what is asked; every figure, chart and sentence is still computed exactly from the surveys, and the dates you name are read by rules. With no time named, a question asked over many waves is answered as a trend with the latest figure first; a question by a group (generation, gender, income) compares the groups in the latest wave. A question no survey asks is said so, with the closest questions, without calling the model. Each answer has Export (CSV, Excel, PowerPoint, PNG image) and Pin, and clearing the question box clears the answers. A new question costs about $0.0002 and the same question again nothing (every reading is kept); spend has a monthly cap (CIP_ASK_BUDGET_USD, $0.50 unless set). 55 of 60 analysts' questions find the right survey question in testing.

## 10 November 2026

### Ask CIP joins a question's codes over the years, answers in Claude and other assistants, and lays answers out as a conversation

A question asked under different codes over the years is now one series: “What share bought from Amazon in all waves?” covers 193 waves from December 2020, joined from five codes (Q10_2, Q12_2, Q6_2, q5, q0007), and the answer says so. A month, quarter or year with no wave shows as a gap in the chart and is named (“Not asked in: 2023”), never drawn as a smooth line. Each answer now appears right under the question box, newest first: the headline figure with its numbers in bold, the other points as a list, the chart, notes, the source with a link to Trends or the Question explorer, and every figure with its base (a long series turns round so periods run down the page). With the Weighted switch on, the answer says it is unweighted. The MCP connector has a new ask tool that answers exactly as the page does, under the same menu and limits, and its search_questions now finds one entry per question over every code it was asked under.

### Ask CIP answers any survey question with exact figures and a chart, in milliseconds

Ask CIP now works out its answers itself, from the surveys only, with no AI model and nothing sent outside Coresight. Ask for a share (“what share bought from Amazon in the latest wave”), how many people, the top answers, a trend week by week, every two weeks, every four weeks, by month, quarter or year, a comparison (“the first wave vs the latest”, “2025 vs 2026”, “October vs September”) or a cut (“by generation”, “Gen Z”, “by region”). It finds the survey question, including annual and ad hoc studies, topic dashboards, sectors and the weekly report's questions, works out every figure exactly from the people who answered (a month or a quarter adds up its waves' respondents), says whether a change is significant, and draws the chart that fits: a line over time, bars, grouped bars by a cut, or a donut. Every figure and its base is in the table under the chart, with a link to the full screen and other questions that match. A code older surveys reused for a different question is kept apart, and words the survey itself uses (“in the past two weeks”, “Valentine's Day 2025”) are not read as dates. An answer takes a few milliseconds; tested on 10,000 generated questions and under 50 people asking at once, while the rest of the portal stayed as fast as when idle.

### In store vs online, and a page for every tracker

A new In store vs online page shows which categories people bought in a store and which online in the past two weeks: four headline figures with their change against last week, every category side by side, and the chosen category over every week since 2020. Pick the week, a group of people (gender, generation, income, region and more) and a category, or click a category in the chart. Each tracker (GenAI, GLP-1, financial health, tariffs and inflation, gas prices, holiday, social commerce) and each sector dashboard now has its own page: pick a week for its headline figures and takeaways, and see every headline figure across all the weeks it ran. Everything is read from files already published, so switching is instant.

### A tidier menu you can hide

The menu on the left is grouped as on the new design: Explore, Core research (the Shopping & Spending survey, in store vs online, consumer sentiment, retailer comparison, the sector databank, expected vs actual), Trackers, Reference, then the admin groups. The button at the top left hides it for more room and shows it again, as does Ctrl or ⌘ with B; the portal remembers your choice. Cards now have a soft red outline that deepens when you point at them.

### A Home page

The portal now opens on a Home page: ask Coresight a question straight away (the answer opens on the Ask CIP page), or start from one of the main research areas: the Shopping & Spending survey, the GenAI survey, in store vs online, consumer sentiment, retailer comparison and the sector databank. It also shows this week's share buying groceries and clothing in store and online, each with its change against last week, and a way into the cross-tabs. The Survey library moved to its own place in the menu, just under Home.

### Retailer comparison, and Ask CIP

A new Retailer comparison page under Research data puts two retailers side by side: how many people bought from each in the past two weeks (any product, food and nonfood), who their shoppers are by gender, generation and household income next to all adults, and how positive people feel about them where the apparel survey asked. Each figure adds the chosen week to the three before it, so a retailer like Costco has enough shoppers to describe; a profile is shown only from 30 shoppers. Every figure is computed when data is published, so the page opens at once. Ask CIP is now called Ask CIP.

### The weekly report checked against the analysts' workbooks

Every number of the weekly report was checked against the analysts' Excel workbooks for 24 weeks (1 June to 9 November 2026) and the seven PDF reports from 22 September to 3 November: the 13-week tables for food and nonfood retailers, categories bought in store and online, and activities match the PDFs to 0.1 point, and so do the weekly and four-week sentiment figures for all respondents. The activities table now leaves out going to a movie theater and to a live performance, as the PDF reports always have. Where the report's income figures differ from the PDFs, the analysts' workbooks were at fault: the 7 September 2026 income columns repeat the 24 August week, and a few 2025 weeks were typed by hand; the portal counts them from the answers.

### Weighted figures and API keys and MCP are switches on the Access page

The Access page has two new switches per role, client and person. Weighted figures: without it the Weighted switch is not in the header, a browser left on weighted goes back to unweighted, and the MCP connector answers unweighted. API keys and MCP: without it the Account page has no keys card, the API guide does not open, no key can be made, and every key the person already made is refused (403) for the API and the MCP connector until it is turned back on. The Account card is now called API keys and MCP. Search questions was already a switch; without it the header search and the Survey library's Search card are hidden too. Everyone keeps both new switches until the super admin turns them off; Acme-style client packages (core, professional) do not include them.

### A screen taken off your menu stays closed

When the super admin takes a screen off someone's menu on the Access page, its address now closes too: a link, a bookmark or a typed address shows "Not included in your subscription" instead of the screen. Until now the Question explorer still opened from a wave's Overview (its questions and Explore all questions button) and from the Survey library's Questions button, because the screen drew from the Overview's own data. The Overview, the Survey library and Survey preview now link only to screens on your menu, and the question search in the header shows only when Search questions is on your menu. Your keys, the API and the MCP connector already refused those screens' data.

### A closed survey loads within 30 minutes, even after a deploy

The pipeline now checks Forsta every 30 minutes, every day, as a short run the scheduler starts itself. Until now the 30-minute checks on a launch Monday were one long run inside the server, and a deploy stopped it with the server: on 9 November the wave launched at 7:08 PM IST was not loaded until the next morning. A deploy now delays a closed survey by at most 30 minutes, and annual and ad hoc studies load within 30 minutes of closing instead of the next morning. If no check has run for 2 hours, the pipeline-failure email says so.

## 9 November 2026

### Sign out now signs you out of Coresight too

Signing out of the portal now also ends your Coresight sign-in (stage3's csr-idp), so the next Continue with work account asks for your password again. Until now staging had no Coresight sign-out address set, so sign-out only cleared the portal's own cookie and Coresight let you straight back in. For admins, each step of signing out and back in is written to the API log as [SIGN-TRACE] (Logs page, search SIGN-TRACE): the cookies sent, where sign-out went, and how long the browser spent at Coresight's sign-in.

## 8 November 2026

### A cleaner look in light and dark

The portal has a new look in both themes. The menu on the left is white in light mode with thin outline icons, in four groups that fold (Explore, Research data, Research operations, Administration), with a link to the current weekly tracker; dark mode moves from warm brown-black to a cool blue-black. The header names the page you are on. A wave's screens are now tabs in the wave's own card at the top of the page, under its date switcher, and a wave screen's title has a small red label naming the wave. Buttons and boxes have fine outlines on a soft fill, text is a size smaller and calmer, cards have rounder corners and lift slightly when you point at them, the figures at the top of a page carry a small coloured tab, and tables have a light grey heading inside a rounded box. Charts have slimmer bars with rounded ends. Ask CIP and Boards open on a panel that says what to do next, with example questions and how boards work beside it, and an empty list shows an icon and what to do. The footer follows the theme, and the menu on the left stays in place and scrolls on its own however far down the page you are. Upload survey shows its four stages across the top (Select, Validate, Review, Publish), filling in red as each is done; each file has its own box saying what to choose, and a note says what Check compares before anything is written. Every rise is shown in bold green and every fall in bold red, on every screen: the change chips, What changed, Trends, Compare waves, cross-tab arrows, Audiences and the hover cards; a significant change keeps its tinted chip, now in its own colour. The weekly report's three data points to watch are now three cards, each naming its table, the change in green or red, and what moved; its tables and Expected vs actual colour their significant changes the same way. On a wave's overview, each “at a glance” figure is its own card (the first with a red tab, the rest light blue), under the block's name and dates, with the key takeaways in a card of their own. The Columns chart is gone: it showed the same figures as Bars, and long answers overlapped under it; links and saved views that asked for it open as Bars. The Coresight logo, fonts and every figure are unchanged.

### China consumer survey: upload a week from Baidu

Admins have a new Upload survey page under Admin in the menu for the China Consumer Survey, which Baidu QSS fields and which has no connection CIP can reach. Choose the week's raw export and Baidu's topline (as downloaded, .csv and .xls, including files saved from SharePoint) and press Check: CIP counts every answer from the raw rows and compares each base and count with Baidu's topline (123 figures a week), translating the Chinese through a reviewed English codebook. Only when every figure matches can the week be published; it then appears as a China wave with its week-on-week changes, cuts by gender, age, income and city tier, trends and search, and the portal's files are rebuilt in the background. Baidu's topline is kept in the database beside CIP's own figures. Uploading the same week again replaces it. The analysts' English converter swapped Optimistic and Pessimistic for the two outlook questions; the codebook keys every answer by its Chinese words so this cannot happen.

### Safer logs download, steadier Ask CIP and sign-in errors

Ask CIP now gives up on a slow Claude after 25 seconds and answers with the cited figures instead, and an answer that states a percentage none of its sources list is replaced by the cited figures. The Logs page's Excel download no longer lets text sent by a visitor run as a formula, and a failed Teams alert no longer writes its secret link to the log. A sign-in cookie or header with unusual characters now gets a normal refusal instead of an error page. The new-wave email is tried three times before giving up, a missing script file is a "not found" instead of a page, the mobile menu respects reduced motion, a weekly report's figures load as soon as its page starts, and downloads of Forsta reports and the Logs workbook no longer fail in Safari and Firefox.

### Faster from far away and on slow connections

A wave's pages ask for their figures as soon as the page starts loading, and the portal's code downloads in one go instead of in steps. The words and figures show first and the charts follow, so a slow connection no longer waits for the chart library before showing anything. From India a first visit to a wave's overview shows its figures in 1.5 s instead of 2.0 s; on a 200 kbit/s connection in 16 s instead of 28 s, and on 100 kbit/s in 31 s instead of 54 s. A second visit takes about 1 s even at 100 kbit/s, as the portal's files stay in the browser.

### Uptime checks see the portal as up

Uptime checks that ask the portal whether it is up with a HEAD request (as many monitors do) now get "up" instead of "Page not found".

## 7 November 2026

### Times in your own time zone, and India time on the Logs page

Every time in the portal is on a 12-hour clock with AM or PM and the zone's name. Pages show your own time, from your computer's setting (8:26 AM EDT in New York, 5:56 PM IST in India, 1:26 PM CET in Berlin); nothing is looked up or sent to the server. The Logs page always shows India time, now also in the raw log lines and in what Show opens (the log files keep the servers' UTC). The Logs page's first visit after a deploy no longer waits about 5 seconds, and each refresh reads each log once instead of eight times.

### For admins: the Logs page for any dates, every visitor, and one download

The Logs page now shows any time range: the last hour or day minute by minute, and 7 days, 30 days, 17 weeks, a year or any two dates hour by hour (hours are kept from 7 November 2026 on). Choose a visitor to see each request they made, where they came from, and whether they are a person, a bot or Azure's own health check. Show on a problem opens the lines around it in its log, such as an error's full traceback. Download everything saves the range as one Excel file: requests, server time, errors, CPU, memory, bandwidth with their charts, response times, how requests were answered, caches, storage, busiest pages, every visitor, sign-ins, problems, restarts and the requests themselves. Every time in the portal is on a 12-hour clock in India time (8:20 PM IST), the admin-token box appears only when the server asks for it, and the page refreshes once a minute, only while it is open on screen.

### Audiences, stacked charts and older wordings

Changing an audience (adding or removing an answer, opening a saved one) now clears the last figures until you show them again, instead of leaving the previous audience's numbers on screen. A stacked chart with many answers keeps its legend on one scrolling line instead of writing over the bar. Older wordings no longer show HTML codes such as &#39; or &amp;. A wave built since the last publish is listed at once instead of "No such wave".

### The wave switcher works again

Previous wave, Next wave, the wave list and the [ and ] keys on a wave's screens now open the chosen wave on the same screen; since 29 October they opened a "Page not found". Copying a new API key also says when the browser blocks it.

### Question codes in any case

The API and the Claude connector now find a question whatever the case of its code (q1 or Q1, XM3 or xm3): cross-tabs answer as results already did, instead of saying the question is not in the wave.

### Company sign-in only, wherever it is set up

Where Coresight's company sign-in is set up, the portal no longer offers the demo sign-in (any email, no password), whatever its settings say: everyone signs in with their own company account. API keys and the MCP connector keep working as before.

### Your own API keys, and Claude through the portal

Anyone signed in can now make their own API keys on the Account page and use the portal from their own programs, or from Claude and other AI assistants through the portal's MCP connector: search questions, read a wave's results, a trend or a cross-tab. A key acts as you and reads only what your menus show; if a menu is taken away, your keys lose it at the same moment. A key is shown once, and you can revoke it at any time. The new API guide lists every address, the connector's tools and the rules a key follows. (Read the API guide: `/app/api-guide`)

### Menus for one client or one person, and trials that end on time

The super admin can now choose menus for a whole role, for one client, or for one person (a trial, an exception), by dragging them on the Access page; a person's choice beats their client's, which beats their role's. When a menu is taken away, its data is refused within a minute on every screen, API key and the MCP connector, even on a page left open, and the left menu redraws within minutes without a refresh.

### For admins: everything Forsta gives, under Forsta in the menu

Admins have a Forsta section: the team's saved reports, run by Forsta itself, with their Excel, PDF and PowerPoint files; a check of Forsta's own cross-tab against CIP's figures, cell by cell (the 2 November wave: 867 of 867 cells match); the funnel by sample source and device; warnings and launch checks; each survey's files; and when Forsta will delete archived surveys. All read from Forsta without changing anything.

### For admins: the logs in India time

The Logs, Fieldwork and Forsta pages now show every time in Indian Standard Time, so it is easy to see who did what and when. The Logs page also tells the Azure disk's own use apart from CIP's files, and no longer shows an old error in every time range.

### Why respondents dropped out, survey by survey

Fieldwork now opens each survey on its own page: its name and dates, then everyone who opened it and how each of them ended. Qualified people finished and are in the data. Terminated people met a screen-out rule, such as answering too fast. Over-quota people fit the survey but their group was already full; the page names the full cell (for the 2 November wave, 281 were turned away because the women's cell had filled). Dropped-out people left part-way; the page shows where. A chart shows finished interviews hour by hour, next to the quota cells and Forsta's own timeline of the survey. The tables scroll inside their cards, so the page stays short. The super admin can let analysts or clients see Fieldwork from the Access page. (What opened, qualified, terminated and over quota mean: `/app/methodology#fieldwork-terms`)

### The weekly report, in the portal

Every weekly tracker wave since July 2025 now has its US Consumer Survey Insights report under Weekly report in the wave's menu, in the order of the PDF: three data points to watch, net better for personal finances and the economy with the news events marked and split by income, the 13-week tables of retailers, categories and activities with their one-week and three-month changes (coloured only when significant), each with a year's chart of its biggest answers, retailers' shopper profiles, the methodology and margins of error. The figures were checked against the 27 October and 3 November reports.

### The report's appendix, and an Export on every table

The appendix gives % worse, % better and net better for 28 weeks, for everyone, each income group or single weeks, with the one-week and four-week changes. Every table on the report, the sector databank and expected vs actual now has the Export menu: CSV, Excel, PowerPoint, or Pin to a board.

### Sector databank

Thirteen retail sectors, from clothing to off-price, as the Databank lays them out: the share who bought in the category, then its retailers, brands and categories, one column per survey back to 2022. The Department stores figures match the Databank page exactly from August 2024 on. (Open the sector databank: `/app/sectors`)

### Expected vs actual for eleven retail events

Valentine's Day to Black Friday: what consumers said before an event they would do, against what they said afterwards, with the difference and whether it is significant. Where the survey asks how much, the median spend and the market size it implies (Halloween 2026: $100, about $14.7 billion, as the seasonal report gives). Below, the holiday spending and finance outlook across every survey that asked it. (Open expected vs actual: `/app/expectations`)

### A new front page, and faster first loads

The public home page now shows only real facts: the latest wave, its size and topics, and a calendar of every week the tracker was fielded since December 2020. Pages load less on the way in: the survey library no longer waits for the charts, and only the latin fonts are downloaded.

## 24 October 2026

### Census-weighted figures, one click away

A Weighted button at the top of every screen switches the survey figures to Census-weighted: each wave is balanced to the US adult population by gender, age and region (US Census Bureau, American Community Survey). Unweighted stays the default, so the numbers still match Forsta and the weekly Excel files. The source line under each chart says which you are looking at. Significance is always tested on the unweighted counts. (How weighting works: `/app/methodology`)

### How much more likely is this audience?

Audiences now show an Index next to each answer: 100 means the same as everyone, 150 means one and a half times as likely, 80 means less likely. Under the table, "What sets this audience apart" lists, across every question in the wave, the answers the audience gives far more or far less often than everyone else, and only where the difference is significant.

### Typed-in answers, charted

Answers people type themselves, such as "Other, please specify", are now grouped into themes and charted like any other question, by gender and generation. Answers two or more people gave become a theme; "n/a" and the like are grouped as Nothing / not sure. Emails and phone numbers are never shown.

### Search in plain English

Ask search a question the way you would ask a colleague, such as "what do people think about tariffs" or "how are shoppers feeling about inflation". It now looks for what the question is about, and a long question finds the closest matches first instead of hundreds of loose ones. (Try search: `/app/search`)

### Use the portal from Claude and your own tools

The portal's data can now be read by a program with a personal API key, and by Claude (or any AI assistant that supports MCP connectors) through the portal's connector: search questions, read a wave's results, a trend or a cross-tab, with the same access you have in the portal. Ask the CIP team for a key.

## 23 October 2026

### Looks and reads like coresight.com

The portal now has the same header, footer and fonts as coresight.com. The header carries the Coresight logo, links to Research & Data, Events, Services and About, and the portal's own search, theme button and Sign out. The footer has the company's links, the Methodology page and a link back to coresight.com. Headings, menus and buttons use Montserrat and the text and figures use Roboto, as on the main site.

### A fresh look, in light and dark

Every screen was redrawn to read faster: calmer cards on the Overview, clearer charts, and colours that meet the accessibility contrast standard in both themes. Switch themes with the moon or sun button at the top right; charts change colour in place without reloading. (Open the survey library: `/app/`)

### One answer to "did this really change?"

Every screen now uses the same rule to call a change significant: a 95 % test against the previous wave or last year, corrected for testing many answers at once, with at least 30 people on each side. The Overview headline, What changed, the question charts and the takeaways can no longer disagree. Real moves that an over-strict count used to hide now show in What changed.

### Cross-tabs that are easier to read

The cross-tab uses six clear shades of blue with a legend, a fine grid, and readable numbers in every cell in both themes. Letters still mark a column that is significantly higher than another in the same cut.

### Each question's tools in one row

On a question, Chart, Cross-tab, Trends and Compare waves now sit in one strip under the question, with Export, Pin and a ⋯ menu (sort, copy link, alert me) on one row. The question itself is the page title.

### Trends you can read at a glance

Over six months or more, Trends shows the 4-week average as the line with each week as a dot, the margin of error as a band, and at most four coloured lines at a time. A bad link no longer breaks the page.

### Every chart says who was asked

The source line under each chart, image and export now comes from the survey itself: who was surveyed, when, how many people and that figures are unweighted. Annual and ad hoc studies say "previous wave" instead of "last week", and a study still collecting answers is marked In field. (Read the methodology: `/app/methodology`)

### A new Methodology page

How the surveys are run and read, in one place: who answers, how a wave is checked, why figures are unweighted, when a group is too small to show and when a change counts as significant. Every chart's source line links to it.

### Faster everywhere

Pages paint in about half the time on a slow connection. Boards, saved views and alerts load at once instead of in a queue, a board opens three times faster, and the Overview fetches its dashboards at the same time as the survey.

### Better on phones, keyboards and touch

On a phone the question list opens as a Question ▾ sheet so the chart is on the first screen, and every button is big enough to tap. Explanations of significance and small groups now open on tap or with the keyboard, not only on mouse hover.

### Safer team spaces

Deleting a board, view, audience or alert can be undone for a few seconds, and deleting a board asks first. Comments and pins carry the name you signed in with.

### Ready for client sign-in

The portal is ready for company sign-in (single sign-on), packages for different clients, and a record of who exported or asked what. The demo works exactly as before: open the link and you are in.

### Corrected figures in two older surveys

Two older surveys had their answer labels shifted when they were imported: in the April 2023 survey, the 818 people who use Facebook were shown as LinkedIn users, and YouTube showed 0 % instead of 47 %. The August 2022 tracker's grocery retailers were shifted the same way. Both now show what respondents actually chose; a check of every older survey found no others.

### A more reliable weekly load

A long decimal answer no longer stops a wave from loading, one hiccup no longer ends the Monday watch for the new wave, and annual and ad hoc studies now wait until fieldwork closes before they appear. The team gets an email for each new wave and if a load fails.

## 22 October 2026

### Boards: pin any table as it is today

Press Board next to the CSV, Excel and PowerPoint buttons on any table. The numbers are kept exactly as they were, with the data version, so a board reads the same next month. Open live shows today's numbers beside them. (Open Boards: `/app/boards`)

### Comments on every pinned table

The team can discuss each table where it sits. Only the person who wrote a comment, pinned a table or made a board can remove it.

### Download a whole board as one branded deck

Download deck (top right of any board) turns the board into a PowerPoint: a Coresight cover, then one slide per table with an editable chart, the question, the wave, the bases and when it was pinned.

### Search shows every match, page by page

Search now says how many questions match in all and pages through them 50 at a time, best match first. The page is in the address, so a results page can be shared. (Try it: `/app/search?q=holiday`)

### More figures shown: only groups under 5 people are hidden

Every figure with 5 or more respondents is now shown; under 50 it is flagged as a small base. A difference is only called significant when both sides have 30 or more people, because smaller groups are too few to test.

### Alerts reach you, not just the channel

An alert you set on an answer now emails you as well as posting to the team's Teams channel when that answer moves significantly.

### The weekly load tells the team when it stops

If the Monday load fails, crashes, is stopped, or simply goes quiet, the team gets a Teams message within the hour. A planned tracker week that is still missing four days later is flagged too.

### Faster weekly load

Building a wave's tables now takes about 43 seconds instead of 61, with identical numbers: fewer database round trips and better-tuned database sessions.
