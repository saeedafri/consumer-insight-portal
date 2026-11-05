import Link from "next/link";
import { NAME, SITE } from "../site";

const CORESIGHT = "https://coresight.com";

// One JSON-LD block. Pure static markup — no runtime cost, read straight from the HTML by crawlers.
export function Jsonld({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

// The brand entity, referenced by @id from every page's schema (helps Google's Knowledge Graph + AI answer engines).
export const ORG = {
  "@type": "Organization", "@id": SITE + "/#org",
  name: "Coresight Research", url: CORESIGHT, logo: SITE + "/coresight-logo.png",
  sameAs: ["https://www.linkedin.com/company/coresight-research/", CORESIGHT + "/"],
  description: "Coresight Research runs the Consumer Insight Portal: a weekly US consumer survey tracking spending, shopping behavior and sentiment across retail categories since December 2020.",
  knowsAbout: ["Consumer research", "US consumer survey data", "Retail and consumer trends", "Consumer sentiment", "Shopper behavior", "Consumer spending"],
  areaServed: "United States",
};
export const WEBSITE = { "@type": "WebSite", "@id": SITE + "/#website", name: NAME, url: SITE, publisher: { "@id": SITE + "/#org" } };

// Organization + WebSite, on every public page.
export function SiteSchema() {
  return <Jsonld data={{ "@context": "https://schema.org", "@graph": [ORG, WEBSITE] }} />;
}

// Visible breadcrumb + BreadcrumbList schema. items: [label, href]; the last is the current page.
export function Breadcrumbs({ items }: { items: [string, string][] }) {
  return <>
    <nav className="crumbs" aria-label="Breadcrumb">
      {items.map(([label, href], i) => i < items.length - 1
        ? <span key={href}><Link href={href}>{label}</Link><span aria-hidden="true"> / </span></span>
        : <span key={href} aria-current="page">{label}</span>)}
    </nav>
    <Jsonld data={{
      "@context": "https://schema.org", "@type": "BreadcrumbList",
      itemListElement: items.map(([label, href], i) => ({ "@type": "ListItem", position: i + 1, name: label, item: SITE + href })),
    }} />
  </>;
}

// Visible FAQ + FAQPage schema (wins long-tail and AI Overviews that answer a direct question).
export function Faq({ items, heading = "Common questions" }: { items: [string, string][]; heading?: string }) {
  return <section className="faq">
    <h2 className="roll"><span>{heading}</span></h2>
    <dl>
      {items.map(([q, a]) => <div className="qa reveal" key={q}><dt>{q}</dt><dd>{a}</dd></div>)}
    </dl>
    <Jsonld data={{
      "@context": "https://schema.org", "@type": "FAQPage",
      mainEntity: items.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
    }} />
  </section>;
}
