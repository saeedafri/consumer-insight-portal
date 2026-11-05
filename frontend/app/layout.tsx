import type { Metadata, Viewport } from "next";
import { NAME, SITE } from "./site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: NAME, template: `%s · ${NAME}` },
  description: "Weekly US consumer survey data from Coresight Research: explore every question by generation, income and region, track trends and compare waves.",
  applicationName: NAME,
  icons: "/favicon.png",
  openGraph: { type: "website", siteName: NAME, title: NAME, description: "Weekly US consumer survey data from Coresight Research — explore by audience, track trends and test for significance.", images: [{ url: "/og.png", width: 1200, height: 630, alt: NAME }] },
  twitter: { card: "summary_large_image", title: NAME, description: "Weekly US consumer survey data from Coresight Research.", images: ["/og.png"] },
  robots: { index: true, follow: true },
  keywords: ["consumer survey", "US consumer tracker", "retail insights", "Coresight Research", "weekly consumer data"],
};

export const viewport: Viewport = { themeColor: "#2D2A29" };

const theme = `try { var t = localStorage.getItem("cip-theme"); } catch (e) {}
document.documentElement.dataset.theme = t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");`;

export default function Root({ children }: { children: React.ReactNode }) {
  return <html lang="en"><head><script dangerouslySetInnerHTML={{ __html: theme }} /></head><body>{children}</body></html>;
}
