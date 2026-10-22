// App frame: a dark rail with the wave's screens, a top bar with the wave switcher and global question search.
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { savedTheme, setTheme } from "../theme";
import type { Theme } from "../theme";
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router";
import { useWaves } from "../api";
import PinDialog from "./PinDialog";
import type { Wave } from "../api";
import { fmtDate } from "../stats";
import { perf } from "../perf";
import { isSaved, removeView, saveView } from "../saved";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

// The perf badge is the developer's: shown only in a browser that opened the portal once with ?perf=1 (?perf=0 hides it again)
const PerfHUD = lazy(() => import("./PerfHUD"));
const showPerf = (() => {
  try {
    const flag = new URLSearchParams(location.search).get("perf");
    if (flag !== null) localStorage.setItem("cip_perf", flag);
    return localStorage.getItem("cip_perf") === "1";
  } catch { return false; }
})();

const SCREENS = [
  ["", "Overview", "M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z"],
  ["questions", "Question explorer", "M4 20h4V10H4zm6 0h4V4h-4zm6 0h4v-7h-4z"],
  ["crosstab", "Cross-tab matrix", "M3 3h18v18H3zm2 2v4h4V5zm6 0v4h4V5zm6 0v4h2V5zM5 11v4h4v-4zm6 0v4h4v-4zm6 0v4h2v-4zM5 17v2h4v-2zm6 0v2h4v-2z"],
  ["trends", "Trends", "M3 17l6-6 4 4 8-8v4h2V3h-8v2h4l-6 6-4-4-8 8z"],
  ["compare", "Compare waves", "M3 5h4v14H3zm7 4h4v10h-4zm7-6h4v16h-4z"],
  ["audience", "Audiences", "M9 11a4 4 0 110-8 4 4 0 010 8zm7 1a3 3 0 110-6 3 3 0 010 6zM2 20c0-3.3 3.1-6 7-6s7 2.7 7 6zm15 0c0-2-.8-3.7-2-5 3 .1 5 2.2 5 5z"],
  ["changes", "What changed", "M12 2l4 8H8zm0 20l-4-8h8zM2 12l8-4v8zm20 0l-8 4V8z"],
  ["survey", "Survey preview", "M6 2h9l5 5v15H6zm8 1v5h5M9 13h8M9 17h8M9 9h3"],
] as const;

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d={d} fill="currentColor" /></svg>;
}

export default function Shell() {
  const { id } = useParams();
  const location = useLocation();
  const [theme, setThemeState] = useState<Theme>(savedTheme);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const toggleTheme = () => { const next = theme === "dark" ? "light" : "dark"; setTheme(next); setThemeState(next); };
  const waves = useWaves();
  const wave = waves.data?.find(w => String(w.survey_id) === id);

  // Track page transitions end-to-end and close mobile drawer
  useEffect(() => {
    perf.startPageTransition(location.pathname + location.search);
    setMobileMenuOpen(false);
  }, [location.pathname, location.search]);

  return <div className={`app ${mobileMenuOpen ? "mobile-nav-open" : ""}`}>
    <a href="#main" className="skip">Skip to content</a>
    {mobileMenuOpen && <div className="rail-backdrop" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />}
    <aside className={`rail ${mobileMenuOpen ? "open" : ""}`} aria-label="Portal Navigation">
      <NavLink to="/" className="brand" aria-label="Consumer Insight Portal home">
        <img src="/coresight-logo-reversed.png" alt="Coresight Research" width="150" height="74" />
        <small>Consumer Insight Portal</small>
      </NavLink>
      <nav aria-label="Library">
        <NavLink to="/" end><Icon d="M4 4h6v16H4zm8 0h8v4h-8zm0 6h8v10h-8z" />Survey library</NavLink>
        <NavLink to="/search"><Icon d="M10 3a7 7 0 015.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1110 3zm0 2a5 5 0 100 10 5 5 0 000-10z" />Search questions</NavLink>
        <NavLink to="/schedule"><Icon d="M7 2v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-2V2h-2v2H9V2zm-2 8h14v10H5zm2 2v2h2v-2zm4 0v2h2v-2zm4 0v2h2v-2z" />Launch schedule</NavLink>
        <NavLink to="/ask"><Icon d="M4 4h16v12H8l-4 4zm4 5v2h2V9zm4 0v2h2V9zm4 0v2h2V9z" />Ask CIP</NavLink>
        <NavLink to="/boards"><Icon d="M16 3l5 5-3 1-4 4 1 5-2 2-4-4-5 5-1-1 5-5-4-4 2-2 5 1 4-4z" />Boards</NavLink>
        <NavLink to="/whats-new"><Icon d="M12 2l2.4 6.9H22l-6 4.4 2.3 7-6.3-4.5L5.7 20.3 8 13.3 2 8.9h7.6z" />What's new</NavLink>
      </nav>
      {wave && <nav aria-label="This wave">
        <p className="rail-label">{wave.survey_family === "CSI-US" ? "Weekly tracker" : "Survey"} · {fmtDate(wave.wave_date)}</p>
        {SCREENS.map(([path, label, d]) =>
          <NavLink key={path} to={`/w/${wave.survey_id}${path ? "/" + path : ""}`} end={!path}><Icon d={d} />{label}</NavLink>)}
      </nav>}
      {wave && <div className="rail-foot">
        <b>{wave.qualified_n.toLocaleString("en-US")}</b>
        <span>qualified respondents</span>
        <div className="rail-foot-tag">
          <span className="badge-verified">✓ Verified Sample</span>
        </div>
      </div>}
    </aside>
    <div className="main-col">
      <TopBar
        waves={waves.data ?? []}
        wave={wave}
        theme={theme}
        onTheme={toggleTheme}
        menuOpen={mobileMenuOpen}
        onToggleMenu={() => setMobileMenuOpen(o => !o)}
      />
      {/* keyed on the theme: charts rebuild with the new palette, data stays cached */}
      <main id="main" tabIndex={-1} key={theme}><Outlet /></main>
      <PinDialog />
      {showPerf && <Suspense fallback={null}><PerfHUD /></Suspense>}
    </div>
  </div>;
}

/** Keep this exact view (wave, screen, question, cut, waves picked) under a name in the Library. */
function SaveButton({ wave }: { wave: Wave }) {
  const location = useLocation();
  const url = location.pathname + location.search;
  const [saved, setSaved] = useState(isSaved(url));
  useEffect(() => setSaved(isSaved(url)), [url]);
  const screen = SCREENS.find(([path]) => path && location.pathname.split("/")[3] === path)?.[1] ?? "Overview";
  const question = decodeURIComponent(location.pathname.split("/")[4] ?? "");
  const toggle = () => {
    if (saved) removeView(url);
    else saveView(url, `${screen}${question ? ` · ${question}` : ""} · ${wave.title} (${fmtDate(wave.wave_date)})`);
    setSaved(!saved);
  };
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            className="save-btn"
            onClick={toggle}
            aria-pressed={saved}
            aria-label={saved ? "Remove saved view" : "Save this view"}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d={
                  saved
                    ? "M6 2h12a1 1 0 011 1v19l-7-4-7 4V3a1 1 0 011-1z"
                    : "M6 2h12a1 1 0 011 1v19l-7-4-7 4V3a1 1 0 011-1zm1 2v14.5l5-2.9 5 2.9V4z"
                }
              />
            </svg>
          </button>
        }
      />
      <TooltipContent side="bottom">
        {saved ? "Saved in your Library: click to remove" : "Save this view to your Library"}
      </TooltipContent>
    </Tooltip>
  );
}

function TopBar({
  waves,
  wave,
  theme,
  onTheme,
  menuOpen,
  onToggleMenu
}: {
  waves: Wave[];
  wave?: Wave;
  theme: Theme;
  onTheme: () => void;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  const navigate = useNavigate();
  const search = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const family = wave ? waves.filter(w => w.survey_family === wave.survey_family && w.study_type === wave.study_type
                                     && (w.rows_built !== 0 || w.survey_id === wave.survey_id)) : [];
  const at = family.findIndex(w => w.survey_id === wave?.survey_id);   // newest first
  const go = (w?: Wave) => w && navigate(location.pathname.replace(/^\/w\/\d+/, `/w/${w.survey_id}`));

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        search.current?.focus();
        return;
      }
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || (e.target as HTMLElement)?.isContentEditable) return;
      if (e.key === "[" && at < family.length - 1) {
        e.preventDefault();
        go(family[at + 1]);
      } else if (e.key === "]" && at > 0) {
        e.preventDefault();
        go(family[at - 1]);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [at, family]);
  return <header className="topbar">
    <button
      className="mobile-menu-btn icon-btn"
      onClick={onToggleMenu}
      aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
      aria-expanded={menuOpen}
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d={menuOpen ? "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" : "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"} fill="currentColor" />
      </svg>
    </button>
    {wave ? <div className="switcher">
      <Tooltip>
        <TooltipTrigger
          render={
            <button
              className="icon-btn"
              disabled={at >= family.length - 1}
              onClick={() => go(family[at + 1])}
              aria-label="Previous survey wave"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z" fill="currentColor"/></svg>
            </button>
          }
        />
        <TooltipContent side="bottom">
          {at >= family.length - 1 ? "Earliest wave loaded" : "Previous wave (shortcut: [)"}
        </TooltipContent>
      </Tooltip>
      <label className="sr-only" htmlFor="wave-pick">Wave</label>
      <select id="wave-pick" value={wave.survey_id} onChange={e => go(family.find(w => w.survey_id === Number(e.target.value)))}>
        {family.map(w => <option key={w.survey_id} value={w.survey_id}>{fmtDate(w.wave_date)} · n={w.qualified_n.toLocaleString("en-US")}</option>)}
      </select>
      <Tooltip>
        <TooltipTrigger
          render={
            <button
              className="icon-btn"
              disabled={at <= 0}
              onClick={() => go(family[at - 1])}
              aria-label="Next survey wave"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" fill="currentColor"/></svg>
            </button>
          }
        />
        <TooltipContent side="bottom">
          {at <= 0 ? "Latest wave" : "Next wave (shortcut: ])"}
        </TooltipContent>
      </Tooltip>
      <span className="context" title={wave.title}>{wave.title}</span>
    </div> : <div className="switcher">{waves.length > 0 && <span className="context">{waves.length.toLocaleString("en-US")} surveys and waves, {waves.at(-1)!.wave_date.slice(0, 4)}–{waves[0].wave_date.slice(0, 4)}</span>}</div>}
    <form className="topbar-search-form" role="search" onSubmit={e => { e.preventDefault(); if (text.trim()) navigate(`/search?q=${encodeURIComponent(text.trim())}`); }}>
      <label className="sr-only" htmlFor="global-search">Search every question</label>
      <span className="search-icon-prefix" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="15" height="15"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor" /></svg>
      </span>
      <input
        id="global-search"
        ref={search}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === "Escape") { e.currentTarget.blur(); setText(""); } }}
        placeholder="Search every question…"
      />
      {text && (
        <button
          type="button"
          onClick={() => { setText(""); search.current?.focus(); }}
          aria-label="Clear search input"
          className="topbar-search-clear"
        >
          ✕
        </button>
      )}
      <kbd aria-hidden="true">⌘K</kbd>
    </form>
    {wave && <SaveButton wave={wave} />}
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            className="theme-btn"
            onClick={onTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d={
                  theme === "dark"
                    ? "M12 7a5 5 0 110 10 5 5 0 010-10zm0-5l1 3h-2zm0 20l-1-3h2zM2 12l3-1v2zm20 0l-3 1v-2zM4.9 4.9l2.8 1.4-1.4 1.4zm14.2 14.2l-2.8-1.4 1.4-1.4zM4.9 19.1l1.4-2.8 1.4 1.4zM19.1 4.9l-1.4 2.8-1.4-1.4z"
                    : "M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"
                }
              />
            </svg>
          </button>
        }
      />
      <TooltipContent side="bottom">
        {theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      </TooltipContent>
    </Tooltip>
  </header>;
}
