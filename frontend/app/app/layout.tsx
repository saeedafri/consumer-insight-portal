// The frame of the signed-in portal (/app and everything under it): its loading screen styles, the theme, and the
// early request for the data every screen needs (see `early` below). The portal itself is src/main.tsx.
import { preload } from "react-dom";
import "./boot.css";

export const metadata = { title: "Portal", robots: { index: false, follow: false } };

// Theme before first paint: the saved choice, else the system setting (no flash of the wrong theme)
const theme = `try { var t = localStorage.getItem("cip-theme"); } catch (e) {}
document.documentElement.dataset.theme = t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");`;

// Ask for the data a screen needs as soon as the HTML arrives, not after the JavaScript has loaded and drawn the screen
// (about 1.5 s from India on a first visit, 0.35 s on a repeat one, measured 8 Nov 2026 with 232 ms added per request):
// src/api.ts get() picks these answers up instead of asking again. On a wave's screens that is also its book, and on
// its overview the "at a glance" dashboards, whose names come with the list of waves.
const EVERY_SCREEN = ["/api/v1/me", "/api/v1/waves"];   // also preloaded from <head> (below)
// The wave screens that open its book: the routes in src/main.tsx (a new wave screen that needs the book goes here too)
const BOOK_SCREENS = "questions|crosstab|trends|compare|audience|changes|survey";
const early = `window.__early = {};
function ask(u) { window.__early[u] = fetch(u, { credentials: "same-origin" }); }
${JSON.stringify([...EVERY_SCREEN, "/api/v1/reports"])}.forEach(ask);   // reports: the menu's weekly-report link
var wave = location.pathname.match(/^\\/app\\/w\\/(\\d+)(\\/(${BOOK_SCREENS})(\\/.*)?)?\\/?$/);
if (wave) ask("/api/v1/waves/" + wave[1] + "/book");
if (wave && !wave[2]) {   // the overview: its dashboards, named in the list of waves
  window.__early["/api/v1/waves"]
    .then(function (r) { return r.ok ? r.clone().json() : []; })
    .then(function (list) {
      list.forEach(function (w) {
        if (String(w.survey_id) !== wave[1]) return;
        (w.dashboards || []).forEach(function (code) { ask("/api/v1/dashboards/" + code + "/" + wave[1]); });
      });
    })
    .catch(function () {});
}`;

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  // Asked from <head>, so the browser sends them before the stylesheet arrives: the script below has to wait for it,
  // one more round trip. The script's fetch() then takes the preloaded answer (same URL, same credentials).
  EVERY_SCREEN.forEach(url => preload(url, { as: "fetch", crossOrigin: "anonymous" }));
  return <><script dangerouslySetInnerHTML={{ __html: theme + "\n" + early }} /><div id="root">{children}</div></>;
}
