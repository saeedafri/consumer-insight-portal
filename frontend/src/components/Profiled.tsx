import { Profiler, type ReactNode } from "react";
import { perf } from "../perf";

interface ProfiledProps {
  id: string;
  children: ReactNode;
}

export default function Profiled({ id, children }: ProfiledProps) {
  return (
    <Profiler id={id} onRender={perf.onRenderProfiler}>
      {children}
    </Profiler>
  );
}

