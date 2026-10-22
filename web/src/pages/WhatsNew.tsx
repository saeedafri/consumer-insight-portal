// What's new in CIP: each release in plain words, newest first, with a screenshot of the screen it changed.
// Screenshots live in web/public/whats-new/ (taken from the real portal, WebP).
import { Link } from "react-router";

type Entry = { title: string; body: string; shot?: string; alt?: string; link?: [string, string] };
const RELEASES: { date: string; entries: Entry[] }[] = [{
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
