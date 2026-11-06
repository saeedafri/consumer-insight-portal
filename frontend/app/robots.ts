// robots.txt for search engines: what they may index (the public site, not the portal). Built once, as a file.
import type { MetadataRoute } from "next";
import { SITE } from "./site";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/", disallow: ["/app/", "/auth/", "/api/"] }, sitemap: `${SITE}/sitemap.xml` };
}
