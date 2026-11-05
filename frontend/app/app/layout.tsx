import "./boot.css";

export const metadata = { title: "Portal", robots: { index: false, follow: false } };

// Theme before first paint: the saved choice, else the system setting (no flash of the wrong theme)
const theme = `try { var t = localStorage.getItem("cip-theme"); } catch (e) {}
document.documentElement.dataset.theme = t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");`;

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return <><script dangerouslySetInnerHTML={{ __html: theme }} /><div id="root">{children}</div></>;
}
