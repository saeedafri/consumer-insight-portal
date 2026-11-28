// What In store vs online (screens/Channels.tsx) and the weekly topic screens (screens/Weekly.tsx: Activities &
// retailers, Spending pressure, Consumer sentiment) share: the group in the address, the trend's weeks, a figure's
// rounding. And In store vs online's share lookup over a weekly survey's published question files
// (api/v1/questions/<family>/tracker/<code>.json.gz, every group with exact counts, fetched once and cached): a question
// asked under more than one code over the years is joined by its wording, and a code that also held other questions in
// other weeks counts only the weeks asked with that wording (the weekly topic screens get theirs from the ETL instead,
// etl/weekly_topics.py, which joins them the same way).
import type { QuestionFile } from "./api";
import { fmtDate, SMALL_BASE } from "./stats";

export type Week = [number, string];   // [survey_id, date]
export const EVERYONE = "total:Total";   // the cut of every respondent: the grey tick on the bars
const YEAR = 365 * 86_400_000;   // the trend's default range: the year up to the chosen week
export const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
export const figure = (v: number | null | undefined) => v == null ? null : +v.toFixed(1);   // a figure as charts and exports show it
/** A group as the screens name it: the data's GenZ and GenX are "Gen Z" and "Gen X", as on the Retailer databank. */
export const groupLabel = (value: string) => value.replace(/^Gen([A-Z])$/, "Gen $1");
/** A group's base for a hover, "n 4", with the small-base caution the rest of CIP gives under SMALL_BASE people. */
export const baseText = (n: number | null | undefined) => `n ${n ?? "–"}${n != null && n < SMALL_BASE ? " ⚠ small base, read with caution" : ""}`;
/** A bar's row label, with ⚠ when its group's base is under SMALL_BASE (as the Cross-tab's amber bases). */
export const rowLabel = (row: string, n: number | null | undefined) => `${groupLabel(row)}${n != null && n < SMALL_BASE ? " ⚠" : ""}`;
/** A value axis's numbers with a true minus (−10), as every figure writes it: ECharts' own "{value}" writes a hyphen. */
export const axisNumber = (unit = "") => (v: number) => `${v < 0 ? "−" : ""}${Math.abs(v)}${unit}`;
/** Answers that are no answer, left out of In store vs online's rankings: "None of these", the catch-all "Other"
 *  ("Other (please specify)"), "Don't know" / "Don't recall", "Prefer not to say"; a real answer that starts with Other
 *  ("Other savings / investments") stays. The same rule as config/weekly_topics.yml leave_out, which the ETL reads. */
export const SKIP = /^(none of|other\s*($|[-–(])|don.?t (know|recall)|prefer not)/i;

/** The group in the address (g, "dim:value"): itself when this week has answers from it, else its kind's first group,
 *  else everyone. */
export const chosenCut = (offered: [string, string][], asked: string) =>
  (offered.find(c => c.join(":") === asked) ?? offered.find(c => c[0] === asked.split(":")[0]))?.join(":") ?? EVERYONE;

/** The trend's weeks, oldest first: the year up to the chosen week (`at` in `weeks`, newest first; the Week filter moves
 *  it, 27 Nov 2026) unless the address's From / To pick others (a From after To is swapped). */
export function trendWeeks(weeks: Week[], at: number, from: string | null, to: string | null) {
  const oldestFirst = [...weeks].reverse();
  const yearBefore = oldestFirst.findIndex(w => time(w[1]) >= time(weeks[at][1]) - YEAR);
  const place = (week: string | null, fallback: number) => { const i = oldestFirst.findIndex(w => String(w[0]) === week); return i < 0 ? fallback : i; };
  const [first, last] = [place(from, yearBefore), place(to, oldestFirst.length - 1 - at)].sort((x, y) => x - y);
  return { oldestFirst, span: oldestFirst.slice(first, last + 1) };
}

/** The weeks a line is drawn over: from the first to the last the group answered (so its end label is a real week's);
 *  a week between without an answer breaks the line, and `unanswered` counts them for the note under it. */
export function drawnWeeks(span: Week[], answered: (w: Week) => boolean) {
  const start = span.findIndex(answered), end = span.length - [...span].reverse().findIndex(answered);
  const drawn = start < 0 ? [] : span.slice(start, end);
  return { drawn, unanswered: drawn.filter(w => !answered(w)).length,
           rangeText: drawn.length ? `${fmtDate(drawn[0][1])} to ${fmtDate(drawn.at(-1)![1])}` : "no weeks" };
}

/** Question files as one share lookup, over the weeks that asked `wording`: share(survey_id, "dim:value", answer)
 *  → % of the group asked, or null; base(survey_id, "dim:value") → people asked; weeks: survey_id → date; labels:
 *  every answer those weeks gave. An answer is its label, or "row: label" for a grid's row (Utilities: Notable
 *  increase), as api/ask_figures.py names them. */
export function shares(files: QuestionFile[], wording: RegExp) {
  const cells = new Map<string, [number | null, number]>();
  const bases = new Map<string, number>();
  const weeks = new Map<number, string>(), labels = new Set<string>();
  for (const file of files) {
    const kept = file.waves.map(w => wording.test(file.versions[w[2] - 1] ?? ""));
    file.waves.forEach((w, i) => kept[i] && weeks.set(w[0], w[1]));
    file.w.forEach((w, k) => {
      if (!kept[w]) return;
      const [item, , answer] = file.answers[file.a[k]];
      const label = item && item !== answer ? `${item}: ${answer}` : item || answer;
      const group = `${file.waves[w][0]}|${file.cuts[file.c[k]].join(":")}`;
      labels.add(label);
      cells.set(`${group}|${label}`, [file.n[k], file.b[k]]);
      bases.set(group, file.b[k]);   // one base for every answer of a group's week (every row of a grid is asked)
    });
  }
  const share = (survey: number, cut: string, label: string) => {
    const cell = cells.get(`${survey}|${cut}|${label}`);
    return cell && cell[0] != null && cell[1] ? 100 * cell[0] / cell[1] : null;
  };
  return { share, base: (survey: number, cut: string) => bases.get(`${survey}|${cut}`) ?? null, weeks, labels };
}
