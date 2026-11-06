// Measures how long a part of the screen takes to draw, for the developers' speed meter (src/perf.ts). When the meter
// is off (every normal visitor) it adds nothing: the children are drawn as they are, with no React <Profiler> around.
import { Profiler, type ReactNode } from "react";
import { perf } from "../perf";

export default function Profiled({ id, children }: { id: string; children: ReactNode }) {
  if (!perf.enabled) return <>{children}</>;
  return <Profiler id={id} onRender={perf.onRenderProfiler}>{children}</Profiler>;
}
