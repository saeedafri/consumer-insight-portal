import Link from "next/link";
import { FEATURES } from "../../features";

export const metadata = {
  title: "Features",
  description: "Survey library, question explorer, cross-tabs, trends, wave comparison, audience index, search, Ask CIP, boards and exports.",
  alternates: { canonical: "/features/" },
};

export default function Features() {
  return <>
    <section className="hero">
      <p className="eyebrow">Features</p>
      <h1>From a question to an answer in seconds</h1>
      <p>Every number is calculated before you ask for it, so each screen opens instantly, however many people use the portal at once.</p>
    </section>
    <ul className="grid">
      {FEATURES.map(([title, text]) => <li key={title} className="card"><h2 className="h3">{title}</h2><p>{text}</p></li>)}
    </ul>
    <section className="actions"><Link className="btn primary" href="/sign-in/">Sign in to the portal</Link></section>
  </>;
}
