import Link from "next/link";
import "./(site)/site.css";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return <main className="signin"><p className="eyebrow">404</p><h1 className="h2">Page not found</h1>
    <p><Link className="btn primary" href="/">Go to the home page</Link></p></main>;
}
