"""Thin client for the Forsta Surveys (Decipher) REST API.

Verified against https://se1.decipherinc.com on 2026-09-28: the API is enabled
on that host and every endpoint below resolves — an unauthenticated call to
/api/v1/surveys/selfserve/58f/260908/datamap returns

    {"$error": "invalid key. ...", "$code": 401}

i.e. the ONLY missing piece is a valid 64-character API key in the
`x-apikey` header.

Reference: https://forstasurveys.zendesk.com/hc/en-us/articles/4409469957531
"""
from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ForstaError(RuntimeError):
    pass


class ForstaAuthError(ForstaError):
    pass


class ForstaClient:
    """Wraps GET /api/v1/... with the x-apikey header, retries and paging."""

    def __init__(
        self,
        host: str,
        api_key: str,
        survey_path: str,
        timeout: int = 120,
        max_retries: int = 4,
    ) -> None:
        if not api_key:
            raise ForstaAuthError(
                "FORSTA_API_KEY is empty. Create one in the Forsta portal: "
                "avatar -> API Access -> Create new API key (64 characters)."
            )
        self.host = host
        self.survey_path = survey_path.strip("/")
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
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _get(self, endpoint: str, **params: Any) -> requests.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 401:
            raise ForstaAuthError(
                f"401 from {url} — the API key is missing, wrong, or not permitted "
                f"for this survey path. Check the key's endpoint/IP restrictions."
            )
        if resp.status_code == 403:
            raise ForstaAuthError(
                f"403 from {url} — the key is valid but the service account lacks "
                f"access to directory '{self.survey_path.split('/')[1] if '/' in self.survey_path else '?'}'."
            )
        if resp.status_code >= 400:
            raise ForstaError(f"{resp.status_code} from {url}: {resp.text[:400]}")
        used = resp.headers.get("x-usage-today")
        if used:
            logger.debug("Forsta usage today: %s", used)
        return resp

    # ── survey endpoints ───────────────────────────────────────────────────
    def whoami(self) -> dict:
        """Cheapest call that proves the key works. Use in test_connection.py."""
        return self._get("rh/users/self").json()

    def datamap(self, fmt: str = "json") -> dict:
        """Survey definition: questions, rows, answer codes and labels.

        GET /api/v1/surveys/<survey>/datamap?format=json
        """
        return self._get(f"surveys/{self.survey_path}/datamap", format=fmt).json()

    def data(
        self,
        fmt: str = "json",
        cond: Optional[str] = "qualified",
        start: Optional[str] = None,
        end: Optional[str] = None,
        layout: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> Any:
        """Respondent-level data.

        GET /api/v1/surveys/<survey>/data?format=json&cond=qualified&start=...

        `cond` takes Forsta filter expressions ("qualified", "qualified and q3.r2").
        `start`/`end` bound the completion datetime — this is how the nightly
        incremental pull avoids re-reading the whole survey.
        """
        params: dict[str, Any] = {"format": fmt}
        if cond:
            params["cond"] = cond
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if layout:
            params["layout"] = layout
        if fields:
            params["fields"] = fields
        resp = self._get(f"surveys/{self.survey_path}/data", **params)
        return resp.json() if fmt == "json" else resp.text

    def layouts(self) -> Any:
        """Custom data layouts. A layout decides whether the export carries
        codes or labels — the sample files we were given use labels."""
        return self._get(f"surveys/{self.survey_path}/layouts").json()

    def completions(self) -> Any:
        """Field-progress counts — drives the 'survey health' page."""
        return self._get(f"surveys/{self.survey_path}/summary/completions").json()

    # ── incremental feed ───────────────────────────────────────────────────
    def datafeed(self, feed_name: str) -> Any:
        """GET /api/v1/datafeed/<feed> — returns only records not yet acked."""
        return self._get(f"datafeed/{feed_name}").json()

    def datafeed_ack(self, feed_name: str) -> Any:
        url = f"{self.base_url}/datafeed/{feed_name}/ack"
        resp = self.session.post(url, timeout=self.timeout)
        if resp.status_code >= 400:
            raise ForstaError(f"{resp.status_code} acking feed: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    def iter_records(self, **kwargs: Any) -> Iterator[dict]:
        payload = self.data(fmt="json", **kwargs)
        if isinstance(payload, dict):
            payload = payload.get("data", payload.get("records", []))
        for row in payload or []:
            yield row
