// What's new in CIP: each release in plain words, newest first, with a screenshot of the screen it changed.
// Screenshots live in web/public/whats-new/ (taken from the real portal, WebP).
import { Link } from "react-router";

type Entry = { title: string; body: string; shot?: string; alt?: string; link?: [string, string] };
const RELEASES: { date: string; entries: Entry[] }[] = [{
  date: "10 November 2026",
  entries: [
    { title: "A closed survey loads within 30 minutes, even after a deploy",
      body: "The pipeline now checks Forsta every 30 minutes, every day, as a short run the scheduler starts itself. Until now the 30-minute checks on a launch Monday were one long run inside the server, and a deploy stopped it with the server: on 9 November the wave launched at 7:08 PM IST was not loaded until the next morning. A deploy now delays a closed survey by at most 30 minutes, and annual and ad hoc studies load within 30 minutes of closing instead of the next morning. If no check has run for 2 hours, the pipeline-failure email says so." },
  ],
}, {
  date: "9 November 2026",
  entries: [
    { title: "Sign out now signs you out of Coresight too",
      body: "Signing out of the portal now also ends your Coresight sign-in (stage3's csr-idp), so the next Continue with work account asks for your password again. Until now staging had no Coresight sign-out address set, so sign-out only cleared the portal's own cookie and Coresight let you straight back in. For admins, each step of signing out and back in is written to the API log as [SIGN-TRACE] (Logs page, search SIGN-TRACE): the cookies sent, where sign-out went, and how long the browser spent at Coresight's sign-in." },
  ],
}, {
  date: "8 November 2026",
  entries: [
    { title: "A cleaner look in light and dark",
      body: "The portal has a new look in both themes. The menu on the left is white in light mode with thin outline icons, in four groups that fold (Explore, Research data, Research operations, Administration), with a link to the current weekly tracker; dark mode moves from warm brown-black to a cool blue-black. The header names the page you are on. A wave's screens are now tabs in the wave's own card at the top of the page, under its date switcher, and a wave screen's title has a small red label naming the wave. Buttons and boxes have fine outlines on a soft fill, text is a size smaller and calmer, cards have rounder corners and lift slightly when you point at them, the figures at the top of a page carry a small coloured tab, and tables have a light grey heading inside a rounded box. Charts have slimmer bars with rounded ends. Ask CIP and Boards open on a panel that says what to do next, with example questions and how boards work beside it, and an empty list shows an icon and what to do. The footer follows the theme, and the menu on the left stays in place and scrolls on its own however far down the page you are. Upload survey shows its four stages across the top (Select, Validate, Review, Publish), filling in red as each is done; each file has its own box saying what to choose, and a note says what Check compares before anything is written. Every rise is shown in bold green and every fall in bold red, on every screen: the change chips, What changed, Trends, Compare waves, cross-tab arrows, Audiences and the hover cards; a significant change keeps its tinted chip, now in its own colour. The weekly report's three data points to watch are now three cards, each naming its table, the change in green or red, and what moved; its tables and Expected vs actual colour their significant changes the same way. On a wave's overview, each “at a glance” figure is its own card (the first with a red tab, the rest light blue), under the block's name and dates, with the key takeaways in a card of their own. The Columns chart is gone: it showed the same figures as Bars, and long answers overlapped under it; links and saved views that asked for it open as Bars. The Coresight logo, fonts and every figure are unchanged." },
    { title: "China consumer survey: upload a week from Baidu",
      body: "Admins have a new Upload survey page under Admin in the menu for the China Consumer Survey, which Baidu QSS fields and which has no connection CIP can reach. Choose the week's raw export and Baidu's topline (as downloaded, .csv and .xls, including files saved from SharePoint) and press Check: CIP counts every answer from the raw rows and compares each base and count with Baidu's topline (123 figures a week), translating the Chinese through a reviewed English codebook. Only when every figure matches can the week be published; it then appears as a China wave with its week-on-week changes, cuts by gender, age, income and city tier, trends and search, and the portal's files are rebuilt in the background. Baidu's topline is kept in the database beside CIP's own figures. Uploading the same week again replaces it. The analysts' English converter swapped Optimistic and Pessimistic for the two outlook questions; the codebook keys every answer by its Chinese words so this cannot happen." },
    { title: "Safer logs download, steadier Ask CIP and sign-in errors",
      body: "Ask CIP now gives up on a slow Claude after 25 seconds and answers with the cited figures instead, and an answer that states a percentage none of its sources list is replaced by the cited figures. The Logs page's Excel download no longer lets text sent by a visitor run as a formula, and a failed Teams alert no longer writes its secret link to the log. A sign-in cookie or header with unusual characters now gets a normal refusal instead of an error page. The new-wave email is tried three times before giving up, a missing script file is a \"not found\" instead of a page, the mobile menu respects reduced motion, a weekly report's figures load as soon as its page starts, and downloads of Forsta reports and the Logs workbook no longer fail in Safari and Firefox." },
    { title: "Faster from far away and on slow connections",
      body: "A wave's pages ask for their figures as soon as the page starts loading, and the portal's code downloads in one go instead of in steps. The words and figures show first and the charts follow, so a slow connection no longer waits for the chart library before showing anything. From India a first visit to a wave's overview shows its figures in 1.5 s instead of 2.0 s; on a 200 kbit/s connection in 16 s instead of 28 s, and on 100 kbit/s in 31 s instead of 54 s. A second visit takes about 1 s even at 100 kbit/s, as the portal's files stay in the browser." },
    { title: "Uptime checks see the portal as up",
      body: "Uptime checks that ask the portal whether it is up with a HEAD request (as many monitors do) now get \"up\" instead of \"Page not found\"." },
  ],
}, {
  date: "7 November 2026",
  entries: [
    { title: "Times in your own time zone, and India time on the Logs page",
      body: "Every time in the portal is on a 12-hour clock with AM or PM and the zone's name. Pages show your own time, from your computer's setting (8:26 AM EDT in New York, 5:56 PM IST in India, 1:26 PM CET in Berlin); nothing is looked up or sent to the server. The Logs page always shows India time, now also in the raw log lines and in what Show opens (the log files keep the servers' UTC). The Logs page's first visit after a deploy no longer waits about 5 seconds, and each refresh reads each log once instead of eight times." },
    { title: "For admins: the Logs page for any dates, every visitor, and one download",
      body: "The Logs page now shows any time range: the last hour or day minute by minute, and 7 days, 30 days, 17 weeks, a year or any two dates hour by hour (hours are kept from 7 November 2026 on). Choose a visitor to see each request they made, where they came from, and whether they are a person, a bot or Azure's own health check. Show on a problem opens the lines around it in its log, such as an error's full traceback. Download everything saves the range as one Excel file: requests, server time, errors, CPU, memory, bandwidth with their charts, response times, how requests were answered, caches, storage, busiest pages, every visitor, sign-ins, problems, restarts and the requests themselves. Every time in the portal is on a 12-hour clock in India time (8:20 PM IST), the admin-token box appears only when the server asks for it, and the page refreshes once a minute, only while it is open on screen." },
    { title: "Audiences, stacked charts and older wordings",
      body: "Changing an audience (adding or removing an answer, opening a saved one) now clears the last figures until you show them again, instead of leaving the previous audience's numbers on screen. A stacked chart with many answers keeps its legend on one scrolling line instead of writing over the bar. Older wordings no longer show HTML codes such as &#39; or &amp;. A wave built since the last publish is listed at once instead of \"No such wave\"." },
    { title: "The wave switcher works again",
      body: "Previous wave, Next wave, the wave list and the [ and ] keys on a wave's screens now open the chosen wave on the same screen; since 29 October they opened a \"Page not found\". Copying a new API key also says when the browser blocks it." },
    { title: "Question codes in any case",
      body: "The API and the Claude connector now find a question whatever the case of its code (q1 or Q1, XM3 or xm3): cross-tabs answer as results already did, instead of saying the question is not in the wave." },
    { title: "Company sign-in only, wherever it is set up",
      body: "Where Coresight's company sign-in is set up, the portal no longer offers the demo sign-in (any email, no password), whatever its settings say: everyone signs in with their own company account. API keys and the MCP connector keep working as before." },
    { title: "Your own API keys, and Claude through the portal",
      body: "Anyone signed in can now make their own API keys on the Account page and use the portal from their own programs, or from Claude and other AI assistants through the portal's MCP connector: search questions, read a wave's results, a trend or a cross-tab. A key acts as you and reads only what your menus show; if a menu is taken away, your keys lose it at the same moment. A key is shown once, and you can revoke it at any time. The new API guide lists every address, the connector's tools and the rules a key follows.",
      link: ["/api-guide", "Read the API guide"] },
    { title: "Menus for one client or one person, and trials that end on time",
      body: "The super admin can now choose menus for a whole role, for one client, or for one person (a trial, an exception), by dragging them on the Access page; a person's choice beats their client's, which beats their role's. When a menu is taken away, its data is refused within a minute on every screen, API key and the MCP connector, even on a page left open, and the left menu redraws within minutes without a refresh." },
    { title: "For admins: everything Forsta gives, under Forsta in the menu",
      body: "Admins have a Forsta section: the team's saved reports, run by Forsta itself, with their Excel, PDF and PowerPoint files; a check of Forsta's own cross-tab against CIP's figures, cell by cell (the 2 November wave: 867 of 867 cells match); the funnel by sample source and device; warnings and launch checks; each survey's files; and when Forsta will delete archived surveys. All read from Forsta without changing anything." },
    { title: "For admins: the logs in India time",
      body: "The Logs, Fieldwork and Forsta pages now show every time in Indian Standard Time, so it is easy to see who did what and when. The Logs page also tells the Azure disk's own use apart from CIP's files, and no longer shows an old error in every time range." },
    { title: "Why respondents dropped out, survey by survey",
      body: "Fieldwork now opens each survey on its own page: its name and dates, then everyone who opened it and how each of them ended. Qualified people finished and are in the data. Terminated people met a screen-out rule, such as answering too fast. Over-quota people fit the survey but their group was already full; the page names the full cell (for the 2 November wave, 281 were turned away because the women's cell had filled). Dropped-out people left part-way; the page shows where. A chart shows finished interviews hour by hour, next to the quota cells and Forsta's own timeline of the survey. The tables scroll inside their cards, so the page stays short. The super admin can let analysts or clients see Fieldwork from the Access page.",
      link: ["/methodology#fieldwork-terms", "What opened, qualified, terminated and over quota mean"] },
    { title: "The weekly report, in the portal",
      body: "Every weekly tracker wave since July 2025 now has its US Consumer Survey Insights report under Weekly report in the wave's menu, in the order of the PDF: three data points to watch, net better for personal finances and the economy with the news events marked and split by income, the 13-week tables of retailers, categories and activities with their one-week and three-month changes (coloured only when significant), each with a year's chart of its biggest answers, retailers' shopper profiles, the methodology and margins of error. The figures were checked against the 27 October and 3 November reports.",
      shot: "report-1107.webp", alt: "The food retailers chart with retail events marked, above its 13-week table" },
    { title: "The report's appendix, and an Export on every table",
      body: "The appendix gives % worse, % better and net better for 28 weeks, for everyone, each income group or single weeks, with the one-week and four-week changes. Every table on the report, the sector databank and expected vs actual now has the Export menu: CSV, Excel, PowerPoint, or Pin to a board.",
      shot: "appendix-1107.webp", alt: "The appendix tables for personal finances and the economy with Export and Pin buttons" },
    { title: "Sector databank",
      body: "Thirteen retail sectors, from clothing to off-price, as the Databank lays them out: the share who bought in the category, then its retailers, brands and categories, one column per survey back to 2022. The Department stores figures match the Databank page exactly from August 2024 on.",
      shot: "sectors-1107.webp", alt: "The Clothing sector table with its purchase rate and retailers by survey", link: ["/sectors", "Open the sector databank"] },
    { title: "Expected vs actual for eleven retail events",
      body: "Valentine's Day to Black Friday: what consumers said before an event they would do, against what they said afterwards, with the difference and whether it is significant. Where the survey asks how much, the median spend and the market size it implies (Halloween 2026: $100, about $14.7 billion, as the seasonal report gives). Below, the holiday spending and finance outlook across every survey that asked it.",
      shot: "expectations-1107.webp", alt: "Halloween expected spend against last year's actual, with median spend and market size", link: ["/expectations", "Open expected vs actual"] },
    { title: "A new front page, and faster first loads",
      body: "The public home page now shows only real facts: the latest wave, its size and topics, and a calendar of every week the tracker was fielded since December 2020. Pages load less on the way in: the survey library no longer waits for the charts, and only the latin fonts are downloaded.",
      shot: "home-1107.webp", alt: "The public home page with the latest wave and the calendar of weeks fielded" },
  ],
}, {
  date: "24 October 2026",
  entries: [
    { title: "Census-weighted figures, one click away",
      body: "A Weighted button at the top of every screen switches the survey figures to Census-weighted: each wave is balanced to the US adult population by gender, age and region (US Census Bureau, American Community Survey). Unweighted stays the default, so the numbers still match Forsta and the weekly Excel files. The source line under each chart says which you are looking at. Significance is always tested on the unweighted counts.",
      link: ["/methodology", "How weighting works"] },
    { title: "How much more likely is this audience?",
      body: "Audiences now show an Index next to each answer: 100 means the same as everyone, 150 means one and a half times as likely, 80 means less likely. Under the table, \"What sets this audience apart\" lists, across every question in the wave, the answers the audience gives far more or far less often than everyone else, and only where the difference is significant." },
    { title: "Typed-in answers, charted",
      body: "Answers people type themselves, such as \"Other, please specify\", are now grouped into themes and charted like any other question, by gender and generation. Answers two or more people gave become a theme; \"n/a\" and the like are grouped as Nothing / not sure. Emails and phone numbers are never shown." },
    { title: "Search in plain English",
      body: "Ask search a question the way you would ask a colleague, such as \"what do people think about tariffs\" or \"how are shoppers feeling about inflation\". It now looks for what the question is about, and a long question finds the closest matches first instead of hundreds of loose ones.",
      link: ["/search", "Try search"] },
    { title: "Use the portal from Claude and your own tools",
      body: "The portal's data can now be read by a program with a personal API key, and by Claude (or any AI assistant that supports MCP connectors) through the portal's connector: search questions, read a wave's results, a trend or a cross-tab, with the same access you have in the portal. Ask the CIP team for a key." },
  ],
}, {
  date: "23 October 2026",
  entries: [
    { title: "Looks and reads like coresight.com",
      body: "The portal now has the same header, footer and fonts as coresight.com. The header carries the Coresight logo, links to Research & Data, Events, Services and About, and the portal's own search, theme button and Sign out. The footer has the company's links, the Methodology page and a link back to coresight.com. Headings, menus and buttons use Montserrat and the text and figures use Roboto, as on the main site." },
    { title: "A fresh look, in light and dark",
      body: "Every screen was redrawn to read faster: calmer cards on the Overview, clearer charts, and colours that meet the accessibility contrast standard in both themes. Switch themes with the moon or sun button at the top right; charts change colour in place without reloading.",
      shot: "overview-1023.webp", alt: "The redesigned Overview in the light theme", link: ["/", "Open the survey library"] },
    { title: "One answer to \"did this really change?\"",
      body: "Every screen now uses the same rule to call a change significant: a 95 % test against the previous wave or last year, corrected for testing many answers at once, with at least 30 people on each side. The Overview headline, What changed, the question charts and the takeaways can no longer disagree. Real moves that an over-strict count used to hide now show in What changed." },
    { title: "Cross-tabs that are easier to read",
      body: "The cross-tab uses six clear shades of blue with a legend, a fine grid, and readable numbers in every cell in both themes. Letters still mark a column that is significantly higher than another in the same cut.",
      shot: "crosstab-dark-1023.webp", alt: "The redesigned cross-tab in the dark theme" },
    { title: "Each question's tools in one row",
      body: "On a question, Chart, Cross-tab, Trends and Compare waves now sit in one strip under the question, with Export, Pin and a ⋯ menu (sort, copy link, alert me) on one row. The question itself is the page title.",
      shot: "questions-1023.webp", alt: "A question with its one-row toolbar and view tabs" },
    { title: "Trends you can read at a glance",
      body: "Over six months or more, Trends shows the 4-week average as the line with each week as a dot, the margin of error as a band, and at most four coloured lines at a time. A bad link no longer breaks the page.",
      shot: "trends-1023.webp", alt: "A trend with its 4-week average, weekly dots and margin of error" },
    { title: "Every chart says who was asked",
      body: "The source line under each chart, image and export now comes from the survey itself: who was surveyed, when, how many people and that figures are unweighted. Annual and ad hoc studies say \"previous wave\" instead of \"last week\", and a study still collecting answers is marked In field.",
      link: ["/methodology", "Read the methodology"] },
    { title: "A new Methodology page",
      body: "How the surveys are run and read, in one place: who answers, how a wave is checked, why figures are unweighted, when a group is too small to show and when a change counts as significant. Every chart's source line links to it." },
    { title: "Faster everywhere",
      body: "Pages paint in about half the time on a slow connection. Boards, saved views and alerts load at once instead of in a queue, a board opens three times faster, and the Overview fetches its dashboards at the same time as the survey." },
    { title: "Better on phones, keyboards and touch",
      body: "On a phone the question list opens as a Question ▾ sheet so the chart is on the first screen, and every button is big enough to tap. Explanations of significance and small groups now open on tap or with the keyboard, not only on mouse hover." },
    { title: "Safer team spaces",
      body: "Deleting a board, view, audience or alert can be undone for a few seconds, and deleting a board asks first. Comments and pins carry the name you signed in with." },
    { title: "Ready for client sign-in",
      body: "The portal is ready for company sign-in (single sign-on), packages for different clients, and a record of who exported or asked what. The demo works exactly as before: open the link and you are in." },
    { title: "Corrected figures in two older surveys",
      body: "Two older surveys had their answer labels shifted when they were imported: in the April 2023 survey, the 818 people who use Facebook were shown as LinkedIn users, and YouTube showed 0 % instead of 47 %. The August 2022 tracker's grocery retailers were shifted the same way. Both now show what respondents actually chose; a check of every older survey found no others." },
    { title: "A more reliable weekly load",
      body: "A long decimal answer no longer stops a wave from loading, one hiccup no longer ends the Monday watch for the new wave, and annual and ad hoc studies now wait until fieldwork closes before they appear. The team gets an email for each new wave and if a load fails." },
  ],
}, {
  date: "22 October 2026",
  entries: [
    { title: "Boards: pin any table as it is today",
      body: "Press Board next to the CSV, Excel and PowerPoint buttons on any table. The numbers are kept exactly as they were, with the data version, so a board reads the same next month. Open live shows today's numbers beside them.",
      shot: "pin.webp", alt: "The Pin to a board dialog over a cross-tab", link: ["/boards", "Open Boards"] },
    { title: "Comments on every pinned table",
      body: "The team can discuss each table where it sits. Only the person who wrote a comment, pinned a table or made a board can remove it.",
      shot: "board.webp", alt: "A board with a comment under a pinned cross-tab and a second pinned table" },
    { title: "Download a whole board as one branded deck",
      body: "Download deck (top right of any board) turns the board into a PowerPoint: a Coresight cover, then one slide per table with an editable chart, the question, the wave, the bases and when it was pinned." },
    { title: "Search shows every match, page by page",
      body: "Search now says how many questions match in all and pages through them 50 at a time, best match first. The page is in the address, so a results page can be shared.",
      shot: "search.webp", alt: "Search results with the match count and page buttons", link: ["/search?q=holiday", "Try it"] },
    { title: "More figures shown: only groups under 5 people are hidden",
      body: "Every figure with 5 or more respondents is now shown; under 50 it is flagged as a small base. A difference is only called significant when both sides have 30 or more people, because smaller groups are too few to test.",
      shot: "smallbase.webp", alt: "A cross-tab showing small groups with their figures" },
    { title: "Alerts reach you, not just the channel",
      body: "An alert you set on an answer now emails you as well as posting to the team's Teams channel when that answer moves significantly." },
    { title: "The weekly load tells the team when it stops",
      body: "If the Monday load fails, crashes, is stopped, or simply goes quiet, the team gets a Teams message within the hour. A planned tracker week that is still missing four days later is flagged too." },
    { title: "Faster weekly load",
      body: "Building a wave's tables now takes about 43 seconds instead of 61, with identical numbers: fewer database round trips and better-tuned database sessions." },
  ],
}];

export default function WhatsNew() {
  return <div className="stack whats-new">
    <div className="page-head"><div><h1>What's new in CIP</h1>
      <p className="lede">Changes to the portal, newest first.</p></div></div>
    {RELEASES.map(r => <section key={r.date} className="stack" aria-labelledby={`r-${r.date}`}>
      <h2 id={`r-${r.date}`} className="release-date">{r.date}</h2>
      {r.entries.map(e => <article key={e.title} className="card new-entry">
        <div className="new-text">
          <h3>{e.title}</h3>
          <p>{e.body}</p>
          {e.link && <Link className="btn" to={e.link[0]}>{e.link[1]}</Link>}
        </div>
        {e.shot && <img src={`/whats-new/${e.shot}`} alt={e.alt} loading="lazy" width={1200} height={750} />}
      </article>)}
    </section>)}
  </div>;
}
