import "./boot.css";

export const metadata = { title: "Portal", robots: { index: false, follow: false } };

// Theme before first paint: the saved choice, else the system setting (no flash of the wrong theme)
const theme = `try { var t = localStorage.getItem("cip-theme"); } catch (e) {}
document.documentElement.dataset.theme = t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");`;

// Ask for the data every screen needs as soon as the HTML arrives, not after the JavaScript (three round trips, about
// 1.5 s from India) has loaded: src/api.ts get() picks these answers up instead of asking again.
const early = `window.__early = {};
["/api/v1/me", "/api/v1/waves"].forEach(function (u) { window.__early[u] = fetch(u, { credentials: "same-origin" }); });`;

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return <><script dangerouslySetInnerHTML={{ __html: theme + "\n" + early }} /><div id="root">{children}</div></>;
}
