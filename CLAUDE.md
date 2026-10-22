# Consumer Insight Portal: rules for every agent (Claude, Gemini, Codex, others)

## LIVE SERVER: NEVER STOP IT (HARD RULE)
- The portal API on 127.0.0.1:8000 and the cloudflared tunnel in front of it are LIVE: the business team uses the shared link right now.
- NEVER stop, kill, restart, reload or rebuild them. This includes `kill`, `pkill`, `lsof ... | xargs kill`, `docker stop`, restarting uvicorn, and killing cloudflared. A new tunnel gets a NEW link, so the team loses access.
- Test, benchmark, stress-test and try changes on a SEPARATE instance on another port (e.g. `uvicorn api.main:app --port 8001`), never on :8000.
- If a code change truly needs the live API restarted, STOP and ask the user first. Restart only after an explicit yes, and kill only the :8000 LISTEN pid (`lsof -ti tcp:8000 -sTCP:LISTEN`), never cloudflared.
- After any change, confirm the public link still returns 200 on /healthz.
