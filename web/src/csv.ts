// Download any table as CSV: what the screen shows, plus the question wording and base (as competitors' exports do).
export function downloadCsv(name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  const cell = (v: unknown) => {
    // text starting = + - @ (an answer label, a respondent's words) would run as a formula in Excel: keep it literal
    const s = v == null ? "" : typeof v === "string" && /^[=+\-@\t\r]/.test(v) ? `'${v}` : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const text = [...notes.map(n => cell(n)), "", header.map(cell).join(","), ...rows.map(r => r.map(cell).join(","))].join("\n");
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv" })), download: `${name}.csv` });
  a.click();
  URL.revokeObjectURL(a.href);
}

export type Format = "csv" | "xlsx" | "pptx";

/** The same table as CSV (built here), an Excel workbook or a PowerPoint slide (built by the API from these rows). */
export async function downloadTable(format: Format, name: string, header: string[], rows: (string | number | null | undefined)[][], notes: string[]) {
  if (format === "csv") return downloadCsv(name, header, rows, notes);
  const response = await fetch(`/api/v1/export/${format}`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, header, rows: rows.map(r => r.map(c => (c === undefined ? null : c))), notes }) });
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await response.blob()), download: `${name}.${format}` });
  a.click();
  URL.revokeObjectURL(a.href);
}
