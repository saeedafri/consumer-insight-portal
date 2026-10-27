"""Tell people what a pipeline run did: one email per loaded survey, one per failure.

A loaded survey's email is short enough to read without scrolling: who answered,
the three biggest significant changes (the portal's own rule), and the files
the data team works from, in their formats (a file this week's survey cannot
fill is named as not attached, with why):

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

import argparse
import html
import json
import logging
import os
import re
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
# The workbooks the team sends each week, named as they name them (Teams, 19 Oct 2026): their two cross-tab banners
# (config/crosstab_banners.yml; "Holiday Inflation" is the inflation_sentiment set: D13 inflation and gas concern, CS1
# outlook, XM3 holiday status), then Forsta's labelled Raw Data and the team's Weekly Line-By-Line.
CROSSTAB_NAMES = {"standard": "Cross Tabs", "inflation_sentiment": "Holiday Inflation Cross Tabs"}
# what a banner's columns are built from: a week whose survey did not ask them gets no file
CROSSTAB_NEEDS = {"standard": "the demographic questions",
                  "inflation_sentiment": "the Middle East concern, outlook and holiday status questions (D13, CS1, XM3)"}
RED = "#d62e2f"


def recipients(kind: str) -> list[str]:
    lists = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if kind == "failure":
        return lists.get("failure") or []
    return lists.get(kind) or lists["default"]


def compose(subject: str, body: str, to: list[str], attachments: list[tuple[str, bytes]] = (), page: str = "",
            copy: bool = True) -> EmailMessage:
    """One email: plain text, an HTML page when given, attachments, and the config's `cc` list on every message."""
    cc = [a for a in yaml.safe_load(CONFIG.read_text(encoding="utf-8")).get("cc") or [] if a not in to] if copy else []
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, os.getenv("EMAIL_FROM", "dataautomation@coresight.com"), ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message.set_content(body)
    if page:
        message.add_alternative(page, subtype="html")
    maintype, subtype = EXCEL_MIME.split("/")
    for name, data in attachments:
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return message


def send(subject: str, body: str, to: list[str], attachments: list[tuple[str, bytes]] = (), page: str = "",
         copy: bool = True) -> bool:
    """One email through Office 365 SMTP (compose: To, Cc, plain text, HTML, attachments)."""
    password = os.getenv("EMAIL_PASSWORD", "").strip()
    if not password:
        log.warning("EMAIL_PASSWORD is not set; not sending %r", subject)
        return False
    message = compose(subject, body, to, attachments, page, copy)
    sender = message["From"]
    try:
        with smtplib.SMTP(os.getenv("EMAIL_SMTP", "smtp.office365.com"), int(os.getenv("EMAIL_PORT", "587")), timeout=60) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)
    except Exception as exc:
        log.warning("Email %r not sent: %s", subject, exc)
        return False
    log.info("Emailed %r to %s", subject, ", ".join(to + ([message["Cc"]] if message["Cc"] else [])))
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
        SELECT s.title, s.wave_label, s.study_type, f.forsta_path, f.launched_at, f.closed_at, f.qualified_n
          FROM cip_survey s LEFT JOIN cip_forsta_survey f ON f.survey_id = s.survey_id WHERE s.survey_id = :s""",
        s=survey_id).iloc[0].to_dict()
    started = int(query("SELECT COUNT(*) AS n FROM cip_respondent WHERE survey_id = :s", s=survey_id)["n"][0])
    return {"info": info, "started": started, "moves": moves(survey_id)}


def moves(survey_id: int, top: int = 3) -> list[dict]:
    """The wave's biggest significant changes against the previous wave, by the portal's own rule (srv_result's
    sig_prior flag: z-test with Benjamini–Hochberg, etl/serving.py). Who answered (D1…) is context, not news."""
    rows = query("""SELECT r.qcode, COALESCE(q.qtext_short, q.qtext) AS question, r.item_label, r.option_label, r.pct, r.prior_pct
                      FROM srv_result r JOIN cip_question q ON q.question_id = r.question_id
                     WHERE r.survey_id = :s AND r.dim = 'total' AND r.flags LIKE '%sig_prior%'""", s=survey_id)
    rows = rows[~rows["qcode"].str.match(r"^D[1-9]$")]
    rows = rows.assign(change=(rows["pct"].astype(float) - rows["prior_pct"].astype(float))).dropna(subset=["change"])
    rows = rows.reindex(rows["change"].abs().sort_values(ascending=False).index)
    return rows.drop_duplicates("qcode").head(top).to_dict("records")   # one per question: Yes +12 and No −12 are one finding


# ── the page ───────────────────────────────────────────────────────────────
def page_shell(headline: str, inner: str) -> str:
    """One short branded email: a red title bar, then plain paragraphs (nothing to scroll through)."""
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;color:#2d2a29;max-width:600px;font-size:14px;line-height:1.5">'
            f'<div style="background:{RED};color:#fff;padding:12px 16px"><div style="font-size:12px;opacity:.9">Coresight Research · '
            f'Consumer Insight Portal</div><div style="font-size:17px;font-weight:600;margin-top:2px">{html.escape(headline)}</div></div>'
            f'<div style="padding:4px 2px">{inner}</div></div>')


def topics(title: str) -> str:
    """"Shopping and Spending - inc Social Commerce + Holiday Tracker + GLP1s" → "Social Commerce, Holiday Tracker, GLP1s"."""
    found = re.search(r"\binc\.?\s+(.+)$", title)
    return ", ".join(t.strip() for t in found[1].split("+")) if found else title


def answer_of(m: dict) -> str:
    return " — ".join(str(v) for v in (m["item_label"], m["option_label"]) if v and str(v) != "nan")


def report(survey_id: int, files: list[str], missing: list[str] = ()) -> tuple[str, str]:
    """(plain text, HTML) of the loaded-survey email: who answered, the biggest real changes, the attached files."""
    d = facts(survey_id)
    i = d["info"]
    weekly = i["study_type"] == "tracker"
    since = "last week" if weekly else "the previous wave"
    launched, closed = pd.to_datetime(i["launched_at"]), pd.to_datetime(i["closed_at"])
    hours = f" in {(closed - launched).total_seconds() / 3600:.0f} hours" if pd.notna(launched) and pd.notna(closed) else ""
    who = (f"<b>{int(i['qualified_n']):,} people</b> completed the survey{hours} ({d['started']:,} started). "
           f"Every answer was checked against Forsta before it reached the portal.")
    if d["moves"]:
        items = "".join(
            f'<li style="margin:6px 0"><b>{m["pct"]:.0f}%</b> {html.escape(answer_of(m))} '
            f'<span style="color:{"#2d7a3a" if m["change"] > 0 else "#b3261e"}">({m["change"]:+.0f} pts vs {since})</span>'
            f'<br><span style="color:#6b6a68;font-size:12px">{html.escape(str(m["question"])[:110])}</span></li>' for m in d["moves"])
        news = f'<p style="margin:14px 0 4px"><b>Biggest changes since {since}</b></p><ul style="margin:0;padding-left:18px">{items}</ul>'
    else:
        news = f'<p style="margin:14px 0 4px">No answer changed significantly against {since}.</p>'
    attached = (f'<p style="color:#6b6a68;font-size:12px;margin-top:14px">Attached: {html.escape(", ".join(files))}.'
                + "".join(f"<br>Not attached this week: {html.escape(m)}." for m in missing) + "</p>")
    week = f"{pd.to_datetime(i['wave_label']):%-d %b %Y}" if weekly else i["wave_label"]
    page = page_shell(f"New survey ready: week of {week}" if weekly else f"New survey ready: {week}",
                      f'<p style="margin:12px 0 0">{html.escape(i["title"])}</p><p style="margin:6px 0 0">{who}</p>'
                      + news + attached)
    plain = (f"New survey ready: {i['title']} ({i['wave_label']})\n{int(i['qualified_n']):,} people completed it{hours}; "
             f"every answer checked against Forsta.\n\nWhat changed vs {since}:\n" +
             ("\n".join(f"  {m['pct']:.0f}% {answer_of(m)} ({m['change']:+.0f} pts) — {m['question']}" for m in d["moves"])
              or "  nothing significant") +
             f"\n\nAttached: {', '.join(files)}\n" + "".join(f"Not attached this week: {m}\n" for m in missing))
    return plain, page


def survey_loaded(survey_id: int) -> bool:
    """Email the report and the team's workbooks for one freshly loaded survey."""
    subject, plain, to, attachments, page, headline = loaded_email(survey_id)
    teams(headline)
    return send(subject, plain, to, attachments, page)


def loaded_email(survey_id: int) -> tuple:
    """(subject, plain, to, attachments, HTML, Teams headline) of one loaded survey's email."""
    info = query("""SELECT s.title, s.wave_label, s.study_type, s.survey_family, f.forsta_path, f.qualified_n
                      FROM cip_survey s LEFT JOIN cip_forsta_survey f ON f.survey_id = s.survey_id WHERE s.survey_id = :s""",
                 s=survey_id).iloc[0]
    stem = f"{info['wave_label']}"
    dated = f"{pd.to_datetime(stem):%m_%d_%y}"   # the team's file date: 10_19_26
    wave = crosstab_export.load_wave(survey_id)
    attachments: list[tuple[str, bytes]] = []
    sets = [key for key in crosstab_export.available(wave) if key in CROSSTAB_NAMES]
    for key in sets:
        attachments.append((f"{CROSSTAB_NAMES[key]} {dated}.xlsx", crosstab_export.build(survey_id, key, wave)))
    missing = [f"{name} (this week's survey did not ask {CROSSTAB_NEEDS[key]})" for key, name in CROSSTAB_NAMES.items()
               if key not in sets]
    if info["forsta_path"]:
        from etl import forsta_etl   # notify is imported by the pipeline, not the other way round
        try:
            attachments.append((f"Raw Data {dated}.xlsx", crosstab_export.raw_data(forsta_etl._client(), info["forsta_path"])))
        except Exception as exc:   # Forsta down: the rest of the email still goes
            log.warning("Raw Data for %s not built: %s", info["forsta_path"], exc)
            missing.append("Raw Data (Forsta could not be reached when this email was built)")
    if info["survey_family"] == tracker_line.load_config()["family"]:
        line = tracker_line.read([survey_id], role="etl")
        attachments.append((f"Weekly Line-By-Line {dated}.xlsx", build_workbook(
            {"Raw Data": line}, f"{info['title']} — wave {stem}", percent_columns=("__none__",),
            notes=[("Survey", info["forsta_path"]), ("Format", "the data team's line-by-line columns (config/tracker_line.yml)")])))
    plain, page = report(survey_id, [name for name, _ in attachments], missing)
    if info["study_type"] == "tracker":
        subject = (f"Weekly Consumer Tracker — week of {pd.to_datetime(stem):%-d %b %Y}: {topics(info['title'])}"
                   f" ({int(info['qualified_n']):,} respondents)")
    else:
        subject = f"{info['title']} — results ready ({int(info['qualified_n']):,} respondents)"
    headline = (f"✅ CIP pipeline succeeded: {info['title'][:90]} (wave {stem}) loaded and verified, "
                f"{info['qualified_n']} qualified. {len(attachments)} files emailed.")
    return subject, plain, recipients(info["study_type"]), attachments, page, headline


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
    """Email only the private failure list; never copy a team channel or the global CC list."""
    subject = f"CIP pipeline FAILED: {what}"
    if already_told(subject):
        log.info("Already told about %r in the last %d h", subject, REPEAT_HOURS)
        return False
    page = (f'<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px"><div style="background:#b3261e;color:#fff;padding:12px 16px;'
            f'font-size:16px;font-weight:600">Pipeline failure</div><p style="font-size:14px"><b>{html.escape(what)}</b></p>'
            f'<pre style="background:#f6f6f6;padding:10px;font-size:12px;white-space:pre-wrap">{html.escape(detail)}</pre>'
            f'<p style="font-size:12px;color:#6b6a68">The next scheduled run tries again. Log: logs/forsta-etl.log</p></div>')
    sent = send(subject, f"{what}\n\n{detail}\n\nThe next scheduled run tries again. Logs: logs/forsta-etl.log\n",
                recipients("failure"), page=page, copy=False)
    if sent:
        mark_told(subject)
    return sent


def idle_run() -> bool:
    if os.getenv("NOTIFY_ON_EMPTY") != "1":
        return False
    return send("CIP pipeline ran: nothing new", "Every closed survey is already loaded.\n", recipients("default"))


def summary() -> tuple[str, str, str]:
    """(subject, plain, HTML) of the portal-wide summary, short enough to read without scrolling (cip_stg counts)."""
    waves = query("""SELECT s.study_type, w.qualified_n FROM cip_survey s JOIN srv_wave w ON w.survey_id = s.survey_id
                      WHERE s.load_status = 'verified'""")
    first, last = query("SELECT MIN(wave_date) AS a, MAX(wave_date) AS b FROM cip_survey WHERE load_status = 'verified'").iloc[0]
    answers = int(query("SELECT COUNT(*) AS n FROM cip_answer")["n"][0])       # exact, about 80 s on cip_stg
    questions = int(query("SELECT COUNT(*) AS n FROM cip_question WHERE is_technical = 0 AND is_virtual = 0")["n"][0])
    latest = query("""SELECT s.survey_id, s.title, s.wave_label, w.qualified_n FROM cip_survey s JOIN srv_wave w ON w.survey_id = s.survey_id
                       ORDER BY s.wave_date DESC, s.survey_id DESC LIMIT 1""").iloc[0]
    count, people = len(waves), int(waves["qualified_n"].sum())
    kinds = {"tracker": "weekly trackers", "annual": "annual studies", "adhoc": "one-off studies"}
    by_kind = [(kinds[k], len(g), g["qualified_n"].mean()) for k, g in waves.groupby("study_type")]
    lines = [f"<b>{count:,} surveys</b> from {first:%b %Y} to {last:%b %Y}",
             f"<b>{people:,} people</b> answered them, <b>{people / count:,.0f}</b> per survey on average",
             f"{questions:,} questions and {answers / 1e6:,.1f} million individual answers",
             " · ".join(f"{n:,} {name} (about {avg:,.0f} people each)" for name, n, avg in sorted(by_kind, key=lambda k: -k[1])),
             f"Latest: {html.escape(latest['title'])}, week of {pd.to_datetime(latest['wave_label']):%-d %b %Y}, {int(latest['qualified_n']):,} people"]
    page = page_shell("What the portal holds today", '<ul style="margin:12px 0 0;padding-left:18px">' +
                      "".join(f'<li style="margin:6px 0">{line}</li>' for line in lines) + "</ul>" +
                      '<p style="color:#6b6a68;font-size:12px">All surveys are in the US; every one was checked against its source before it reached the portal.</p>')
    subject = f"Consumer Insight Portal — data summary as of {time.strftime('%-d %b %Y')}: {count:,} surveys, {people:,} respondents"
    plain = "What the Consumer Insight Portal holds today\n\n" + "\n".join("  " + re.sub("<[^>]+>", "", line) for line in lines) + "\n"
    return subject, plain, page


def main() -> int:
    """Preview (default: .eml files to open and check) or --send the summary and/or one survey's loaded email."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")   # show each send
    p = argparse.ArgumentParser(description=main.__doc__)
    p.add_argument("--summary", action="store_true", help="the portal-wide summary, to the `default` list")
    p.add_argument("--survey", type=int, help="one survey's loaded email (survey_id), to its study type's list")
    p.add_argument("--send", action="store_true", help="send; without it, write .eml previews to --out")
    p.add_argument("--to", help="comma-separated addresses instead of the configured lists (a test send to yourself)")
    p.add_argument("--no-files", action="store_true", help="leave the workbooks off (a look at the email outside Coresight)")
    p.add_argument("--out", default="data/exports/email-preview")   # git-ignored: attachments hold respondent rows
    a = p.parse_args()
    emails = []
    if a.summary:
        subject, plain, page = summary()
        emails.append(("summary", subject, plain, recipients("default"), [], page))
    if a.survey:
        subject, plain, to, attachments, page, _ = loaded_email(a.survey)
        emails.append((f"survey-{a.survey}", subject, plain, to, attachments, page))
    if not emails:
        p.print_help()
        return 1
    for name, subject, plain, to, attachments, page in emails:
        to = [t.strip() for t in a.to.split(",") if t.strip()] if a.to else to
        attachments = [] if a.no_files else attachments
        if a.send:
            if not send(subject, plain, to, attachments, page, copy=not a.to):   # a test send to --to goes to them alone
                return 1
            continue
        out = Path(a.out) / f"{name}.eml"
        out.parent.mkdir(parents=True, exist_ok=True)
        message = compose(subject, plain, to, attachments, page, copy=not a.to)
        out.write_bytes(bytes(message))
        out.with_suffix(".html").write_text(page, encoding="utf-8")
        print(f"{out}\n  Subject: {subject}\n  To: {message['To']}\n  Cc: {message['Cc'] or '–'}\n"
              f"  Attachments: {', '.join(n for n, _ in attachments) or '–'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
