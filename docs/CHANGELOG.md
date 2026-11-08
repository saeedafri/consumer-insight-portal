# What's new in CIP

Every feature, enhancement and update, newest first: the same entries as the portal's What's new page
(`frontend/src/screens/WhatsNew.tsx`). Add each change to both; `tests/test_docs.py` fails if they differ.
The API and the MCP connector are documented in [API.md](API.md).

## 8 November 2026

### A cleaner look in light and dark

The portal has a new look in both themes. The menu on the left is now white in light mode, with the page you are on shown as a red-tinted row, and the page behind the cards is a cool light grey. Dark mode moves from warm brown-black to a cool blue-black. Cards have rounder corners and a softer shadow, the figures at the top of a page carry a small coloured tab (red for the main one), and table headings are a light grey band instead of a dark one. The Coresight logo, fonts, charts' colours, menus and every figure are unchanged.

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
