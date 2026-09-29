"""Coresight header bar — the same pattern as the Market Data Portal.

No sidebar. A full-bleed sticky bar carries the logo and the horizontal nav,
Streamlit's own chrome is hidden, and the active link is brand red. Nav items
are plain anchors with `target="_self"` so a click is a normal same-tab
navigation to the page's `url_path`, not a widget rerun.
"""
from __future__ import annotations

import streamlit as st

LOGO = ("https://production-wordpress-cdn-dpa0g9bzd7b3h7gy.z03.azurefd.net"
        "/wp-content/uploads/2023/12/coresight-logo-1.png")

BRAND_RED = "#d62e2f"
INK = "#2d2a29"
BAR_BG = "#f2f2f2"

# label, url_path (what render_header matches on), href.
# The default page is served at "/" and its url_path 404s, so Overview links home.
NAV: tuple[tuple[str, str, str], ...] = (
    ("Overview", "overview", "/"),
    ("Questions", "questions", "/questions"),
    ("Analysis Builder", "analysis", "/analysis"),
    ("Cross-tabs", "crosstabs", "/crosstabs"),
    ("Trends", "trends", "/trends"),
    ("Data Health", "data-health", "/data-health"),
)

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

/* Streamlit's own chrome: gone. The header below replaces it. */
header[data-testid="stHeader"] {{
  display: none !important; height: 0 !important; min-height: 0 !important;
}}
section[data-testid="stSidebar"], div[data-testid="stSidebarNav"],
div[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
div[data-testid="stAppViewContainer"] > section:first-child {{ display: none !important; }}

.stApp {{ overflow-x: hidden !important; }}
html, body {{ overflow-x: hidden !important; max-width: 100% !important; }}

.block-container {{
  padding-top: 1.25rem !important;
  max-width: 1440px;
}}

.csi-header {{
  background-color: {BAR_BG};
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  margin-right: calc(-50vw + 50%);
  box-sizing: border-box;
  position: sticky; top: 0; z-index: 1000;
  border-bottom: 1px solid #e3e3e3;
}}
.csi-header-inner {{
  max-width: 1440px; margin: 0 auto; height: 72px;
  display: flex; align-items: center; gap: 40px; padding: 0 40px;
}}
.csi-header-logo img {{ width: 118px; height: 54px; object-fit: contain; display: block; }}
.csi-header-nav {{ display: flex; align-items: center; gap: 34px; flex-wrap: wrap; }}
.csi-header-nav a {{
  font-family: 'Roboto', sans-serif; font-size: 16px; font-weight: 500;
  color: {INK}; text-decoration: none; white-space: nowrap;
  line-height: 26px; padding-bottom: 2px; border-bottom: 2px solid transparent;
  transition: color .18s ease, border-color .18s ease;
}}
.csi-header-nav a:hover {{ color: {BRAND_RED}; }}
.csi-header-nav a.active {{ color: {BRAND_RED}; border-bottom-color: {BRAND_RED}; }}
.csi-header-meta {{
  margin-left: auto; font-family: 'Inter', sans-serif; font-size: 12px;
  color: #6b6a68; text-align: right; line-height: 1.5; white-space: nowrap;
}}
.csi-header-meta .dot {{ font-size: 15px; vertical-align: -1px; }}

@media (max-width: 1100px) {{
  .csi-header-inner {{ height: auto; padding: 12px 20px; gap: 20px; flex-wrap: wrap; }}
  .csi-header-nav {{ gap: 20px; }}
  .csi-header-meta {{ margin-left: 0; width: 100%; text-align: left; }}
}}

/* Page title block */
.csi-page-title {{
  font-family: 'Inter', sans-serif; font-size: 30px; font-weight: 700;
  color: #1a1a2e; margin: 6px 0 2px 0; letter-spacing: -0.01em;
}}
.csi-page-sub {{
  font-family: 'Inter', sans-serif; font-size: 14px; color: #6b6a68;
  margin: 0 0 18px 0;
}}
</style>
"""


def render_header(active: str, db_status: str = "", environment: str = "") -> None:
    """Draw the header. `active` is the url_path of the current page."""
    links = "".join(
        f'<a href="{href}" target="_self" class="{"active" if path == active else ""}">{label}</a>'
        for label, path, href in NAV
    )
    meta = ""
    if db_status or environment:
        ok = db_status.startswith("connected")
        colour = "#1b7f4f" if ok else "#a61f20"
        meta = (
            f'<div class="csi-header-meta">'
            f'<div><strong>Consumer Insight Portal</strong>'
            f'{" · " + environment if environment else ""}</div>'
            f'<div style="color:{colour}"><span class="dot">●</span> {db_status}</div>'
            f"</div>"
        )
    st.markdown(
        _CSS
        + f'<div class="csi-header"><div class="csi-header-inner">'
          f'<div class="csi-header-logo"><img src="{LOGO}" alt="Coresight Research"></div>'
          f'<nav class="csi-header-nav">{links}</nav>{meta}</div></div>',
        unsafe_allow_html=True,
    )


def page_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="csi-page-title">{title}</div>'
        + (f'<div class="csi-page-sub">{subtitle}</div>' if subtitle else '<div style="height:12px"></div>'),
        unsafe_allow_html=True,
    )
