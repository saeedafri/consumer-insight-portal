// sitemap.xml for search engines: the public pages' addresses. Built once, as a file.
import type { MetadataRoute } from "next";
import { SITE } from "./site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", "/this-week/", "/features/", "/data/", "/methodology/", "/sign-in/"].map(path => ({ url: SITE + path, changeFrequency: "weekly" }));
}
