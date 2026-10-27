# CIP final remediation — before/after benchmarks

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Base: clean detached `6f978b0595b2c71c064991ae10b832514637a0da`  
Patched: identical detached base plus the review patch  
State: uncommitted local patch  
Runner: `scripts/cip_final_benchmark.py`  
Cross-links: [verdict](00_EXECUTIVE_VERDICT.md), [changes](02_CODE_CHANGES_WITH_EVIDENCE.md), [approvals](04_OPEN_DB_APPROVAL_ITEMS.md)

## Controls and limitations

- Apple host, Python 3.13, same virtual environment and filesystem.
- Separate processes for base and patched runs; five samples per case.
- Temporary SQLite databases with checked-in schema and foreign keys enabled.
- Synthetic data only; sockets blocked and live integration variables blank.
- Output hashes exclude volatile manifests but include every decompressed published JSON path/body.
- `p95` is the fourth ordered observation of five, as implemented by the checked-in runner; raw samples are below.
- SQLite does not reproduce MySQL collation, execution plans, rows examined, TempTable behavior, `LOAD DATA`, network latency, CPU/IOPS or shared-server contention.

## Qualtrics snapshot import

| Respondents | Variant | elapsed samples, seconds | median | p95 | SQL statements/sample | transactions/sample | peak RSS | output SHA-256 |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 100 | Base | 0.093087, 0.080945, 0.083599, 0.082991, 0.083133 | 0.083133 | 0.083599 | 359 | 118 | 91,111,424 B | `94b9fc1b…b25220` |
| 100 | Patched | 0.037454, 0.026560, 0.027353, 0.026539, 0.026617 | 0.026617 | 0.027353 | 63 | 19 | 91,373,568 B | `94b9fc1b…b25220` |
| 500 | Base | 0.407930, 0.462774, 0.402584, 0.412692, 0.413002 | 0.412692 | 0.413002 | 1,559 | 518 | 96,075,776 B | `dcf3c323…b88f3` |
| 500 | Patched | 0.096586, 0.084365, 0.084027, 0.084567, 0.085354 | 0.084567 | 0.085354 | 63 | 19 | 96,665,600 B | `dcf3c323…b88f3` |
| 2,000 | Base | 1.782597, 1.781923, 1.782160, 1.755413, 1.735497 | 1.781923 | 1.782160 | 6,060 | 2,018 | 105,316,352 B | `11fb69a6…f1deb` |
| 2,000 | Patched | 0.318133, 0.306260, 0.307043, 0.305703, 0.305406 | 0.306260 | 0.307043 | 66 | 19 | 112,377,856 B | `11fb69a6…f1deb` |

Observed SQLite median reductions: 68.0%, 79.5% and 82.8%. Query and transaction counts become bounded instead of respondent-linear. Each size has identical base/patched output hashes and zero errors. Peak RSS did not improve at 2,000 respondents; it rose about 6.7 MiB, so no memory improvement is claimed.

This is a demonstrated local application/round-trip improvement, not a MySQL/staging speedup.

## Publisher

Each wave has 404 synthetic respondents and one question. Every base/patched pair produced the same output hash and byte count:

| Waves | Output SHA-256 | JSON bytes |
|---:|---|---:|
| 2 | `a4183f033240d7b2864816f00fb1a1410e495c1cf902e97a97e7b537a05248a6` | 9,030 |
| 8 | `fdc994b873760427fa2d7da9618d7cb8d5a9c6d0d010e85f29565ec5c000fdaa` | 35,519 |
| 24 | `18665e5056445ee3565512f98eb8e3b7fc7ad6de277bd317453a9373e5690e3b` | 106,331 |

SQL result: every base sample executed one discovery query; every patched sample executed zero. Total SQL statements fell by exactly one: 29→28 (2 waves), 89→88 (8), 249→248 (24). The two `srv_answer` reads per fresh wave remain.

| Waves/jobs | Base samples (s) | Patched samples (s) | Base median/p95 | Patched median/p95 |
|---|---|---|---|---|
| 2/1 | .017847, .007317, .007135, .007294, .007086 | .017450, .007101, .007152, .007229, .007047 | .007294/.007317 | .007152/.007229 |
| 2/2 | .016951, .008236, .007798, .007833, .007537 | .016975, .008146, .007818, .007881, .007704 | .007833/.008236 | .007881/.008146 |
| 2/4 | .016870, .007793, .007791, .007563, .008535 | .016727, .007957, .007739, .007985, .007578 | .007793/.008535 | .007957/.007985 |
| 8/1 | .032786, .023727, .022535, .022770, .022690 | .033481, .023285, .023418, .023585, .023068 | .022770/.023727 | .023418/.023585 |
| 8/2 | .032111, .025533, .024901, .024990, .024528 | .033007, .025639, .025560, .023608, .025462 | .024990/.025533 | .025560/.025639 |
| 8/4 | .054209, .047872, .046278, .049735, .051194 | .055278, .054186, .052693, .052755, .052927 | .049735/.051194 | .052927/.054186 |
| 24/1 | .075010, .064402, .063909, .063755, .063904 | .076304, .067879, .065957, .067130, .065892 | .063909/.064402 | .067130/.067879 |
| 24/2 | .080141, .070127, .070386, .074914, .074594 | .075904, .067894, .071119, .066442, .071110 | .074594/.074914 | .071110/.071119 |
| 24/4 | .142885, .133424, .136045, .134825, .138499 | .159694, .153796, .152930, .155764, .154201 | .136045/.138499 | .154201/.155764 |

Peak RSS was higher in every patched publisher process by roughly 5–6 MiB. The code no longer retains cut and people dictionaries together, but process-level RSS did not demonstrate a gain and Python's high-water mark cannot show released-object timing. **NO PUBLISHER WALL-CLOCK OR RSS PERFORMANCE GAIN DEMONSTRATED.** The proven improvement is removal of one exact discovery SQL statement with identical artifacts.

SQLite favored one worker at 8 and 24 waves; four workers was slower in both trees. This does not establish the best shared-MySQL setting. Default remains four pending an approved representative server run.

## Not measured

- Rows examined: SQLite does not expose a comparable MySQL counter.
- MySQL plan/collation/FK/trigger parity: unavailable.
- Historic slow-log attribution: not inferable from synthetic runs.
- Shared-server CPU, IOPS, lock waits, TempTable spills and connection pressure: no staging workload was run.
