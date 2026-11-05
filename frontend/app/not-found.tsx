import Link from "next/link";
import "./(site)/site.css";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return <main className="signin-box"><p className="eyebrow">404</p><h1>Page not found</h1>
    <p style={{ marginTop: 16 }}><Link className="btn primary" href="/">Go to the home page</Link></p></main>;
}
