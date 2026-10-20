import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/montserrat";
import "./styles.css";
import Shell from "./components/Shell";
import { Loading } from "./components/bits";

const page = (load: () => Promise<{ default: React.ComponentType }>) => {
  const Page = lazy(load);
  return <Suspense fallback={<Loading what="screen" />}><Page /></Suspense>;
};

const router = createBrowserRouter([{
  element: <Shell />,
  children: [
    { path: "/", element: page(() => import("./pages/Library")) },
    { path: "/search", element: page(() => import("./pages/Search")) },
    { path: "/w/:id", element: page(() => import("./pages/Overview")) },
    { path: "/w/:id/questions/:q?", element: page(() => import("./pages/Explorer")) },
    { path: "/w/:id/crosstab/:q?", element: page(() => import("./pages/Crosstab")) },
    { path: "/w/:id/trends/:q?", element: page(() => import("./pages/Trends")) },
    { path: "/w/:id/changes", element: page(() => import("./pages/Changes")) },
    { path: "/w/:id/survey/:q?", element: page(() => import("./pages/Survey")) },
  ],
}]);

const queries = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });
createRoot(document.getElementById("root")!).render(
  <StrictMode><QueryClientProvider client={queries}><RouterProvider router={router} /></QueryClientProvider></StrictMode>);
