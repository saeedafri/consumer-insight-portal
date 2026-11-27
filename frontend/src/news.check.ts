// node src/news.check.ts — the left menu's "New" badges (news.ts): a first visit stays quiet, news shows, opening clears it.
import assert from "node:assert/strict";
import { fresh, remember } from "./news.ts";

const first = remember({ library: 700, boards: undefined }, {});
assert.deepEqual(first, { library: 700 });                                           // first visit: seen, no badge
assert.deepEqual([...fresh({ library: 700 }, first)], []);
const later = { library: 725, us_tracker: 725, whats_new: Date.parse("2026-11-27") };
const seen = { library: 700, us_tracker: 725, whats_new: Date.parse("2026-11-26") };
assert.deepEqual([...fresh(later, seen)], ["library", "whats_new"]);                 // a new survey, a new What's new entry
const opened = remember(later, seen, "library");
assert.deepEqual([...fresh(later, opened)], ["whats_new"]);                          // opening the Library clears its badge only
assert.deepEqual([...fresh({ boards: undefined }, { boards: 5 })], []);              // nothing known yet: no badge
console.log("news.check: ok");
