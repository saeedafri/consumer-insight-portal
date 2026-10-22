// A wave at a glance: the biggest significant moves, then one chart per section. Every number is
// computed from the wave, so the page works for any survey, not one written by hand.
import CountUp from "../components/CountUp";
import { useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useBook, useWaves } from "../api";
import type { Question } from "../api";
import { BaseNote, Card, Change, Failure, Loading, SourceLine } from "../components/bits";
import Glance from "../components/Glance";
import QuestionChart from "../components/QuestionChart";
import Profiled from "../components/Profiled";
import { biggest, isProfile, moves } from "../moves";
import { fmtDate, pct, pts } from "../stats";
import { Button, buttonVariants } from "@/components/ui/button";
import { Printer as PrinterIcon } from "lucide-react";

export default function Overview() {
  const id = Number(useParams().id);
  const { data: book, isLoading, error } = useBook(id);
  const waves = useWaves().data ?? [];
  const navigate = useNavigate();
  const all = useMemo(() => (book ? moves(book) : []), [book]);
  if (isLoading) return <Loading what="wave" />;
  if (error || !book) return <Failure error={error} />;
  const w = book.wave;
  const prior = waves.find(x => x.survey_id === w.prior_survey_id);
  const up = biggest(all);
  const lead = up[0];
  const sections = [...new Map(book.questions.map(q => [q.section, q])).values()].sort((a, b) => a.section.localeCompare(b.section));   // sections in alphabetical order
  const firstOf = (q: Question) => q.groups.length > 1 ? "stacked" as const : "bars" as const;
  return <Profiled id="Overview">
    <div className="page-head"><div>
      <h1>{lead ? `${lead.label} ${lead.d! > 0 ? "rose" : "fell"} ${Math.abs(lead.d!).toFixed(1)} points to ${lead.now.toFixed(1)}%`
                : w.prior_survey_id ? "No significant change against last week" : w.title}</h1>
      <p className="lede">Wave of {fmtDate(w.wave_date)} · {w.qualified_n.toLocaleString("en-US")} qualified respondents · {book.questions.length} {book.questions.length === 1 ? "question" : "questions"}. {lead ? <>{lead.q.text} {up.length > 1 && <>· {up.length} answers moved significantly against {prior ? fmtDate(prior.wave_date) : "last week"}.</>}</> : w.title}</p>
    </div>
      <div className="toolbar">
        <Link className={buttonVariants({ variant: "default" })} to={`/w/${id}/questions`}>{book.questions.length === 1 ? "Explore the question" : `Explore all ${book.questions.length} questions`}</Link>
        <Link className={buttonVariants({ variant: "outline" })} to={`/w/${id}/changes`}>What changed</Link>
        <Button variant="outline" onClick={() => window.print()} title="Print briefing or save as PDF">
          <PrinterIcon size={14} />
          Print report
        </Button>
      </div>
    </div>

    <Profiled id="Overview:Glance">
      {(waves.find(x => x.survey_id === id)?.dashboards ?? []).map(code => <Glance key={code} code={code} id={id} />)}
    </Profiled>

    <Profiled id="Overview:Kpis">
      <div className="grid g5" style={{ marginBottom: 16 }}>
        <div className="card kpi lead"><div className="k-label">Qualified respondents</div><div className="k-value"><CountUp text={w.qualified_n.toLocaleString("en-US")} /></div>
          <div className="k-note">{Object.entries(book.n).filter(([k]) => k !== "Total").slice(0, 2).map(([k, v]) => `${k} ${v}`).join(" · ")}</div></div>
        {(up.length ? up : all.filter(m => m.q.type === "single" && !isProfile(m))).filter((m, i, list) =>
          list.findIndex(x => x.q.id === m.q.id) === i).slice(0, 4).map(m =>   // one card per question
          <button key={m.q.id + m.label} className="card kpi" onClick={() => navigate(`/w/${id}/questions/${encodeURIComponent(m.q.id)}`)}>
            <div className="k-label clamp">{m.q.short || m.q.text}</div>
            <div className="k-value"><CountUp text={pct(m.now)} /></div>
            <div className="k-note"><b>{m.label.length > 48 ? m.label.slice(0, 46) + "…" : m.label}</b><br />
              <Change now={m.now} base={m.g.base} before={m.prior} beforeBase={m.r.prior_base} label="vs last week" routing={m.routing} /></div>
          </button>)}
      </div>
    </Profiled>

    <div className="grid g3" style={{ marginBottom: 16 }}>
      <Card className="span2" title="Biggest significant moves this week" sub={prior ? `Against the wave of ${fmtDate(prior.wave_date)} · two-proportion test, Benjamini–Hochberg corrected · routing changes excluded` : "No prior week to compare against"}
            aside={<Link to={`/w/${id}/changes`} className={buttonVariants({ variant: "outline", size: "sm" })}>What changed</Link>}>
        {up.length ? <div className="table-wrap"><table className="data">
          <thead><tr><th>Answer</th><th className="num">Now</th><th className="num">Last week</th><th className="num">Change</th></tr></thead>
          <tbody>{up.slice(0, 8).map(m => <tr key={m.q.id + m.label}>
            <th scope="row"><Link to={`/w/${id}/trends/${encodeURIComponent(m.q.id)}`}>{m.label}</Link><br /><small className="muted">{m.q.id} · {m.q.short || m.q.text}</small></th>
            <td className="num"><b>{pct(m.now)}</b></td><td className="num muted">{pct(m.prior)}</td>
            <td className="num sig">{m.d! > 0 ? "▲" : "▼"} {pts(m.d!).replace(/^[+−]/, "")}</td></tr>)}</tbody>
        </table></div> : <p className="muted">{w.prior_survey_id
          ? `Nothing moved beyond the margin of error. With ${w.qualified_n} respondents each week, a change needs to be about ±${(196 * Math.sqrt(0.5 / Math.max(w.qualified_n, 1))).toFixed(0)} points to count.`
          : "This survey has no earlier wave within 14 days to compare against."}</p>}
      </Card>
      <Card title="Comparisons for this wave">
        <dl className="facts">
          <dt>Last week</dt><dd>{prior ? <Link to={`/w/${prior.survey_id}`}>{fmtDate(prior.wave_date)} · n={prior.qualified_n.toLocaleString("en-US")}</Link> : "none within 14 days"}</dd>
          <dt>Same week last year</dt><dd>{w.ly_status === "loaded" ? "loaded" : w.ly_status === "not_loaded" ? "fielded but not loaded" : "none"}</dd>
          <dt>Significant vs last week</dt><dd>{up.length} answers</dd>
          <dt>Routing changes</dt><dd>{all.filter(m => m.routing).length} answers not comparable</dd>
        </dl>
        <BaseNote base={w.qualified_n} label="wave base" />
      </Card>
    </div>

    <div className="grid g2">
      {sections.map(q => <Card key={q.id} title={<Link to={`/w/${id}/questions/${encodeURIComponent(q.id)}`} style={{ color: "inherit", textDecoration: "none" }}>{q.short || q.text}</Link>}
                              sub={<>{q.section} · {q.id} · {q.type.replace("_", " ")}</>} aside={<BaseNote base={q.groups[0].base} />}>
        <QuestionChart question={{ ...q, groups: q.groups.map(g => ({ ...g, rows: g.rows.slice(0, 10) })) }} view={firstOf(q)} columns={["Total"]} sort wave={fmtDate(w.wave_date)} />
        <SourceLine wave={fmtDate(w.wave_date)} base={`base n=${q.groups[0].base}`} asked={q.base_desc} from={w} />
      </Card>)}
    </div>
  </Profiled>;
}
