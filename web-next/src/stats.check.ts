// node src/stats.check.ts — the significance maths the screens rely on, against known values.
import assert from "node:assert/strict";
import { fdr, moe, pValue, significant, survivesFdr } from "./stats.ts";

assert.ok(Math.abs(pValue(50, 400, 50, 400) - 1) < 1e-6);                 // no difference
assert.ok(Math.abs(pValue(55, 404, 45, 401) - 0.0046) < 0.0005);         // z ≈ 2.84
assert.equal(significant(55, 404, 48, 401), true);
assert.equal(significant(55, 404, 52, 401), false);
assert.ok(Math.abs(moe(50, 400) - 4.9) < 0.01);                          // ±4.9 pts at n=400
// Benjamini–Hochberg, the textbook case: of p = .01 .04 .03 .005 at q = .05, all four survive (.04 ≤ 4/4·.05)
assert.deepEqual(survivesFdr([0.01, 0.04, 0.03, 0.005]), [true, true, true, true]);
// a lone p = .04 among 20 nulls does not survive, though it is "significant" alone
assert.deepEqual(survivesFdr([0.04, ...Array(19).fill(0.6)]).filter(Boolean).length, 0);
// untestable rows (null) stay out of m: p = 1.3e-4 survives among 368 tests, but not when 209 p = 1 rows are padded in (UI-01)
const real = [1.3e-4, ...Array(367).fill(0.9)];
assert.equal(fdr([...real, ...Array(209).fill(null)])[0], true);
assert.equal(survivesFdr([...real, ...Array(209).fill(1)])[0], false);
assert.deepEqual(fdr([null, 0.01, null]), [false, true, false]);
console.log("stats checks passed");
