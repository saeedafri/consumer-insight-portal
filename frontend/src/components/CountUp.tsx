// A headline figure counts up to its value once (450 ms, decelerating), keeping its own format: "62.9%", "190k",
// "+3.5 pts". Text without a number, and readers who asked for reduced motion, get the final value at once.
import { useEffect, useRef, useState } from "react";
import { REDUCED_MOTION } from "./EChart";

const NUMBER = /-?\d[\d,]*(\.\d+)?/;

export default function CountUp({ text }: { text: string }) {
  const [shown, setShown] = useState(() => (REDUCED_MOTION ? text : text.replace(NUMBER, m => (0).toFixed(m.split(".")[1]?.length ?? 0))));
  const from = useRef(0);
  useEffect(() => {
    const match = text.match(NUMBER);
    if (!match || REDUCED_MOTION) { setShown(text); return; }
    const target = Number(match[0].replace(/,/g, "")), decimals = match[1] ? match[1].length - 1 : 0;
    const grouped = match[0].includes(","), start = from.current, t0 = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const k = Math.min(1, Math.max(0, now - t0) / 450), eased = 1 - Math.pow(2, -10 * k);   // a frame stamp can predate t0
      const value = (start + (target - start) * (k === 1 ? 1 : eased)).toFixed(decimals);
      const formatted = grouped ? Number(value).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : value;
      setShown(text.replace(match[0], formatted));
      if (k < 1) frame = requestAnimationFrame(tick); else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [text]);
  return <span className="count-up">{shown}</span>;
}
