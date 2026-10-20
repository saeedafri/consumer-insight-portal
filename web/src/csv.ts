// Download any table as CSV: what the screen shows, plus the question wording and base (as competitors' exports do).
export function downloadCsv(name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  const cell = (v: unknown) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const text = [...notes.map(n => cell(n)), "", header.map(cell).join(","), ...rows.map(r => r.map(cell).join(","))].join("\n");
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv" })), download: `${name}.csv` });
  a.click();
  URL.revokeObjectURL(a.href);
}
