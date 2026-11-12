// The signed-in portal's front door: the list of screens and their addresses (/app/w/532/questions, /app/logs…).
// Loaded by app/app/page.tsx in the browser. Each screen's code downloads only when it is first opened; the first
// screen's starts at once, and the screens most often opened next download while the browser is idle.
"use client";
import { lazy, StrictMode, Suspense } from "react";
import { createBrowserRouter, Link, RouterProvider } from "react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import "./fonts.css";
import "./styles.css";
import Shell from "./components/Shell";
import { SkeletonScreen } from "./components/bits";
import { queries } from "./api";

const page = (load: () => Promise<{ default: React.ComponentType }>) => {
  const Page = lazy(load);
  return (
    <Suspense fallback={<SkeletonScreen kind="page" />}>
      <Page />
    </Suspense>
  );
};

const router = createBrowserRouter([{
  element: <Shell />,
  errorElement: (
    <div style={{ padding: "40px 28px", maxWidth: 640, margin: "40px auto", background: "var(--surface)", borderRadius: "var(--radius)", border: "1px solid var(--mist)" }}>
      <p style={{ color: "var(--ink)", fontWeight: 700, margin: 0 }}>Portal Notice</p>
      <h1 style={{ margin: "8px 0", fontSize: 24 }}>Unable to display this view</h1>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.55 }}>An unexpected application event occurred. You can return to the Survey Library.</p>
      <p style={{ marginTop: 16 }}><a href="/app/" style={{ color: "#fff", background: "var(--red)", padding: "8px 14px", borderRadius: 8, textDecoration: "none", fontWeight: 600 }}>Return to Library</a></p>
    </div>
  ),
  children: [
    { path: "/", element: page(() => import("./screens/Home")) },
    { path: "/library", element: page(() => import("./screens/Library")) },
    { path: "/search", element: page(() => import("./screens/Search")) },
    { path: "/schedule", element: page(() => import("./screens/Schedule")) },
    { path: "/w/:id", element: page(() => import("./screens/Overview")) },
    { path: "/w/:id/questions/:q?", element: page(() => import("./screens/Explorer")) },
    { path: "/w/:id/crosstab/:q?", element: page(() => import("./screens/Crosstab")) },
    { path: "/w/:id/trends/:q?", element: page(() => import("./screens/Trends")) },
    { path: "/w/:id/compare/:q?", element: page(() => import("./screens/Compare")) },
    { path: "/w/:id/audience/:q?", element: page(() => import("./screens/Audience")) },
    { path: "/ask", element: page(() => import("./screens/Ask")) },
    { path: "/boards/:id?", element: page(() => import("./screens/Boards")) },
    { path: "/whats-new", element: page(() => import("./screens/WhatsNew")) },
    { path: "/sectors", element: page(() => import("./screens/Sectors")) },
    { path: "/retailers", element: page(() => import("./screens/Retailers")) },
    { path: "/channels", element: page(() => import("./screens/Channels")) },
    { path: "/trackers/:code?", element: page(() => import("./screens/Trackers")) },
    { path: "/expectations", element: page(() => import("./screens/Expectations")) },
    { path: "/methodology", element: page(() => import("./screens/Methodology")) },
    { path: "/account", element: page(() => import("./screens/Account")) },
    { path: "/api-guide", element: page(() => import("./screens/ApiGuide")) },
    { path: "/logs", element: page(() => import("./screens/Logs")) },
    { path: "/ingest", element: page(() => import("./screens/Ingest")) },
    { path: "/fieldwork", element: page(() => import("./screens/Fieldwork")) },
    { path: "/fieldwork/:survey", element: page(() => import("./screens/FieldworkSurvey")) },
    { path: "/access", element: page(() => import("./screens/Access")) },
    { path: "/forsta/:section?", element: page(() => import("./screens/Forsta")) },
    { path: "/w/:id/changes", element: page(() => import("./screens/Changes")) },
    { path: "/w/:id/report", element: page(() => import("./screens/Report")) },
    { path: "/w/:id/survey/:q?", element: page(() => import("./screens/Survey")) },
    {
      path: "*",
      element: (
        <div className="card pad" style={{ maxWidth: 640, margin: "24px 0" }}>
          <p className="eyebrow">404</p>
          <h1 style={{ margin: "6px 0 10px", fontSize: 24 }}>Page not found</h1>
          <p className="lede">The requested report or route does not exist.</p>
          <p style={{ marginTop: 14 }}>
            <Link className="btn primary" to="/library">Return to Survey Library</Link>
          </p>
        </div>
      )
    },
  ],
}], { basename: "/app" });

// the first screen's chunk starts downloading now, in parallel with React's first render, not after the router matches it
if (location.pathname === "/app/") void import("./screens/Library");
else if (/^\/app\/w\/\d+\/?$/.test(location.pathname)) void import("./screens/Overview");

export default function Portal() {
  return <StrictMode><QueryClientProvider client={queries}><RouterProvider router={router} /></QueryClientProvider></StrictMode>;
}

// the chart library (≈190 KB gzipped) loads while the first screen is idle, so the first chart never waits for it
const idle = window.requestIdleCallback ?? ((run: () => void) => setTimeout(run, 1500));
// and the screens most often opened next (a wave's overview and its questions, ≈ 7 KB gzipped together)
idle(() => { void import("./components/EChart"); void import("./screens/Overview"); void import("./screens/Explorer"); });
