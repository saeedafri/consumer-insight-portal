"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";

// All motion is gated on html.anim, added here only when JS runs AND motion is allowed. No scroll handlers:
// IntersectionObserver fires on enter, so there is no per-frame work. Without JS or with reduced motion,
// nothing is hidden and nothing animates — the page is complete and readable for crawlers and everyone.
export default function Motion() {
  const path = usePathname();
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = document.documentElement;
    root.classList.add("anim");
    const reveal = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    document.querySelectorAll(".reveal, .roll").forEach((el) => reveal.observe(el));
    // the gian-style active word: whichever list line crosses the middle of the screen brightens
    const active = new IntersectionObserver((entries) => {
      for (const e of entries) e.target.classList.toggle("active", e.isIntersecting);
    }, { rootMargin: "-48% 0px -48% 0px" });
    document.querySelectorAll(".roll-item").forEach((el) => active.observe(el));
    // safety net: a heading or block must never stay hidden. If the observer hasn't revealed something a few
    // seconds in (odd viewport, a capture tool that never scrolls, a missed callback), reveal all that remains.
    const sweep = () => document.querySelectorAll(".reveal:not(.in), .roll:not(.in)").forEach((el) => el.classList.add("in"));
    const fallback = window.setTimeout(sweep, 4000);
    return () => { reveal.disconnect(); active.disconnect(); clearTimeout(fallback); };
  }, [path]);
  return null;
}
