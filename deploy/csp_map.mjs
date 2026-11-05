// nginx map from page address to the SHA-256 hashes of that page's inline scripts (Next.js's own, the theme one),
// for the Content-Security-Policy in deploy/cip_headers.conf. One list per page, not one list for the whole site:
// nginx refuses a single parameter over 4 KB, which the whole site's list passed (Nov 2026), and each page then
// allows only its own scripts.
//   node deploy/csp_map.mjs frontend/out > cip_csp_map.conf
import { createHash } from "crypto";
import { readdirSync, readFileSync } from "fs";

const site = process.argv[2];
const lines = ["map $uri $page_script_hashes {", '  default "";'];
for (const page of readdirSync(site, { recursive: true }).filter((n) => n.endsWith(".html")).sort()) {
  const html = readFileSync(`${site}/${page}`, "utf8");
  const hashes = [...new Set([...html.matchAll(/<script(?: id="\w+")?>([\s\S]*?)<\/script>/g)]
    .map((m) => `'sha256-${createHash("sha256").update(m[1]).digest("base64")}'`))].sort().join(" ");
  const file = `/${page}`;
  if (file.endsWith("/index.html")) {   // try_files leaves $uri as /x/, /x/index.html or even /x//index.html
    const dir = file.slice(0, -"/index.html".length).replace(/[^\w/-]/g, "\\$&");
    lines.push(`  "~^${dir}/+(index\\.html)?$" "${hashes}";`);
  } else lines.push(`  "${file}" "${hashes}";`);
  if (file === "/app/index.html") lines.push(`  ~^/app/ "${hashes}";`);   // every deep link into the app gets this page
}
lines.push("}");
console.log(lines.join("\n"));
