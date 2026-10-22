"""Tell people what a pipeline run did: one email per loaded survey, one per failure.

A loaded survey's email is an HTML report (fieldwork, load and verification,
the survey calendar, core measures against the previous wave) with the files
the data team works from, in their formats:

  Cross Tabs / Holiday Status Cross Tabs / Inflation_Sentiment Cross Tabs
      their Forsta cross-tab workbooks (Summary, Percentages, Counts), rebuilt
      from cip_stg with etl/crosstab_export.py — a banner set is attached only
      when the wave's questionnaire can fill it
  Weekly Line-By-Line  one row per qualified respondent, their headers and order
                       (tracker waves; config/tracker_line.yml)

Runs that find nothing to do send nothing unless NOTIFY_ON_EMPTY=1.

SMTP settings use the same names and defaults as Modular-Code
(sip_components/weekly_report_scheduler.py): EMAIL_SMTP (smtp.office365.com),
EMAIL_PORT (587, STARTTLS), EMAIL_FROM (dataautomation@coresight.com) and
EMAIL_PASSWORD, which is never written to a file here. TEAMS_WEBHOOK_URL, if set,
gets the headline as a Teams message. Nothing here can fail a run.
"""
from __future__ import annotations

import html
import json
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import requests
import yaml
from sqlalchemy import text

from app.components.export import EXCEL_MIME, build_workbook
from app.core import config as _config  # noqa: F401  loads .env
from app.core.database import get_engine
from etl import crosstab_export, tracker_line

log = logging.getLogger("cip.notify")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "notify.yml"
CROSSTAB_NAMES = {"standard": "Cross Tabs", "holiday_status": "Holiday Status Cross Tabs",
                  "inflation_sentiment": "Inflation_Sentiment Cross Tabs"}
RED = "#d62e2f"


def recipients(kind: str) -> list[str]:
    lists = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return lists.get(kind) or lists["default"]


def send(subject: str, body: str, to: list[str], attachments: list[tuple[str, bytes]] = (), page: str = "") -> bool:
    """One email through Office 365 SMTP: plain text, an HTML page when given, and attachments."""
    password = os.getenv("EMAIL_PASSWORD", "").strip()
    if not password:
        log.warning("EMAIL_PASSWORD is not set; not sending %r", subject)
        return False
    sender = os.getenv("EMAIL_FROM", "dataautomation@coresight.com")
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, sender, ", ".join(to)
    message.set_content(body)
    if page:
        message.add_alternative(page, subtype="html")
    maintype, subtype = EXCEL_MIME.split("/")
    for name, data in attachments:
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    try:
        with smtplib.SMTP(os.getenv("EMAIL_SMTP", "smtp.office365.com"), int(os.getenv("EMAIL_PORT", "587")), timeout=60) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)
    except Exception as exc:
        log.warning("Email %r not sent: %s", subject, exc)
        return False
    log.info("Emailed %r to %s", subject, ", ".join(to))
    return True


def teams(headline: str) -> bool:
    url = os.getenv("TEAMS_WEBHOOK_URL", "").strip()
    if url:
        try:
            card = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4",
                "body": [{"type": "TextBlock", "text": headline, "wrap": True}]}}]}
            requests.post(url, json=card, timeout=30).raise_for_status()
            return True
        except Exception as exc:
            log.warning("Teams message not sent: %s", exc)
    return False


# ── the facts ──────────────────────────────────────────────────────────────
def query(sql: str, **params) -> pd.DataFrame:
    with get_engine("etl").connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def facts(survey_id: int) -> dict:
    info = query("""
        SELECT s.title, s.wave_label, s.study_type, s.survey_family, s.sample_source, f.forsta_path, f.launched_at,
               f.closed_at, f.qualified_n, f.total_n
          FROM cip_survey s LEFT JOIN cip_forsta_survey f ON f.survey_id = s.survey_id WHERE s.survey_id = :s""",
        s=survey_id).iloc[0].to_dict()
    load = query("""SELECT rows_read, rows_loaded, rows_bad, TIMESTAMPDIFF(SECOND, started_at, finished_at) AS seconds
                      FROM cip_load_log WHERE survey_id = :s AND source_type = 'api' ORDER BY load_id DESC LIMIT 1""",
                 s=survey_id).iloc[0].to_dict()
    status = query("SELECT status_label, COUNT(*) AS n FROM cip_respondent WHERE survey_id = :s GROUP BY status_label",
                   s=survey_id).set_index("status_label")["n"].to_dict()
    people = query("""SELECT interview_secs, device FROM cip_respondent WHERE survey_id = :s AND is_qualified = 1""", s=survey_id)
    answers = int(query("SELECT COUNT(*) AS n FROM cip_answer WHERE survey_id = :s", s=survey_id)["n"][0])
    questions = int(query("SELECT COUNT(*) AS n FROM cip_question WHERE survey_id = :s AND is_technical = 0 AND is_virtual = 0",
                          s=survey_id)["n"][0])
    modules = query("""SELECT module_name, kind, is_lead, series_wave_no, season FROM cip_wave_module
                        WHERE forsta_path = :p ORDER BY is_lead DESC, kind""", p=info["forsta_path"])
    return {"info": info, "load": load, "status": status, "people": people, "answers": answers, "questions": questions,
            "modules": modules, "measures": measures(survey_id, info["survey_family"])}


MEASURES = ("q1", "CS1", "CS2")


def measures(survey_id: int, family: str) -> pd.DataFrame:
    """Core tracker measures (activities, household and economic outlook) for this wave and the one before it."""
    previous = query("""SELECT survey_id FROM cip_survey WHERE survey_family = :f AND load_status = 'verified'
                           AND wave_date < (SELECT wave_date FROM cip_survey WHERE survey_id = :s)
                         ORDER BY wave_date DESC LIMIT 1""", f=family, s=survey_id)
    ids = [survey_id] + ([int(previous["survey_id"][0])] if len(previous) else [])
    frame = query("""
        SELECT c.survey_id, q.qcode, q.qtext_short AS question, COALESCE(i.item_label, o.value_label) AS answer,
               c.n, c.base_n, COALESCE(i.sort_order, o.sort_order, 0) AS ord
          FROM cip_agg_cell c JOIN cip_question q ON q.question_id = c.question_id AND q.qcode IN :codes
          LEFT JOIN cip_item i ON i.item_id = c.item_id LEFT JOIN cip_option o ON o.option_id = c.option_id
         WHERE c.survey_id IN :ids AND c.dim = 'total' AND c.cohort_id IS NULL""".replace(
        ":codes", "('q1','CS1','CS2')").replace(":ids", "(" + ",".join(str(i) for i in ids) + ")"))
    if frame.empty:
        return frame
    frame["pct"] = frame["n"] / frame["base_n"].where(frame["base_n"] > 0)
    now = frame[frame["survey_id"] == survey_id].set_index(["qcode", "question", "answer"])
    out = now[["pct", "ord"]].copy()
    out["last"] = frame[frame["survey_id"] != survey_id].set_index(["qcode", "question", "answer"])["pct"]
    return out.reset_index()


# ── the page ───────────────────────────────────────────────────────────────
def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def table(headers: list[str], rows: list[list[str]], widths: list[str] | None = None) -> str:
    head = "".join(f'<th style="text-align:{"left" if i == 0 else "right"};padding:6px 10px;background:#f0f0f0;'
                   f'border-bottom:2px solid {RED};font-size:12px">{html.escape(h)}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(
        f'<td style="text-align:{"left" if i == 0 else "right"};padding:5px 10px;border-bottom:1px solid #e0e0e0;'
        f'font-size:13px">{c}</td>' for i, c in enumerate(row)) + "</tr>" for row in rows)
    return f'<table style="border-collapse:collapse;width:100%;margin:6px 0 18px"><tr>{head}</tr>{body}</table>'


def section(title: str, inner: str) -> str:
    return (f'<h3 style="margin:22px 0 4px;font-size:15px;color:{RED};border-bottom:1px solid #e0e0e0;'
            f'padding-bottom:4px">{html.escape(title)}</h3>{inner}')


def delta(now, last) -> str:
    if pd.isna(last):
        return "–"
    points = round((now - last) * 100)
    colour = "#2d7a3a" if points > 0 else "#b3261e" if points < 0 else "#6b6a68"
    return f'<span style="color:{colour}">{points:+d} pts</span>'


def report(survey_id: int, files: list[tuple[str, int, str]], seconds_build: float = 0.0, wave=None, sets: tuple = ()) -> tuple[str, str]:
    """(plain text, HTML) of the loaded-survey email."""
    d = facts(survey_id)
    i, load, status = d["info"], d["load"], d["status"]
    qualified = status.get("Qualified", i["qualified_n"])
    started = sum(status.values()) or i["total_n"]
    minutes = d["people"]["interview_secs"].median() / 60 if d["people"]["interview_secs"].notna().any() else float("nan")
    mobile = (d["people"]["device"].fillna("").str.lower().str.contains("mobile|phone|tablet")).mean() if len(d["people"]) else float("nan")
    launched, closed = pd.to_datetime(i["launched_at"]), pd.to_datetime(i["closed_at"])
    hours = (closed - launched).total_seconds() / 3600 if pd.notna(launched) and pd.notna(closed) else float("nan")

    fieldwork = [["Survey", html.escape(i["title"])], ["Forsta path", i["forsta_path"]],
            ["Wave (Monday)", i["wave_label"]], ["Type", i["study_type"]],
            ["Launched", str(launched)[:16] if pd.notna(launched) else "–"], ["Closed", str(closed)[:16] if pd.notna(closed) else "–"],
            ["Time in field", "–" if pd.isna(hours) else f"{hours:.1f} hours"]]
    page = f"""<div style="font-family:Segoe UI,Arial,sans-serif;color:#2d2a29;max-width:760px">
<div style="background:{RED};color:#fff;padding:14px 18px"><div style="font-size:12px;opacity:.9">Coresight Research · Consumer Insight Portal</div>
<div style="font-size:18px;font-weight:600;margin-top:2px">New survey loaded and verified</div></div>
<p style="font-size:14px;margin:14px 2px">{html.escape(i["title"])}<br><b>Wave {i["wave_label"]}</b> · {qualified} qualified respondents · every record and answer proven equal to Forsta before it appeared in reports.</p>"""
    page += section("Fieldwork", table(["", ""], fieldwork))
    page += section("Respondents", table(["Status", "Respondents"], [
        [html.escape(str(k)), f"{v:,}"] for k, v in sorted(status.items(), key=lambda kv: -kv[1])] +
        [["<b>Started</b>", f"<b>{started:,}</b>"], ["Incidence (qualified ÷ started)", pct(qualified / started if started else float('nan'))],
         ["Median interview, qualified", "–" if pd.isna(minutes) else f"{minutes:.1f} min"],
         ["Completed on a mobile device", pct(mobile)]]))
    page += section("Load and verification", table(["Check", "Result"], [
        ["Respondents loaded", f"{load['rows_loaded']:,} of {load['rows_read']:,} read"],
        ["Answers stored", f"{d['answers']:,}"], ["Questions (excluding paradata)", f"{d['questions']:,}"],
        ["Rows rejected", f"{load['rows_bad']:,}"], ["Respondent count equals Forsta", "✓ passed"],
        ["Every Forsta variable has a field", "✓ passed"], ["Every field's answer count equals Forsta", "✓ passed"],
        ["Load time", f"{load['seconds']} s"]]))
    if len(d["modules"]):
        page += section("Where this wave sits in the survey calendar", table(["Module", "Kind", "Wave in series"], [
            [("<b>" if m.is_lead else "") + html.escape(m.module_name) + (" (lead)" if m.is_lead else "") + ("</b>" if m.is_lead else ""),
             m.kind, "–" if pd.isna(m.series_wave_no) else f"{int(m.series_wave_no)}" + (f" of season {int(m.season)}" if pd.notna(m.season) else "")]
            for m in d["modules"].itertuples()]))
    if len(d["measures"]):
        rows = []
        for code, group in d["measures"].groupby("qcode", sort=False):
            group = group.sort_values("pct", ascending=False).head(6) if code == "q1" else group.sort_values("ord")
            for r in group.itertuples():
                rows.append([f"<span style='color:#6b6a68'>{r.qcode}</span> {html.escape(str(r.answer))}", pct(r.pct), pct(r.last), delta(r.pct, r.last)])
        page += section("Core tracker measures vs the previous wave", table(["Measure", "This wave", "Previous", "Change"], rows)
                        + '<div style="font-size:11px;color:#6b6a68;margin-top:-12px">q1 shows the six most common activities; CS1 household and CS2 economic outlook show every answer. Percentages use each question\'s own base.</div>')
    if wave is not None:
        page += crosstab_sections(wave, sets)
    page += section("Attached files", table(["File", "What it is", "Size"], [
        [html.escape(name), what, f"{size / 1024:,.0f} KB"] for name, size, what in files]))
    page += (f'<p style="font-size:11px;color:#6b6a68;margin-top:20px">Built by the ETL from cip_stg in {seconds_build:.0f} s. '
             f'Cross-tab workbooks use the team\'s Forsta segment definitions, qualified respondents only, percentages on total answering, '
             f'flags * under 100 and ** under 30 respondents. Paradata tables (browser, OS, dropout) are not rebuilt.</p></div>')
    plain = (f"{i['title']}\nWave {i['wave_label']} · {i['forsta_path']}\nQualified {qualified} of {started} started · {load['rows_loaded']} "
             f"respondents loaded, {d['answers']:,} answers, verified against Forsta.\n\nAttached:\n" +
             "\n".join(f"  {name} — {what}" for name, _, what in files) + "\n\nOpen this email in HTML for the full report.\n")
    return plain, page


PREVIEW_COLUMNS = ["Total", "Male", "Female", "GenZ", "Millennial", "GenX", "Boomer"]
PREVIEW_TABLES = [("q1", 8), ("CS1", 0), ("CS2", 0)]


def crosstab_sections(wave, sets) -> str:
    """The cross-tabs in the email itself: a preview table per core question, then every attached banner's segments."""
    out = ""
    if "standard" in sets:
        inner = ""
        for qcode, top in PREVIEW_TABLES:
            title, labels, rows, bases = crosstab_export.preview(wave, "standard", qcode, PREVIEW_COLUMNS, top)
            if not rows:
                continue
            inner += f'<div style="font-size:13px;font-weight:600;margin-top:10px">{html.escape(title[:150])}</div>'
            inner += table([""] + labels, [[html.escape(str(name))] + [pct(v) if v is not None else "–" for v in values] for name, values in rows]
                           + [["<span style='color:#6b6a68'>Base (n)</span>"] + [f"<span style='color:#6b6a68'>{b}{crosstab_export.flag(b)}</span>" for b in bases]])
        out += section("Cross-tab preview — standard banner", inner + '<div style="font-size:11px;color:#6b6a68;margin-top:-12px">'
                       'Column percentages, qualified respondents. The attached Cross Tabs workbook has every question and every segment. * under 100, ** under 30.</div>')
    for key in sets:
        rows = crosstab_export.segment_rows(wave, key)
        out += section(f"Banner — {CROSSTAB_NAMES[key]}: segments and definitions", table(
            ["Segment", "Definition", "n"], [[html.escape(a), f"<span style='color:#6b6a68'>{html.escape(b)}</span>", f"{n}{crosstab_export.flag(n)}"] for a, b, n in rows]))
    return out


def survey_loaded(survey_id: int) -> bool:
    """Email the report and the team's workbooks for one freshly loaded survey."""
    started = time.perf_counter()
    info = query("""SELECT s.title, s.wave_label, s.study_type, s.survey_family, f.forsta_path, f.qualified_n
                      FROM cip_survey s LEFT JOIN cip_forsta_survey f ON f.survey_id = s.survey_id WHERE s.survey_id = :s""",
                 s=survey_id).iloc[0]
    stem = f"{info['wave_label']}"
    wave = crosstab_export.load_wave(survey_id)
    attachments: list[tuple[str, bytes]] = []
    for key in crosstab_export.available(wave):
        attachments.append((f"{CROSSTAB_NAMES[key]} {stem}.xlsx", crosstab_export.build(survey_id, key, wave)))
    if info["survey_family"] == tracker_line.load_config()["family"]:
        line = tracker_line.read([survey_id], role="etl")
        attachments.append((f"Weekly Line-By-Line {stem}.xlsx", build_workbook(
            {"Raw Data": line}, f"{info['title']} — wave {stem}", percent_columns=("__none__",),
            notes=[("Survey", info["forsta_path"]), ("Format", "the data team's line-by-line columns (config/tracker_line.yml)")])))
    what = {"Cross Tabs": "their standard banner: gender, age and generation, ethnicity, income, residence, politics, outlook",
            "Holiday Status Cross Tabs": "banner: holiday-shopping status and recent holiday purchases",
            "Inflation_Sentiment Cross Tabs": "banner: Middle East concern, outlook and holiday status",
            "Weekly Line-By-Line": "one row per qualified respondent, the team's headers"}
    files = [(n, len(b), next(v for k, v in what.items() if n.startswith(k))) for n, b in attachments]
    plain, page = report(survey_id, files, time.perf_counter() - started, wave, tuple(crosstab_export.available(wave)))
    subject = f"CIP loaded: {info['title']} (wave {stem}, {info['qualified_n']} qualified)"
    teams(f"✅ CIP pipeline succeeded: {info['title'][:90]} (wave {stem}) loaded and verified, "
          f"{info['qualified_n']} qualified. {len(attachments)} files emailed.")
    return send(subject, plain, recipients(info["study_type"]), attachments, page)


REPEAT_HOURS = 6                   # polling runs every 30 minutes: the same failure is told once per window
STATE = Path(__file__).resolve().parents[1] / "logs" / "notify-state.json"


def already_told(subject: str) -> bool:
    now = time.time()
    try:
        told = json.loads(STATE.read_text())
    except (OSError, ValueError):
        told = {}
    return now - told.get(subject, 0) < REPEAT_HOURS * 3600


def mark_told(subject: str) -> None:
    """Start the repeat window, only once the message really went out: a failed send must not silence the alert."""
    now = time.time()
    try:
        told = json.loads(STATE.read_text())
    except (OSError, ValueError):
        told = {}
    told[subject] = now
    try:
        STATE.write_text(json.dumps({k: v for k, v in told.items() if now - v < 86400}))
    except OSError:
        pass


def failure(what: str, detail: str) -> bool:
    """Email the failure list that a run (or one survey) did not complete (once per REPEAT_HOURS)."""
    subject = f"CIP pipeline FAILED: {what}"
    if already_told(subject):
        log.info("Already told about %r in the last %d h", subject, REPEAT_HOURS)
        return False
    first = next((line for line in detail.splitlines() if line.strip()), "")[:300]
    posted = teams(f"❌ CIP pipeline failed: {what}. {first} (full detail in the email and logs/forsta-etl.log)")
    page = (f'<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px"><div style="background:#b3261e;color:#fff;padding:12px 16px;'
            f'font-size:16px;font-weight:600">Pipeline failure</div><p style="font-size:14px"><b>{html.escape(what)}</b></p>'
            f'<pre style="background:#f6f6f6;padding:10px;font-size:12px;white-space:pre-wrap">{html.escape(detail)}</pre>'
            f'<p style="font-size:12px;color:#6b6a68">The next scheduled run tries again. Log: logs/forsta-etl.log</p></div>')
    sent = send(subject, f"{what}\n\n{detail}\n\nThe next scheduled run tries again. Logs: logs/forsta-etl.log\n", recipients("failure"), page=page)
    if sent or posted:   # the team channel alone counts as told
        mark_told(subject)
    return sent or posted


def idle_run() -> bool:
    if os.getenv("NOTIFY_ON_EMPTY") != "1":
        return False
    return send("CIP pipeline ran: nothing new", "Every closed survey is already loaded.\n", recipients("default"))
