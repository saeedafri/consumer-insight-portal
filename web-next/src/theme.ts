import { useSyncExternalStore } from "react";
// Coresight 2026 palette (Color Palette and Style Guide). Primary first; accents only where the guide allows.
// Two themes share the brand colours; dark swaps the surfaces and moves blue text and series to light blue.
const LIGHT = {
  red: "#D62E2F",        // highlight: always some red in a chart; fills (bars, logo, active nav, primary button)
  redLine: "#D62E2F",    // the focus line
  ink: "#2D2A29",        // text
  ink2: "#5F5C5B",       // secondary text (ink at 75 %)
  ink3: "#757170",       // tertiary text and value axes: 4.8:1 on the paper
  paper: "#FAFAFA",      // background
  surface: "#FFFFFF",    // cards
  raised: "#FFFFFF",     // tooltips, popovers
  blue: "#005F8F",
  sky: "#A3C0CE",        // light blue: neutral answers and fills; never text on white
  bar: "#5E8CA3",        // default bar colour: 3.6:1 against white (WCAG 1.4.11 asks 3:1 for chart marks)
  s1: "#005F8F", s2: "#357599", s3: "#5B8FAD",   // series ramp, strongest first (6.9, 5.1, 3.5:1 on white)
  other: "#8A8684",      // context series beyond the fourth: 3.6:1
  rose: "#D07676",
  grey: "#7F7F7F",
  silver: "#B2B2B2",
  line: "#E5E3E1",       // hairlines and grid
  lineStrong: "#8A8684", // axis lines and control borders: 3.6:1
  mist: "#E5E3E1",
  warn: "#8A5A00",
  green: "#61A575",      // positive only, against red as negative
  negStrong: "#7F7F7F", negMild: "#B2B2B2", posMild: "#D07676", posStrong: "#D62E2F",   // scale answers
  heat: ["#F1F6F9", "#D3E2EA", "#A3C0CE", "#6E9CB7", "#357599", "#005F8F"],             // cross-tab, low to high
  heatInk: ["#2D2A29", "#2D2A29", "#2D2A29", "#2D2A29", "#FFFFFF", "#FFFFFF"],         // every step ≥ 4.5:1
  shadow2: "0 8px 24px rgba(45,42,41,.12)",
};
const DARK: typeof LIGHT = {
  ...LIGHT, redLine: "#E5484A", ink: "#FAFAFA", ink2: "#C9C5C3", ink3: "#A39F9D", paper: "#1B1918", surface: "#242120", raised: "#2D2A29",
  blue: "#A3C0CE", bar: "#A3C0CE", s1: "#A3C0CE", s2: "#7FA7BC", s3: "#5C8DA8", other: "#8C8785",
  grey: "#A39F9D", silver: "#6E6A68", line: "#3D3937", lineStrong: "#77726F", mist: "#3D3937", warn: "#FEBC20",
  negStrong: "#C9C5C3", negMild: "#8C8785", posMild: "#D07676", posStrong: "#E5484A",
  heat: ["#2C3134", "#344550", "#41606F", "#5C8DA8", "#86AEC2", "#B9D2DE"],
  heatInk: ["#FAFAFA", "#FAFAFA", "#FAFAFA", "#141211", "#141211", "#141211"],
  shadow2: "0 8px 24px rgba(0,0,0,.5)",
};
export { DARK, LIGHT };

export type Theme = "light" | "dark";
export let C = document.documentElement.dataset.theme === "dark" ? DARK : LIGHT;   // set before paint by index.html;
// a live binding, so modules read the current theme's colours at render time

const listeners = new Set<() => void>();
export function setTheme(theme: Theme) {
  C = theme === "dark" ? DARK : LIGHT;
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("cip-theme", theme); } catch { /* private mode: the choice lasts this visit */ }
  listeners.forEach(run => run());
}
export const savedTheme = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");
/** The theme as React state: charts and heat cells re-colour in place on a switch, nothing remounts. */
export const useTheme = () => useSyncExternalStore(run => { listeners.add(run); return () => listeners.delete(run); }, savedTheme);

/** Build something (a chart option) with the light palette whatever the screen shows: PNGs go into decks. */
export function inLight<T>(build: () => T): T {
  const now = C;
  C = LIGHT;
  try { return build(); } finally { C = now; }
}

const mix = (a: string, b: string, t: number) => "#" + [1, 3, 5].map(i => Math.round(parseInt(a.slice(i, i + 2), 16) * (1 - t) + parseInt(b.slice(i, i + 2), 16) * t)
  .toString(16).padStart(2, "0")).join("");

/** n series colours, strongest first: the solid series ramp, then a solid fade towards the light end for long lists. */
export function blues(n: number): string[] {
  if (n <= 1) return [C.bar];
  const ramp = [C.s1, C.s2, C.s3];
  if (n <= 3) return ramp.slice(0, n);
  const end = C === DARK ? "#41606F" : "#A3C0CE";
  return Array.from({ length: n }, (_, i) => mix(C.s1, end, i / (n - 1)));
}

/** A cross-tab cell's fill and text at this share of the table's largest value (0–1): six solid steps, all ≥ 4.5:1. */
export function heatStep(ratio: number): { background: string; color: string } {
  const i = Math.min(5, Math.max(0, Math.floor(Math.max(0, ratio) * 6)));
  return { background: C.heat[i], color: C.heatInk[i] };
}

const NEGATIVE = /decrease|worse|less|lower|dissatisf|unlikely|disagree|poor|bad|cut|reduc|unfavou?r/i;
const POSITIVE = /increase|better|more|higher|satisf|likely|agree|good|excellent|favou?r/i;
const NEUTRAL = /no (meaningful )?change|same|neither|neutral|unchanged|about the same/i;
const UNSURE = /don.?t know|not sure|prefer not|n\/a/i;

/** Colours for a scale's answers, as the guide asks: greys for negatives, blue for neutral, reds for
 *  positives, the strongest ends darkest; null when the answers are not a scale (use the blue ombre). */
export function scaleColours(labels: string[]): string[] | null {
  const kind = labels.map(l => UNSURE.test(l) ? "u" : NEUTRAL.test(l) ? "0" : NEGATIVE.test(l) && !/^not\b/i.test(l) ? "-" : POSITIVE.test(l) ? "+" : "?");
  if (!kind.includes("-") || !kind.includes("+") || kind.includes("?")) return null;
  const neg = kind.filter(k => k === "-").length, posCount = kind.filter(k => k === "+").length;
  let n = 0, q = 0;
  const negShades = [C.negStrong, C.negMild], posShades = [C.posMild, C.posStrong];
  return kind.map(k => {
    if (k === "u") return C.line;
    if (k === "0") return C.sky;
    if (k === "-") { const i = n++; return negShades[neg === 1 ? 0 : Math.round((i / (neg - 1)) * (negShades.length - 1))]; }
    const i = q++; return posShades[posCount === 1 ? 1 : Math.round((i / (posCount - 1)) * (posShades.length - 1))];
  });
}

const luminance = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
  .map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);

/** Ink or white for a label on a solid fill: white when it keeps 4.5:1 on the fill, else ink. */
export function labelOn(fill: string): string {
  return 1.05 / (luminance(fill) + 0.05) >= 4.5 ? "#FFFFFF" : "#2D2A29";
}
