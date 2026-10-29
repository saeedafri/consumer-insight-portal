import { Breadcrumbs, Faq } from "../seo";

export const metadata = {
  title: "Methodology",
  description: "How the Consumer Insight Portal's figures are made: panel, qualification, fielding, weighting, data quality and significance testing.",
  alternates: { canonical: "/methodology/" },
};

const SECTIONS: [string, string][] = [
  ["Panel", "Respondents come from an online opt-in research panel. Each survey's quotas are set before it fields and tracked cell by cell while it runs."],
  ["Who counts", "Only qualified completes count. A respondent who screens out, abandons the survey or fails its quality checks is not in any base. Every wave's qualified count is reconciled with the survey platform before it is published."],
  ["Fielding", "Weekly tracker waves launch on Monday and usually field for two to three days; the wave date is the launch Monday. A wave still collecting answers is marked as in field."],
  ["Weighting", "Figures are unweighted by default: each percentage is the share of qualified respondents who gave that answer. A Weighted view rakes each wave to US adult shares by gender, age and Census region (American Community Survey), with weights trimmed to between 0.2 and 5 times the average. Significance is always tested on unweighted counts."],
  ["Data quality", "Each loaded wave is checked against the survey platform for qualified completes, respondents and answers before it is marked verified. A question whose wording changed is treated as a new version: trends and comparisons never join two versions."],
  ["Small bases", "Every figure is shown, however few people answered. Groups under 50 are marked as a small base: read them with caution."],
  ["Significance", "A change is called significant when a two-sided two-proportion z-test against the previous wave, or the same week last year, gives p < 0.05 after a Benjamini-Hochberg false-discovery correction across the wave, with at least 30 people on each side and an unchanged question base."],
];

const METHOD_FAQ: [string, string][] = [
  ["Is the survey data weighted?", "Figures are unweighted by default. A Census-weighting option rakes each wave to US adult shares by gender, age and region; significance is always tested on the unweighted counts."],
  ["How is a change tested for significance?", "A two-sided two-proportion z-test against the previous wave or the same week last year, with a Benjamini-Hochberg false-discovery correction, p < 0.05, at least 30 respondents on each side and an unchanged question base."],
  ["How are small sample sizes handled?", "Every figure is shown, but a group of fewer than 50 respondents is flagged as a small base and should be read with caution."],
  ["What happens when a question's wording changes?", "A reworded question is treated as a new version. Trends and comparisons never join two versions of a question."],
];

export default function Methodology() {
  return <article className="wrap prose">
    <Breadcrumbs items={[["Home", "/"], ["Methodology", "/methodology/"]]} />
    <p className="eyebrow">Methodology</p>
    <h1>How the numbers are made</h1>
    <p>Coresight&apos;s weekly US Consumer Survey asks about 400 US adults aged 18 and over each week. Annual and ad hoc studies sit alongside it.</p>
    {SECTIONS.map(([h, t]) => <div key={h}><h2>{h}</h2><p>{t}</p></div>)}
    <Faq items={METHOD_FAQ} />
  </article>;
}
