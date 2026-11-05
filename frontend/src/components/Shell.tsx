// App frame: the coresight.com header (logo, site links, search, theme, sign-in), a dark rail with the wave's screens,
// a wave bar with the wave switcher, and the coresight.com footer.
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { setTheme, useTheme } from "../theme";
import { setWeighted, useWeighted } from "../weight";
import type { Theme } from "../theme";
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router";
import { allowed, useMe, useWaves } from "../api";
import PinDialog from "./PinDialog";
import { UndoBar } from "./bits";
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

// [path, label, icon]; FEATURE names the /me feature a screen needs (config/access.yml): unlisted screens always show
const FEATURE: Record<string, string> = { questions: "explorer", crosstab: "crosstab", trends: "trends", compare: "trends", audience: "audiences" };
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

// coresight.com links, as on its own header and footer (checked live 23 Oct 2026); same tab, like any site link
const SITE = "https://coresight.com";
const SITE_LINKS = [["/research/", "Research & Data"], ["/events/", "Events"], ["/memberships/", "Services"], ["/about-us/", "About"]] as const;
const FOOT_LINKS = [
  ["Services", [["/memberships/", "Research & Data Memberships"], ["/innovator-services/", "Innovator Market Development"],
                ["/custom-research-advisory-services/", "Advisory & Custom Research"], ["/coresight-ai-council/", "AI Council"]]],
  ["Get in touch", [["/about-us/contact/", "Contact Us"], ["https://5jdoa.share.hsforms.com/2OopvqR9nRLa_8920kgYvaQ", "Media Inquiries"]]],
  ["Quick links", [["/research/", "All Research"], ["/events/", "Events"], ["/newsroom/", "Newsroom"], ["/retailistic-podcast/", "The Retaili$tic Podcast"]]],
] as const;
const LEGAL = [["/terms-of-service/", "Terms of Use"], ["/privacy-policy/", "Privacy Policy"],
               ["/coresight-research-responsible-vulnerability-disclosure-policy/", "Vulnerability Disclosure Policy"]] as const;
const siteUrl = (path: string) => path.startsWith("http") ? path : SITE + path;

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d={d} fill="currentColor" /></svg>;
}

export default function Shell() {
  const { id } = useParams();
  const location = useLocation();
  const theme = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const waves = useWaves();
  const me = useMe().data;
  const wave = waves.data?.find(w => String(w.survey_id) === id);
  const rail = useRef<HTMLElement>(null);

  // Track page transitions end-to-end and close mobile drawer
  useEffect(() => {
    perf.startPageTransition(location.pathname + location.search);
    setMobileMenuOpen(false);
  }, [location.pathname, location.search]);

  // the phone drawer is modal: focus moves in, Tab stays inside, Escape closes it, focus returns to the menu button
  useEffect(() => {
    if (!mobileMenuOpen || !rail.current) return;
    const drawer = rail.current, opener = document.activeElement as HTMLElement | null;
    const items = () => [...drawer.querySelectorAll<HTMLElement>("a[href], button:not([disabled])")];
    items()[0]?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMobileMenuOpen(false); return; }
      if (e.key !== "Tab") return;
      const list = items(), first = list[0], last = list.at(-1);
      if (!drawer.contains(document.activeElement) || (e.shiftKey ? document.activeElement === first : document.activeElement === last)) {
        e.preventDefault(); (e.shiftKey ? last : first)?.focus();
      }
    };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); opener?.focus(); };
  }, [mobileMenuOpen]);

  return <div className={`app ${mobileMenuOpen ? "mobile-nav-open" : ""}`}>
    <a href="#main" className="skip">Skip to content</a>
    <SiteHeader theme={theme} onTheme={toggleTheme} menuOpen={mobileMenuOpen} onToggleMenu={() => setMobileMenuOpen(o => !o)} />
    {mobileMenuOpen && <div className="rail-backdrop" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />}
    <aside ref={rail} className={`rail ${mobileMenuOpen ? "open" : ""}`} aria-label="Portal Navigation"
           {...(mobileMenuOpen ? { role: "dialog", "aria-modal": true } : {})}>
      <nav aria-label="Library">
        <NavLink to="/" end><Icon d="M4 4h6v16H4zm8 0h8v4h-8zm0 6h8v10h-8z" />Survey library</NavLink>
        {allowed(me, "search") && <NavLink to="/search"><Icon d="M10 3a7 7 0 015.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1110 3zm0 2a5 5 0 100 10 5 5 0 000-10z" />Search questions</NavLink>}
        {allowed(me, "schedule") && <NavLink to="/schedule"><Icon d="M7 2v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-2V2h-2v2H9V2zm-2 8h14v10H5zm2 2v2h2v-2zm4 0v2h2v-2zm4 0v2h2v-2z" />Launch schedule</NavLink>}
        {allowed(me, "ask") && <NavLink to="/ask"><Icon d="M4 4h16v12H8l-4 4zm4 5v2h2V9zm4 0v2h2V9zm4 0v2h2V9z" />Ask CIP</NavLink>}
        {allowed(me, "boards") && <NavLink to="/boards"><Icon d="M16 3l5 5-3 1-4 4 1 5-2 2-4-4-5 5-1-1 5-5-4-4 2-2 5 1 4-4z" />Boards</NavLink>}
        <NavLink to="/methodology"><Icon d="M12 2a10 10 0 110 20 10 10 0 010-20zm-1 15h2v-6h-2zm0-8h2V7h-2z" />Methodology</NavLink>
        <NavLink to="/whats-new"><Icon d="M12 2l2.4 6.9H22l-6 4.4 2.3 7-6.3-4.5L5.7 20.3 8 13.3 2 8.9h7.6z" />What's new</NavLink>
      </nav>
      {wave && <nav aria-label="This wave">
        <p className="rail-label">{wave.survey_family === "CSI-US" ? "Weekly tracker" : "Survey"} · {fmtDate(wave.wave_date)}</p>
        {SCREENS.filter(([path]) => !FEATURE[path] || allowed(me, FEATURE[path])).map(([path, label, d]) =>
          <NavLink key={path} to={`/w/${wave.survey_id}${path ? "/" + path : ""}`} end={!path}><Icon d={d} />{label}</NavLink>)}
      </nav>}
      {wave && <div className="rail-foot">
        <b>{wave.qualified_n.toLocaleString("en-US")}</b>
        <span>qualified respondents</span>
        {(wave.verified || wave.in_field) && <div className="rail-foot-tag">
          {wave.in_field ? <span className="badge-partial">In field — partial</span> : <span className="badge-verified">✓ Verified sample</span>}
        </div>}
      </div>}
      {me && <p className="rail-user">{me.name || me.email}{me.role || me.tier ? ` · ${[me.role, me.tier].filter(Boolean).join(", ")}` : ""}
        {me.client ? <><br />{me.client}</> : null}<br /><a href="/auth/logout">Sign out</a></p>}
    </aside>
    <div className="main-col">
      <TopBar waves={waves.data ?? []} wave={wave} />
      {/* a theme switch re-colours in place (CSS tokens, EChart setTheme): scroll and focus stay where they were */}
      <main id="main" tabIndex={-1}><Outlet /></main>
      <PinDialog />
      <UndoBar />
      {showPerf && <Suspense fallback={null}><PerfHUD /></Suspense>}
    </div>
    <SiteFooter />
  </div>;
}

/** The coresight.com footer: dark band, the company's link groups, the way back to the main site, the copyright. */
function SiteFooter() {
  return <footer className="site-foot">
    <div className="site-foot-cols">
      <section>
        <img src="/coresight-logo-reversed.png" alt="Coresight Research" width="120" height="60" />
        <h2>Consumer Insight Portal</h2>
        <ul>
          <li><a href={SITE + "/"}>Back to coresight.com</a></li>
          <li><Link to="/methodology">Methodology</Link></li>
          <li><Link to="/whats-new">What's new</Link></li>
        </ul>
      </section>
      {FOOT_LINKS.map(([head, links]) => <section key={head}>
        <h2>{head}</h2>
        <ul>{links.map(([path, label]) => <li key={label}><a href={siteUrl(path)}>{label}</a></li>)}</ul>
      </section>)}
    </div>
    <div className="site-foot-base">
      <p>© {new Date().getFullYear()} Coresight Research. All rights reserved.</p>
      <ul>
        {LEGAL.map(([path, label]) => <li key={label}><a href={SITE + path}>{label}</a></li>)}
        <li><a href="https://www.linkedin.com/company/coresight-research/">LinkedIn</a></li>
      </ul>
    </div>
  </footer>;
}

/** The coresight.com header on every screen: logo and portal name, the site's top menus, then the portal's own
 *  controls (question search, theme, who is signed in). On phones the site links move to the footer. */
function SiteHeader({ theme, onTheme, menuOpen, onToggleMenu }: { theme: Theme; onTheme: () => void; menuOpen: boolean; onToggleMenu: () => void }) {
  const navigate = useNavigate();
  const me = useMe().data;
  const search = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);   // phones: the search is a row under the bar, opened by its icon

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); search.current?.focus(); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return <header className="site-head">
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
    <Link to="/" className="site-brand" aria-label="Consumer Insight Portal home">
      <img src={theme === "dark" ? "/coresight-logo-reversed.png" : "/coresight-logo.png"} alt="" width="76" height="38" />
      <span>Consumer Insight Portal</span>
    </Link>
    <nav className="site-links" aria-label="Coresight.com">
      {SITE_LINKS.map(([path, label]) => <a key={path} href={SITE + path}>{label}</a>)}
    </nav>
    <button className="icon-btn search-toggle" onClick={() => { setSearchOpen(o => !o); setTimeout(() => search.current?.focus()); }}
            aria-label="Search every question" aria-expanded={searchOpen}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor" /></svg>
    </button>
    <form className={`topbar-search-form ${searchOpen ? "open" : ""}`} role="search" onSubmit={e => { e.preventDefault(); if (text.trim()) { setSearchOpen(false); navigate(`/search?q=${encodeURIComponent(text.trim())}`); } }}>
      <label className="sr-only" htmlFor="global-search">Search every question</label>
      <span className="search-icon-prefix" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="15" height="15"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor" /></svg>
      </span>
      <input
        id="global-search"
        ref={search}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === "Escape") { e.currentTarget.blur(); setText(""); setSearchOpen(false); } }}
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
    <WeightSwitch />
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
    {me && <p className="site-user"><span>{me.name || me.email}</span>
      <a className="site-signout" href="/auth/logout">Sign out</a></p>}
  </header>;
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

/** The wave bar: the wave switcher ([ and ] step through the waves) and Save view. */
function TopBar({ waves, wave }: { waves: Wave[]; wave?: Wave }) {
  const navigate = useNavigate();
  const me = useMe().data;
  const family = wave ? waves.filter(w => w.survey_family === wave.survey_family && w.study_type === wave.study_type
                                     && (w.rows_built !== 0 || w.survey_id === wave.survey_id)) : [];
  const at = family.findIndex(w => w.survey_id === wave?.survey_id);   // newest first
  const go = (w?: Wave) => w && navigate(location.pathname.replace(/^\/w\/\d+/, `/w/${w.survey_id}`));

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
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
  return <div className={`topbar ${wave ? "" : "bare"}`}>
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
    {wave && allowed(me, "saved_views") && <SaveButton wave={wave} />}
  </div>;
}

/** Unweighted (default, matches Forsta and the Excel files) or Census-weighted figures on every wave screen. */
function WeightSwitch() {
  const weighted = useWeighted();
  return <button className="weight-btn" aria-pressed={weighted} onClick={() => setWeighted(!weighted)}
    title={weighted ? "Showing Census-weighted figures (gender, age, region). Click for unweighted." : "Showing unweighted figures, as in Forsta. Click for Census-weighted."}>
    {weighted ? "Weighted" : "Unweighted"}
  </button>;
}
