/// <reference types="vite/client" />
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Link, Navigate, RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/montserrat";
import "./styles.css";
import Shell from "./components/Shell";
import Profiled from "./components/Profiled";
import { Loading } from "./components/bits";
import { Busy } from "./api";

// Dynamically load React Scan only when enabled: keeps baseline bundle tiny & RAM minimal
if (import.meta.env.DEV) {   // dev server only: production builds drop react-scan (≈ 400 KB) entirely
  const isScanEnabled = localStorage.getItem("cip_scan") === "1" || location.search.includes("scan=1");
  if (isScanEnabled) {
    import("react-scan").then(({ scan }) => {
      scan({
        enabled: true,
        log: false,
        trackUnnecessaryRenders: true,
      });
    });
  }
}

const page = (name: string, load: () => Promise<{ default: React.ComponentType }>) => {
  const Page = lazy(load);
  return (
    <Suspense fallback={<Loading what="screen" />}>
      <Profiled id={name}>
        <Page />
      </Profiled>
    </Suspense>
  );
};

const router = createBrowserRouter([{
  element: <Shell />,
  errorElement: (
    <div style={{ padding: "40px 28px", maxWidth: 640, margin: "40px auto", background: "var(--surface)", borderRadius: "var(--radius)", border: "1px solid var(--mist)" }}>
      <p style={{ color: "var(--ink)", fontWeight: 700, margin: 0 }}>Portal Notice</p>
      <h2 style={{ margin: "8px 0" }}>Unable to display this view</h2>
      <p style={{ color: "var(--ink-2)", lineHeight: 1.55 }}>An unexpected application event occurred. You can return to the Survey Library.</p>
      <p style={{ marginTop: 16 }}><a href="/" style={{ color: "#fff", background: "var(--red)", padding: "8px 14px", borderRadius: 8, textDecoration: "none", fontWeight: 600 }}>Return to Library</a></p>
    </div>
  ),
  children: [
    { path: "/", element: page("Page:Library", () => import("./pages/Library")) },
    { path: "/library", element: <Navigate to="/" replace /> },
    { path: "/search", element: page("Page:Search", () => import("./pages/Search")) },
    { path: "/schedule", element: page("Page:Schedule", () => import("./pages/Schedule")) },
    { path: "/w/:id", element: page("Page:Overview", () => import("./pages/Overview")) },
    { path: "/w/:id/questions/:q?", element: page("Page:Explorer", () => import("./pages/Explorer")) },
    { path: "/w/:id/crosstab/:q?", element: page("Page:Crosstab", () => import("./pages/Crosstab")) },
    { path: "/w/:id/trends/:q?", element: page("Page:Trends", () => import("./pages/Trends")) },
    { path: "/w/:id/compare/:q?", element: page("Page:Compare", () => import("./pages/Compare")) },
    { path: "/w/:id/audience/:q?", element: page("Page:Audience", () => import("./pages/Audience")) },
    { path: "/ask", element: page("Page:Ask", () => import("./pages/Ask")) },
    { path: "/w/:id/changes", element: page("Page:Changes", () => import("./pages/Changes")) },
    { path: "/w/:id/survey/:q?", element: page("Page:Survey", () => import("./pages/Survey")) },
    {
      path: "*",
      element: (
        <div className="card pad" style={{ maxWidth: 640, margin: "24px 0" }}>
          <p className="eyebrow">404</p>
          <h2 style={{ margin: "6px 0 10px" }}>Page not found</h2>
          <p className="lede">The requested report or route does not exist.</p>
          <p style={{ marginTop: 14 }}>
            <Link className="btn primary" to="/">Return to Survey Library</Link>
          </p>
        </div>
      )
    },
  ],
}]);

const queries = new QueryClient({ defaultOptions: { queries: {
  refetchOnWindowFocus: false,
  retry: (count, error) => (error instanceof Busy ? count < 3 : count < 1),   // busy: up to 3 tries, 3 s apart
  retryDelay: (_, error) => (error instanceof Busy ? 3000 : 800),
} } });
createRoot(document.getElementById("root")!).render(
  <StrictMode><QueryClientProvider client={queries}><RouterProvider router={router} /></QueryClientProvider></StrictMode>);

// the chart library (≈190 KB gzipped) loads while the first screen is idle, so the first chart never waits for it
const idle = window.requestIdleCallback ?? ((run: () => void) => setTimeout(run, 1500));
idle(() => { void import("./components/EChart"); });
