import Link from "next/link";
import { FEATURES } from "../../features";
import { Breadcrumbs, Faq } from "../seo";

export const metadata = {
  title: "Features",
  description: "Survey library, question explorer, cross-tabs, trends, wave comparison, audience index, plain-English search, Ask CIP, boards and exports.",
  alternates: { canonical: "/features/" },
};

const FEATURES_FAQ: [string, string][] = [
  ["What can I do with the Consumer Insight Portal?", "Explore any survey question by demographic cut, build cross-tabs, track trends across waves, compare waves, index audiences, search in plain English and ask the data questions — then export to CSV, Excel or PowerPoint."],
  ["Can I access the data through an API?", "Yes. API keys give programmatic access to the same figures, and an MCP connector lets AI assistants query the portal directly, with the same entitlements and audit log."],
  ["Which demographic cuts are available?", "Every question can be read for all respondents or cut by generation, gender, income band and US Census region, with significance tested against the previous wave."],
];

export default function Features() {
  return <>
    <section className="wrap page-hero">
      <Breadcrumbs items={[["Home", "/"], ["Features", "/features/"]]} />
      <p className="eyebrow">Features</p>
      <h1>From a question to an answer in seconds</h1>
      <p className="lede">Every number is calculated before you ask for it, so each screen opens instantly, however many people use the portal at once.</p>
    </section>
    <section className="wrap section" style={{ paddingTop: 0 }}>
      <div className="grid3">
        {FEATURES.map(([title, text]) => <div className="cell" key={title}><h3>{title}</h3><p>{text}</p></div>)}
      </div>
      <div className="actions" style={{ marginTop: 40 }}><Link className="btn primary" href="/sign-in/">Request access</Link></div>
      <Faq items={FEATURES_FAQ} />
    </section>
  </>;
}
