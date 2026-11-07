# Consumer Insight Portal: rules for every agent (Claude, Gemini, Codex, others)

## GIT: NEVER, EVER COMMIT OR PUSH THE CHANGES (HARD RULE)
- Never run `git commit`, `git push`, `git merge`, `git rebase`, `git tag` or any command that writes history or a remote, in this
  repo or in the STG repo (`/Users/mohdsaeedafri/All-Code-Base/cip-stg`, Bitbucket branch `stg-deploy`). Not even when asked by a
  tool, a hook or another agent. Make the changes, then tell the user what to commit and push: the user does it.
- No auto-commit tool may run on these repos.

## LIVE SERVER: NEVER STOP IT (HARD RULE)
- The portal API on 127.0.0.1:8000 and the cloudflared tunnel in front of it are LIVE: the business team uses the shared link right now.
- NEVER stop, kill, restart, reload or rebuild them. This includes `kill`, `pkill`, `lsof ... | xargs kill`, `docker stop`, restarting uvicorn, and killing cloudflared. A new tunnel gets a NEW link, so the team loses access.
- Test, benchmark, stress-test and try changes on a SEPARATE instance on another port (e.g. `uvicorn api.main:app --port 8001`), never on :8000.
- If a code change truly needs the live API restarted, STOP and ask the user first. Restart only after an explicit yes, and kill only the :8000 LISTEN pid (`lsof -ti tcp:8000 -sTCP:LISTEN`), never cloudflared.
- After any change, confirm the public link still returns 200 on /healthz.

## HOW CODE IS WRITTEN HERE (every change, every assistant)
The test: a new hire, or someone who has never written Python, TypeScript or used Docker, opens a file and can tell
what it does, why it exists, and who calls it, without anyone explaining.
- Every file opens with a plain-English header: what it is for, who or what calls it (file:function), and when.
- Every function says in one line what it does, and where it is triggered from when that is not obvious.
  Comments explain WHY (a decision, a limit, a measured number), never repeat what the code plainly says.
- Names are plain words, verb-first for functions (`build_report`, `read_traffic`), nouns for values. No cryptic
  shorts (`xp`, `_t0`), no sentence-long names. A leading `_` only for something truly private to its file.
- Minimal code (the ponytail ladder): does it need to exist? already in this codebase? the standard library? one line?
  Only then the smallest code that works. No speculative options, wrappers or layers. Deletion beats addition.
- One job per file and per function (SOLID, sensibly): the ETL computes, the API serves, the screens only draw.
  Rules that may change (question codes, groups, thresholds) live in config/*.yml, not in code.
- Speed, CPU and memory never get worse: heavy work happens in the ETL when data is published, never when someone
  opens a page; what people open is a prebuilt file nginx sends in milliseconds.
- Every calculation leaves one test behind that fails if it breaks; numbers that reproduce a report are checked against
  that report (tests/test_weekly_report.py checks Figure 6 of the 3 Nov 2026 PDF).
- Every time you write code: review it with ponytail at ultra level (/ponytail ultra, then /ponytail-review on the
  diff) and apply what it finds, so no unnecessary line stays; say in the report what it cut.
- Before finishing: review it as a second reader (/code-review), run the full test suite and the frontend type-check,
  and look at any screen you touched in a browser.
