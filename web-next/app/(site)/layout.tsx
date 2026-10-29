import Link from "next/link";
import { Playfair_Display, Inter, Montserrat } from "next/font/google";
import "./site.css";
import ThemeToggle from "./ThemeToggle";
import Motion from "./Motion";
import { SiteSchema } from "./seo";

// next/font self-hosts each face and generates a metric-matched fallback, so text does not reflow when the
// webfont arrives (zero font-swap layout shift) — the fonts also preload, so this is faster, not just steadier.
const serif = Playfair_Display({ subsets: ["latin"], variable: "--f-serif", display: "swap" });
const sans = Inter({ subsets: ["latin"], variable: "--f-sans", display: "swap" });
const head = Montserrat({ subsets: ["latin"], variable: "--f-head", display: "swap" });
const fonts = `${serif.variable} ${sans.variable} ${head.variable}`;

// The coresight.com chrome, identical to the portal (web/src/components/Shell.tsx): logo + name, the site's top menus,
// and the dark footer. Links go to coresight.com, in the same tab, like any site link.
const CORESIGHT = "https://coresight.com";
const SITE_LINKS: [string, string][] = [["/research/", "Research & Data"], ["/events/", "Events"], ["/memberships/", "Services"], ["/about-us/", "About"]];
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
  return <div className={fonts}>
    <header className="site-head">
      <Link href="/" className="site-brand" aria-label="Consumer Insight Portal home">
        <img className="logo-light" src="/coresight-logo.png" alt="Coresight Research" width="76" height="38" />
        <img className="logo-dark" src="/coresight-logo-reversed.png" alt="Coresight Research" width="76" height="38" />
        <span>Consumer Insight Portal</span>
      </Link>
      <nav className="site-links" aria-label="Coresight.com">
        {SITE_LINKS.map(([path, label]) => <a key={path} href={CORESIGHT + path}>{label}</a>)}
      </nav>
      <ThemeToggle />
      <Link className="site-signin" href="/sign-in/">Sign in</Link>
      <Link className="btn primary" href="/sign-in/">Request access</Link>
    </header>
    <nav className="subnav" aria-label="Portal">
      <div className="wrap inner">
        <Link href="/features/">Features</Link>
        <Link href="/this-week/">This week</Link>
        <Link href="/data/">Consumer data</Link>
        <Link href="/methodology/">Methodology</Link>
        <Link href="/#api">API &amp; MCP</Link>
      </div>
    </nav>
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
