// One question at a time: wording, base, top answer, any chart type that suits it, by Total or a cut.
import { useMemo, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { allowed as hasFeature, COLUMNS, isFiller, present, useBook, useMe } from "../api";
import type { Column } from "../api";
import { BaseNote, Card, Change, compared, copyLink, Empty, Failure, IconLink, Menu, SkeletonScreen, SourceLine, sourceText, ExportButtons , QuestionCode } from "../components/bits";
import { moveOf } from "../moves";
import type { Chart } from "../components/EChart";
import QuestionChart, { sharesOfMentions, VIEWS } from "../components/QuestionChart";
import type { View } from "../components/QuestionChart";
import QuestionNav from "../components/QuestionNav";
import QuestionHeader from "../components/QuestionHeader";
import QuestionTabs from "../components/QuestionTabs";
import AlertMe from "../components/AlertMe";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { fmtDate, HIDDEN_BASE, pct, SMALL_BASE } from "../stats";
import { perf } from "../perf";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const CUTS: { key: string; label: string; cols: Column[] }[] = [
  { key: "total", label: "Total", cols: ["Total"] },
  { key: "gender", label: "Gender", cols: ["Total", "Male", "Female"] },
  { key: "generation", label: "Generation", cols: ["Total", "Gen Z", "Millennial", "Gen X", "Boomer"] },
  { key: "all", label: "All", cols: COLUMNS },
];

export default function Explorer() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: book, isLoading, error } = useBook(id);
  const me = useMe().data;
  const chart = useRef<Chart | null>(null);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  if (isLoading) return <SkeletonScreen kind="question" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  // every question offers all five views (bars, columns, stacked, donut, table); a hand-edited ?view= falls back to bars
  const view = (VIEWS.some(v => v.key === params.get("view")) ? params.get("view") : "bars") as View;
  const shown = present(book.n);   // cuts with respondents in this wave
  const cuts = CUTS.map(c => ({ ...c, cols: c.cols.filter(col => shown.includes(col)) })).filter(c => c.key === "total" || c.cols.length > 1);
  const cut = cuts.find(c => c.key === params.get("cut")) ?? cuts[0];
  const group = Math.max(0, Math.min(Math.trunc(Number(params.get("row") ?? 0)) || 0, question.groups.length - 1));   // a hand-edited ?row= never breaks the page
  const set = (k: string, v: string) => {
    perf.startFilterChange(k, v);
    const p = new URLSearchParams(params);
    p.set(k, v);
    setParams(p, { replace: true });
  };
  const sort = params.get("sort") !== "0";   // in the link, so a shared view keeps its order
  const g = question.groups[group];
  const top = [...g.rows].filter(r => !isFiller(r.label) && r.Total != null).sort((a, b) => (b.Total ?? 0) - (a.Total ?? 0))[0];
  const small = cut.cols.filter(c => (g.bases[c] ?? 0) < SMALL_BASE);
  const wave = fmtDate(book.wave.wave_date);
  const vs = compared(book.wave);   // annual and ad hoc studies compare with their previous wave, not last week
  const bases = cut.cols.map(c => `${c} n=${g.bases[c] ?? 0}`).join(", ");
  const exportAs = (format: Format) => downloadTable(format, `${question.number}-${book.wave.wave_date}`, ["Answer", ...cut.cols.map(c => `${c} %`), `${vs.Prior} %`],
    g.rows.map(r => [r.label, ...cut.cols.map(c => r[c]), r.prior]),
    [`${question.number}: ${question.text}`, `${book.wave.title}, wave of ${wave}`, `Base: ${bases}`, sourceText(book.wave, wave, bases)]);
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/questions/${encodeURIComponent(q.id)}?${params}`)} />
    <div className="stack">
      <Card>
        <QuestionHeader waveId={id} question={question} questions={book.questions} open={q => navigate(`/w/${id}/questions/${encodeURIComponent(q.id)}?${params}`)} />
        <div className="qhead"><QuestionCode q={question} /><span>{question.section}</span><span>· {question.type.replace("_", " ")}</span><BaseNote base={g.base} /></div>
        <h1 className="qtext">{question.text}</h1>
        {question.base_desc ? <p className="muted" style={{ margin: "0 0 6px" }}>Asked of: {question.base_desc}</p>
          : g.base < book.n.Total && <p className="muted" style={{ margin: "0 0 6px" }}>Asked of {g.base.toLocaleString("en-US")} of the wave's {book.n.Total.toLocaleString("en-US")} respondents; the rest were routed past it. Percentages use these {g.base.toLocaleString("en-US")}.</p>}
        {top && <p className="top-answer">Top answer{g.label ? ` for ${g.label}` : ""}: <b>{top.label}</b> at <em>{pct(top.Total)}</em>{" "}
          <Change now={top.Total ?? undefined} before={top.prior} label={`vs ${vs.prior}`} routing={top.flags.includes("base_changed_prior")} move={moveOf(top)} /></p>}
        <QuestionTabs id={id} q={question.id} />
      </Card>
      <Card>
        <div className="toolbar one-row">
          <Tabs value={view} onValueChange={v => set("view", v)}>
            <TabsList>
              {VIEWS.map(v => (
                <TabsTrigger key={v.key} value={v.key}>{v.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          {view !== "donut" && view !== "stacked" && (
            <Tabs value={cut.key} onValueChange={k => set("cut", k)}>
              <TabsList>
                {cuts.map(c => (
                  <TabsTrigger key={c.key} value={c.key}>{c.label}</TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}
          {question.groups.length > 1 && view !== "stacked" && <select aria-label="Grid row" value={group} onChange={e => set("row", e.target.value)}>
            {question.groups.map((x, i) => <option key={x.label} value={i}>{x.label}</option>)}
          </select>}
          <span className="toolbar-gap" />
          <ExportButtons onExport={exportAs} png={view === "table" ? undefined : () => chart.current && import("../components/EChart").then(m => m.downloadPng(chart.current!, `${question.number}: ${question.text}`,
            sourceText(book.wave, wave, `base n=${g.base}`), `${question.number}-${book.wave.wave_date}`))} />
          <Menu label="" icon={<span aria-hidden>⋯</span>} keep>
            <label className="check"><input type="checkbox" checked={sort} onChange={e => { const p = new URLSearchParams(params); perf.startFilterChange("sort", String(e.target.checked)); e.target.checked ? p.delete("sort") : p.set("sort", "0"); setParams(p, { replace: true }); }} /> Sort by value</label>
            <button onClick={e => copyLink(e.currentTarget)}><IconLink /> <span>Copy link</span></button>
            {hasFeature(me, "alerts") && <AlertMe surveyId={id} question={question} group={g} />}
          </Menu>
        </div>
        <QuestionChart question={question} group={group} view={view} columns={view === "donut" || view === "stacked" ? ["Total"] : cut.cols} sort={sort} wave={wave} vs={vs.prior}
          onReady={c => { chart.current = c; }} />
        <div className="legend-line">
          {(view === "bars" || view === "columns") && cut.cols.length === 1 && <>
            <span><i style={{ background: "var(--red)" }} />Top answer</span><span><i style={{ background: "var(--bar)" }} />Other answers</span></>}
          <span>Hover or tap any bar for n, base, margin of error and the change vs {vs.prior}; the Table view lists the same figures.</span>
          {(view === "donut" || view === "stacked") && sharesOfMentions(question) &&
            <span>People could pick more than one answer, so the answers add up to more than 100%: each slice is that answer's share of all mentions.</span>}
          {small.length > 0 && <span style={{ color: "var(--warn)" }}>Small base (n&lt;{SMALL_BASE}): {small.join(", ")}, shown faded; under {HIDDEN_BASE} no figure is shown</span>}
        </div>
        <SourceLine wave={wave} base={bases} asked={question.base_desc} from={book.wave} />
      </Card>
    </div>
  </div>;
}
