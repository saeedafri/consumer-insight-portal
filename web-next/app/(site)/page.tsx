import Link from "next/link";
import { FEATURES } from "../features";
import { NAME, SITE } from "../site";

export const metadata = { alternates: { canonical: "/" } };

const schema = {
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", name: "Coresight Research", url: SITE, logo: `${SITE}/coresight-logo.png` },
    { "@type": "WebSite", name: NAME, url: SITE },
    { "@type": "WebApplication", name: NAME, url: SITE, applicationCategory: "BusinessApplication", operatingSystem: "Web",
      description: "Explore Coresight Research's weekly US consumer surveys by question, demographic and wave." },
  ],
};

export default function Home() {
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />
    <section className="hero">
      <p className="eyebrow">Coresight Research</p>
      <h1>What US consumers are doing, every week</h1>
      <p>The Consumer Insight Portal puts Coresight&apos;s weekly US consumer surveys at your fingertips: every question, every wave, by generation, income and region, with significance testing built in.</p>
      <div className="actions">
        <Link className="btn primary" href="/sign-in/">Sign in to the portal</Link>
        <Link className="btn" href="/features/">See what it does</Link>
      </div>
    </section>
    <ul className="stats" aria-label="The portal in numbers">
      <li><b>370+</b>survey waves</li>
      <li><b>190,000+</b>qualified responses</li>
      <li><b>Weekly</b>tracker since December 2020</li>
      <li><b>~400</b>US adults each week</li>
    </ul>
    <section>
      <h2>Built for retail and consumer teams</h2>
      <ul className="grid">
        {FEATURES.slice(0, 6).map(([title, text]) => <li key={title} className="card"><h3>{title}</h3><p>{text}</p></li>)}
      </ul>
      <p className="actions"><Link href="/features/">See all features</Link></p>
    </section>
    <section className="prose">
      <h2>Numbers you can stand behind</h2>
      <p>Every figure comes from qualified completes, reconciled with the survey platform before it is published. Changes are only called significant after a two-proportion test with a false-discovery correction, and small bases are flagged.</p>
      <p><Link href="/methodology/">Read the methodology</Link></p>
    </section>
  </>;
}
