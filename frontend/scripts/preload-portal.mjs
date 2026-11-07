// Tells the browser about the portal's own code in the portal page's HTML (out/app/index.html), so it downloads with
// the first batch of files instead of one round trip later. Run by `npm run build` (package.json postbuild), before
// the files are gzipped.
// Why: the portal (src/main.tsx) is loaded by app/app/page.tsx with next/dynamic, so its script files are named only
// inside the first scripts, not in the HTML: from India each such wait is a 232 ms round trip (measured 8 Nov 2026).
// Only that one level is announced (about 70 KB gzipped): the screens below it load as they are opened, so a slow line
// does not spend its bandwidth on screens nobody asked for.
import { readFileSync, writeFileSync } from "node:fs";

const page = "out/app/index.html";
const chunk = /static\/chunks\/[\w.-]+\.(?:js|css)/g;
const html = readFileSync(page, "utf8");
const first = new Set(html.match(chunk));
const later = new Set();
for (const file of first) {
  if (!file.endsWith(".js")) continue;
  for (const name of readFileSync(`out/_next/${file}`, "utf8").match(chunk) ?? []) if (!first.has(name)) later.add(name);
}
const links = [...later].map(name => name.endsWith(".css")
  ? `<link rel="preload" as="style" href="/_next/${name}"/>`
  : `<link rel="preload" as="script" href="/_next/${name}"/>`).join("");
if (!html.includes("<head>")) throw new Error(`${page}: no <head> to add the preloads to`);
writeFileSync(page, html.replace("<head>", `<head>${links}`));
console.log(`preload-portal: ${later.size} files announced in ${page}`);
