// Coresight 2026 palette (Color Palette and Style Guide). Primary first; accents only where the guide allows.
export const C = {
  red: "#D62E2F",        // highlight: always some red in a chart
  ink: "#2D2A29",        // text
  paper: "#FAFAFA",      // background
  blue: "#005F8F",
  sky: "#A3C0CE",        // default bar colour; never text on white
  rose: "#D07676",
  grey: "#7F7F7F",
  silver: "#B2B2B2",
  mist: "#E5E5E5",
  green: "#61A575",      // positive only, against red as negative
};

/** An ombre of the dark blue (the guide's "opacity trick"), darkest first, for n series. */
export function blues(n: number): string[] {
  if (n <= 1) return [C.sky];
  return Array.from({ length: n }, (_, i) => {
    const alpha = 1 - (i * 0.75) / (n - 1);
    return `rgba(0, 95, 143, ${alpha.toFixed(2)})`;
  });
}

/** Text that keeps contrast on a cell of the blue ombre: white on the dark end, ink on the light end. */
export function inkOn(alpha: number): string {
  return alpha > 0.55 ? "#FFFFFF" : C.ink;
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
export const labelOn = (fill: string) => ([C.red, C.grey, C.blue, C.ink].includes(fill) || fill.startsWith("rgba(0, 95, 143, 1") || fill.startsWith("rgba(0, 95, 143, 0.9") || fill.startsWith("rgba(0, 95, 143, 0.8") ? "#FFFFFF" : C.ink);
