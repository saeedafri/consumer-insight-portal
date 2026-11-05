"use client";
import dynamic from "next/dynamic";

// The signed-in portal: the React Router app (src/main.tsx), run only in the browser. The server serves this one
// page for every /app/... path, and the app's own router picks the screen.
export default dynamic(() => import("../../src/main"), {
  ssr: false,
  loading: () => <div className="boot" aria-busy="true"><div className="boot-head">Coresight Research · Consumer Insight Portal</div>
    <div className="boot-rail" /><div><div className="boot-main"><b /><s /><s /></div></div></div>,
});
