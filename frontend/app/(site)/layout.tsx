// The frame of the public site's pages (home, features, the data, this week, methodology, sign-in): the coresight.com
// header (logo, the portal's name, and coresight.com's Research & Data, Events, Services) and footer, and its fonts.
// Signing in starts from each page's own buttons (/sign-in/). The signed-in portal (/app) has its own frame.
import Link from "next/link";
// The same fonts as the signed-in portal (src/main.tsx), from the same packages, so both read alike and the browser
// downloads them once: a visitor who signs in from here already has them. Roboto for text, Montserrat for headings.
import "@fontsource-variable/montserrat";
import "@fontsource-variable/roboto";
import "./site.css";
import Motion from "./Motion";
import { SiteSchema } from "./seo";

// The coresight.com chrome, identical to the portal (src/components/Shell.tsx): logo + name, the site's top menus,
// and the dark footer. Links go to coresight.com, in the same tab, like any site link.
const CORESIGHT = "https://coresight.com";
const SITE_LINKS: [string, string][] = [["/research/", "Research & Data"], ["/events/", "Events"], ["/memberships/", "Services"]];
const FOOT_LINKS: [string, [string, string][]][] = [
  ["Services", [["/memberships/", "Research & Data Memberships"], ["/innovator-services/", "Innovator Market Development"],
                ["/custom-research-advisory-services/", "Advisory & Custom Research"], ["/coresight-ai-council/", "AI Council"]]],
  ["Get in touch", [["/about-us/contact/", "Contact Us"], ["https://5jdoa.share.hsforms.com/2OopvqR9nRLa_8920kgYvaQ", "Media Inquiries"]]],
  ["Quick links", [["/research/", "All Research"], ["/events/", "Events"], ["/newsroom/", "Newsroom"], ["/retailistic-podcast/", "The Retaili$tic Podcast"]]],
];
const LEGAL: [string, string][] = [["/terms-of-service/", "Terms of Use"], ["/privacy-policy/", "Privacy Policy"],
  ["/coresight-research-responsible-vulnerability-disclosure-policy/", "Vulnerability Disclosure Policy"]];
const siteUrl = (path: string) => path.startsWith("http") ? path : CORESIGHT + path;

export default function Site({ children }: { children: React.ReactNode }) {
  return <div>
    <header className="site-head">
      <Link href="/" className="site-brand" aria-label="Consumer Insight Portal home">
        <img className="logo-light" src="/coresight-logo.png" alt="Coresight Research" width="76" height="38" />
        <img className="logo-dark" src="/coresight-logo-reversed.png" alt="Coresight Research" width="76" height="38" />
        <span>Consumer Insight Portal</span>
      </Link>
      <nav className="site-links" aria-label="Coresight.com">
        {SITE_LINKS.map(([path, label]) => <a key={path} href={CORESIGHT + path}>{label}</a>)}
      </nav>
    </header>
    <SiteSchema />
    <Motion />
    <main>{children}</main>
    <footer className="site-foot">
      <div className="site-foot-cols">
        <section>
          <img src="/coresight-logo-reversed.png" alt="Coresight Research" width="120" height="60" />
          <h2>Consumer Insight Portal</h2>
          <ul>
            <li><a href={CORESIGHT + "/"}>Back to coresight.com</a></li>
            <li><Link href="/methodology/">Methodology</Link></li>
            <li><Link href="/features/">Features</Link></li>
          </ul>
        </section>
        {FOOT_LINKS.map(([head, links]) => <section key={head}>
          <h2>{head}</h2>
          <ul>{links.map(([path, label]) => <li key={label}><a href={siteUrl(path)}>{label}</a></li>)}</ul>
        </section>)}
      </div>
      <div className="site-foot-base">
        <p>© {new Date().getFullYear()} Coresight Research. All rights reserved.</p>
        <ul>
          {LEGAL.map(([path, label]) => <li key={label}><a href={CORESIGHT + path}>{label}</a></li>)}
          <li><a href="https://www.linkedin.com/company/coresight-research/">LinkedIn</a></li>
        </ul>
      </div>
    </footer>
  </div>;
}
