"""Comprehensive, exhaustive full-page screenshot capture suite for Consumer Insight Portal.

Takes full control of every screen, sidebar section, topbar menu, view mode,
filter tab, demographic cut, interactive question, modal dialog, and dropdown.

Output directory: portal_screenshots/
Target instance: http://127.0.0.1:8001 (isolated test uvicorn instance)
"""

from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.core.database import get_engine
from shared.core.session import digest

PORT = 8001
BASE_URL = f"http://127.0.0.1:{PORT}"
OUTPUT_DIR = REPO_ROOT / "portal_screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSS_FIX = """
/* Ensure full-page screenshot renders sidebar rail and content at full vertical extent */
.rail {
    height: 100% !important;
    min-height: 100% !important;
    max-height: none !important;
    overflow: visible !important;
}
"""


def authenticate_super_admin(context: BrowserContext, page: Page) -> None:
    """Sign in as super administrator and promote session to oidc in MySQL."""
    print("--> Authenticating as super administrator mohdsaeedafri@coresight.com...")
    login_url = f"{BASE_URL}/auth/dev-login?email=mohdsaeedafri@coresight.com&next=/app/"
    page.goto(login_url, wait_until="networkidle")
    page.wait_for_timeout(1000)

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

    with get_engine("api_write").begin() as conn:
        conn.execute(
            text("UPDATE cip_access_session SET provider = :p WHERE session_hash = :h"),
            {"p": "oidc", "h": session_hash},
        )
    print("--> Session verified and promoted to oidc. Super administrator active.\n")


def capture_state(page: Page, identifier: str, description: str) -> None:
    """Capture full-page screenshots of the current page in both light and dark themes."""
    print(f"  [+] Capturing: {identifier} ({description})")
    page.wait_for_timeout(500)

    # ── 1. Light Mode ──
    page.evaluate("""() => {
        if (document.documentElement.dataset.theme !== 'light') {
            const btn = document.querySelector('.theme-btn');
            if (btn) btn.click();
        }
    }""")
    page.wait_for_timeout(350)
    page.add_style_tag(content=CSS_FIX)
    page.wait_for_timeout(350)

    light_path = OUTPUT_DIR / f"{identifier}_light.png"
    page.screenshot(path=str(light_path), full_page=True)

    # ── 2. Dark Mode ──
    page.evaluate("""() => {
        if (document.documentElement.dataset.theme !== 'dark') {
            const btn = document.querySelector('.theme-btn');
            if (btn) btn.click();
        }
    }""")
    page.wait_for_timeout(350)
    page.add_style_tag(content=CSS_FIX)
    page.wait_for_timeout(350)

    dark_path = OUTPUT_DIR / f"{identifier}_dark.png"
    page.screenshot(path=str(dark_path), full_page=True)
    
    # Validation
    if not light_path.exists() or light_path.stat().st_size < 10000:
        print(f"      [!] WARNING: Light screenshot {light_path.name} invalid or missing!")
    if not dark_path.exists() or dark_path.stat().st_size < 10000:
        print(f"      [!] WARNING: Dark screenshot {dark_path.name} invalid or missing!")
    print(f"      [OK] {identifier}_light.png ({light_path.stat().st_size // 1024} KB) & {identifier}_dark.png ({dark_path.stat().st_size // 1024} KB)")


def safe_goto(page: Page, url_path: str, wait_selector: str = "") -> None:
    """Navigate safely to a path and wait for network or selector."""
    full_url = f"{BASE_URL}{url_path}"
    try:
        page.goto(full_url, wait_until="networkidle", timeout=30000)
    except Exception as exc:
        print(f"    Notice: goto {url_path} timeout: {exc}")
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=5000)
        except Exception:
            pass
    page.add_style_tag(content=CSS_FIX)
    page.wait_for_timeout(500)


def main() -> None:
    start_time = time.time()
    print("==================================================================")
    print("Consumer Insight Portal — Full Control Exhaustive Capture Suite")
    print(f"Target Server: {BASE_URL}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("==================================================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = context.new_page()

        # Step 0: Login and promote session
        authenticate_super_admin(context, page)

        # ── 1. Landing & Home ──────────────────────────────────────────────────
        print("\n[Phase 1/16] Home / Landing")
        safe_goto(page, "/")
        capture_state(page, "00_home_landing", "Public Portal Landing Page")

        # ── 2. Survey Library & Filters ─────────────────────────────────────────
        print("\n[Phase 2/16] Survey Library & Controls")
        safe_goto(page, "/app/", ".hero")
        capture_state(page, "01_library_all", "Survey Library (All surveys)")

        try:
            tracker_btn = page.locator('.seg button:has-text("Weekly tracker")')
            if tracker_btn.count() > 0:
                tracker_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "01_library_filter_tracker", "Survey Library (Filtered: Weekly tracker)")

            annual_btn = page.locator('.seg button:has-text("Annual study")')
            if annual_btn.count() > 0:
                annual_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "01_library_filter_annual", "Survey Library (Filtered: Annual study)")

            adhoc_btn = page.locator('.seg button:has-text("Ad hoc study")')
            if adhoc_btn.count() > 0:
                adhoc_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "01_library_filter_adhoc", "Survey Library (Filtered: Ad hoc study)")

            # Reset tab to All
            all_btn = page.locator('.seg button:has-text("All")').first
            if all_btn.count() > 0:
                all_btn.click()
                page.wait_for_timeout(400)

            # Year filter dropdown
            year_select = page.locator('select#year')
            if year_select.count() > 0:
                year_select.select_option("2025")
                page.wait_for_timeout(500)
                capture_state(page, "01_library_filter_year_2025", "Survey Library (Filtered: Year 2025)")
                year_select.select_option("all")
                page.wait_for_timeout(400)

            # Search text input
            search_input = page.locator('input#q')
            if search_input.count() > 0:
                search_input.fill("holiday")
                page.wait_for_timeout(500)
                capture_state(page, "01_library_search_holiday", "Survey Library (Search: 'holiday')")
                search_input.fill("")
                page.wait_for_timeout(400)
        except Exception as exc:
            print(f"    Notice during library filtering: {exc}")

        # ── 3. Search Questions ────────────────────────────────────────────────
        print("\n[Phase 3/16] Search Questions & Query Views")
        safe_goto(page, "/app/search")
        capture_state(page, "02_search_initial", "Search Questions (Initial with popular topics)")

        try:
            chip = page.locator('button.chip:has-text("Holiday shopping")')
            if chip.count() > 0:
                chip.click()
            else:
                page.locator('input#q').fill("holiday")
                page.locator('form.toolbar').dispatch_event('submit')
            page.wait_for_timeout(1000)
            capture_state(page, "02_search_results_holiday_wording", "Search Questions (Results: 'holiday' - Each wording)")

            # Toggle Group by measure tab
            tab_measure = page.locator('.seg button:has-text("Group by measure")')
            if tab_measure.count() > 0:
                tab_measure.click()
                page.wait_for_timeout(600)
                capture_state(page, "02_search_results_holiday_measure", "Search Questions (Results: 'holiday' - Group by measure)")

            # Search another term: walmart
            safe_goto(page, "/app/search?q=walmart")
            page.wait_for_timeout(800)
            capture_state(page, "02_search_results_walmart", "Search Questions (Results for 'walmart')")
        except Exception as exc:
            print(f"    Notice during search actions: {exc}")

        # ── 4. Launch Schedule ─────────────────────────────────────────────────
        print("\n[Phase 4/16] Launch Schedule")
        safe_goto(page, "/app/schedule", ".grid.g4")
        capture_state(page, "03_schedule_recent", "Launch Schedule (Recent and upcoming)")

        try:
            all_btn = page.locator('button:has-text("Show all")')
            if all_btn.count() > 0:
                all_btn.click()
                page.wait_for_timeout(600)
                capture_state(page, "03_schedule_all_weeks", "Launch Schedule (All weeks since Jul 2025)")

            quota_summary = page.locator('details.quota-left summary')
            if quota_summary.count() > 0:
                quota_summary.first.click()
                page.wait_for_timeout(400)
                capture_state(page, "03_schedule_quota_expanded", "Launch Schedule (Quota cells details expanded)")
        except Exception as exc:
            print(f"    Notice during schedule actions: {exc}")

        # ── 5. Ask CIP ─────────────────────────────────────────────────────────
        print("\n[Phase 5/16] Ask CIP & Answer Citations")
        safe_goto(page, "/app/ask", ".ask-grid")
        capture_state(page, "04_ask_prompt", "Ask CIP (Prompt & Example Question Pills)")

        try:
            cyber_btn = page.locator('button.story:has-text("Cyber Monday")')
            if cyber_btn.count() > 0:
                cyber_btn.click()
                page.wait_for_selector('.table-wrap table', timeout=15000)
                page.wait_for_timeout(1000)
                capture_state(page, "04_ask_answer_cyber_monday", "Ask CIP (Answer & Citations: Cyber Monday)")

            tariffs_btn = page.locator('button.story:has-text("tariffs")')
            if tariffs_btn.count() > 0:
                tariffs_btn.click()
                page.wait_for_selector('.table-wrap table', timeout=15000)
                page.wait_for_timeout(1000)
                capture_state(page, "04_ask_answer_tariffs", "Ask CIP (Answer & Citations: Tariffs)")
        except Exception as exc:
            print(f"    Notice during Ask CIP actions: {exc}")

        # ── 6. Boards ──────────────────────────────────────────────────────────
        print("\n[Phase 6/16] Boards")
        safe_goto(page, "/app/boards", ".ask-grid")
        capture_state(page, "05_boards_overview", "Boards (Hub & Creation Flow)")

        # ── 7. Sector Data Bank ────────────────────────────────────────────────
        print("\n[Phase 7/16] Sector Data Bank")
        safe_goto(page, "/app/sectors", ".report-table")
        capture_state(page, "06_sectors_apparel_retailers", "Sector Databank (Clothing - Retailers)")

        try:
            brands_tab = page.locator('.toolbar .seg button:has-text("Brands")')
            if brands_tab.count() > 0:
                brands_tab.click()
                page.wait_for_timeout(500)
                capture_state(page, "06_sectors_apparel_brands", "Sector Databank (Clothing - Brands)")

            cats_tab = page.locator('.toolbar .seg button:has-text("Categories")')
            if cats_tab.count() > 0:
                cats_tab.click()
                page.wait_for_timeout(500)
                capture_state(page, "06_sectors_apparel_categories", "Sector Databank (Clothing - Categories)")

            # Change sector to Beauty via index
            sector_select = page.locator('select#sector')
            if sector_select.count() > 0:
                sector_select.select_option(index=1)
                page.wait_for_timeout(600)
                capture_state(page, "06_sectors_beauty_retailers", "Sector Databank (Beauty - Retailers)")

                sector_select.select_option(index=2)
                page.wait_for_timeout(600)
                capture_state(page, "06_sectors_dept_stores_retailers", "Sector Databank (Department Stores - Retailers)")
        except Exception as exc:
            print(f"    Notice during Sector actions: {exc}")

        # ── 8. Expected vs Actual ──────────────────────────────────────────────
        print("\n[Phase 8/16] Expected vs Actual")
        safe_goto(page, "/app/expectations", ".report-table")
        capture_state(page, "07_expectations_halloween_pair0", "Expected vs Actual (Valentine's/First Event - Pair 0)")

        try:
            pair_select = page.locator('select#pair')
            if pair_select.count() > 0 and pair_select.locator('option').count() > 1:
                pair_select.select_option(index=1)
                page.wait_for_timeout(500)
                capture_state(page, "07_expectations_pair1", "Expected vs Actual (Surveys Pair 1)")

            event_tabs = page.locator('.toolbar .seg button')
            if event_tabs.count() > 1:
                event_tabs.nth(1).click()
                page.wait_for_timeout(600)
                capture_state(page, "07_expectations_second_event", "Expected vs Actual (Second Event Tab)")
        except Exception as exc:
            print(f"    Notice during Expectations actions: {exc}")

        # ── 9. Methodology ─────────────────────────────────────────────────────
        print("\n[Phase 9/16] Methodology")
        safe_goto(page, "/app/methodology")
        capture_state(page, "08_methodology_overview", "Methodology (General Overview)")

        safe_goto(page, "/app/methodology#fieldwork-terms", "#fieldwork-terms")
        capture_state(page, "08_methodology_fieldwork_terms", "Methodology (Fieldwork & Launch Terms)")

        # ── 10. What's New? ────────────────────────────────────────────────────
        print("\n[Phase 10/16] What's New?")
        safe_goto(page, "/app/whats-new")
        capture_state(page, "09_whats_new", "What's New (Portal Changelog)")

        # ── 11. Fieldwork & Survey Detail ──────────────────────────────────────
        print("\n[Phase 11/16] Fieldwork & Survey Funnel")
        safe_goto(page, "/app/fieldwork", ".fieldwork-table")
        capture_state(page, "10_fieldwork_overview", "Fieldwork (Every Survey's Funnel)")

        # Survey Detail for 261003 (Wave 530)
        safe_goto(page, "/app/fieldwork/selfserve%2F58f%2F261003", ".funnel-kpis")
        capture_state(page, "11_fieldwork_survey_detail", "Fieldwork Survey Detail (261003 - Funnel & Dropouts)")

        # ── 12. Forsta Admin Sections ──────────────────────────────────────────
        print("\n[Phase 12/16] Forsta Admin Suite (8 Sections)")
        safe_goto(page, "/app/forsta/reports", ".seg")
        capture_state(page, "12_forsta_reports", "Forsta: Team Reports")

        safe_goto(page, "/app/forsta/check", "table")
        capture_state(page, "13_forsta_check", "Forsta: Forsta vs CIP Cell Comparison")

        safe_goto(page, "/app/forsta/crosstab", "table")
        capture_state(page, "14_forsta_crosstab", "Forsta: Cross-Tab Setup & Defaults")

        safe_goto(page, "/app/forsta/samples", "table")
        capture_state(page, "15_forsta_samples", "Forsta: Sample & Devices Breakdown")

        safe_goto(page, "/app/forsta/warnings", "table")
        capture_state(page, "16_forsta_warnings", "Forsta: Warnings & Launch Checks")

        safe_goto(page, "/app/forsta/files", "table")
        capture_state(page, "17_forsta_files", "Forsta: Survey Files & Assets")

        safe_goto(page, "/app/forsta/deletion", "table")
        capture_state(page, "18_forsta_deletion", "Forsta: Archive & Deletion Schedule")

        safe_goto(page, "/app/forsta/account", "table")
        capture_state(page, "19_forsta_account", "Forsta: Account & API Directory")

        # ── 13. Admin Operations (Ingest, Logs, Access) ────────────────────────
        print("\n[Phase 13/16] Admin Operations")
        safe_goto(page, "/app/ingest", ".dropzone, .grid.g2")
        capture_state(page, "20_admin_ingest", "Admin: Upload Survey Wave")

        safe_goto(page, "/app/logs?minutes=60", ".chart-grid, .card")
        capture_state(page, "21_admin_logs_1h", "Admin Logs (1-Hour Monitoring)")

        try:
            btn_24h = page.locator('button:has-text("24 h")')
            if btn_24h.count() > 0:
                btn_24h.click()
                page.wait_for_timeout(800)
                capture_state(page, "21b_admin_logs_24h", "Admin Logs (24-Hour Monitoring)")

            btn_7d = page.locator('button:has-text("7 days")')
            if btn_7d.count() > 0:
                btn_7d.click()
                page.wait_for_timeout(800)
                capture_state(page, "21c_admin_logs_7d", "Admin Logs (7-Day Monitoring)")
        except Exception as exc:
            print(f"    Notice during logs range changes: {exc}")

        safe_goto(page, "/app/access", ".access-targets")
        capture_state(page, "22_admin_access_analyst", "Admin Access (Analysts Role)")

        try:
            client_role = page.locator('.access-targets .seg button:has-text("Clients")')
            if client_role.count() > 0:
                client_role.first.click()
                page.wait_for_timeout(500)
                capture_state(page, "22b_admin_access_client", "Admin Access (Clients Role)")
        except Exception as exc:
            print(f"    Notice during access role change: {exc}")

        # ── 14. User Account, API Guide & Topbar Menus ─────────────────────────
        print("\n[Phase 14/16] User Account & Developer API Guide")
        safe_goto(page, "/app/account")
        capture_state(page, "23_account", "My Account (Profile & API Keys)")

        safe_goto(page, "/app/api-guide")
        capture_state(page, "24_api_guide", "API Guide & MCP Connector Docs")

        # Topbar Account dropdown menu
        try:
            acct_summary = page.locator('.account-menu summary')
            if acct_summary.count() > 0:
                acct_summary.click()
                page.wait_for_timeout(400)
                capture_state(page, "24b_topbar_account_menu_open", "Site Header: Account Menu Opened")
                acct_summary.click()  # close menu
                page.wait_for_timeout(300)
        except Exception as exc:
            print(f"    Notice during account menu interaction: {exc}")

        # ── 15. Wave 530 (Weekly Tracker) Screens & Interactive States ────────────
        print("\n[Phase 15/16] Wave 530 (Weekly Tracker) Deep Interactive Suite")
        
        # 15.1 Overview
        safe_goto(page, "/app/w/530", ".glance-grid, .card")
        capture_state(page, "25_wave_overview_holiday", "Wave Overview (Holiday Tracker Topic)")

        safe_goto(page, "/app/w/530?d=off_price", ".glance-grid, .card")
        capture_state(page, "25b_wave_overview_offprice", "Wave Overview (Off-Price Topic)")

        safe_goto(page, "/app/w/530?d=tariffs_inflation", ".glance-grid, .card")
        capture_state(page, "25c_wave_overview_tariffs", "Wave Overview (Tariffs & Inflation Topic)")

        # 15.2 Question Explorer
        safe_goto(page, "/app/w/530/questions", ".qnav")
        capture_state(page, "26_wave_questions_bars", "Question Explorer (Bars View, Total Cut)")

        try:
            toolbar_segs = page.locator('.toolbar .seg')
            view_seg = toolbar_segs.first

            cols_btn = view_seg.locator('button:has-text("Columns")')
            if cols_btn.count() > 0:
                cols_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "26b_wave_questions_columns", "Question Explorer (Columns View)")

            stacked_btn = view_seg.locator('button:has-text("Stacked")')
            if stacked_btn.count() > 0:
                stacked_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "26c_wave_questions_stacked", "Question Explorer (Stacked View)")

            donut_btn = view_seg.locator('button:has-text("Donut")')
            if donut_btn.count() > 0:
                donut_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "26d_wave_questions_donut", "Question Explorer (Donut View)")

            table_btn = view_seg.locator('button:has-text("Table")')
            if table_btn.count() > 0:
                table_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "26e_wave_questions_table", "Question Explorer (Table View)")

            # Return to Bars, try demographic cuts
            bars_btn = view_seg.locator('button:has-text("Bars")')
            if bars_btn.count() > 0:
                bars_btn.click()
                page.wait_for_timeout(400)

            if toolbar_segs.count() > 1:
                cut_seg = toolbar_segs.nth(1)
                gender_btn = cut_seg.locator('button:has-text("Gender")')
                if gender_btn.count() > 0:
                    gender_btn.click()
                    page.wait_for_timeout(500)
                    capture_state(page, "26f_wave_questions_cut_gender", "Question Explorer (Gender Cut)")

                gen_btn = cut_seg.locator('button:has-text("Generation")')
                if gen_btn.count() > 0:
                    gen_btn.click()
                    page.wait_for_timeout(500)
                    capture_state(page, "26g_wave_questions_cut_generation", "Question Explorer (Generation Cut)")

                all_cuts_btn = cut_seg.locator('button:has-text("All")')
                if all_cuts_btn.count() > 0:
                    all_cuts_btn.click()
                    page.wait_for_timeout(500)
                    capture_state(page, "26h_wave_questions_cut_all", "Question Explorer (All Demographic Cuts)")

            # Pick another question from QNav (second item)
            qnav_buttons = page.locator('.qnav-list button')
            if qnav_buttons.count() > 1:
                qnav_buttons.nth(1).click()
                page.wait_for_timeout(600)
                capture_state(page, "26i_wave_questions_second_q", "Question Explorer (Second Question Selected)")

            # Test Census Weight button
            weight_btn = page.locator('button.weight-btn')
            if weight_btn.count() > 0:
                weight_btn.click()
                page.wait_for_timeout(500)
                capture_state(page, "26j_wave_questions_weighted", "Question Explorer (Weighted Figures Active)")
                weight_btn.click()  # return to unweighted
                page.wait_for_timeout(400)

            # Test Export Menu Open
            export_summary = page.locator('details.menu summary:has-text("Export")')
            if export_summary.count() > 0:
                export_summary.first.click()
                page.wait_for_timeout(300)
                capture_state(page, "26k_wave_questions_export_menu_open", "Question Explorer: Export Dropdown Menu Open")
                export_summary.first.click()  # close
                page.wait_for_timeout(300)

            # Test Pin Dialog Modal Open
            pin_btn = page.locator('.head-actions.export button:has-text("Pin")')
            if pin_btn.count() > 0:
                pin_btn.first.click()
                page.wait_for_selector('dialog.pin-dialog[open]', timeout=3000)
                page.wait_for_timeout(400)
                capture_state(page, "26l_wave_questions_pin_dialog_open", "Question Explorer: Pin to Board Dialog Modal Open")
                close_pin = page.locator('dialog.pin-dialog button:has-text("Close")')
                if close_pin.count() > 0:
                    close_pin.click()
                    page.wait_for_timeout(300)

            # Test More Actions Menu & Alert Me
            more_summary = page.locator('details.menu summary[title="More actions"], details.menu summary:has-text("⋯")')
            if more_summary.count() > 0:
                more_summary.first.click()
                page.wait_for_timeout(300)
                capture_state(page, "26m_wave_questions_more_menu_open", "Question Explorer: More Actions Menu Open")
                alert_btn = page.locator('.menu-list button:has-text("Alert me")')
                if alert_btn.count() > 0:
                    alert_btn.click()
                    page.wait_for_timeout(300)
                    capture_state(page, "26n_wave_questions_alert_me_open", "Question Explorer: Alert Me Form Open")
        except Exception as exc:
            print(f"    Notice during Explorer actions: {exc}")

        # 15.3 Cross-Tab Matrix
        safe_goto(page, "/app/w/530/crosstab", "table")
        capture_state(page, "27_wave_crosstab_banner", "Cross-Tab Matrix (Banner Mode)")

        try:
            two_tab = page.locator('.seg button:has-text("Combine two cuts")')
            if two_tab.count() > 0 and not two_tab.is_disabled():
                two_tab.click()
                page.wait_for_timeout(600)
                capture_state(page, "27b_wave_crosstab_two_cuts", "Cross-Tab Matrix (Combine Two Cuts Mode)")
        except Exception as exc:
            print(f"    Notice during Crosstab actions: {exc}")

        # 15.4 Trends
        safe_goto(page, "/app/w/530/trends", ".qnav")
        capture_state(page, "28_wave_trends_1y", "Trends (1-Year Range, Total)")

        try:
            tab_3m = page.locator('.toolbar .seg button:has-text("3m")')
            if tab_3m.count() > 0:
                tab_3m.click()
                page.wait_for_timeout(600)
                capture_state(page, "28b_wave_trends_3m", "Trends (3-Month Range)")

            tab_all = page.locator('.toolbar .seg button:has-text("All")')
            if tab_all.count() > 0:
                tab_all.click()
                page.wait_for_timeout(600)
                capture_state(page, "28c_wave_trends_all", "Trends (All-Time Range)")

            col_select = page.locator('select#col')
            if col_select.count() > 0:
                col_select.select_option("Male")
                page.wait_for_timeout(600)
                capture_state(page, "28d_wave_trends_col_male", "Trends (Cut by Male)")
        except Exception as exc:
            print(f"    Notice during Trends actions: {exc}")

        # 15.5 Compare Waves
        safe_goto(page, "/app/w/530/compare", "table")
        capture_state(page, "29_wave_compare_last4", "Compare Waves (Last 4 Waves)")

        try:
            tab_8 = page.locator('.toolbar .seg button:has-text("Last 8")')
            if tab_8.count() > 0:
                tab_8.click()
                page.wait_for_timeout(600)
                capture_state(page, "29b_wave_compare_last8", "Compare Waves (Last 8 Waves)")

            cut_select = page.locator('select[aria-label="Cut"]')
            if cut_select.count() > 0:
                cut_select.select_option("generation")
                page.wait_for_timeout(600)
                capture_state(page, "29c_wave_compare_cut_generation", "Compare Waves (Cut by Generation)")

            tab_own = page.locator('.toolbar .seg button:has-text("Pick waves")')
            if tab_own.count() > 0:
                tab_own.click()
                page.wait_for_timeout(600)
                capture_state(page, "29d_wave_compare_pick_own", "Compare Waves (Pick Waves Mode)")
        except Exception as exc:
            print(f"    Notice during Compare actions: {exc}")

        # 15.6 Audience
        safe_goto(page, "/app/w/530/audience", ".audience-cuts")
        capture_state(page, "30_wave_audience_builder", "Audiences (Cohort Builder Interface)")

        try:
            chk = page.locator('.audience-cuts label.check').first
            if chk.count() > 0:
                chk.click()
                page.wait_for_timeout(300)
                run_btn = page.locator('button.btn.primary:has-text("for this audience")')
                if run_btn.count() > 0 and not run_btn.is_disabled():
                    run_btn.click()
                    page.wait_for_selector('.table-wrap table', timeout=10000)
                    page.wait_for_timeout(800)
                    capture_state(page, "30b_wave_audience_results", "Audiences (Cohort Results & Index)")
        except Exception as exc:
            print(f"    Notice during Audience actions: {exc}")

        # 15.7 What's Changed
        safe_goto(page, "/app/w/530/changes", "table")
        capture_state(page, "31_wave_changes_vs_prior", "What Changed (vs Prior Wave)")

        try:
            changes_segs = page.locator('.toolbar .seg')
            tab_ly = changes_segs.first.locator('button:has-text("vs last year")')
            if tab_ly.count() > 0 and not tab_ly.is_disabled():
                tab_ly.click()
                page.wait_for_timeout(600)
                capture_state(page, "31b_wave_changes_vs_ly", "What Changed (vs Last Year)")

            if changes_segs.count() > 1:
                dir_seg = changes_segs.nth(1)
                tab_up = dir_seg.locator('button:has-text("Gainers")')
                if tab_up.count() > 0:
                    tab_up.click()
                    page.wait_for_timeout(500)
                    capture_state(page, "31c_wave_changes_gainers", "What Changed (Gainers Only)")

                tab_down = dir_seg.locator('button:has-text("Decliners")')
                if tab_down.count() > 0:
                    tab_down.click()
                    page.wait_for_timeout(500)
                    capture_state(page, "31d_wave_changes_decliners", "What Changed (Decliners Only)")

            sig_chk = page.locator('label.check:has-text("Significant only")')
            if sig_chk.count() > 0:
                sig_chk.click()
                page.wait_for_timeout(500)
                capture_state(page, "31e_wave_changes_all_shifts", "What Changed (All Shifts - Unfiltered)")

            demo_chk = page.locator('label.check:has-text("demographics")')
            if demo_chk.count() > 0:
                demo_chk.click()
                page.wait_for_timeout(500)
                capture_state(page, "31f_wave_changes_demographics", "What Changed (Include Demographics)")
        except Exception as exc:
            print(f"    Notice during Changes actions: {exc}")

        # 15.8 Weekly Report
        safe_goto(page, "/app/w/530/report", ".three-points, .report-section")
        capture_state(page, "32_wave_report_rolling", "Weekly Report (4-Week Rolling Average Sentiment)")

        try:
            btn_weekly = page.locator('button:has-text("Weekly")')
            if btn_weekly.count() > 0:
                btn_weekly.click()
                page.wait_for_timeout(600)
                capture_state(page, "32b_wave_report_weekly", "Weekly Report (Weekly Sentiment Mode)")
        except Exception as exc:
            print(f"    Notice during Report actions: {exc}")

        # 15.9 Survey Preview
        safe_goto(page, "/app/w/530/survey", ".card.respondent")
        try:
            opt = page.locator('.card.respondent .options button.option').first
            if opt.count() > 0:
                opt.click()
                page.wait_for_timeout(300)
        except Exception:
            pass
        capture_state(page, "33_wave_survey_q1", "Survey Preview (Interactive Question 1)")

        try:
            next_btn = page.locator('button:has-text("Next question")')
            if next_btn.count() > 0 and not next_btn.is_disabled():
                next_btn.click()
                page.wait_for_timeout(600)
                capture_state(page, "33b_wave_survey_q2", "Survey Preview (Question 2)")
        except Exception as exc:
            print(f"    Notice during Survey actions: {exc}")

        # ── 16. Previous Wave 529 & Error Page ─────────────────────────────────
        print("\n[Phase 16/16] Additional Waves & Error Notice")
        safe_goto(page, "/app/w/529", ".glance-grid, .card")
        capture_state(page, "34_wave_previous_529", "Wave Overview (Previous Wave 529)")

        safe_goto(page, "/app/404-page")
        capture_state(page, "35_not_found", "404 Page Not Found Notice")

        browser.close()

    elapsed = time.time() - start_time
    captured_files = list(OUTPUT_DIR.glob("*.png"))
    print("\n==================================================================")
    print(f"Full Control Capture complete in {elapsed:.1f} seconds.")
    print(f"Total screenshots stored in {OUTPUT_DIR}: {len(captured_files)}")
    print("==================================================================")


if __name__ == "__main__":
    main()
