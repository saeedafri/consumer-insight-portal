# 84 · coresight.com header, footer and fonts

**Date:** 23 Oct 2026 · **Scope:** `web/src/*`, `web/index.html`, `web/package.json` + lock. Builds on [82](82-fixes-frontend.md) and [83](83-ui-redesign.md) and keeps their behaviour and accessibility fixes. No homepage or landing page (on hold).

**Guard rails:** `npm run build` was not run and `web/dist` was not written. The build is in **`web/dist.new`**, ready for the swap script. Port 8000 and cloudflared were not touched. Public `/healthz` returned 200 after the work. Nothing was committed.

## Verification

| Check | Result |
|---|---|
| `npx tsc --noEmit -p web` | clean |
| `node web/src/stats.check.ts` | passes |
| `.venv/bin/python -m pytest -q tests/test_access.py` | 12 passed |
| `vite build --outDir dist.new --emptyOutDir` | succeeds: entry 296.2 / 93.1 KB gzip, CSS 48.7 KB (was 41.6), charts unchanged |
| Live walk | Scratch Vite on :5179, `/api` and `/auth` proxied to the tunnel. Signed in through `/auth/dev-login`. Every non-GET request was aborted by the test, and there were none. Headless Chrome (playwright-core) covered Library, Overview and Questions × light/dark × 1440/390. Both processes were closed afterwards |
| Header height | 56 px at every width |
| Overflow | 0 px horizontal overflow at 390, 901, 1024, 1180, 1280, 1366 and 1440 |
| Touch targets | phone header: 0 targets under 44 px (menu, logo, search, theme). Phone footer: 0 links under 44 px |
| Headings | exactly one `<h1>` on every screen |
| Fonts | computed `h1` font is `Montserrat Variable` and `body` is `Roboto Variable` |
| Errors | 0 page or console errors, apart from the known /me and /methodology 404s |
| Drawer | Escape closes it and focus returns to the menu button |

## Changes

| What | Where |
|---|---|
| **Site links, checked live.** Each URL was fetched on 23 Oct and returned 200. Redirecting URLs were replaced by their final URL: `/subscriptions/` became `/memberships/`, `/about/` became `/about-us/`, and `/about/contact` became `/about-us/contact/`. "Become a Client" was dropped: it redirects to Contact, and portal users are already clients. All links open in the same tab | `Shell.tsx:39-50` |
| **Header** (`SiteHeader`), full width above the rail on every screen:<br>• Coresight logo plus "Consumer Insight Portal", linking to the portal home (the light or reversed logo follows the theme);<br>• the site's top menus: Research & Data, Events, Services, About;<br>• the portal's question search (⌘K), the theme button, the signed-in name, and **Sign out** as the site's outlined red button.<br>Search, ⌘K and the phone search row moved here from the wave bar unchanged | `Shell.tsx:93, 163-252` |
| **Wave bar** (`TopBar`) keeps the wave switcher, the `[` `]` keys and Save view. It is sticky under the header. On phones it is hidden when there is no wave | `Shell.tsx:298-321`; `styles.css:126, 820` |
| **Rail.** The rail's logo block was removed because the header carries the brand. The rail is sticky at 56 px. On desktop the user line is hidden because the header shows it. It stays in the phone drawer | `Shell.tsx:96-…`; `styles.css:81, 111` |
| **Footer** (`SiteFooter`): a dark `#2D2A29` band in both themes, with four columns:<br>• Consumer Insight Portal: Back to coresight.com, Methodology, What's new;<br>• Services;<br>• Get in touch;<br>• Quick links.<br>The base row has "© 2026 Coresight Research. All rights reserved." (year from the clock), Terms of Use, Privacy Policy, Vulnerability Disclosure Policy and LinkedIn. It is two columns on phones, with 44 px links | `Shell.tsx:129, 134-160`; `styles.css:113-123, 825-830` |
| **Responsive header**:<br>• ≤1180 px: the portal name is hidden and the search keeps at least 200 px;<br>• ≤1024 px: the user name is hidden and Sign out stays;<br>• ≤900 px: the site links and user are hidden (the footer and the drawer have them);<br>• ≤520 px: logo only | `styles.css:105-106, 821-824` |
| **Fonts**:<br>• `@fontsource-variable/roboto@5.3.0` is self-hosted and imported beside Montserrat. It is the one new package; nothing else provided Roboto;<br>• `--font` is split into `--font-head` (Montserrat) and `--font-body` (Roboto);<br>• `--t-display`, `--t-h2`, `--t-h3` and `--t-kpi` use the heading font. `--t-body`, `--t-data` and `--t-meta` use the body font;<br>• headings, `.btn`, segment buttons, menus, rail nav, question tabs, the wave select and the rail KPI use Montserrat;<br>• chart text (`EChart.tsx` `FONT`) is Roboto. The PNG export title stays Montserrat;<br>• `tabular-nums` on body is unchanged | `main.tsx:7`; `styles.css:26-31, 150`; `EChart.tsx:13` |
| **Hover red**: light `--red-hover` is now `#AF2223`. Dark keeps `#E04A4B` | `styles.css:20` |
| **Focus on dark bands**: the focus ring is `#FAFAFA` in the footer and the rail. The red ring there was 2.91:1, below 3:1; this was an existing gap in the light-theme rail | `styles.css:117` |
| **Print** hides the header and footer | `styles.css:643` |
| **Boot shell** in `index.html` now paints the 56 px white header row before JS, so there is no layout jump | `index.html:19-33` |
| **What's new**: added the entry "Looks and reads like coresight.com" | `pages/WhatsNew.tsx:9` |

## Contrast (WCAG 2.x, computed)

| Pair | Need | Light | Dark |
|---|--:|--:|--:|
| Header link / portal name (ink on header surface) | 4.5 | 14.24 | 15.32 |
| Header link hover (red-text) | 4.5 | 5.70 | 7.05 |
| Signed-in name (ink-2) | 4.5 | 6.63 | 9.33 |
| Sign out text (red-text) | 4.5 | 5.70 | 7.05 |
| Sign out border (red) | 3 | 4.89 | 3.27 |
| Sign out hover (white on red) | 4.5 | 4.89 | 4.89 |
| Focus ring on header | 3 | 4.89 | 7.05 |
| Footer heading (white on #2D2A29) | 4.5 | 14.24 | 14.24 |
| Footer link (#D9D6D4) | 4.5 | 9.85 | 9.85 |
| Footer copyright (#BDB9B7) | 4.5 | 7.31 | 7.31 |
| Footer / rail focus ring (#FAFAFA) | 3 | 13.64 | 13.64 |
| Primary button hover (white on `--red-hover`) | 4.5 | **6.83** (was 5.96 with #BF2627) | **4.00, fails** |

**Open: dark hover.** The dark `--red-hover #E04A4B` under white 13 px button text is 4.00:1. That is below 4.5 and passes only for large text. It was there before this pass and was kept on instruction. A dark hover of `#C42829` (5.7:1) or keeping `#D62E2F` with an outline change would fix it. That is the user's call.

## Screenshots

All are in `screens/header-footer/`. File names are `{d,m}-{library,overview,questions}-{light,dark}.png`, at 1440×900 and 390×844 @2x, for wave 415. Also:
- `{d,m}-footer-{light,dark}.png`: scrolled to the footer;
- `m-drawer-light.png`: the phone drawer;
- `m-search-open-light.png`: the phone search row;
- `d1024-overview-light.png`: a small laptop.

## Not done / notes

- `DESIGN.md` and `PRODUCT.md` still name Montserrat as the only typeface. They are outside this pass's files. They should add "Roboto for body and data".
- The phone drawer no longer has the brand block at its top, because the header above it has the brand.
- `web/package-lock.json`'s diff against HEAD also contains pass 82's dependency removals. Only the Roboto entry is new here.
