# 82 · Frontend fixes (web/)

**Date:** 23 Oct 2026 · **Scope:** `web/src/*`, `web/package.json`, `web/package-lock.json`. Nothing under `web/dist`, `api/`, `etl/` or `app/` was touched by this pass, and nothing was committed. `npm run build` was never run. The live API on :8000 and the tunnel were not touched. `/healthz` on the public link returned 200 after the work.

**Not deployed yet:** `web/dist` is unchanged, so the live link still serves the old bundle. Deploying this pass means building into `web/dist`, which is a deploy decision for the user.

## Verification

| Check | Result |
|---|---|
| `npx tsc --noEmit -p web` | clean |
| `node web/src/stats.check.ts` | passes. It has a new UI-01 regression check: p = 1.3e-4 survives Benjamini–Hochberg (BH) over 368 tests, fails when 209 padded p = 1 rows are added, and `fdr()` leaves null (untestable) rows out of m. |
| Scratch build `vite build --outDir <scratchpad>/dist-check` | succeeds (sizes below) |
| `npm audit` | 0 vulnerabilities (before: 2 low, both from mermaid-cli) |
| Live walk | Vite dev server on :5179 with `/api` and `/auth` proxied to the public tunnel. GET only, signed in through the existing dev-login link. Headless Chrome visited 16 screens at desktop width and 1 at 390 px. Clicks were local UI only: tooltip focus, an undo test with a dummy action, sort toggle, the drawer and the theme. The walk ran no deletes and no creates. |

Walk results (wave 415 unless noted):
- **Headline vs What changed:** Overview reads "Personal subscription rose 13.3 points to 30.5%". What changed reads "4 significant changes against last week · of 228 answers tested". Before this pass both pages said 0 significant. The KPIs are now "Largest significant increase +13.3" and "Largest significant decrease −11.7 (CS3 'Yes')".
- **Bad link:** `/w/415/trends/q1?range=foo` renders the 1-year view; it used to crash. `crosstab?mode=two&a=bogus&weeks=9` falls back to gender × generation, 1 week.
- **B2B study (wave 259):** the source line reads "Coresight Research · T-Mobile AI Governance · Survey respondents". The wording reads "against the previous wave". The "Male 0 · Female 0" note is gone.
- **Unknown wave `/w/999999`:** the page shows "Could not load: No such wave · Back to the survey library", with no Refresh button.
- **Headings:** every screen has exactly one `<h1>`.
- **Phone width:** `overflowX = 0`.
- **Console:** no console errors apart from the expected 404 on `/api/v1/me` and `/api/v1/methodology`. The backend changes in the worktree are not running live yet. The UI falls back to everything visible and the built-in methodology text.
- **Keyboard and focus:** the significance chip's tooltip appears when the chip has keyboard focus and Escape hides it. The undo bar appears and Undo cancels the dummy action. Explorer sort writes `?sort=0`. On a phone the chart sits above the question list. The drawer takes focus, Tab stays inside it after 40 presses, and Escape closes it and returns focus to the menu button.

Screenshots: `<scratchpad>/walk/*.png`. They are not in the repo.

## Bundle (scratch builds, minified / gzip)

| Chunk | Before | After |
|---|--:|--:|
| entry `index-*.js` + shared `chunk-*.js` (both preloaded) | 375.95 / 119.17 KB | 288.31 + 93.52 = 381.83 / 121.88 KB |
| `charts-*.js` (idle-prefetched) | 549.31 / 186.53 KB | unchanged |
| CSS | 35.7 KB | 36.9 KB |
| New `Methodology-*.js` route chunk | – | 4.2 / 2.0 KB |

The entry grows by about 2.7 KB gzip. That covers moves.ts moving into the entry (books get their verdicts as they load), the tooltip, the undo bar and /me. Every route is still code-split.

## Gap → change

| ID | Change (file:line) | Verified |
|---|---|---|
| **UI-01** BH denominator | `stats.ts:35` adds `fdr()`, which is BH over the non-null p only. `moves.ts` computes `testable` / `testableLy` with the same rule as `etl/serving.py`: prior present, no `base_changed_*` or `wording_changed_*`, both bases ≥ 30, not filler. Untestable rows get `p = null` and stay out of m. `Changes.tsx:36` shows that same m ("of N answers tested"). | stats.check; live: 0 → 4 significant over 228 tested |
| **UI-02** one rule everywhere | `moves.ts:20-37`: if the book carries `sig_prior` / `sig_ly` tokens, they are the verdict. Otherwise the client applies the fixed BH. `api.ts:138` `bookOf()` runs `moves()` once per book as it loads, and `moveOf(row)` gives any row its verdict. The `Change` chip (`bits.tsx`, prop `move`), the Overview KPIs, the Explorer top-answer chip, the QuestionChart hover card, the table "Change" column and What changed all read it. `SIG_RULE` (`bits.tsx:30`) is the one wording. | Live Overview headline matches What changed |
| **UI-04** KPIs from significant moves | `Changes.tsx:37-38`: gainers and decliners come from `sigMoves`. The labels are "Largest significant increase/decrease", and when there is none the card reads "No significant increase". | Live wave 415 and wave 259 |
| **UI-09** Trends / Compare / crosstab marks | Labelled as uncorrected rather than corrected. Trends: a `SINGLE` subtitle, "sig. (single test)" in the tooltip, the table header and the source line (`Trends.tsx:24-25`). Compare: the subtitle, export note and source line. Crosstab letters and arrows: subtitle and export note. Audience result: subtitle. The Methodology page states the split. | Screens read on live data |
| **UI-03** provenance | `bits.tsx:108-131`: `population(w)` uses the wave's `population`, falling back to "US adults 18+" for trackers and "Survey respondents" otherwise. The survey name is the tracker name or `Coresight Research · <title>`. Weighting comes from `w.weighting` (default "unweighted"). In-field waves get a partial-results note. `SourceLine` now needs `from`, and every chart has it. `sourceText(from, date, base)` feeds the PNG footer (Explorer, Trends) and the CSV/XLSX/PPT notes (Explorer, Trends, Compare, Crosstab, Changes). The Library hero uses `population()`. The "Verified sample" badge shows only when `wave.verified === true` (`Shell.tsx`, rail foot). The backend does not send `verified` today, so the badge stays hidden. | Live wave 259 source line |
| Methodology page | New route `/methodology` (`main.tsx`), nav link (`Shell.tsx`) and page `pages/Methodology.tsx`. It renders the backend's flat `config/methodology.yml` JSON (panel, qualification, fielding, weighting_text, small_cells, significance, data_quality, population). It also accepts `{sections}` or plain text. It falls back to built-in text taken from stats.ts/moves.ts. Every `SourceLine` links to it, and every export and PNG footer carries `<origin>/methodology`. | Live: built-in fallback renders (API 404 today) |
| **UI-05** URL params | Trends `rangeOf()` (`Trends.tsx:24`), plus `at = -1` now falls back to the latest wave (`:157`). Compare `PICKS` is used for both the tab and the table. Crosstab two-cut `a`/`b` must be known cuts and `weeks` must be 1, 2 or 4 (`Crosstab.tsx:236`). Changes `dir` and `section` are validated. Library `kind` is validated. Audience `aud` is parsed defensively. | Live bad-param links render |
| **UI-06** small-cell copy | `stats.ts:54` adds `HIDDEN_NOTE = n<${HIDDEN_BASE}`. It replaces "n<30" in QuestionChart, both crosstab modes and Audience. The two-cut subtitle now says "No significance tests in this view". Comments now say HIDDEN_BASE. | grep: no "n<30" left |
| **UI-07** study-type wording | `bits.tsx:114` `compared(w)` returns prior/Prior/ly wording: "last week" for trackers and "the previous wave" otherwise. It is used in Overview (headline, card titles, table header, facts), Changes (h1, tab, column, lede, export), Explorer (chip, export header, legend) and the QuestionChart tooltip and table header (`vs` prop). Library labels "Latest wave" and "What changed" for non-trackers. `in_field` waves show an "In field — partial" badge in the rail and in the Overview lede. | Live wave 259 |
| **UI-08** title-only help | `components/ui/tooltip.tsx` rewritten. It renders a real `role="tooltip"` element tied to its trigger with `aria-describedby`. It shows on hover or focus; a plain chip gets `tabIndex=0` so a tap or Tab opens it. Escape hides it. CSS is in `styles.css` (`.tip`), with `display:none` when hidden so it never causes overflow. Every existing Tooltip use upgrades automatically: change chips, base notes, wave and question arrows, save, theme. Trends average and margin-of-error help moved from `title` to Tooltip. The Changes demographics note is now visible text. The crosstab hover card also opens on click or tap (`Crosstab.tsx:43`). Export buttons use `aria-label` instead of `title`. | Live: focus shows the tooltip, Escape hides it |
| **UI-10** names | `window.prompt` is removed. `api.ts:212-222` adds `useMe()` and an async `myName()`, which uses /me name, then email, then an old `cip_name`, then "Portal user". The server should take "by" from the session. Saved views, alerts and audiences use it. | tsc; no prompt in the bundle |
| **UI-11** destructive actions | `bits.tsx:177` `deleteLater()` and `UndoBar` (mounted in Shell). The item is hidden at once and the DELETE is sent after 6 s unless Undo is pressed. If the delete fails, the item comes back and the bar says why. Board delete also asks `confirm()` first (`Boards.tsx:68`). Covered: pinned items, comments, team saved views and team alerts (`Library.tsx:166`). | Live: dummy undo test |
| **UI-12** 401 | `api.ts:74` `signIn()` sends the user to `/auth/login?next=<path+query>`. It is used by `get`, `send` and the XLSX/PPTX export fetch (`csv.ts:34`). The rail shows **Sign out** (`/auth/logout`) when /me answers. | Code read |
| /me in the shell, feature gates | `Shell.tsx` rail shows name or email, role and tier, client and Sign out. `allowed(me, feature)` (`api.ts`) uses the `config/access.yml` names and treats `"*"` as all. It gates Search, Ask, Boards, the Explorer/Crosstab/Trends/Compare/Audience screens, the Save view button, export, the Board button and Alert me. Without /me, everything is visible. | Live: no /me, so all visible |
| **UI-13** MOE band | `Trends.tsx:215-216`: the band is built from the drawn `values`, so it follows the 4-week average when that is on. | Screenshot with avg + band |
| **UI-14** download revoke | `csv.ts:4` `save()` revokes the blob URL after 1 s. Also in csv.ts: the formula guard now catches a leading space before `= + - @`, and plain numbers such as "-3.2" are no longer turned into text. | Code read |
| **UI-15** /boards on every page | `PinDialog.tsx:15` calls `useBoards(spec != null)`, so it fetches only while the dialog is open. Team lists (boards, board, team views, alerts, audiences) get a 5-minute `staleTime` (`api.ts:202`) and refresh through `invalidateQueries` after the writes that change them. The query client moved to `api.ts` (`queries`) so non-React code can invalidate. | Live: no `/boards` request outside /boards |
| **UI-16** deps | `npm uninstall mermaid @mermaid-js/mermaid-cli reactflow @xyflow/react`. `react-scan` moved to devDependencies. `node_modules` went from 823 MB to 386 MB. | npm audit 0 |
| **UI-17** h1 | `.qtext` is now an `<h1>` (Explorer, Crosstab, Trends, Compare). Audience card is `as="h1"` (Card accepts h1). 404 and the error element use h1. Library empty state has an h1. | Live: 1 h1 per screen |
| **UI-18** drawer | `Shell.tsx:58-75`: while open the rail is `role="dialog" aria-modal`. Focus moves in, Tab wraps inside, Escape closes it and focus returns to the opener. | Live phone test |
| **UI-19** phone question list | `styles.css`: under 900 px, `.split > .qnav { order: 2 }`, so the chart comes first and the list follows. | Live: qtext at 319 px, nav at 1656 px |
| **UI-20** sort and audience in URL | Explorer `?sort=0` (`Explorer.tsx:53`). Audience `?aud=` (JSON of cuts and answers without the wording, rebuilt from the book; `Audience.tsx:14`). | Live: `?sort=0` written |
| **UI-21** empty catalogue | `Library.tsx:39` shows an empty state when there is no wave. "Since …" is guarded when there are no trackers, and the hero falls back to the newest wave. | Code read |
| **UI-22** time zone | `bits.tsx:93` `eastern()` formats times as US Eastern with the zone label (EDT/EST), for the fielding window in provenance and every Schedule time. The Schedule lede now says "Monday around 8:30 AM EDT (7:30 AM EST)". | Live: "8:27 AM EDT – 2:35 PM EDT" |
| **UI-23** bar contrast | `theme.ts:11` adds a new `bar` token. Light #5E8CA3 is 3.65:1 on white and 3.5:1 on #FAFAFA. Dark keeps #A3C0CE at 7.5:1 on #2D2A29. It is used for single-series bars, `blues(1)`, and the Explorer legend through `--bar`. `sky` is unchanged for neutral scale answers. | Computed; screenshots |
| **UI-25** dead-end error | `bits.tsx:76-86`: `Failure` always offers "Back to the survey library" and hides Refresh for not-found errors. | Live `/w/999999` |
| Performance | Library prefetches the latest tracker wave's book (`Library.tsx:35`). The idle callback also loads the Overview and Explorer chunks (`main.tsx`). Every book's verdicts are computed once and cached by WeakMap, where three pages used to recompute them. /me and methodology are fetched once per session. | Live request log |
| Dev-only bug found | `EChart.tsx`: `replaceMerge` listed `dataZoom` and `visualMap`, which are not registered. ECharts' dev build asserts and the chart screens crashed under `vite` dev. The production build strips the assert, so the live site was not affected. Removed. | Live dev walk |

## Left for others / known limits

- **Glance takeaways still contradict the headline.** The takeaway text comes from `api/dashboards.py`. On wave 415 it still says "Biggest significant move … +17.0 pts" using its own test. The backend should use the same `sig_*` verdict or say "single comparison". It cannot be fixed safely in the UI.
- **No `verified` field.** The backend sends population, weighting, in_field, client and visibility, but not `verified`, so the badge stays hidden until it does.
- **Undo is client-side.** A delete is held for 6 s before the DELETE is sent. Closing the tab inside that window keeps the item, which is the safe direction. There is no server-side soft delete.
- **Reading order on phones.** The CSS `order` puts the question list after the chart visually, but it stays first in DOM and tab order.
- **perf.ts in the entry.** It is still in the entry chunk (about 567 lines). Moving it behind `?perf=1` is a follow-up.
