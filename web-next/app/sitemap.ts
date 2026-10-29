import type { MetadataRoute } from "next";
import { SITE } from "./site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/", "/features/", "/methodology/", "/sign-in/"].map(path => ({ url: SITE + path, changeFrequency: "weekly" }));
}
