// App frame: a dark rail with the wave's screens, a top bar with the wave switcher and global question search.
import { useEffect, useRef, useState } from "react";
import { savedTheme, setTheme } from "../theme";
import type { Theme } from "../theme";
import { NavLink, Outlet, useNavigate, useParams } from "react-router";
import { useWaves } from "../api";
import type { Wave } from "../api";
import { fmtDate } from "../stats";

const SCREENS = [
  ["", "Overview", "M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z"],
  ["questions", "Question explorer", "M4 20h4V10H4zm6 0h4V4h-4zm6 0h4v-7h-4z"],
  ["crosstab", "Cross-tab matrix", "M3 3h18v18H3zm2 2v4h4V5zm6 0v4h4V5zm6 0v4h2V5zM5 11v4h4v-4zm6 0v4h4v-4zm6 0v4h2v-4zM5 17v2h4v-2zm6 0v2h4v-2z"],
  ["trends", "Trends", "M3 17l6-6 4 4 8-8v4h2V3h-8v2h4l-6 6-4-4-8 8z"],
  ["changes", "What changed", "M12 2l4 8H8zm0 20l-4-8h8zM2 12l8-4v8zm20 0l-8 4V8z"],
  ["survey", "Survey preview", "M6 2h9l5 5v15H6zm8 1v5h5M9 13h8M9 17h8M9 9h3"],
] as const;

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden><path d={d} fill="currentColor" /></svg>;
}

export default function Shell() {
  const { id } = useParams();
  const [theme, setThemeState] = useState<Theme>(savedTheme);
  const toggle = () => { const next = theme === "dark" ? "light" : "dark"; setTheme(next); setThemeState(next); };
  const waves = useWaves();
  const wave = waves.data?.find(w => String(w.survey_id) === id);
  return <div className="app">
    <a href="#main" className="skip">Skip to content</a>
    <aside className="rail">
      <NavLink to="/" className="brand" aria-label="Consumer Insight Portal home">
        <span className="mark" aria-hidden>C</span>
        <span><b>Coresight</b><small>Consumer Insight Portal</small></span>
      </NavLink>
      <nav aria-label="Library">
        <NavLink to="/" end><Icon d="M4 4h6v16H4zm8 0h8v4h-8zm0 6h8v10h-8z" />Survey library</NavLink>
        <NavLink to="/search"><Icon d="M10 3a7 7 0 015.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1110 3zm0 2a5 5 0 100 10 5 5 0 000-10z" />Search questions</NavLink>
      </nav>
      {wave && <nav aria-label="This wave">
        <p className="rail-label">{wave.survey_family === "CSI-US" ? "Weekly tracker" : "Survey"} · {fmtDate(wave.wave_date)}</p>
        {SCREENS.map(([path, label, d]) =>
          <NavLink key={path} to={`/w/${wave.survey_id}${path ? "/" + path : ""}`} end={!path}><Icon d={d} />{label}</NavLink>)}
      </nav>}
      {wave && <div className="rail-foot"><b>{wave.qualified_n.toLocaleString("en-US")}</b><span>qualified respondents</span></div>}
    </aside>
    <div className="main-col">
      <TopBar waves={waves.data ?? []} wave={wave} theme={theme} onTheme={toggle} />
      {/* keyed on the theme: charts rebuild with the new palette, data stays cached */}
      <main id="main" tabIndex={-1} key={theme}><Outlet /></main>
    </div>
  </div>;
}

function TopBar({ waves, wave, theme, onTheme }: { waves: Wave[]; wave?: Wave; theme: Theme; onTheme: () => void }) {
  const navigate = useNavigate();
  const search = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); search.current?.focus(); } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const family = wave ? waves.filter(w => w.survey_family === wave.survey_family && w.study_type === wave.study_type
                                     && (w.rows_built !== 0 || w.survey_id === wave.survey_id)) : [];
  const at = family.findIndex(w => w.survey_id === wave?.survey_id);   // newest first
  const go = (w?: Wave) => w && navigate(location.pathname.replace(/^\/w\/\d+/, `/w/${w.survey_id}`));
  return <header className="topbar">
    {wave ? <div className="switcher">
      <button className="icon-btn" disabled={at >= family.length - 1} onClick={() => go(family[at + 1])} aria-label="Previous wave">‹</button>
      <label className="sr-only" htmlFor="wave-pick">Wave</label>
      <select id="wave-pick" value={wave.survey_id} onChange={e => go(family.find(w => w.survey_id === Number(e.target.value)))}>
        {family.map(w => <option key={w.survey_id} value={w.survey_id}>{fmtDate(w.wave_date)} · n={w.qualified_n}</option>)}
      </select>
      <button className="icon-btn" disabled={at <= 0} onClick={() => go(family[at - 1])} aria-label="Next wave">›</button>
      <span className="context" title={wave.title}>{wave.title}</span>
    </div> : <div className="switcher">{waves.length > 0 && <span className="context">{waves.length.toLocaleString("en-US")} surveys and waves, {waves.at(-1)!.wave_date.slice(0, 4)}–{waves[0].wave_date.slice(0, 4)}</span>}</div>}
    <form role="search" onSubmit={e => { e.preventDefault(); if (text.trim()) navigate(`/search?q=${encodeURIComponent(text.trim())}`); }}>
      <label className="sr-only" htmlFor="global-search">Search every question</label>
      <input id="global-search" ref={search} value={text} onChange={e => setText(e.target.value)} placeholder="Search every question…" />
      <kbd aria-hidden>⌘K</kbd>
    </form>
    <button className="theme-btn" onClick={onTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title={`${theme === "dark" ? "Light" : "Dark"} theme`}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden><path fill="currentColor" d={theme === "dark"
        ? "M12 7a5 5 0 110 10 5 5 0 010-10zm0-5l1 3h-2zm0 20l-1-3h2zM2 12l3-1v2zm20 0l-3 1v-2zM4.9 4.9l2.8 1.4-1.4 1.4zm14.2 14.2l-2.8-1.4 1.4-1.4zM4.9 19.1l1.4-2.8 1.4 1.4zM19.1 4.9l-1.4 2.8-1.4-1.4z"
        : "M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"} /></svg>
    </button>
  </header>;
}
