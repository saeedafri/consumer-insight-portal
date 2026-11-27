// A weekly survey's published question files as one share lookup, read by In store vs online (screens/Channels.tsx) and
// the weekly topic screens (screens/Weekly.tsx: Activities & retailers, Spending pressure, Consumer sentiment). The
// files (api/v1/questions/<family>/tracker/<code>.json.gz, every group with exact counts) are fetched once and cached;
// a question asked under more than one code over the years is joined by its wording, and a code that also held other
// questions in other weeks counts only the weeks asked with that wording.
import type { QuestionFile } from "./api";

/** Answers that are no answer, left out of the rankings: "None of these", "Other", "Don't know". */
export const SKIP = /^(none of|other|don.?t know)/i;

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
