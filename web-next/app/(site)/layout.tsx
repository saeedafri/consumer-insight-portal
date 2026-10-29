import Link from "next/link";
import "@fontsource-variable/montserrat";
import "@fontsource-variable/roboto";
import "./site.css";

export default function Site({ children }: { children: React.ReactNode }) {
  return <>
    <header className="top">
      <Link href="/" className="brand"><picture><source srcSet="/coresight-logo-reversed.png" media="(prefers-color-scheme: dark)" /><img src="/coresight-logo.png" alt="Coresight Research" width="97" height="48" /></picture></Link>
      <nav aria-label="Main">
        <Link href="/features/">Features</Link>
        <Link href="/methodology/">Methodology</Link>
        <Link href="/sign-in/" className="btn">Sign in</Link>
      </nav>
    </header>
    <main>{children}</main>
    <footer className="foot">
      <p>© {new Date().getFullYear()} Coresight Research. Consumer Insight Portal.</p>
      <nav aria-label="Footer"><Link href="/features/">Features</Link><Link href="/methodology/">Methodology</Link><Link href="/sign-in/">Sign in</Link></nav>
    </footer>
  </>;
}
