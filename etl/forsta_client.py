"""Thin client for the Forsta Surveys (Decipher) REST API.

Checked against https://se1.decipherinc.com on 2026-09-29: the API is enabled
and authenticates with the `x-apikey` header. The key on file is rejected with

    {"$error": "API user account is not valid: account disabled", "$code": 401}

(since replaced by a working key, Oct 2026). Every call is a GET: the client
never changes a survey in Forsta.

Reference: https://forstasurveys.zendesk.com/hc/en-us/articles/4409469957531
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ForstaError(RuntimeError):
    pass


class ForstaAuthError(ForstaError):
    pass


class ForstaBusy(ForstaError):
    """429 or a 5xx: worth retrying."""


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
                f"403 from {url} — the key is valid but the service account lacks access to this survey."
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ForstaBusy(f"{resp.status_code} from {url}: {resp.text[:400]}")
        if resp.status_code >= 400:
            raise ForstaError(f"{resp.status_code} from {url}: {resp.text[:400]}")
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
        return self._get(f"surveys/{path.strip('/')}/data", format="json", **params).json()

    def whoami(self) -> dict:
        """Cheapest call that proves the key works. Use in test_connection.py."""
        return self._get("rh/users/self").json()
