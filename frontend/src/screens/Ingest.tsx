// Upload survey (/app/ingest), admins only, opened from the Admin menu (components/Shell.tsx): a week of the China
// Consumer Survey from Baidu QSS, which has no API CIP can reach. The analyst picks Baidu's raw export and its topline;
// Check sends both to POST /api/v1/admin/survey/preview (api/ingest.py), which counts every answer from the raw rows
// and compares each count with the topline, writing nothing. Publish is offered only when every figure matches; it loads
// the wave and rebuilds the published files. This screen only draws what the API answers.
import { useState } from "react";
import { Link } from "react-router";
import { sendSurvey } from "../api";
import type { SurveyCheck, SurveyLoaded } from "../api";
import { Card, count, day } from "../components/bits";
import { FileSpreadsheet, FileText, Info } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// The four stages (Design 1's tracker); which one you are at follows from what you have done, nothing to click
const STAGES = [["Select", "Choose both files"], ["Validate", "Count and compare"], ["Review", "Every figure"], ["Publish", "Load the week"]] as const;

/** One of the two file boxes (Design 2's step card): what it is, what to choose, then the chosen file's name and size. */
function FilePick({ icon: Glyph, label, hint, accept, file, pick }: { icon: LucideIcon; label: string; hint: string; accept: string; file: File | null; pick: (f: File | null) => void }) {
  return <label className={`card file-pick ${file ? "chosen" : ""}`}>
    <span className="file-pick-head"><Glyph size={18} strokeWidth={1.8} aria-hidden="true" />{label}</span>
    <span className="muted">{hint}</span>
    <input type="file" accept={accept} onChange={e => pick(e.target.files?.[0] ?? null)} />
    {file && <b>{file.name} · {Math.ceil(file.size / 1024)} KB</b>}
  </label>;
}

export default function Ingest() {
  const [raw, setRaw] = useState<File | null>(null);
  const [topline, setTopline] = useState<File | null>(null);
  const [check, setCheck] = useState<SurveyCheck | null>(null);
  const [loaded, setLoaded] = useState<SurveyLoaded | null>(null);
  const [busy, setBusy] = useState<"" | "preview" | "publish">("");
  const [error, setError] = useState("");

  // a new file makes the last check and load stale
  const choose = (set: (f: File | null) => void) => (f: File | null) => { set(f); setCheck(null); setLoaded(null); setError(""); };
  /** Check (writes nothing) or publish the two files; the API's refusal is shown as it worded it. */
  async function send(step: "preview" | "publish") {
    if (!raw || !topline) return;
    setBusy(step); setError("");
    try {
      if (step === "preview") setCheck(await sendSurvey<SurveyCheck>("preview", raw, topline));
      else setLoaded(await sendSurvey<SurveyLoaded>("publish", raw, topline));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  const clean = check && check.problem_count === 0;
  const stage = loaded ? 4 : clean ? 3 : check ? 2 : raw && topline ? 1 : 0;   // stages done

  return <div className="stack" style={{ maxWidth: 1000 }}>
    <div className="page-head"><div>
      <h1>Upload survey</h1>
      <p className="lede">One week of the China Consumer Survey from Baidu QSS: its raw export and Baidu's topline. Every count is
        checked against the topline before anything is loaded.</p>
    </div><span className="chip sig">Admin only</span></div>

    <section className="card">
      <ol className="stages" aria-label="Upload stages">
        {STAGES.map(([name, note], i) => <li key={name} className={i < stage ? "done" : i === stage ? "now" : ""} aria-current={i === stage ? "step" : undefined}>
          <b>{i + 1}. {name}</b><span>{note}</span></li>)}
      </ol>
      <div className="grid g2">
        <FilePick icon={FileSpreadsheet} label="Raw export" hint="Baidu's .csv (or .xlsx), one row per respondent" accept=".csv,.xlsx,.aspx" file={raw} pick={choose(setRaw)} />
        <FilePick icon={FileText} label="Topline" hint="Baidu's Consumer Tracker .xls (or .xlsx)" accept=".xls,.xlsx,.aspx" file={topline} pick={choose(setTopline)} />
      </div>
      <p className="callout"><Info size={16} strokeWidth={1.8} aria-hidden="true" /><span><b>Before publishing.</b> Check counts every answer from the raw rows,
        translates the Chinese through the reviewed codebook, and compares each base and count with Baidu's topline. Nothing is written until every figure matches.</span></p>
      <button className="btn primary" type="button" disabled={!raw || !topline || !!busy} onClick={() => send("preview")}>
        {busy === "preview" ? "Checking…" : "Check the files"}</button>
    </section>

    {error && <p role="alert" className="badge-partial" style={{ display: "block", padding: 12, borderRadius: 8 }}>{error}</p>}

    {loaded && <Card title={`Loaded: week of ${day(loaded.wave)}`} sub={`${count(loaded.respondents)} respondents; ${loaded.matched} figures equal to Baidu's topline. The portal's files are being rebuilt in the background (a few minutes); the wave opens now.`}>
      <Link className="btn primary" to={`/w/${loaded.survey_id}`}>Open the wave</Link>
    </Card>}

    {check && !loaded && <>
      <div className="grid g4">
        {([["Wave (Monday)", day(check.wave)], ["Respondents", count(check.respondents)],
           ["Figures equal to the topline", count(check.matched)], ["Median time taken", check.median_seconds == null ? "–" : `${Math.round(check.median_seconds)} s`]] as const)
          .map(([label, value]) => <div key={label} className="card kpi"><div className="k-label">{label}</div><div className="k-value">{value}</div></div>)}
      </div>
      {clean
        ? <Card title="Every figure matches Baidu's topline" sub={`Answers submitted ${day(check.field_start)} to ${day(check.field_end)}. Publishing the same week again replaces it.`}>
            <button className="btn primary" type="button" disabled={!!busy} onClick={() => send("publish")}>{busy === "publish" ? "Loading…" : "Publish this week"}</button>
          </Card>
        : <Card title={`${check.problem_count} problem${check.problem_count === 1 ? "" : "s"}: nothing can be loaded`}
            sub="A wording missing from config/china_codebook.yml, or a count that differs from the topline (are both files the same week?).">
            <ul>{check.problems.map(p => <li key={p}>{p}</li>)}</ul>
          </Card>}
      <Card title="What would load" sub="Counted from the raw rows, as the portal will show them">
        <div className="table-wrap"><table className="data report-table">
          <thead><tr><th scope="col">Question</th><th scope="col">Answer</th><th scope="col">People</th><th scope="col">%</th></tr></thead>
          <tbody>{check.questions.flatMap(q => q.answers.map(([label, n, pct], i) =>
            <tr key={q.qcode + label}>{i === 0 && <th scope="row" rowSpan={q.answers.length} style={{ maxWidth: 320 }}>
              {q.qcode} · {q.text} <span className="muted">(n = {count(q.base)})</span></th>}
              <td>{label}</td><td>{count(n)}</td><td>{pct.toFixed(1)}</td></tr>))}</tbody>
        </table></div>
      </Card>
    </>}
  </div>;
}
