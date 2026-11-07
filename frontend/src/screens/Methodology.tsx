// How the figures are made and tested: the API's methodology text (api /methodology) when it is served, else the
// rules this portal applies (stats.ts, moves.ts), so every source line's "Methodology" link always lands somewhere true.
import { useEffect } from "react";
import { useLocation } from "react-router";
import { useMethodology } from "../api";
import type { Methodology as Text } from "../api";
import { Card, Loading } from "../components/bits";
import { SMALL_BASE, TEST_BASE } from "../stats";

const BUILT_IN: Text = { sections: [
  { title: "Who is surveyed", body: [
    "The weekly Coresight Research US Consumer Survey asks about 400 qualified US adults aged 18+ each week, with quotas on the sample. Annual, ad hoc and client studies each state their own population on every chart; a study that does not name one is shown as \"Survey respondents\".",
    "Each source line names the fieldwork platform and, where the platform records it, the fielding window in US Eastern time. A wave still in field is marked \"In field — partial\": its figures can change." ] },
  { title: "What a percentage is", body: [
    "Every figure is the unweighted share of the qualified respondents who were asked the question (its base). Routing means some questions are asked of only part of the sample; the base shown is the people asked.",
    `Every figure is shown, however few people answered. Under ${SMALL_BASE} people a figure is flagged as a small base and drawn faded: read it with caution.`,
    "The margin of error shown is the 95 % interval of a simple random sample of that base. Quota samples are not random samples, so treat it as a guide to noise, not a guarantee." ] },
  { title: "When a change is called significant", body: [
    "Changes against the previous wave and against last year are tested with a two-proportion z-test. Because every answer of every question is tested at once, a change is called significant only if it survives the Benjamini–Hochberg correction at a 5 % false-discovery rate across all the answers of the wave that could be tested.",
    `Answers are not tested when either side has fewer than ${TEST_BASE} people, or when the question was asked of a different group or in different words than before. Questions that describe the respondents (age, gender, region…) are tested but kept out of the headlines: they shift with each week's sample.`,
    "The Overview headline, What changed, the change chips and the significance in hover cards all use this one rule. Rings on Trends, arrows on Compare waves, letters and arrows on the cross-tab and audience differences are single 95 % comparisons, not corrected for the many cells compared, and are labelled so." ] },
  { title: "Comparisons", body: [
    "A weekly tracker wave is compared with the week before (only when it is within 14 days) and with the matching wave a year earlier. Other studies are compared with their previous wave. A question code reused for a different question is never joined into a trend or comparison.",
    "Cross-tab letters compare groups of the same cut only (men with women, one generation with another); a group is compared with everyone else, never with the Total that contains it." ] },
] };

/** What the fieldwork and launch numbers mean (Fieldwork, a survey's fieldwork page, the Launch schedule): the same on
 *  every screen, so they live here rather than in the API's text. Linked from the Fieldwork page (#fieldwork-terms). */
const TERMS: [string, string][] = [
  ["Planned", "A week in the data team's launch plan with no survey set up in Forsta yet (Launch schedule)."],
  ["New (set up in Forsta)", "The survey exists in Forsta in its testing state: being programmed and checked, no real respondents yet."],
  ["Launched (in field)", "The survey went live in Forsta and is collecting respondents. The launch time is Forsta's own record."],
  ["Closed", "Fieldwork is over: Forsta stopped taking respondents, because every quota filled or the team closed it. CIP then loads it (\"In the portal\")."],
  ["Opened", "Everyone who opened the first page of the survey (Forsta calls it click-through). Each of them ends in exactly one of the four outcomes below, so Opened = Qualified + Terminated + Over quota + Dropped out."],
  ["Qualified", "Finished the whole interview and fit the sample. These are the only answers in every chart and table of the portal, and what the Launch schedule counts against its quota of 400."],
  ["Terminated", "Screened out by a rule in the questionnaire (a \"term\"), for example finishing faster than 25 seconds or 2 minutes (a speeder). The survey's page lists the rule that removed each group."],
  ["Over quota", "Fit the survey, but the quota for their group (a gender, a region, an income band) was already full, so Forsta ended the interview. The survey's page shows which cell was full."],
  ["Dropped out", "Opened the survey and left before the end (Forsta calls it partial). The survey's page shows the page each of them left on."],
  ["Incidence", "Qualified ÷ Opened: the share of people who opened the survey and ended up in the data."],
  ["Reached (page by page)", "How many people got to a page. It falls page by page as people drop out, are terminated or go over quota, so a page's count is never the survey's Opened total."],
];
const EXAMPLE = "Example, the weekly tracker of 2 November 2026 (Forsta survey 261003): 1,193 opened = 403 qualified + 32 terminated (22 + 10 speeders) + 609 over quota (281 because the women's cell was full, 158 the South, and so on) + 149 dropped out. " +
  "The Launch schedule shows 403 of 400: the qualified people against the quota. The weekly charts use the 403 qualified people. A number such as 1,809 on a page-by-page table is the people who reached that page of one survey " +
  "(the Holiday 2025 survey's TM3: 1,810 reached it, 1,809 went on; that survey had 2,478 opened), never a survey's total.";

/** The API's config/methodology.yml (flat text fields) as titled sections; unknown fields are skipped. */
const FIELDS: [string, string][] = [["panel", "Who is surveyed"], ["qualification", "Who counts"], ["fielding", "Fielding"],
  ["weighting_text", "Weighting"], ["small_cells", "Small groups"], ["significance", "When a change is called significant"], ["data_quality", "Data quality"]];
function fromApi(data: unknown): Text | null {
  if (typeof data === "string") return { sections: [{ title: "Methodology", body: data }] };
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown> & Partial<Text>;
  if (Array.isArray(d.sections) && d.sections.length) return d as Text;
  const sections: Text["sections"] = FIELDS.flatMap(([k, title]): Text["sections"] => typeof d[k] === "string" ? [{ title, body: d[k] as string }]
    : Array.isArray(d[k]) ? [{ title, body: (d[k] as unknown[]).map(String) }] : []);
  const pop = d.population as { default?: string; study_types?: Record<string, string> } | undefined;
  if (pop?.default) sections.unshift({ title: "Population", body: [`Weekly tracker: ${pop.study_types?.tracker ?? "US adults 18+"}. Other studies state their own population on every chart; one that does not name it is shown as “${pop.default}”.`] });
  return sections.length ? { sections } : null;
}

export default function Methodology() {
  const { data, isLoading } = useMethodology();
  const { hash } = useLocation();
  useEffect(() => { if (!isLoading && hash) document.getElementById(hash.slice(1))?.scrollIntoView(); }, [hash, isLoading]);   // a link to one section (#fieldwork-terms)
  if (isLoading) return <Loading what="methodology" />;
  const text = fromApi(data) ?? BUILT_IN;
  return <div className="stack">
    <div className="page-head"><div><h1>{text.title ?? "Methodology"}</h1>
      <p className="lede">How the portal's figures are made, what is hidden and when a change is called significant.{text.updated ? ` Updated ${text.updated}.` : ""}</p></div></div>
    {text.sections.map(s => <Card key={s.title} title={s.title}>
      {(Array.isArray(s.body) ? s.body : s.body.split(/\n{2,}/)).map((p, i) => <p key={i} style={{ margin: "0 0 10px", lineHeight: 1.6, maxWidth: 820 }}>{p}</p>)}
    </Card>)}
    <section className="card" id="fieldwork-terms" aria-labelledby="fieldwork-terms-title">
      <div className="card-head"><div><h2 id="fieldwork-terms-title">Fieldwork and launch terms</h2>
        <p className="sub">What each number on Fieldwork, a survey's fieldwork page and the Launch schedule counts. All come from Forsta, read without changing anything.</p></div></div>
      <dl className="details terms-list">{TERMS.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl>
      <p style={{ margin: "14px 0 0", lineHeight: 1.6, maxWidth: 820 }}>{EXAMPLE}</p>
    </section>
  </div>;
}
