"""Environment-based configuration for the Consumer Insight Portal.

Follows the same LOCAL / STAGING / PRODUCTION pattern as market-data-stg so
deployment and secret handling are identical across Coresight portals.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


class Environment(Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_enabled: bool = False
    ssl_ca: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # avoids the ~4s Azure SSL re-handshake penalty

    sqlite_path: Optional[str] = None

    @property
    def url(self) -> str:
        """SQLAlchemy URL. Never log this — it contains the password."""
        from urllib.parse import quote_plus

        if self.sqlite_path:
            return f"sqlite:///{self.sqlite_path}"
        return (
            f"mysql+pymysql://{self.user}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )

    @property
    def connect_args(self) -> dict:
        if not self.ssl_enabled:
            return {}
        ca = self.ssl_ca
        if ca and not Path(ca).is_absolute():
            ca = str(REPO_ROOT / ca)
        if ca and Path(ca).exists():
            return {"ssl": {"ca": ca}}
        # Azure requires TLS; fall back to TLS without local CA pinning.
        return {"ssl": {}}


@dataclass(frozen=True)
class ForstaConfig:
    """Forsta Surveys (Decipher) REST API settings.

    The three values that matter are the host, the 64-character API key and
    the survey path. All are visible in the survey's portal URL except the key,
    which is issued in Portal -> avatar -> API Access.
    """

    host: str
    api_key: str
    survey_path: str
    layout_id: Optional[str] = None
    report_path: Optional[str] = None
    datafeed_name: Optional[str] = None
    timeout: int = 120
    max_retries: int = 4

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/api/v1"

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.api_key and self.survey_path)


class Config:
    def __init__(self) -> None:
        raw = _env("APP_ENV", "LOCAL").lower()
        self.environment = {
            "local": Environment.LOCAL,
            "staging": Environment.STAGING,
            "stg": Environment.STAGING,
            "production": Environment.PRODUCTION,
            "prod": Environment.PRODUCTION,
        }.get(raw, Environment.LOCAL)
        self.debug = _env("DEBUG", "0") in {"1", "true", "True"}

    @property
    def is_local(self) -> bool:
        return self.environment is Environment.LOCAL

    def database(self, role: str = "app") -> DatabaseConfig:
        """role='app' -> read-only account; role='etl' -> writer account."""
        # LOCAL runs against the STG (dwh_stg) database, like the Market Data
        # Portal's local launcher, unless a SQLite file or a local MySQL is named.
        if self.is_local and (_env("LOCAL_SQLITE_PATH") or _env("LOCAL_DB_HOST")):
            sqlite_path = _env("LOCAL_SQLITE_PATH")
            if sqlite_path:
                return DatabaseConfig(
                    host="", port=0, database=sqlite_path, user="", password="",
                    sqlite_path=str((REPO_ROOT / sqlite_path).resolve()
                                    if not Path(sqlite_path).is_absolute() else sqlite_path),
                )
            return DatabaseConfig(
                host=_env("LOCAL_DB_HOST", "127.0.0.1"),
                port=_int_env("LOCAL_DB_PORT", 3306),
                database=_env("LOCAL_DB_NAME", "csi_local"),
                user=_env("LOCAL_DB_USER", "root"),
                password=_env("LOCAL_DB_PASSWORD"),
                ssl_enabled=False,
                pool_size=_int_env("DB_POOL_SIZE", 5),
                max_overflow=_int_env("DB_MAX_OVERFLOW", 10),
            )

        if role == "app" and _env("APP_DB_USER"):
            user, password = _env("APP_DB_USER"), _env("APP_DB_PASSWORD")
        else:
            user, password = _env("STG_DB_USER"), _env("STG_DB_PASSWORD")

        return DatabaseConfig(
            host=_env("STG_DB_HOST"),
            port=_int_env("STG_DB_PORT", 3306),
            database=_env("STG_DB_NAME"),
            user=user,
            password=password,
            ssl_enabled=True,
            ssl_ca=_env("STG_DB_SSL_CA", "DigiCertGlobalRootG2.crt.pem"),
            pool_size=_int_env("DB_POOL_SIZE", 10),
            max_overflow=_int_env("DB_MAX_OVERFLOW", 20),
        )

    @property
    def forsta(self) -> ForstaConfig:
        return ForstaConfig(
            host=_env("FORSTA_HOST", "se1.decipherinc.com"),
            api_key=_env("FORSTA_API_KEY"),
            survey_path=_env("FORSTA_SURVEY_PATH"),
            layout_id=_env("FORSTA_DATA_LAYOUT_ID") or None,
            report_path=_env("FORSTA_REPORT_PATH") or None,
            datafeed_name=_env("FORSTA_DATAFEED_NAME") or None,
            timeout=_int_env("FORSTA_TIMEOUT_SECONDS", 120),
            max_retries=_int_env("FORSTA_MAX_RETRIES", 4),
        )

    @property
    def ingest_cond(self) -> str:
        return _env("INGEST_COND", "qualified")

    @property
    def batch_size(self) -> int:
        return _int_env("INGEST_BATCH_SIZE", 2000)


config = Config()
