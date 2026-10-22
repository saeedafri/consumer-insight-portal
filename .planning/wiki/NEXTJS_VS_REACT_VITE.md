# Next.js or React + Vite for CIP

22 Oct 2026. The backend stays Python + FastAPI either way; this is only about the screens.

## The short answer

- **Logged-in portal:** stay on React 19 + Vite. Next.js's extras either need a second Node.js server running next to FastAPI on our single core, or repeat what FastAPI and the pre-built files already do.
- **Public site (product page, methodology, sample charts):** this is where Next.js fits. Build it as static pages (`output: 'export'`), hosted apart from the portal, so nothing new runs on the CIP server.
- **SEO cannot reach pages behind a login**, in any framework: search engines see only the sign-in page. The portal's figures are licensed panel data and must stay out of search results.

## What Next.js offers besides SEO, and whether CIP needs it

| Next.js feature | What it does | Same thing in React + Vite | Cost for CIP | Verdict |
|---|---|---|---|---|
| Server rendering and streaming | Builds the page's HTML on the server for each request | React Router 7 framework mode, or Vite's own server rendering | A Node.js process doing that work on the one core the API uses. Our charts draw in the browser anyway, so first paint gains little | Not needed |
| React Server Components | Parts of the page run only on the server and send no code to the browser | Not in plain Vite; experimental in React Router 7 | Needs a Node.js server. Had a critical remote-code-execution flaw in Dec 2025 (CVE-2025-55182). Our data and statistics live in Python, so these would only pass FastAPI's answers along | Not needed (adds risk) |
| Server Actions | A button or form calls server code directly | React 19 Actions (`useActionState`, `useOptimistic`, `<form action>`) work without a framework and call FastAPI | A second backend with its own sign-in checks; our writes are already FastAPI routes | Not needed |
| File-based routing and nested layouts | Pages and layouts follow the folder structure | React Router 7 gives nested routes, layouts, loaders and per-page code splitting | None | Already have it |
| Data cache, ISR, `"use cache"` | Caches pages and data on the server, refreshes them on a schedule | Our ETL already pre-builds every screen's data as files; TanStack Query caches in the browser | A second cache to keep in step with each weekly publish | Not needed (duplicates our design) |
| Partial prerendering | A static page shell with live parts streamed in | React Router 7 can pre-build static pages | Node.js server plus streaming proxy setup | Not needed |
| Image optimisation | Resizes and converts images on the server | Pre-sized images or a build-time plugin | CPU and memory on our core; the portal shows charts, not photos | Not needed (portal); minor (public site) |
| Font optimisation | Hosts fonts and avoids layout jumps | `@fontsource` (CIP already self-hosts Montserrat this way) | None | Already have it |
| Middleware ("proxy" since Next.js 16) | Code that runs before every page, often for sign-in | nginx `auth_request` plus FastAPI checks: the real security boundary | Next.js itself calls it a last resort; a 2025 flaw (CVE-2025-29927) let requests skip it | Keep sign-in in FastAPI |
| API routes | Backend endpoints written in Node.js | FastAPI | Two backends, two sets of sign-in rules | Not needed |
| Metadata API, sitemap, robots | Page titles, social previews, sitemap.xml | React 19 renders titles and meta tags from any component; a static robots.txt | None | Not needed for the portal (it must stay unindexed); useful for the public site |
| Built-in translation routing | — | `react-i18next` | — | Not needed (Next.js has no built-in i18n routing in the App Router either) |
| Bundling and code splitting | Turbopack, splits code per page | Vite, splits per page with `import()` | — | Same |
| How it runs | `next start` as a Node.js service behind nginx | `vite build` gives plain files nginx serves; nothing extra runs | A new service to run, patch and size on a 1-core box that also runs the live API | Strongly against for the portal |

How much memory a running Next.js server takes: no reliable published figure. Next.js's own guide gives none and says the server keeps every page's code loaded once started, so it grows with the number of pages. Forum reports of 200–600 MB idle are anecdotes; we would measure it before choosing.

Next.js built as static files (`output: 'export'`) runs no server, but then loses middleware, Server Actions, ISR, cookies, redirects, server API routes and image optimisation. It is then a static site generator, which is exactly what a public marketing site needs.

React 19 features available in both: Actions, `useActionState`, `useOptimistic`, `useFormStatus`, `use()`, page titles and meta tags from components, `ref` as a prop. Only Server Components and Server Actions need a server framework.

## Recommendation

1. **Portal:** keep React 19 + Vite + React Router 7, built as static files behind nginx, with FastAPI. Optionally move React Router to its "framework mode" (still static, no server) for typed routes; that is a contained change, not a rewrite.
2. **Public site:** a separate static site, either Next.js (`output: 'export'`) or React Router 7 pre-rendering, on its own address (for example `insights.coresight.com`), linking to the portal (`cip.coresight.com`). Decide first which headline figures, if any, may be public under the panel licence.

## Sources

[Next.js 16](https://nextjs.org/blog/next-16) · [Self-hosting](https://nextjs.org/docs/app/guides/self-hosting) · [Static exports](https://nextjs.org/docs/app/guides/static-exports) · [Proxy](https://nextjs.org/docs/app/api-reference/file-conventions/proxy) · [Memory usage](https://nextjs.org/docs/app/guides/memory-usage) · [React 19](https://react.dev/blog/2024/12/05/react-19) · [Building a React app from scratch](https://react.dev/learn/build-a-react-app-from-scratch) · [RSC vulnerability CVE-2025-55182](https://react.dev/blog/2025/12/03/critical-security-vulnerability-in-react-server-components) · [Middleware bypass CVE-2025-29927](https://fastly.com/blog/cve-2025-29927-authorization-bypass-in-next-js) · [React Router modes](https://reactrouter.com/start/modes) · [React Router pre-rendering](https://reactrouter.com/how-to/pre-rendering) · [Vite build](https://vite.dev/guide/features.html#build-optimizations)
