"use client";
import { useEffect, useState } from "react";

// Same control and storage key ("cip-theme") as the portal, so the choice carries between the public pages and /app.
export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => { setTheme((document.documentElement.dataset.theme as "light" | "dark") || "light"); }, []);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("cip-theme", next); } catch {}
  };
  return (
    <button className="theme-btn" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path fill="currentColor" d={theme === "dark"
          ? "M12 7a5 5 0 110 10 5 5 0 010-10zm0-5l1 3h-2zm0 20l-1-3h2zM2 12l3-1v2zm20 0l-3 1v-2zM4.9 4.9l2.8 1.4-1.4 1.4zm14.2 14.2l-2.8-1.4 1.4-1.4zM4.9 19.1l1.4-2.8 1.4 1.4zM19.1 4.9l-1.4 2.8-1.4-1.4z"
          : "M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"} />
      </svg>
    </button>
  );
}
