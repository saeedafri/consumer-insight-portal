import Link from "next/link";
import { SITE } from "../../site";
import { Jsonld, Breadcrumbs, Faq } from "../seo";
import { siteFacts } from "../pipeline";

export const metadata = {
  title: { absolute: "US Weekly Consumer Survey Data — 370+ Waves Since 2020 | Coresight Consumer Insight Portal" },
  description: "Coresight's weekly US consumer survey data: 370+ waves and 190,000+ responses since December 2020, tracking spending, shopping behavior and sentiment across retail categories. Explore trends by generation, income and region.",
  alternates: { canonical: "/data/" },
};

const FAQ: [string, string][] = [
  ["How often is the consumer data updated?", "A new weekly US consumer tracker wave is fielded every week and launched on a Monday. Annual and ad hoc studies run alongside the weekly tracker, so the dataset grows continuously."],
  ["How large is the sample?", "About 400 qualified US adults aged 18 and over answer each weekly wave. Across 370+ waves since December 2020 that is more than 190,000 qualified responses."],
  ["Is the survey data weighted?", "Figures are unweighted by default — each percentage is the share of qualified respondents who gave that answer. A Census-weighting option rakes each wave to US adult shares by gender, age and region. Significance is always tested on unweighted counts."],
  ["What does the consumer tracker cover?", "Consumer spending intentions, category spend, shopping channels, brand consideration and sentiment across US retail and consumer categories, cut by generation, gender, income and Census region."],
  ["How is a change tested for significance?", "A two-sided two-proportion z-test against the previous wave, or the same week last year, with a Benjamini-Hochberg false-discovery correction and p < 0.05, requiring at least 30 respondents on each side and an unchanged question base."],
  ["How do I access the full dataset?", "The full Consumer Insight Portal is available to subscribers. Sign in with a work account, or request access, to explore every question, cross-tab, trend and audience."],
];

export default function DataPage() {
  const f = siteFacts();
  const dataset = {
    "@context": "https://schema.org", "@type": "Dataset",
    name: "Coresight Weekly US Consumer Survey Tracker",
    description: `Weekly survey of US adults aged 18+ tracking consumer spending intentions, shopping behavior, category spend and sentiment across retail categories. ${f.waves} waves and ${f.responses.toLocaleString()} qualified responses since December 2020, with roughly 400 qualified respondents per weekly wave.`,
    url: SITE + "/data/",
    keywords: ["US consumer survey data", "weekly consumer tracker", "retail consumer trends", "consumer sentiment", "shopper behavior", "consumer spending"],
    creator: { "@id": SITE + "/#org" },
    publisher: { "@id": SITE + "/#org" },
    temporalCoverage: "2020-12-28/" + f.latestDate,
    dateModified: f.latestDate,
    spatialCoverage: { "@type": "Place", name: "United States" },
    measurementTechnique: "Online opt-in research panel survey",
    variableMeasured: ["Consumer spending intentions", "Category spend", "Shopping channel", "Brand consideration", "Consumer sentiment"],
    isAccessibleForFree: false,
    license: "https://coresight.com/terms-of-service/",
    includedInDataCatalog: { "@type": "DataCatalog", name: "Coresight Consumer Insight Portal", url: SITE + "/" },
  };
  return <article className="wrap prose data-page">
    <Breadcrumbs items={[["Home", "/"], ["Consumer data", "/data/"]]} />
    <p className="eyebrow">US weekly consumer tracker</p>
    <h1>US weekly consumer survey data, every week since 2020</h1>
    <p className="lede">The Coresight Consumer Insight Portal is a continuous survey of US consumers. Every week a fresh wave measures what people are buying, where they shop and how they feel about spending — so retail, CPG and investment teams see what changed this week, not last quarter.</p>

    <ul className="stats inline-stats">
      <li><b>{f.waves}</b> survey waves</li>
      <li><b>{f.responses.toLocaleString()}</b> qualified responses</li>
      <li><b>Weekly</b> since December 2020</li>
      <li><b>~400</b> US adults per wave</li>
    </ul>

    <h2>What the dataset measures</h2>
    <p>Each weekly wave asks a consistent core of questions plus timely modules. The tracker covers consumer spending intentions, spend by category, the channels people shop (store, online, marketplace, social), brand and retailer consideration, and overall consumer sentiment. Every figure can be read for all respondents or cut by generation, gender, income band and US Census region, so you can compare how Gen Z, higher-income households or the Northeast differ from the national picture.</p>
    <p>Because the same questions are asked week after week, the value is in the movement: a three-point rise in households planning to cut non-essential spending, a category that holds while others soften, or a shopping channel gaining share. The portal tests each of those changes for statistical significance before it is called a real move.</p>

    <h2>How the survey is run</h2>
    <p>Respondents come from an online opt-in research panel. Each weekly US Consumer Survey targets about 400 qualified US adults aged 18 and over, with quotas set before fielding and tracked cell by cell while the wave is in field. Weekly tracker waves launch on Monday and usually field for two to three days; the wave date is the launch Monday. Annual and ad hoc studies — {f.annual} annual and {f.adhoc} ad hoc waves to date — field on their own dates and sit alongside the weekly tracker.</p>
    <p>Only qualified completes count. A respondent who screens out, abandons the survey or fails its quality checks is not in any base, and every wave's qualified count is reconciled with the survey platform before it is published. That reconciliation, run on every wave since December 2020, is what lets the data be used with confidence rather than caveats.</p>

    <h2>Weighting and significance</h2>
    <p>Figures are unweighted by default: each percentage is simply the share of qualified respondents who gave that answer. A Census-weighting option rakes each wave to US adult shares by gender, age (18-29, 30-44, 45-60, over 60) and Census region, using American Community Survey targets, with weights trimmed to between 0.2 and 5 times the average. Significance is always tested on the unweighted counts.</p>
    <p>A change is called significant only when a two-sided two-proportion z-test against the previous wave, or the same week a year earlier, gives p &lt; 0.05 after a Benjamini-Hochberg false-discovery correction across the wave, with at least 30 respondents on each side and an unchanged question base. Groups under 50 respondents are shown but flagged as a small base, and a question whose wording changed is treated as a new version — trends never join two versions. The full method is on the <Link href="/methodology/">methodology page</Link>.</p>

    <h2>What you can do with it</h2>
    <p>Inside the portal, the same dataset drives every screen: a question explorer for any question by demographic cut, cross-tabs that put one question against two cuts at once, trend lines across every wave a question was asked, wave-to-wave comparison with significance built in, an audience index that shows where a group over- and under-indexes, plain-English search across every question, and an assistant that answers questions only from published figures with sources cited. See the full list on the <Link href="/features/">features page</Link>.</p>

    <h2>Who uses weekly consumer data</h2>
    <p>Retail and CPG teams use it to see demand shift before it shows up in sales. Investment and research teams use it as an independent read on the US consumer between official economic releases. Strategy and insights teams use it to size audiences and track brand consideration over time. In every case the draw is the same: a long, consistent, weekly record of US consumer behavior that most organizations cannot build for themselves.</p>

    <Faq items={FAQ} />

    <p className="data-cta"><Link className="btn primary" href="/sign-in/">Request access to the full dataset</Link></p>

    <Jsonld data={dataset} />
  </article>;
}
