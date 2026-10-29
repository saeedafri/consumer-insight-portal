export const metadata = {
  title: "Methodology",
  description: "How the Consumer Insight Portal's figures are made: panel, qualification, fielding, weighting, data quality and significance testing.",
  alternates: { canonical: "/methodology/" },
};

export default function Methodology() {
  return <article className="prose">
    <section className="hero">
      <p className="eyebrow">Methodology</p>
      <h1>How the numbers are made</h1>
      <p>Coresight&apos;s weekly US Consumer Survey asks about 400 US adults aged 18 and over each week. Annual and ad hoc studies sit alongside it.</p>
    </section>
    <h2>Panel</h2>
    <p>Respondents come from an online opt-in research panel. Each survey&apos;s quotas are set before it fields and tracked cell by cell while it runs.</p>
    <h2>Who counts</h2>
    <p>Only qualified completes count. A respondent who screens out, abandons the survey or fails its quality checks is not in any base. Every wave&apos;s qualified count is reconciled with the survey platform before it is published.</p>
    <h2>Fielding</h2>
    <p>Weekly tracker waves launch on Monday and usually field for two to three days; the wave date is the launch Monday. A wave still collecting answers is marked as in field.</p>
    <h2>Weighting</h2>
    <p>Figures are unweighted by default: each percentage is the share of qualified respondents who gave that answer. A Weighted view rakes each wave to US adult shares by gender, age and Census region (American Community Survey), with weights trimmed to between 0.2 and 5 times the average. Significance is always tested on unweighted counts.</p>
    <h2>Data quality</h2>
    <p>Each loaded wave is checked against the survey platform for qualified completes, respondents and answers before it is marked verified. A question whose wording changed is treated as a new version: trends and comparisons never join two versions.</p>
    <h2>Small bases</h2>
    <p>Every figure is shown, however few people answered. Groups under 50 are marked as a small base: read them with caution.</p>
    <h2>Significance</h2>
    <p>A change is called significant when a two-sided two-proportion z-test against the previous wave, or the same week last year, gives p &lt; 0.05 after a Benjamini-Hochberg false-discovery correction across the wave, with at least 30 people on each side and an unchanged question base.</p>
  </article>;
}
