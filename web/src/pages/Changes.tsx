// Every answer of the wave against last week or the same week last year, most significant first.
import CountUp from "../components/CountUp";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useBook } from "../api";
import { Card, Failure, Loading, ExportButtons } from "../components/bits";
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
  const dir = params.get("dir") ?? "all";
  const section = params.get("section") ?? "all";
  const profile = params.get("profile") === "1";
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v ? p.set(k, v) : p.delete(k); setParams(p, { replace: true }); };
  const key = against === "ly" ? "dLy" : "d";
  const comparableMoves = all.filter(m => m[key] != null && (profile || !isProfile(m)));
  const sigMoves = comparableMoves.filter(m => against === "ly" ? m.sigLy : m.sig);
  const rows = comparableMoves
    .filter(m => (!onlySig || (against === "ly" ? m.sigLy : m.sig)) && (section === "all" || m.q.section === section)
      && (dir === "all" || (dir === "up" ? m[key]! > 0 : m[key]! < 0)))
    .sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
  
  // asked of a different group than then: not a comparable move, so never the headline (the test leaves it out too)
  const testable = comparableMoves.filter(m => !m.r.flags.includes(against === "ly" ? "base_changed_ly" : "base_changed_prior"));
  const gainers = testable.filter(m => m[key]! > 0).sort((a, b) => b[key]! - a[key]!);
  const decliners = testable.filter(m => m[key]! < 0).sort((a, b) => a[key]! - b[key]!);
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
      <h1>{rows.length} {onlySig ? "significant " : ""}changes against {against === "ly" ? "the same week last year" : "last week"}</h1>
      <p className="lede">Wave of {fmtDate(book.wave.wave_date)} · Every answer of every question, tested with a two-proportion z-test and kept as significant only if it survives the Benjamini–Hochberg correction across the whole wave (5 % false discoveries), so chance moves are not reported as news. Answers whose question was asked of a different group than last week ({routing}) are left out of the test rather than shown as a false move.</p>
    </div></div>

    <div className="grid g4" style={{ marginBottom: 18 }}>
      <div className="card kpi lead">
        <div className="k-label">Significant shifts</div>
        <div className="k-value"><CountUp text={String(sigMoves.length)} /></div>
        <div className="k-note">of {comparableMoves.length} answers evaluated (95 % conf.)</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Largest increase</div>
        <div className="k-value" style={{ color: "var(--sig)" }}><CountUp text={topGainer ? `+${topGainer[key]!.toFixed(1)} pts` : "—"} /></div>
        <div className="k-note clamp"><b>{topGainer ? topGainer.label : "None"}</b>{topGainer ? ` · now ${pct(topGainer.now)}` : ""}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Largest decrease</div>
        <div className="k-value" style={{ color: "var(--blue)" }}><CountUp text={topDecliner ? `${topDecliner[key]!.toFixed(1)} pts` : "—"} /></div>
        <div className="k-note clamp"><b>{topDecliner ? topDecliner.label : "None"}</b>{topDecliner ? ` · now ${pct(topDecliner.now)}` : ""}</div>
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
            <TabsTrigger value="prior">vs last week</TabsTrigger>
            <TabsTrigger value="ly" disabled={noLy} title={noLy ? "Last year's week is not loaded" : undefined}>
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
        <label className="check" title="Age, gender, income, relationship… shift with each week's sample: context, not news">
          <input type="checkbox" checked={profile} onChange={e => set("profile", e.target.checked ? "1" : "")} /> Include respondent demographics</label>
        <select aria-label="Filter by survey section" value={section} onChange={e => set("section", e.target.value === "all" ? "" : e.target.value)}>
          <option value="all">All sections ({sections.length})</option>{sections.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span style={{ flex: 1 }} />
        <ExportButtons onExport={format => downloadTable(format, `changes-${book.wave.wave_date}`, ["Code", "Question", "Answer", "Now %", "Then %", "Change pts", "Significant"],
          rows.map(m => [m.q.id, m.q.text, m.label, m.now, against === "ly" ? m.ly : m.prior, m[key]?.toFixed(1), (against === "ly" ? m.sigLy : m.sig) ? "yes" : "no"]),
          [`${book.wave.title}, wave of ${fmtDate(book.wave.wave_date)}`, `Compared against ${against === "ly" ? "the same week last year" : "last week"}`])} />
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
                <th className="num" style={{ width: 100 }}>{against === "ly" ? "Last year" : "Last week"}</th>
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
