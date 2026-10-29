// How the figures are made and tested: the API's methodology text (api /methodology) when it is served, else the
// rules this portal applies (stats.ts, moves.ts), so every source line's "Methodology" link always lands somewhere true.
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
  if (isLoading) return <Loading what="methodology" />;
  const text = fromApi(data) ?? BUILT_IN;
  return <div className="stack">
    <div className="page-head"><div><h1>{text.title ?? "Methodology"}</h1>
      <p className="lede">How the portal's figures are made, what is hidden and when a change is called significant.{text.updated ? ` Updated ${text.updated}.` : ""}</p></div></div>
    {text.sections.map(s => <Card key={s.title} title={s.title}>
      {(Array.isArray(s.body) ? s.body : s.body.split(/\n{2,}/)).map((p, i) => <p key={i} style={{ margin: "0 0 10px", lineHeight: 1.6, maxWidth: 820 }}>{p}</p>)}
    </Card>)}
  </div>;
}
