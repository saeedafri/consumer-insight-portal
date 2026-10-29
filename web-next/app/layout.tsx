import type { Metadata, Viewport } from "next";
import { NAME, SITE } from "./site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: NAME, template: `%s · ${NAME}` },
  description: "Weekly US consumer survey data from Coresight Research: explore every question by generation, income and region, track trends and compare waves.",
  applicationName: NAME,
  icons: "/favicon.png",
  openGraph: { type: "website", siteName: NAME, images: "/coresight-logo.png" },
  twitter: { card: "summary" },
};

export const viewport: Viewport = { themeColor: "#2D2A29" };

export default function Root({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
