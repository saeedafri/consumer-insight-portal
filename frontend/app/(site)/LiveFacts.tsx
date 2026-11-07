// The home page's figures (app/(site)/page.tsx): the latest wave beside the hero, and the catalogue's counts below it.
// The site is built without the survey data (deploy/Dockerfile), so the build's figures (pipeline.ts) are only a
// starting point: once the page loads it asks for the published ones (GET /api/v1/public/facts, etl/publish.py
// site_facts: counts and dates, no survey answer, no sign-in) and shows those. One request of about 3 KB.
"use client";
import { useEffect, useState } from "react";
import type { Facts } from "./pipeline";

const DAY = 86_400_000;
const longDate = (iso: string) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });

/** Every week from the tracker's first wave to its latest, one row per year, each week marked when a tracker wave was
 *  fielded within it (a wave fielded off its Monday still counts for that week). */
function fieldedYears(dates: string[], first: string, latest: string) {
  const asked = dates.map((d) => Date.parse(d + "T00:00:00Z"));
  const years: { year: string; weeks: { day: string; fielded: boolean }[] }[] = [];
  for (let monday = Date.parse(first + "T00:00:00Z"); monday <= Date.parse(latest + "T00:00:00Z"); monday += 7 * DAY) {
    const day = new Date(monday).toISOString().slice(0, 10);
    const week = { day, fielded: asked.some((t) => t >= monday - 3 * DAY && t < monday + 4 * DAY) };
    const year = day.slice(0, 4);
    if (years.at(-1)?.year === year) years.at(-1)!.weeks.push(week); else years.push({ year, weeks: [week] });
  }
  return years;
}

/** The published figures when they arrive, the build's until then. */
function useFacts(built: Facts): Facts {
  const [facts, setFacts] = useState(built);
  useEffect(() => {
    const ask = new AbortController();
    fetch("/api/v1/public/facts", { signal: ask.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((live) => { if (live?.latestDate) setFacts({ ...built, ...live }); })
      .catch(() => { /* offline or not published yet: the build's figures stay */ });
    return () => ask.abort();
  }, [built]);
  return facts;
}

/** The latest wave: its week, size, questions, topics, and the calendar of every week the tracker was fielded. */
export function Ledger({ built }: { built: Facts }) {
  const f = useFacts(built);
  const years = f.trackerDates.length ? fieldedYears(f.trackerDates, f.firstTracker, f.latestDate) : [];
  const all = years.flatMap((y) => y.weeks);
  const fielded = all.filter((w) => w.fielded).length;
  return <aside className="ledger" aria-labelledby="latest">
    <h2 id="latest">{f.latestLabel}</h2>
    <dl className="ledger-facts">
      <div><dt>Respondents</dt><dd>{f.latestN.toLocaleString("en-US")} US adults 18+</dd></div>
      <div><dt>Questions</dt><dd>{f.questions}</dd></div>
    </dl>
    {f.latestTopics.length > 0 && <ul className="topics" aria-label="Topics this week">
      {f.latestTopics.map((t) => <li key={t}>{t}</li>)}
    </ul>}
    {years.length > 0 && <figure className="calendar">
      <div className="years" role="img" aria-label={`A survey wave in ${fielded} of the ${all.length} weeks since ${longDate(f.firstTracker)}`}>
        {years.map((y) => <div className="year" key={y.year}><span className="year-label">{y.year}</span><div className="weeks">
          {y.weeks.map((w) => <i key={w.day} className={w.fielded ? "on" : undefined} title={`Week of ${longDate(w.day)}${w.fielded ? "" : ": no wave"}`} />)}
        </div></div>)}
      </div>
      <figcaption>A wave in {fielded} of the {all.length} weeks since {longDate(f.firstTracker)}: one row a year, one square a week, this week in red.</figcaption>
    </figure>}
  </aside>;
}

/** The catalogue in one ruled row. */
export function Counts({ built }: { built: Facts }) {
  const f = useFacts(built);
  return <dl className="facts">
    <div><dt>Survey waves</dt><dd>{f.waves.toLocaleString("en-US")}</dd></div>
    <div><dt>Qualified responses</dt><dd>{Math.floor(f.responses / 1000).toLocaleString("en-US")},000+</dd></div>
    <div><dt>Weekly tracker waves</dt><dd>{f.trackers.toLocaleString("en-US")}</dd></div>
    <div><dt>Annual and ad hoc studies</dt><dd>{f.annual + f.adhoc}</dd></div>
  </dl>;
}
