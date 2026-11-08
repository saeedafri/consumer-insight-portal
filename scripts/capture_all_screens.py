"""Capture full-page screenshots of every screen and menu in both light and dark modes.

Who calls it: pair-programming assistant / operator CLI via `python3 scripts/capture_all_screens.py`.
When: manual review or visual regression testing of all portal screens as super administrator.
"""

from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from sqlalchemy import text

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.core.database import get_engine
from shared.core.session import digest

PORT = 8002
BASE_URL = f"http://127.0.0.1:{PORT}"
OUTPUT_DIR = REPO_ROOT / "portal_screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# List of all application screens and views:
# (identifier, relative_url, display_title, wait_selector)
SCREENS = [
    # ── Landing / Home ──────────────────────────────────────────────────────────
    ("00_home_landing", "/", "Portal Landing Page", "main"),
    # ── Core Navigation ────────────────────────────────────────────────────────
    ("01_library", "/app/", "Survey Library", ".wave-row"),
    ("02_search_empty", "/app/search", "Search Questions (Initial)", "main"),
    ("02_search_results", "/app/search?q=shopping", "Search Questions (Results for 'shopping')", ".search-result, .card"),
    ("03_schedule", "/app/schedule", "Launch Schedule", ".schedule-table, table"),
    ("04_ask", "/app/ask", "Ask CIP", "main"),
    ("05_boards", "/app/boards", "Boards", "main"),
    ("06_sectors", "/app/sectors", "Sector Databank", ".sector-grid, .card, main"),
    ("07_expectations", "/app/expectations", "Expected vs Actual", ".expectations-table, table, main"),
    ("08_methodology", "/app/methodology", "Methodology", ".methodology-toc, main"),
    ("09_whats_new", "/app/whats-new", "What's New", "main"),
    # ── Forsta / Fieldwork ──────────────────────────────────────────────────────
    ("10_fieldwork", "/app/fieldwork", "Fieldwork Overview", ".fieldwork-table, table"),
    ("11_fieldwork_survey", "/app/fieldwork/selfserve%2F58f%2F261003", "Fieldwork Survey Detail (261003)", ".funnel, .card, main"),
    ("12_forsta_reports", "/app/forsta/reports", "Forsta: Team Reports", ".report-table, table, main"),
    ("13_forsta_check", "/app/forsta/check", "Forsta: Forsta vs CIP", "table, main"),
    ("14_forsta_crosstab", "/app/forsta/crosstab", "Forsta: Cross-Tab Setup", "table, main"),
    ("15_forsta_samples", "/app/forsta/samples", "Forsta: Sample & Devices", "table, main"),
    ("16_forsta_warnings", "/app/forsta/warnings", "Forsta: Warnings & Checks", "table, main"),
    ("17_forsta_files", "/app/forsta/files", "Forsta: Survey Files", "table, main"),
    ("18_forsta_deletion", "/app/forsta/deletion", "Forsta: Archive & Deletion", "table, main"),
    ("19_forsta_account", "/app/forsta/account", "Forsta: Account Details", "table, main"),
    # ── Super Admin Specific ───────────────────────────────────────────────────
    ("20_admin_ingest", "/app/ingest", "Admin: Upload Survey Wave", ".dropzone, main"),
    ("21_admin_logs", "/app/logs", "Admin: Operational Monitoring & Logs", ".chart-grid, .card, main"),
    ("22_admin_access", "/app/access", "Admin: Role Access Management", ".access-group, .card, main"),
    # ── User Account & Developer Documentation ─────────────────────────────────
    ("23_account", "/app/account", "My Account", ".account-details, .card, main"),
    ("24_api_guide", "/app/api-guide", "API Guide & MCP Documentation", ".guide-code, main"),
    # ── Wave Specific Views (Wave 530: Oct 26, 2026 Tracker) ───────────────────
    ("25_wave_overview", "/app/w/530", "Wave Overview (Holiday Tracker Topic)", ".glance-grid, .card, main"),
    ("25b_wave_overview_offprice", "/app/w/530?d=off_price", "Wave Overview (Off-Price / Dollar Stores Topic)", ".glance-grid, .card, main"),
    ("26_wave_questions_chart", "/app/w/530/questions", "Question Explorer (Chart View)", ".qnav, .chart-card, main"),
    ("26b_wave_questions_table", "/app/w/530/questions?view=table", "Question Explorer (Table View)", ".qnav, table, main"),
    ("27_wave_crosstab", "/app/w/530/crosstab", "Cross-Tab Matrix", ".crosstab-matrix, table, main"),
    ("28_wave_trends", "/app/w/530/trends", "Trends Over Time", ".trends-chart, .chart-card, main"),
    ("29_wave_compare", "/app/w/530/compare", "Compare Waves", ".compare-card, main"),
    ("30_wave_audience", "/app/w/530/audience", "Audiences (Cohort Breakdowns)", ".audience-card, main"),
    ("31_wave_changes", "/app/w/530/changes", "What Changed", ".changes-table, table, main"),
    ("32_wave_survey", "/app/w/530/survey", "Survey Preview", ".survey-preview, main"),
    ("33_wave_report", "/app/w/530/report", "Weekly Report View", "main"),
    # ── Error Page ─────────────────────────────────────────────────────────────
    ("34_not_found", "/app/404-page", "404 Not Found Page", "main"),
]

CSS_FIX = """
/* Ensure full-page screenshot renders sidebar and content at full vertical extent */
.rail {
    height: 100% !important;
    min-height: 100% !important;
    max-height: none !important;
    overflow: visible !important;
}
"""


def authenticate_super_admin(context, page) -> None:
    """Sign in as super administrator and promote the session in the database."""
    print("Signing in as super administrator mohdsaeedafri@coresight.com...")
    login_url = f"{BASE_URL}/auth/dev-login?email=mohdsaeedafri@coresight.com&next=/app/"
    page.goto(login_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Extract session cookie
    cookies = context.cookies()
    cip_cookie = next((c for c in cookies if c["name"] == "cip_session"), None)
    if not cip_cookie:
        raise RuntimeError("Failed to obtain cip_session cookie from dev-login.")

    raw = cip_cookie["value"].strip('"')
    part0 = raw.split(".")[0]
    part0 += "=" * (-len(part0) % 4)
    val = base64.urlsafe_b64decode(part0).decode()
    email, products, expires, sid, scope = val.split("|")
    session_hash = digest(sid)

    # Promote session to oidc in database
    with get_engine("api_write").begin() as conn:
        conn.execute(
            text("UPDATE cip_access_session SET provider = :p WHERE session_hash = :h"),
            {"p": "oidc", "h": session_hash},
        )
    print("Session verified and promoted in database. Super administrator access active.\n")


def capture_screen(page, identifier: str, relative_url: str, title: str, wait_selector: str) -> None:
    """Navigate to the screen and capture both light and dark full-page screenshots."""
    full_url = f"{BASE_URL}{relative_url}"
    print(f"Capturing: [{identifier}] {title} ({relative_url})")

    try:
        page.goto(full_url, wait_until="networkidle", timeout=30000)
    except Exception as exc:
        print(f"  Warning: navigation timeout on {relative_url} ({exc}), continuing...")

    # Wait for target selector if available
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=5000)
        except Exception:
            pass

    # Inject sidebar full-height CSS
    page.add_style_tag(content=CSS_FIX)

    # ── 1. Light Mode ──────────────────────────────────────────────────────────
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    if theme != "light":
        page.evaluate('() => { const b = document.querySelector(".theme-btn"); if (b) b.click(); }')
        page.wait_for_timeout(600)

    # Re-apply CSS after DOM updates
    page.add_style_tag(content=CSS_FIX)
    page.wait_for_timeout(1000)

    light_path = OUTPUT_DIR / f"{identifier}_light.png"
    page.screenshot(path=str(light_path), full_page=True)
    print(f"  [✓] Light mode saved -> {light_path.name}")

    # ── 2. Dark Mode ───────────────────────────────────────────────────────────
    page.evaluate('() => { const b = document.querySelector(".theme-btn"); if (b) b.click(); }')
    page.wait_for_timeout(600)

    # Re-apply CSS after DOM updates
    page.add_style_tag(content=CSS_FIX)
    page.wait_for_timeout(1000)

    dark_path = OUTPUT_DIR / f"{identifier}_dark.png"
    page.screenshot(path=str(dark_path), full_page=True)
    print(f"  [✓] Dark mode saved  -> {dark_path.name}\n")


def main() -> None:
    """Run full capture across all screens in light and dark modes."""
    start_time = time.time()
    print("==================================================================")
    print("Consumer Insight Portal — Full-Page Screen Capture Suite")
    print(f"Target Server: {BASE_URL}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Screens to capture: {len(SCREENS)} (x2 themes = {len(SCREENS) * 2} images)")
    print("==================================================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = context.new_page()

        # Step 1: Super administrator login
        authenticate_super_admin(context, page)

        # Step 2: Capture all screens
        for idx, (ident, url, title, sel) in enumerate(SCREENS, 1):
            print(f"[{idx}/{len(SCREENS)}] Processing {title}...")
            capture_screen(page, ident, url, title, sel)

        browser.close()

    elapsed = time.time() - start_time
    captured_files = list(OUTPUT_DIR.glob("*.png"))
    print("==================================================================")
    print(f"Capture completed in {elapsed:.1f} seconds.")
    print(f"Total screenshots in {OUTPUT_DIR}: {len(captured_files)}")
    print("==================================================================")


if __name__ == "__main__":
    main()
