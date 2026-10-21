// Coresight 2026 palette (Color Palette and Style Guide). Primary first; accents only where the guide allows.
// Two themes share the brand colours; dark swaps the surfaces and moves blue text and series to light blue.
const LIGHT = {
  red: "#D62E2F",        // highlight: always some red in a chart
  ink: "#2D2A29",        // text
  ink2: "#5F5C5B",       // secondary text (ink at 75 %)
  paper: "#FAFAFA",      // background
  surface: "#FFFFFF",    // cards, tooltips
  blue: "#005F8F",
  sky: "#A3C0CE",        // default bar colour; never text on white
  rose: "#D07676",
  grey: "#7F7F7F",
  silver: "#B2B2B2",
  mist: "#E5E5E5",
  warn: "#8A5A00",
  green: "#61A575",      // positive only, against red as negative
  series: "0, 95, 143",  // the blue the ombre is made of (rgb)
};
const DARK: typeof LIGHT = {
  ...LIGHT, ink: "#FAFAFA", ink2: "#C9C5C3", paper: "#1B1918", surface: "#2D2A29", blue: "#A3C0CE",
  grey: "#A39F9D", silver: "#6E6A68", mist: "#45413F", warn: "#FEBC20", series: "163, 192, 206",
};

export type Theme = "light" | "dark";
export let C = document.documentElement.dataset.theme === "dark" ? DARK : LIGHT;   // set before paint by index.html;
// a live binding, so modules read the current theme's colours at render time

export function setTheme(theme: Theme) {
  C = theme === "dark" ? DARK : LIGHT;
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("cip-theme", theme); } catch { /* private mode: the choice lasts this visit */ }
}
export const savedTheme = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

/** An ombre of the series blue (the guide's "opacity trick"), strongest first, for n series. */
export function blues(n: number): string[] {
  if (n <= 1) return [C.sky];
  return Array.from({ length: n }, (_, i) => `rgba(${C.series}, ${(1 - (i * 0.75) / (n - 1)).toFixed(2)})`);
}

/** Contrast-guaranteed heat ombre alpha avoiding WCAG dead zones (0.55-0.78). */
export function heatAlpha(ratio: number): number {
  const r = Math.max(0, Math.min(1, ratio));
  if (r < 0.65) return 0.06 + 0.44 * (r / 0.65);
  return 0.82 + 0.16 * ((r - 0.65) / 0.35);
}

/** A cell of the heat ombre at this strength (0–1). */
export const heat = (alpha: number) => `rgba(${C.series}, ${alpha.toFixed(2)})`;

/** Text that keeps contrast on a cell of the blue ombre: white on the dark end, ink on the light end. */
export function inkOn(alpha: number): string {
  if (C === DARK) return alpha > 0.45 ? "#141211" : "#FAFAFA";   // dark ink on light-tint cells, crisp white on dark
  return alpha >= 0.80 ? "#FFFFFF" : "#1B1918";
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
  const negShades = [C.grey, C.silver], posShades = [C.rose, C.red];
  return kind.map(k => {
    if (k === "u") return C.mist;
    if (k === "0") return C.sky;
    if (k === "-") { const i = n++; return negShades[neg === 1 ? 0 : Math.round((i / (neg - 1)) * (negShades.length - 1))]; }
    const i = q++; return posShades[posCount === 1 ? 1 : Math.round((i / (posCount - 1)) * (posShades.length - 1))];
  });
}

/** Ink or white for a label on a fill, keeping at least 4.5:1. */
export function labelOn(fill: string): string {
  const strong = /^rgba\(0, 95, 143, (1|0\.[89])/.test(fill) || ["#D62E2F", "#7F7F7F", "#005F8F", "#2D2A29"].includes(fill);
  return strong ? "#FFFFFF" : "#2D2A29";   // fills are light or brand-strong in both themes
}
