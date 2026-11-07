// All motion is gated on html.anim, added here only when JS runs AND motion is allowed. No scroll handlers:
// IntersectionObserver fires on enter, so there is no per-frame work. Without JS or with reduced motion,
// nothing is hidden and nothing animates — the page is complete and readable for crawlers and everyone.
"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function Motion() {
  const path = usePathname();
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = document.documentElement;
    root.classList.add("anim");
    const reveal = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    // a block lifts into place as it enters view; it is never hidden, so nothing waits on this to be read
    document.querySelectorAll(".reveal").forEach((el) => reveal.observe(el));
    return () => reveal.disconnect();
  }, [path]);
  return null;
}
