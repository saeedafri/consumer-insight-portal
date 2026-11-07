"""Thin client for the Forsta Surveys (Decipher) REST API.

Checked against https://se1.decipherinc.com on 2026-09-29: the API is enabled
and authenticates with the `x-apikey` header. The key on file is rejected with

    {"$error": "API user account is not valid: account disabled", "$code": 401}

(since replaced by a working key, Oct 2026). The client never changes a survey in Forsta: every call is a GET,
except the few POSTs Forsta uses for a computation that only reads (READ_ONLY_POSTS: running a cross-tab or a saved
report, exporting a saved report as a file). read_post() refuses any other POST before it leaves this machine, and
etl/fieldwork.py checks after each survey's POSTs that the survey's last edit did not move.

Reference: https://forstasurveys.zendesk.com/hc/en-us/articles/4409469957531
"""
from __future__ import annotations

import codecs
import json
import logging
import re
from collections.abc import Iterator
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, wait_exponential

logger = logging.getLogger(__name__)


class ForstaError(RuntimeError):
    pass


# The only POSTs this client sends: each computes from the survey and changes nothing in it (checked live on survey
# 261003, 7 Nov 2026: last edit and audit log unchanged; docs/FORSTA_API_REVIEW.md section 2). Anything else that
# Forsta takes as a POST (launch, close, data edits, evaluate, share links, distribute…) is refused by read_post().
SURVEY = r"surveys/[\w.-]+(?:/[\w.-]+)*"
READ_ONLY_POSTS = (
    re.compile(SURVEY + r"/crosstabs/execute"),                                    # Forsta's own cross-tab, in memory
    re.compile(SURVEY + r"/crosstabs/saved/\w+/execute"),                          # runs a report the team saved
    re.compile(SURVEY + r"/crosstabs/saved/\w+/export/(?:excel|pdf|pptx)"),        # the same report as a file
)


class ForstaAuthError(ForstaError):
    pass


class ForstaBusy(ForstaError):
    """429 or a 5xx: worth retrying."""


def _json_records(response: requests.Response) -> Iterator[dict]:
    """Decode an array with memory proportional to a chunk and its largest record."""
    utf8 = codecs.getincrementaldecoder("utf-8-sig")()
    chunks = iter(response.iter_content(chunk_size=65536))
    decoder = json.JSONDecoder()
    buffer, position, exhausted = "", 0, False

    def fill() -> bool:
        nonlocal buffer, position, exhausted
        if exhausted:
            return False
        while True:
            try:
                chunk = next(chunks)
            except StopIteration:
                exhausted = True
                tail = utf8.decode(b"", final=True)
                buffer, position = buffer[position:] + tail, 0
                return bool(tail)
            if chunk:
                buffer, position = buffer[position:] + utf8.decode(chunk), 0
                return True

    def whitespace() -> bool:
        nonlocal position
        while True:
            while position < len(buffer) and buffer[position] in " \t\r\n":
                position += 1
            if position < len(buffer):
                return True
            if not fill():
                return False

    if not whitespace() or buffer[position] != "[":
        raise ForstaError("Forsta data export must be a JSON array")
    position += 1
    after_comma = False
    while True:
        if not whitespace():
            raise ForstaError("Forsta data export ended before its array was complete")
        if buffer[position] == "]":
            if after_comma:
                raise ForstaError("Forsta data export has a trailing comma")
            position += 1
            if whitespace():
                raise ForstaError("Forsta data export has content after its array")
            return
        if buffer[position] != "{":
            raise ForstaError("Forsta data export contains a non-object respondent")
        while True:
            try:
                record, end = decoder.raw_decode(buffer, position)
                break
            except json.JSONDecodeError as exc:
                # A split string, literal or escape can need the next chunk.
                incomplete = exc.msg.startswith("Unterminated string") or exc.pos >= len(buffer) - 6
                if not incomplete or not fill():
                    raise ForstaError("Forsta data export contains invalid or truncated JSON") from exc
        position = end
        yield record
        if not whitespace():
            raise ForstaError("Forsta data export ended before its array was complete")
        if buffer[position] == ",":
            position += 1
            after_comma = True
        elif buffer[position] == "]":
            after_comma = False
        else:
            raise ForstaError("Forsta data export is missing a respondent separator")


class ForstaClient:
    """Wraps GET /api/v1/... with the x-apikey header, retries and paging."""

    def __init__(
        self,
        host: str,
        api_key: str,
        timeout: int = 120,
        max_retries: int = 4,
    ) -> None:
        if not api_key:
            raise ForstaAuthError(
                "FORSTA_API_KEY is empty. Create one in the Forsta portal: "
                "avatar -> API Access -> Create new API key (64 characters)."
            )
        self.host = host
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {"x-apikey": api_key, "Accept": "application/json", "User-Agent": "coresight-cip/1.0"}
        )

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/api/v1"

    # ── low level ──────────────────────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, ForstaBusy)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=lambda state: state.attempt_number >= state.args[0].max_retries,   # FORSTA_MAX_RETRIES (default 4)
        reraise=True,
    )
    def _get(self, endpoint: str, *, _stream: bool = False, _body: dict | None = None, **params: Any) -> requests.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        transport = {"stream": True} if _stream else {}
        if _body is None:
            resp = self.session.get(url, params=params, timeout=self.timeout, **transport)
        else:   # only from read_post(), which has checked the endpoint against READ_ONLY_POSTS
            resp = self.session.post(url, json=_body, timeout=self.timeout)
        if resp.status_code == 401:
            resp.close()
            raise ForstaAuthError(
                f"401 from {url} — the API key is missing, wrong, or not permitted "
                f"for this survey path. Check the key's endpoint/IP restrictions."
            )
        if resp.status_code == 403:
            resp.close()
            raise ForstaAuthError(
                f"403 from {url} — the key is valid but the service account lacks access to this survey."
            )
        if resp.status_code >= 400:
            try:
                if _stream:
                    detail = next(resp.iter_content(chunk_size=400), b"").decode("utf-8", errors="replace")[:400]
                else:
                    detail = resp.text[:400]
            finally:
                resp.close()
            error = ForstaBusy if resp.status_code == 429 or resp.status_code >= 500 else ForstaError
            raise error(f"{resp.status_code} from {url}: {detail}")
        used = resp.headers.get("x-usage-today")
        if used:
            logger.debug("Forsta usage today: %s", used)
        return resp

    # ── survey endpoints ───────────────────────────────────────────────────
    def surveys(self) -> list[dict]:
        """Every survey the key can see: GET /api/v1/rh/companies/all/surveys."""
        return self._get("rh/companies/all/surveys").json()

    def survey_datamap(self, path: str) -> dict:
        return self._get(f"surveys/{path.strip('/')}/datamap", format="json").json()

    def survey_data(self, path: str, **params: Any) -> list[dict]:
        return list(self.iter_survey_data(path, **params))

    def iter_survey_data(self, path: str, **params: Any) -> Iterator[dict]:
        """Read one JSON export without buffering its body or all respondents.

        Callers stopping early must close the iterator. Transport failures after
        rows are yielded propagate; retrying a partial body would duplicate rows.
        """
        response = self._get(f"surveys/{path.strip('/')}/data", _stream=True, format="json", **params)
        try:
            yield from _json_records(response)
        except UnicodeDecodeError as exc:
            raise ForstaError("Forsta data export contains invalid UTF-8") from exc
        finally:
            response.close()

    def survey_quota(self, path: str) -> dict:
        """Each quota cell's limit and completes; 428 while the survey is hibernated."""
        return self._get(f"surveys/{path.strip('/')}/quota").json()

    # The fieldwork record (etl/fieldwork.py SURVEY_READS, COMPANY_READS): any of Forsta's read-only GET endpoints
    def read_json(self, endpoint: str, **params: Any) -> Any:
        """One read-only endpoint's JSON answer, as Forsta sent it (a GET: nothing in Forsta changes)."""
        return self._get(endpoint, **params).json()

    def read_post(self, endpoint: str, body: dict) -> requests.Response:
        """A POST that only computes (READ_ONLY_POSTS): a cross-tab, a saved report's tables or its file. Any other
        endpoint raises before anything is sent."""
        endpoint = endpoint.strip("/")
        if ".." in endpoint or not any(rule.fullmatch(endpoint) for rule in READ_ONLY_POSTS):   # "..": no path tricks
            raise ForstaError(f"Refused: POST {endpoint} is not one of the read-only POSTs (etl/forsta_client.py)")
        return self._get(endpoint, _body=body)

    def survey_file(self, path: str, name: str) -> bytes:
        """One of the survey's files as Forsta keeps it, such as survey.xml (the questionnaire's source and logic)."""
        return self._get(f"surveys/{path.strip('/')}/files/{name}").content

    def whoami(self) -> dict:
        """Cheapest call that proves the key works. Use in test_connection.py."""
        return self._get("rh/users/self").json()
