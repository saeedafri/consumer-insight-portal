// Every answer of the wave against last week or the same week last year, most significant first.
import CountUp from "../components/CountUp";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useBook } from "../api";
import { Card, compared, Failure, Loading, ExportButtons, sourceText } from "../components/bits";
import { downloadTable } from "../csv";
import { isProfile, moves } from "../moves";
import { fmtDate, pct, pts } from "../stats";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Changes() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const all = useMemo(() => (book ? moves(book) : []), [book]);
  if (isLoading) return <Loading what="changes" />;
  if (error || !book) return <Failure error={error} />;
  const against = params.get("vs") === "ly" ? "ly" : "prior";
  const onlySig = params.get("all") !== "1";
  const dir = ["up", "down"].includes(params.get("dir") ?? "") ? params.get("dir")! : "all";   // a hand-edited link falls back
  const section = book.questions.some(q => q.section === params.get("section")) ? params.get("section")! : "all";
  const vs = compared(book.wave);
  const profile = params.get("profile") === "1";
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v ? p.set(k, v) : p.delete(k); setParams(p, { replace: true }); };
  const key = against === "ly" ? "dLy" : "d";
  const comparableMoves = all.filter(m => m[key] != null && (profile || !isProfile(m)));
  const sigMoves = comparableMoves.filter(m => against === "ly" ? m.sigLy : m.sig);
  const rows = comparableMoves
    .filter(m => (!onlySig || (against === "ly" ? m.sigLy : m.sig)) && (section === "all" || m.q.section === section)
      && (dir === "all" || (dir === "up" ? m[key]! > 0 : m[key]! < 0)))
    .sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
  
  // the headline KPIs come from significant moves only: a big move on a small base is noise, not news
  const tested = all.filter(m => (against === "ly" ? m.testableLy : m.testable)).length;
  const gainers = sigMoves.filter(m => m[key]! > 0).sort((a, b) => b[key]! - a[key]!);
  const decliners = sigMoves.filter(m => m[key]! < 0).sort((a, b) => a[key]! - b[key]!);
  const topGainer = gainers[0];
  const topDecliner = decliners[0];
  
  const sectionCounts = sigMoves.reduce((acc, m) => {
    acc[m.q.section] = (acc[m.q.section] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  const topSection = Object.entries(sectionCounts).sort(([, a], [, b]) => b - a)[0];

  const routing = all.filter(m => m.routing).length;
  const sections = [...new Set(book.questions.map(q => q.section))].sort((a, b) => a.localeCompare(b));
  const noLy = book.wave.ly_status !== "loaded";

  return <>
    <div className="page-head"><div>
      <h1>{rows.length} {onlySig ? "significant " : ""}changes against {against === "ly" ? vs.ly : vs.prior}</h1>
      <p className="lede">Wave of {fmtDate(book.wave.wave_date)} · Every answer of every question with a comparable figure, tested with a two-proportion z-test and kept as significant only if it survives the Benjamini–Hochberg correction across the {tested} answers that could be tested (5 % false discoveries), so chance moves are not reported as news. Answers whose question was asked of a different group than in {vs.prior} ({routing}), and answers with fewer than 30 people on one side are not tested. Respondent demographics are tested but hidden unless asked for: they shift with each week's sample.</p>
    </div></div>

    <div className="grid g4" style={{ marginBottom: 18 }}>
      <div className="card kpi lead">
        <div className="k-label">Significant shifts</div>
        <div className="k-value"><CountUp text={String(sigMoves.length)} /></div>
        <div className="k-note">of {tested} answers tested (Benjamini–Hochberg, 5 %)</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Largest significant increase</div>
        <div className="k-value" style={{ color: topGainer ? "var(--sig)" : undefined }}><CountUp text={topGainer ? `+${topGainer[key]!.toFixed(1)} pts` : "—"} /></div>
        <div className="k-note clamp"><b>{topGainer ? topGainer.label : "No significant increase"}</b>{topGainer ? ` · now ${pct(topGainer.now)}` : ""}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Largest significant decrease</div>
        <div className="k-value" style={{ color: topDecliner ? "var(--blue)" : undefined }}><CountUp text={topDecliner ? `${topDecliner[key]!.toFixed(1)} pts` : "—"} /></div>
        <div className="k-note clamp"><b>{topDecliner ? topDecliner.label : "No significant decrease"}</b>{topDecliner ? ` · now ${pct(topDecliner.now)}` : ""}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Most active section</div>
        <div className="k-value" style={{ fontSize: 24 }}>{topSection ? `${topSection[1]} moves` : "Stable"}</div>
        <div className="k-note clamp"><b>{topSection ? topSection[0] : "All sections steady"}</b></div>
      </div>
    </div>

    <Card>
      <div className="toolbar" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Tabs value={against} onValueChange={v => set("vs", v === "ly" ? "ly" : "")}>
          <TabsList>
            <TabsTrigger value="prior">vs {vs.prior}</TabsTrigger>
            <TabsTrigger value="ly" disabled={noLy} aria-label={noLy ? "vs last year: last year's wave is not loaded" : undefined}>
              vs last year{noLy ? " (not loaded)" : ""}
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <Tabs value={dir} onValueChange={d => set("dir", d === "all" ? "" : d)}>
          <TabsList>
            <TabsTrigger value="all">All shifts</TabsTrigger>
            <TabsTrigger value="up">▲ Gainers</TabsTrigger>
            <TabsTrigger value="down">▼ Decliners</TabsTrigger>
          </TabsList>
        </Tabs>
        <label className="check"><input type="checkbox" checked={onlySig} onChange={e => set("all", e.target.checked ? "" : "1")} /> Significant only</label>
        <label className="check">
          <input type="checkbox" checked={profile} onChange={e => set("profile", e.target.checked ? "1" : "")} /> Include respondent demographics
          <small className="muted">(they shift with each week's sample: context, not news)</small></label>
        <select aria-label="Filter by survey section" value={section} onChange={e => set("section", e.target.value === "all" ? "" : e.target.value)}>
          <option value="all">All sections ({sections.length})</option>{sections.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span style={{ flex: 1 }} />
        <ExportButtons onExport={format => downloadTable(format, `changes-${book.wave.wave_date}`, ["Code", "Question", "Answer", "Now %", "Then %", "Change pts", "Significant"],
          rows.map(m => [m.q.id, m.q.text, m.label, m.now, against === "ly" ? m.ly : m.prior, m[key]?.toFixed(1), (against === "ly" ? m.sigLy : m.sig) ? "yes" : "no"]),
          [`${book.wave.title}, wave of ${fmtDate(book.wave.wave_date)}`, `Compared against ${against === "ly" ? vs.ly : vs.prior}`,
           `Significant = survives Benjamini–Hochberg (5 %) over the ${tested} answers tested`, sourceText(book.wave, fmtDate(book.wave.wave_date), `n=${book.wave.qualified_n}`)])} />
      </div>
      {rows.length === 0 ? (
        <div style={{ textAlign: "center", padding: "36px 16px" }}>
          <p className="muted" style={{ margin: "0 0 12px" }}>No changes match these filters{onlySig ? ". Uncheck “Significant only” or select all shifts to view movements." : "."}</p>
          <Button variant="outline" size="sm" onClick={() => setParams({})}>Reset all filters</Button>
        </div>
      ) : (
        <>
          <div className="table-wrap"><table className="data">
            <thead>
              <tr>
                <th style={{ minWidth: 180 }}>Answer</th>
                <th style={{ minWidth: 260 }}>Question</th>
                <th className="num" style={{ width: 85 }}>Now</th>
                <th className="num" style={{ width: 100 }}>{against === "ly" ? "Last year" : vs.Prior}</th>
                <th className="num" style={{ width: 90 }}>Change</th>
                <th style={{ width: 170, textAlign: "center" }}>
                  <span>Size of change</span>
                  <small style={{ fontSize: 10, color: "var(--head-sub)", display: "block" }}>◄ Negative · Positive ►</small>
                </th>
              </tr>
            </thead>
            <tbody>{rows.slice(0, 300).map(m => {
              const d = m[key]!, sig = against === "ly" ? m.sigLy : m.sig;
              const qText = m.q.short || m.q.text;
              return <tr key={m.q.id + m.label}>
                <th scope="row">{m.label}</th>
                <td><Link to={`/w/${id}/trends/${encodeURIComponent(m.q.id)}`}><code style={{ color: "var(--ink)", fontWeight: 700 }}>{m.q.id}</code></Link> <span className="muted">{qText.length > 88 ? qText.slice(0, 86) + "…" : qText}</span></td>
                <td className="num"><b>{pct(m.now)}</b></td>
                <td className="num muted">{pct(against === "ly" ? m.ly : m.prior)}</td>
                <td className={`num ${sig ? "sig" : "muted"}`}>{pts(d)}</td>
                <td><div className="bar-delta" aria-hidden><span style={{ [d > 0 ? "left" : "right"]: "50%", width: `${Math.min(50, Math.abs(d) * 2)}%`, background: sig ? "var(--red)" : "var(--silver)" }} /></div></td>
              </tr>;
            })}</tbody>
          </table></div>
          {rows.length > 300 && <p className="muted" style={{ marginTop: 10 }}>Showing the 300 largest of {rows.length}. Download the CSV for all.</p>}
        </>
      )}
    </Card>
  </>;
}
