"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("VINYLS_DATA_DIR", "/data")))
    sync_dir: Path = field(default_factory=lambda: Path(os.environ.get("VINYLS_SYNC_DIR", "/sync")))
    # local time of the nightly export, HH:MM (container time zone: TZ in .env)
    nightly_export: str = field(default_factory=lambda: os.environ.get("NIGHTLY_EXPORT", "03:00"))
    background_jobs: bool = field(default_factory=lambda: _bool("BACKGROUND_JOBS", True))
    static_dir: Path = field(default_factory=lambda: Path(os.environ.get("VINYLS_STATIC_DIR", "/app/static")))
    # "live" talks to api.discogs.com; "demo" uses built-in fake data (no account needed).
    discogs_mode: str = field(default_factory=lambda: os.environ.get("DISCOGS_MODE", "live").strip().lower())
    discogs_consumer_key: str = field(default_factory=lambda: os.environ.get("DISCOGS_CONSUMER_KEY", ""))
    discogs_consumer_secret: str = field(default_factory=lambda: os.environ.get("DISCOGS_CONSUMER_SECRET", ""))
    # Public HTTPS address of the app, e.g. https://vinyl-server.tailnet.ts.net (needed for Discogs sign-in).
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", "").rstrip("/"))
    secure_cookies: bool = field(default_factory=lambda: _bool("SECURE_COOKIES", True))
    currency: str = "EUR"
    user_agent: str = "33Vinyls/0.1 +private-self-hosted"
    session_days: int = 180
    price_ttl_hours: int = 24
    release_ttl_days: int = 30

    @property
    def demo(self) -> bool:
        return self.discogs_mode == "demo"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "33vinyls.sqlite3"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.discogs_consumer_key and self.discogs_consumer_secret)


settings = Settings()
