// App frame: the coresight.com header (logo, site links, search, theme, sign-in), a rail with the wave's screens,
// a wave bar with the wave switcher, and the coresight.com footer.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { setTheme, useTheme } from "../theme";
import { setWeighted, useWeighted } from "../weight";
import type { Theme } from "../theme";
import { Link, NavLink, Outlet, useLocation, useNavigate, useNavigationType, useParams } from "react-router";
import { allowed, useMe, useReportWaves, useWaves } from "../api";
import { SECTIONS } from "../forstaSections";
import { TRACKERS } from "../trackers";
import PinDialog from "./PinDialog";
import { Menu, UndoBar } from "./bits";
import type { Me, Wave } from "../api";
import { fmtDate } from "../stats";
import { isSaved, removeView, saveView } from "../saved";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Activity, CalendarDays, ChartColumn, CheckCheck, ChevronDown, Database, FileText, Files, Filter, Globe, House, Info, Layers, LayoutDashboard, LibraryBig, PanelLeftClose, PanelLeftOpen, Pin, ScrollText, Search, ShieldCheck, Smartphone, Star, Store, Table2, Trash2, TriangleAlert, Upload, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// [path, label, icon]; FEATURE names the /me feature a screen needs (config/access.yml): unlisted screens always show
const FEATURE: Record<string, string> = { questions: "explorer", crosstab: "crosstab", trends: "trends", compare: "compare", audience: "audiences",
                                          changes: "changes", report: "report", survey: "survey" };
const TOP_FEATURE: Record<string, string> = { search: "search", schedule: "schedule", ask: "ask", boards: "boards", sectors: "sectors",
                                              expectations: "expectations", "api-guide": "api" };
/** The feature the screen at this address needs, or undefined when it always shows: a hidden menu also closes its
 *  address, so a link, a bookmark or a typed URL never opens a screen the menus take away (10 Nov 2026). */
export function featureOf(pathname: string): string | undefined {
  const [, first, , screen] = pathname.split("/");
  return first === "w" ? FEATURE[screen ?? ""] : TOP_FEATURE[first];
}
const FORSTA_ICONS: Record<string, LucideIcon> = {   // the Forsta group's icons (forstaSections.ts names the pages)
  reports: FileText,
  crosstab: Table2,
  check: CheckCheck,
  samples: Smartphone,
  warnings: TriangleAlert,
  files: Files,
  deletion: Trash2,
  account: UserRound,
};
const SCREENS = [   // a wave's screens: the tabs in its card (TopBar)
  ["", "Overview"], ["questions", "Questions"], ["crosstab", "Cross-tabs"], ["trends", "Trends"], ["compare", "Compare waves"],
  ["audience", "Audiences"], ["changes", "What changed"], ["report", "Weekly report"],   // weekly tracker waves only
  ["survey", "Survey preview"],
] as const;

// coresight.com links, as on its own header and footer (checked live 23 Oct 2026); same tab, like any site link
const SITE = "https://coresight.com";
const FOOT_LINKS = [
  ["Services", [["/memberships/", "Research & Data Memberships"], ["/innovator-services/", "Innovator Market Development"],
                ["/custom-research-advisory-services/", "Advisory & Custom Research"], ["/coresight-ai-council/", "AI Council"]]],
  ["Get in touch", [["/about-us/contact/", "Contact Us"], ["https://5jdoa.share.hsforms.com/2OopvqR9nRLa_8920kgYvaQ", "Media Inquiries"]]],
  ["Quick links", [["/research/", "All Research"], ["/events/", "Events"], ["/newsroom/", "Newsroom"], ["/retailistic-podcast/", "The Retaili$tic Podcast"]]],
] as const;
const LEGAL = [["/terms-of-service/", "Terms of Use"], ["/privacy-policy/", "Privacy Policy"],
               ["/coresight-research-responsible-vulnerability-disclosure-policy/", "Vulnerability Disclosure Policy"]] as const;
const siteUrl = (path: string) => path.startsWith("http") ? path : SITE + path;

/** A menu icon: lucide's thin outline set at one size and weight, as in the 8 Nov 2026 mockups. */
// The small red label over a wave screen's title (styles.css .page-head h1::before): which wave it is. Other pages
// have none: the header's breadcrumb already names them, and a label repeating the menu would only decorate.
function eyebrow(wave?: Wave): string {
  return wave ? `${wave.survey_family === "CSI-US" ? "Weekly tracker" : wave.survey_family === "CSI-CN" ? "China weekly tracker" : "Survey"} / ${fmtDate(wave.wave_date)}` : "";
}

// Each page's name, for the header's breadcrumb and a saved view's name
const PAGES: Record<string, string> = { "": "Home", library: "Survey library", search: "Search questions", schedule: "Launch schedule", ask: "Ask Coresight",
  boards: "Boards", sectors: "Sector databank", retailers: "Retailer databank", channels: "In store vs online", trackers: "Trackers", expectations: "Expected vs actual", methodology: "Methodology", "whats-new": "What's new",
  account: "My account", "api-guide": "API guide", fieldwork: "Fieldwork", ingest: "Upload survey", logs: "Logs", access: "Access" };
function pageName(pathname: string): string {
  const [, first, , screen] = pathname.split("/");
  if (first === "w") return SCREENS.find(([path]) => path === (screen ?? ""))?.[1] ?? "Overview";
  if (first === "forsta") return SECTIONS.find(([path]) => path === pathname.split("/")[2])?.[1] ?? "Forsta";
  return PAGES[first] ?? "";
}

/** A menu group that folds (Design 2): open unless `closed`, which a group of admin pages is until you are on one. */
function RailGroup({ label, closed = false, children }: { label: string; closed?: boolean; children: ReactNode }) {
  return <details className="rail-group" open={!closed}>
    <summary className="rail-label">{label}<ChevronDown size={14} aria-hidden="true" /></summary>
    <nav aria-label={label}>{children}</nav>
  </details>;
}

function Icon({ of: Glyph }: { of: LucideIcon }) {
  return <Glyph size={17} strokeWidth={1.8} aria-hidden="true" />;
}

export default function Shell() {
  const { id } = useParams();
  const location = useLocation();
  const theme = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // the menu can be hidden for more room (header button, or Ctrl/⌘+B); the choice is kept in this browser
  const [railHidden, setRailHidden] = useState(() => { try { return localStorage.getItem("cip-rail") === "hidden"; } catch { return false; } });
  const toggleRail = () => setRailHidden(hidden => {
    try { localStorage.setItem("cip-rail", hidden ? "shown" : "hidden"); } catch { /* private mode: this visit only */ }
    return !hidden;
  });
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") { e.preventDefault(); toggleRail(); } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  // closeDropdowns: an open menu or picker (<details class="menu|picker">) closes on Escape or a click outside it, as a
  // select does; native <details> stays open until its own summary is clicked (the Retailer databank pickers, 12 Nov 2026)
  useEffect(() => {
    const closeDropdowns = (e: Event) => document.querySelectorAll<HTMLDetailsElement>("details.menu[open], details.picker[open]").forEach(d => {
      if (e instanceof KeyboardEvent ? e.key !== "Escape" : d.contains(e.target as Node)) return;
      d.open = false;
      if (e instanceof KeyboardEvent) d.querySelector("summary")?.focus();
    });
    document.addEventListener("pointerdown", closeDropdowns);
    document.addEventListener("keydown", closeDropdowns);
    return () => { document.removeEventListener("pointerdown", closeDropdowns); document.removeEventListener("keydown", closeDropdowns); };
  }, []);
  // Azure closes an idle connection after about 4 minutes (measured 12 Nov 2026: kept after 125 s, closed by 245 s), and a
  // new one costs ~0.5-0.7 s of TLS handshake from India. While the tab is in view, a tiny HEAD every 2 minutes keeps it
  // open, so the next question or page pays only the distance (~0.26 s). Hidden tabs send nothing.
  useEffect(() => {
    const warm = setInterval(() => { if (document.visibilityState === "visible") fetch("/healthz", { method: "HEAD", cache: "no-store" }).catch(() => {}); }, 120_000);
    return () => clearInterval(warm);
  }, []);
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const waves = useWaves();
  const me = useMe().data;
  const isAdmin = !!me?.permissions?.includes("admin_pages");   // the role's permission (shared/core/access.py can())
  const weighted = useWeighted();
  useEffect(() => {   // "Weighted figures" taken off this person's menu: a switch left on in this browser goes off
    if (me?.features && !allowed(me, "weighted") && weighted) setWeighted(false);
  }, [me, weighted]);
  const wave = waves.data?.find(w => String(w.survey_id) === id);
  const latest = waves.data?.find(w => w.survey_family === "CSI-US" && w.rows_built !== 0);   // newest first
  const china = waves.data?.find(w => w.survey_family === "CSI-CN" && w.rows_built !== 0);    // the China Consumer Survey (Baidu)
  const reportWaves = useReportWaves().data;   // the waves with a weekly report (since Jul 2025: etl/weekly_report.py)
  const hasReport = !!wave && !!reportWaves?.includes(wave.survey_id);
  const rail = useRef<HTMLElement>(null);
  const howArrived = useNavigationType();

  // Where the reader is on each page, so that a link opens a new page at its top (not at the scroll position of the
  // page it was clicked on: the library is long) and Back/Forward ("POP") return to the same place. A filter that only
  // changes ?query= stays on the same page and keeps its place.
  const places = useRef(new Map<string, number>());
  const here = useRef(location.pathname);
  useEffect(() => {
    history.scrollRestoration = "manual";   // the browser would restore before the page is drawn; we do it after
    const remember = () => places.current.set(here.current, window.scrollY);
    addEventListener("scroll", remember, { passive: true });
    return () => removeEventListener("scroll", remember);
  }, []);
  useLayoutEffect(() => {
    here.current = location.pathname;
    window.scrollTo(0, howArrived === "POP" ? places.current.get(location.pathname) ?? 0 : 0);
  }, [location.pathname]);

  // a new page closes the phone drawer
  useEffect(() => {
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

  return <div className={`app ${mobileMenuOpen ? "mobile-nav-open" : ""} ${railHidden ? "rail-hidden" : ""}`}>
    <a href="#main" className="skip">Skip to content</a>
    <SiteHeader here={pageName(location.pathname)} railHidden={railHidden} onToggleRail={toggleRail} theme={theme} onTheme={toggleTheme} menuOpen={mobileMenuOpen} onToggleMenu={() => setMobileMenuOpen(o => !o)} />
    {mobileMenuOpen && <div className="rail-backdrop" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />}
    <aside ref={rail} id="portal-menu" className={`rail ${mobileMenuOpen ? "open" : ""}`} aria-label="Portal Navigation"
           {...(mobileMenuOpen ? { role: "dialog", "aria-modal": true } : {})}>
      <RailGroup label="Explore">
        <NavLink to="/" end><Icon of={House} />Home</NavLink>
        <NavLink to="/library"><Icon of={LibraryBig} />Survey library</NavLink>
        {allowed(me, "search") && <NavLink to="/search"><Icon of={Search} />Search questions</NavLink>}
        {allowed(me, "schedule") && <NavLink to="/schedule"><Icon of={CalendarDays} />Launch schedule</NavLink>}
        {allowed(me, "boards") && <NavLink to="/boards"><Icon of={Pin} />Boards</NavLink>}
      </RailGroup>
      <RailGroup label="Core research">
        {latest && <NavLink to={`/w/${latest.survey_id}`} className={() => wave?.survey_id === latest.survey_id ? "active" : ""}>
          <Icon of={LayoutDashboard} />Shopping & Spending</NavLink>}
        {china && <NavLink to={`/w/${china.survey_id}`} className={() => wave?.survey_family === "CSI-CN" ? "active" : ""}>
          <Icon of={Globe} />China weekly tracker</NavLink>}
        {allowed(me, "explorer") && <NavLink to="/channels"><Icon of={Layers} />In store vs online</NavLink>}
        {allowed(me, "retailers") && <NavLink to="/retailers"><Icon of={Store} />Retailer databank</NavLink>}
        {allowed(me, "sectors") && <NavLink to="/sectors"><Icon of={Database} />Sector databank</NavLink>}
        {allowed(me, "expectations") && <NavLink to="/expectations"><Icon of={ChartColumn} />Expected vs actual</NavLink>}
      </RailGroup>
      {allowed(me, "dashboards") && <RailGroup label="Trackers" closed={!location.pathname.startsWith("/trackers")}>
        {TRACKERS.map(([code, label]) => <NavLink key={code} to={`/trackers/${code}`}><Icon of={Activity} />{label}</NavLink>)}
      </RailGroup>}
      <RailGroup label="Reference">
        <NavLink to="/methodology"><Icon of={Info} />Methodology</NavLink>
        <NavLink to="/whats-new"><Icon of={Star} />What's new</NavLink>
      </RailGroup>
      {(isAdmin || me?.features?.includes("fieldwork")) && <RailGroup label="Research operations" closed={!/^\/(fieldwork|forsta)/.test(location.pathname)}>
        <NavLink to="/fieldwork"><Icon of={Filter} />Fieldwork</NavLink>
        {isAdmin && SECTIONS.map(([path, label]) => <NavLink key={path} to={`/forsta/${path}`}><Icon of={FORSTA_ICONS[path]} />{label}</NavLink>)}
      </RailGroup>}
      {isAdmin && <RailGroup label="Administration" closed={!/^\/(ingest|logs|access)/.test(location.pathname)}>
        <NavLink to="/ingest"><Icon of={Upload} />Upload survey</NavLink>
        <NavLink to="/logs"><Icon of={ScrollText} />Logs</NavLink>
        {me?.permissions?.includes("manage_roles") && <NavLink to="/access"><Icon of={ShieldCheck} />Access</NavLink>}
      </RailGroup>}
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
      {wave && <TopBar waves={waves.data ?? []} wave={wave} hasReport={hasReport} />}
      {/* a theme switch re-colours in place (CSS tokens, EChart setTheme): scroll and focus stay where they were */}
      <main id="main" tabIndex={-1} style={{ "--eyebrow": JSON.stringify(eyebrow(wave)) } as React.CSSProperties}>
        {allowed(me, featureOf(location.pathname) ?? "") || !featureOf(location.pathname) ? <Outlet /> :
          <div className="card" style={{ padding: 24 }}><h1>Not included in your subscription</h1>
            <p className="muted">This screen is not on your menu. Ask your Coresight contact if you need it.</p>
            <p><Link to={wave ? `/w/${wave.survey_id}` : "/"}>Back to {wave ? "the wave's overview" : "the survey library"}</Link></p></div>}
      </main>
      <PinDialog />
      <UndoBar />
      {/* under the content only: across the full width it ended the rail's row, and the sticky rail scrolled away with it */}
      <SiteFooter theme={theme} />
    </div>
  </div>;
}

/** The coresight.com footer: the page's own surface (light or dark with the theme), the company's link groups, the way back to the main site, the copyright. */
function SiteFooter({ theme }: { theme: Theme }) {
  return <footer className="site-foot">
    <div className="site-foot-cols">
      <section>
        <img src={theme === "dark" ? "/coresight-logo-reversed.png" : "/coresight-logo.png"} alt="Coresight Research" width="120" height="60" />
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

/** The portal's header on every screen: the Coresight logo and the portal's name, then the portal's own controls
 *  (question search, weighting, theme, who is signed in, sign out). coresight.com's menus (Research & Data, Events,
 *  Services) are on the public site's header only (app/(site)/layout.tsx); the footer below keeps its links. */
function SiteHeader({ here, railHidden, onToggleRail, theme, onTheme, menuOpen, onToggleMenu }: { here: string; railHidden: boolean; onToggleRail: () => void;
  theme: Theme; onTheme: () => void; menuOpen: boolean; onToggleMenu: () => void }) {
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
    <Tooltip>
      <TooltipTrigger render={<button className="icon-btn rail-toggle" onClick={onToggleRail} aria-expanded={!railHidden} aria-controls="portal-menu"
                                      aria-label={railHidden ? "Show the menu" : "Hide the menu"}>
        {railHidden ? <PanelLeftOpen size={17} strokeWidth={1.8} aria-hidden="true" /> : <PanelLeftClose size={17} strokeWidth={1.8} aria-hidden="true" />}</button>} />
      <TooltipContent side="right">{railHidden ? "Show the menu" : "Hide the menu"} (Ctrl/⌘ B)</TooltipContent>
    </Tooltip>
    <Link to="/" className="site-brand" aria-label="Consumer Insight Portal home">
      <img src={theme === "dark" ? "/coresight-logo-reversed.png" : "/coresight-logo.png"} alt="" width="76" height="38" />
      <span>Consumer Insight Portal{here && <small> / {here}</small>}</span>
    </Link>
    {allowed(me, "search") && <button className="icon-btn search-toggle" onClick={() => { setSearchOpen(o => !o); setTimeout(() => search.current?.focus()); }}
            aria-label="Search every question" aria-expanded={searchOpen}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor" /></svg>
    </button>}
    {allowed(me, "search") && <form className={`topbar-search-form ${searchOpen ? "open" : ""}`} role="search" onSubmit={e => { e.preventDefault(); if (text.trim()) { setSearchOpen(false); navigate(`/search?q=${encodeURIComponent(text.trim())}`); } }}>
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
    </form>}
    {allowed(me, "weighted") && <WeightSwitch />}
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
    {me && <AccountMenu me={me} />}
  </header>;
}

/** The signed-in person as a round icon at the far right of the header; it opens their name and email, My account
 *  (screens/Account.tsx) and Sign out. */
function AccountMenu({ me }: { me: Me }) {
  const person = <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 12a4.5 4.5 0 100-9 4.5 4.5 0 000 9zm0 2c-4.4 0-8 2.2-8 5v2h16v-2c0-2.8-3.6-5-8-5z" /></svg>;
  return <Menu label="" icon={person} name={`Account: ${me.email}`} className="account-menu">
    <div className="account-who"><b>{me.name || me.email.split("@")[0]}</b><span>{me.email}</span></div>
    <Link className="btn" to="/account">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 12a4.5 4.5 0 100-9 4.5 4.5 0 000 9zm0 2c-4.4 0-8 2.2-8 5v2h16v-2c0-2.8-3.6-5-8-5z" /></svg>
      My account</Link>
    <a className="btn account-signout" href="/auth/logout">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M10 17l1.4-1.4-2.6-2.6H20v-2H8.8l2.6-2.6L10 7l-5 5 5 5zM4 5h7V3H4a2 2 0 00-2 2v14a2 2 0 002 2h7v-2H4V5z" /></svg>
      Sign out</a>
  </Menu>;
}

/** Keep this exact view (wave, screen, question, cut, waves picked) under a name in the Library. */
function SaveButton({ wave }: { wave: Wave }) {
  const location = useLocation();
  const url = location.pathname + location.search;
  const [saved, setSaved] = useState(isSaved(url));
  useEffect(() => setSaved(isSaved(url)), [url]);
  const screen = pageName(location.pathname);
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
function TopBar({ waves, wave, hasReport }: { waves: Wave[]; wave: Wave; hasReport: boolean }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();   // the router's path (/w/530/…), not the browser's (/app/w/530/…): that doubled /app
  const me = useMe().data;
  const family = waves.filter(w => w.survey_family === wave.survey_family && w.study_type === wave.study_type
                                     && (w.rows_built !== 0 || w.survey_id === wave.survey_id));
  const at = family.findIndex(w => w.survey_id === wave.survey_id);   // newest first
  const go = (w?: Wave) => w && navigate(pathname.replace(/^\/w\/\d+/, `/w/${w.survey_id}`));

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
  return <div className="topbar">
    <div className="topbar-row"><div className="switcher">
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
    </div>
    {allowed(me, "saved_views") && <SaveButton wave={wave} />}</div>
    <nav className="wave-tabs" aria-label="This wave">
      {SCREENS.filter(([path]) => (!FEATURE[path] || allowed(me, FEATURE[path])) && (path !== "report" || hasReport)).map(([path, label]) =>
        <NavLink key={path} to={`/w/${wave.survey_id}${path ? "/" + path : ""}`} end={!path}>{label}</NavLink>)}
    </nav>
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
