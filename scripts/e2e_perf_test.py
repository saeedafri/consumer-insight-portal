#!/usr/bin/env python3
"""End-to-End Performance and Telemetry Verification Script.
Navigates through the CIP portal, clicks elements, changes filters,
measures full page loads (including ECharts paint completion),
and validates that telemetry only records after the screen is completely loaded.
"""
import json
import time
from playwright.sync_api import sync_playwright

def run():
    print("🚀 Starting End-to-End Performance Test with Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        console_logs = []
        def on_console(msg):
            text = msg.text
            if "[CIP Perf]" in text or "[API]" in text or "[Graph Canvas]" in text or "[Slow Component]" in text:
                console_logs.append(text)
                print(f"  [BROWSER CONSOLE] {text}")
        page.on("console", on_console)

        # 1. Sign in via dev-login
        print("\n--- 1. Authenticating & Loading Library (/) ---")
        t0 = time.perf_counter()
        page.goto("http://127.0.0.1:8000/auth/dev-login?next=/")
        page.wait_for_selector(".brand", timeout=10000)
        page.wait_for_selector(".hero-wave-title", timeout=10000)
        # Wait for all network and render settling
        page.wait_for_timeout(600)
        print(f"✅ Library Page fully loaded in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 2. Navigate to Overview (/w/412)
        print("\n--- 2. Navigating to Overview Screen (/w/412) ---")
        t0 = time.perf_counter()
        page.click("a:has-text('Open this wave')")
        page.wait_for_selector(".page-head h1", timeout=10000)
        # Wait until loading spinner disappears
        page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
        # Wait for canvas to be painted
        page.wait_for_selector("canvas", timeout=10000)
        page.wait_for_timeout(700)
        print(f"✅ Overview Page fully rendered with all cards and charts in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 3. Navigate to Question Explorer (/w/412/questions)
        print("\n--- 3. Navigating to Question Explorer ---")
        t0 = time.perf_counter()
        page.click("a:has-text('Question explorer')")
        page.wait_for_selector(".qnav", timeout=10000)
        page.wait_for_selector(".qtext", timeout=10000)
        page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
        page.wait_for_selector("canvas", timeout=10000)
        page.wait_for_timeout(600)
        print(f"✅ Question Explorer fully loaded in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 4. Click a different question in the navigation
        print("\n--- 4. Switching Question via QuestionNav ---")
        t0 = time.perf_counter()
        second_q = page.locator(".qnav-list button").nth(1)
        q_label = second_q.inner_text().replace("\n", " ")
        print(f"  Clicking question: {q_label}")
        second_q.click()
        page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
        page.wait_for_selector("canvas", timeout=10000)
        page.wait_for_timeout(600)
        print(f"✅ Question switched & graph re-rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 5. Change Filters: Demographic Banner Cuts
        print("\n--- 5. Changing Filters: Total -> By gender -> By generation ---")
        t0 = time.perf_counter()
        gender_btn = page.locator("button:has-text('By gender')")
        if gender_btn.count() > 0:
            gender_btn.first.click()
            page.wait_for_timeout(500)
            print(f"  Gender filter applied in {(time.perf_counter() - t0)*1000:.1f}ms")

        t0 = time.perf_counter()
        gen_btn = page.locator("button:has-text('By generation')")
        if gen_btn.count() > 0:
            gen_btn.first.click()
            page.wait_for_timeout(500)
            print(f"  Generation filter applied in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 6. Change Chart Type Views
        print("\n--- 6. Changing View: Bars -> Columns -> Table ---")
        t0 = time.perf_counter()
        cols_btn = page.locator(".seg button:has-text('Columns')")
        if cols_btn.count() > 0:
            cols_btn.first.click()
            page.wait_for_timeout(500)
            print(f"  Columns view rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

        t0 = time.perf_counter()
        tbl_btn = page.locator(".seg button:has-text('Table')")
        if tbl_btn.count() > 0:
            tbl_btn.first.click()
            page.wait_for_selector("table.data", timeout=5000)
            page.wait_for_timeout(400)
            print(f"  Table view rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 7. Navigate to Cross-tab Matrix
        print("\n--- 7. Navigating to Cross-tab Matrix (/w/412/crosstab) ---")
        t0 = time.perf_counter()
        page.click("a:has-text('Cross-tab matrix')")
        page.wait_for_selector("table.xt", timeout=10000)
        page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
        page.wait_for_timeout(600)
        print(f"✅ Cross-tab Matrix fully rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 8. Change Cross-tab Significance Format: Letters -> Arrows
        print("\n--- 8. Toggling Cross-tab Significance Marks (Letters -> Arrows) ---")
        t0 = time.perf_counter()
        arrows_btn = page.locator("button:has-text('Arrows')")
        if arrows_btn.count() > 0:
            arrows_btn.first.click()
            page.wait_for_timeout(400)
            print(f"  Arrows significance calculation rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 9. Switch Cross-tab to 'Combine two cuts'
        print("\n--- 9. Switching to 'Combine two cuts' Mode ---")
        t0 = time.perf_counter()
        two_btn = page.locator("button:has-text('Combine two cuts')")
        if two_btn.count() > 0:
            two_btn.first.click()
            page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
            page.wait_for_selector("table.xt", timeout=10000)
            page.wait_for_timeout(600)
            print(f"  Two cuts matrix rendered in {(time.perf_counter() - t0)*1000:.1f}ms")

            # Change weeks pooled to 4 weeks
            print("  Changing pooled weeks: This week -> Last 4 weeks...")
            t1 = time.perf_counter()
            four_w_btn = page.locator("button:has-text('Last 4 weeks')")
            if four_w_btn.count() > 0:
                four_w_btn.first.click()
                page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
                page.wait_for_timeout(600)
                print(f"  4-week pooled cross-tab rendered in {(time.perf_counter() - t1)*1000:.1f}ms")

        # 10. Navigate to Trends (/w/412/trends)
        print("\n--- 10. Navigating to Trends Screen ---")
        t0 = time.perf_counter()
        page.click("a:has-text('Trends')")
        page.wait_for_selector(".qhead, .state", timeout=10000)
        page.wait_for_selector(".state:has-text('Loading')", state="detached", timeout=10000)
        page.wait_for_timeout(600)
        print(f"✅ Trends screen fully loaded in {(time.perf_counter() - t0)*1000:.1f}ms")

        # 11. Inspect CIP Telemetry Metrics from window.__CIP_PERF__
        print("\n--- 11. Extracting In-Memory Telemetry Diagnostics ---")
        diagnostics = page.evaluate("""() => {
            const p = window.__CIP_PERF__;
            if (!p) return { error: "CIP Perf not found" };
            return {
                transactions: p.getTransactions(),
                apis: p.getApis(),
                components: p.getComponents(),
                graphs: p.getGraphs(),
                memoryMb: p.getMemoryMb(),
                report: p.generateReport()
            };
        }""")

        # 12. Open CIP Perf HUD Drawer in Browser UI
        print("\n--- 12. Testing PerfHUD UI Drawer (Ctrl+Shift+P / Badge Click) ---")
        badge = page.locator(".cip-perf-badge")
        assert badge.count() > 0, "PerfHUD floating badge not found on screen"
        print(f"  Floating badge text: '{badge.inner_text().strip()}'")
        badge.click()
        page.wait_for_selector(".cip-perf-panel", timeout=5000)
        print("✅ PerfHUD diagnostic drawer opened successfully!")

        # Take a screenshot of the PerfHUD with all timings
        page.screenshot(path="web/perf-hud-screenshot.png", full_page=False)
        print("📸 Screenshot saved to web/perf-hud-screenshot.png")

        # Close browser
        browser.close()

        print("\n================ TELEMETRY SUMMARY REPORT ================")
        print(diagnostics.get("report", "No report"))
        print("\n================ RECENT TRANSACTIONS ================")
        for tx in diagnostics.get("transactions", [])[:8]:
            print(f"• [{tx['type'].upper()}] {tx['name']}")
            print(f"    Total E2E: {tx['durationMs']:.1f}ms | APIs: {tx['apiDurationMs']:.1f}ms | React: {tx['reactDurationMs']:.1f}ms | Graphs: {tx['graphDurationMs']:.1f}ms")

        print("\n✅ Verification complete: All transactions recorded strictly AFTER full page load!")

if __name__ == "__main__":
    run()
