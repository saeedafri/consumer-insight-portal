// My account (/app/account), opened from the account icon at the top right (components/Shell.tsx AccountMenu): who is
// signed in, what their access includes, their saved items, the new-survey email switch, the questions they asked Ask
// CIP, and the theme.
import { useState } from "react";
import { Link } from "react-router";
import { allowed, queries, send, useAlerts, useAskHistory, useMe, useSurveyEmails, useTeamViews } from "../api";
import ApiKeys from "../components/ApiKeys";
import { Card } from "../components/bits";
import { savedViews } from "../saved";
import { setTheme, useTheme } from "../theme";

const FEATURES: [string, string][] = [["dashboards", "Dashboards"], ["explorer", "Question explorer"], ["crosstab", "Cross-tabs"],
  ["trends", "Trends"], ["search", "Search"], ["ask", "Ask CIP"], ["export", "Export"], ["boards", "Boards"],
  ["audiences", "Audiences"], ["alerts", "Alerts"], ["saved_views", "Saved views"], ["schedule", "Launch schedule"],
  ["weighted", "Weighted figures"], ["api", "API keys and MCP"]];
const ROLES: Record<string, string> = { super_admin: "Super administrator", analyst: "Analyst", client: "Client" };

export default function Account() {
  const me = useMe().data;
  const theme = useTheme();
  const alerts = useAlerts().data ?? [];
  const teamViews = useTeamViews().data ?? [];
  if (!me) return <p className="muted">Loading your account…</p>;
  const name = me.name || me.email.split("@")[0];
  const initials = name.split(/[\s.]+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
  const row = (label: string, value: React.ReactNode) =>
    <div style={{ display: "flex", gap: 16, padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
      <span className="muted" style={{ width: 160, flex: "none" }}>{label}</span><span>{value}</span></div>;
  return <div className="stack" style={{ maxWidth: 760 }}>
    <div className="page-head"><div>
      <p className="eyebrow">My account</p>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 8 }}>
        <span aria-hidden style={{ width: 56, height: 56, borderRadius: "50%", background: "var(--red)", color: "#FFFFFF", display: "grid",
          placeItems: "center", font: "700 20px var(--font-head)" }}>{initials}</span>
        <div><h1 style={{ margin: 0 }}>{name}</h1><p className="muted" style={{ margin: "4px 0 0" }}>{me.email}</p></div>
      </div>
    </div></div>

    <Card title="Your access">
      {row("Role", ROLES[me.role ?? ""] ?? me.role ?? "–")}
      {row("Plan", me.tier ? me.tier[0].toUpperCase() + me.tier.slice(1) : "–")}
      {row("Organisation", me.client ?? "Coresight Research")}
      {row("Can use", <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {FEATURES.filter(([key]) => allowed(me, key)).map(([key, label]) => <span key={key} className="tag">{label}</span>)}</span>)}
    </Card>

    <Card title="Your saved items">
      {row("Saved views", <Link to="/library">{savedViews().length} in the survey library</Link>)}
      {row("Team views", `${teamViews.length} shared with your team`)}
      {row("Alerts", `${alerts.length} watching for changes`)}
      {allowed(me, "alerts") && row("New surveys", <SurveyEmails />)}
      {row("Boards", <Link to="/boards">Open your boards</Link>)}
    </Card>

    {allowed(me, "ask") && <AskHistory />}

    {allowed(me, "api") && <ApiKeys />}

    <Card title="Preferences">
      {row("Theme", <span className="seg" role="group" aria-label="Theme">
        {(["light", "dark"] as const).map(t => <button key={t} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t === "light" ? "Light" : "Dark"}</button>)}</span>)}
    </Card>

    <p><a className="btn" href="/auth/logout" style={{ color: "var(--red-text)", borderColor: "var(--red)" }}>Sign out</a></p>
  </div>;
}

/** "Email me each new survey" (PUT /api/v1/alerts/new-surveys, api/team.py): after each new survey the pipeline's
 * summary goes to this person too, without the team's workbooks (etl/notify.py tell_subscribers). */
function SurveyEmails() {
  const setting = useSurveyEmails();
  const on = setting.data?.subscribed;
  const [note, setNote] = useState("");
  if (setting.isError) return <span className="small muted">Could not read this setting: {(setting.error as Error).message}</span>;
  const flip = (subscribed: boolean) => send<{ subscribed: boolean }>("PUT", "/api/v1/alerts/new-surveys", { subscribed })
    .then(answer => { queries.setQueryData(["survey-emails"], answer); setNote(""); }, e => setNote((e as Error).message));
  return <label style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
    <input type="checkbox" checked={!!on} disabled={on === undefined} onChange={e => void flip(e.target.checked)} />
    Email me each new survey I can open, with its biggest changes{note && <span className="small" role="alert"> · {note}</span>}
  </label>;
}

/** The questions this person asked Ask CIP, newest first (GET /api/v1/ask/history): each opens Ask with it again. */
function AskHistory() {
  const questions = useAskHistory().data?.questions ?? [];
  return <Card title="Your Ask CIP questions">
    {questions.length ? <ol className="stack" style={{ gap: 6, margin: 0, paddingLeft: 20 }}>
      {questions.map(q => <li key={q.question}><Link to={`/ask?q=${encodeURIComponent(q.question)}`}>{q.question}</Link>
        <span className="small muted"> · {new Date(q.asked_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span></li>)}
    </ol> : <p className="muted">Questions you ask in <Link to="/ask">Ask CIP</Link> are listed here.</p>}
  </Card>;
}
