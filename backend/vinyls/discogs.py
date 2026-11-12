"""Discogs API access.

Each user links their own Discogs account, either with Discogs sign-in (OAuth 1.0a,
PLAINTEXT signature over HTTPS) or by pasting a personal access token. In demo mode
(DISCOGS_MODE=demo) a built-in fake catalogue is used instead, so the app can be
tested without any account or network access.
"""
from __future__ import annotations

import asyncio
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from . import db, demo_data
from .config import settings
from .security import decrypt, encrypt

API = "https://api.discogs.com"
AUTHORIZE_URL = "https://www.discogs.com/oauth/authorize"


class DiscogsError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class NotLinked(DiscogsError):
    def __init__(self) -> None:
        super().__init__("Link your Discogs account in Settings first.", status=409)


@dataclass
class Credentials:
    method: str            # 'oauth' | 'token' | 'demo'
    token: str
    secret: str = ""


def _oauth_header(token: str = "", token_secret: str = "", **extra: str) -> str:
    params = {
        "oauth_consumer_key": settings.discogs_consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "PLAINTEXT",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        "oauth_signature": f"{settings.discogs_consumer_secret}&{token_secret}",
    }
    if token:
        params["oauth_token"] = token
    params.update(extra)
    return "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in params.items())


def auth_headers(creds: Credentials) -> dict[str, str]:
    headers = {"User-Agent": settings.user_agent}
    if creds.method == "oauth":
        headers["Authorization"] = _oauth_header(creds.token, creds.secret)
    elif creds.method == "token":
        headers["Authorization"] = f"Discogs token={creds.token}"
    return headers


# ---------------------------------------------------------------- stored links

def get_credentials(user_id: int) -> Credentials:
    if settings.demo:
        return Credentials("demo", "demo")
    row = db.one("SELECT * FROM discogs_links WHERE user_id=?", (user_id,))
    if row is None:
        raise NotLinked()
    return Credentials(row["method"], decrypt(row["token_enc"]), decrypt(row["secret_enc"]) if row["secret_enc"] else "")


def save_link(user_id: int, method: str, username: str, token: str, secret: str = "") -> None:
    db.run(
        "INSERT INTO discogs_links(user_id, username, method, token_enc, secret_enc, linked_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, method=excluded.method, "
        "token_enc=excluded.token_enc, secret_enc=excluded.secret_enc, linked_at=excluded.linked_at",
        (user_id, username, method, encrypt(token), encrypt(secret) if secret else None, db.now()),
    )


def link_status(user_id: int) -> dict[str, Any]:
    if settings.demo:
        return {"linked": True, "username": "demo", "method": "demo", "demo": True, "oauth_available": False}
    row = db.one("SELECT username, method, linked_at FROM discogs_links WHERE user_id=?", (user_id,))
    base = {"demo": False, "oauth_available": settings.oauth_enabled}
    if row is None:
        return {"linked": False, **base}
    return {"linked": True, "username": row["username"], "method": row["method"], "linked_at": row["linked_at"], **base}


# ---------------------------------------------------------------- HTTP

_rate_lock = asyncio.Lock()
_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=API, timeout=15.0)
    return _client


async def _get(creds: Credentials, path: str, params: dict[str, Any] | None = None) -> Any:
    for attempt in range(3):
        async with _rate_lock:
            try:
                response = await client().get(path, params=params, headers=auth_headers(creds))
            except httpx.HTTPError as exc:
                raise DiscogsError(f"Discogs could not be reached ({exc.__class__.__name__}).") from exc
            remaining = int(response.headers.get("X-Discogs-Ratelimit-Remaining", "60"))
            if remaining < 5:
                await asyncio.sleep(2)
        if response.status_code == 429 and attempt < 2:
            await asyncio.sleep(5 * (attempt + 1))
            continue
        if response.status_code == 401:
            raise DiscogsError("Discogs refused the request: reconnect your Discogs account in Settings.", 409)
        if response.status_code == 404:
            raise DiscogsError("Not found on Discogs.", 404)
        if response.status_code >= 400:
            raise DiscogsError(f"Discogs error {response.status_code}.")
        return response.json()
    raise DiscogsError("Discogs rate limit reached, try again in a minute.", 429)


# ---------------------------------------------------------------- API calls

async def identity(creds: Credentials) -> dict[str, Any]:
    if creds.method == "demo":
        return {"username": "demo"}
    return await _get(creds, "/oauth/identity")


async def search(creds: Credentials, **params: Any) -> list[dict[str, Any]]:
    params = {k: v for k, v in params.items() if v}
    params.setdefault("type", "release")
    params.setdefault("per_page", 25)
    if creds.method == "demo":
        return demo_data.search(**params)
    data = await _get(creds, "/database/search", params)
    return data.get("results", [])


async def release(creds: Credentials, release_id: int) -> dict[str, Any]:
    if creds.method == "demo":
        found = demo_data.release(release_id)
        if not found:
            raise DiscogsError("Not found on Discogs.", 404)
        return found
    return await _get(creds, f"/releases/{release_id}", {"curr_abbr": settings.currency})


async def master_versions(creds: Credentials, master_id: int, max_pages: int = 4) -> list[dict[str, Any]]:
    if creds.method == "demo":
        return demo_data.versions(master_id)
    versions: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = await _get(creds, f"/masters/{master_id}/versions", {"page": page, "per_page": 100})
        versions.extend(data.get("versions", []))
        if page >= data.get("pagination", {}).get("pages", 1):
            break
    return versions


async def marketplace_stats(creds: Credentials, release_id: int) -> dict[str, Any]:
    if creds.method == "demo":
        return demo_data.stats(release_id)
    return await _get(creds, f"/marketplace/stats/{release_id}", {"curr_abbr": settings.currency})


async def price_suggestions(creds: Credentials, release_id: int) -> dict[str, Any] | None:
    """Needs the user's Discogs seller settings to be filled in; returns None otherwise."""
    if creds.method == "demo":
        return demo_data.suggestions(release_id)
    try:
        return await _get(creds, f"/marketplace/price_suggestions/{release_id}")
    except DiscogsError:
        return None


async def fetch_image(url: str) -> bytes:
    if url.startswith("demo:"):
        return demo_data.cover_png(int(url.split(":", 1)[1]))
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": settings.user_agent}) as http:
        response = await http.get(url)
        response.raise_for_status()
        return response.content


# ---------------------------------------------------------------- OAuth flow

async def oauth_request_token(callback_url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=15.0) as http:
        response = await http.get(
            f"{API}/oauth/request_token",
            headers={
                "User-Agent": settings.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": _oauth_header(oauth_callback=callback_url),
            },
        )
    if response.status_code != 200:
        raise DiscogsError(f"Discogs sign-in could not start ({response.status_code}).")
    data = dict(urllib.parse.parse_qsl(response.text))
    return data["oauth_token"], data["oauth_token_secret"]


async def oauth_access_token(request_token: str, request_secret: str, verifier: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=15.0) as http:
        response = await http.post(
            f"{API}/oauth/access_token",
            headers={
                "User-Agent": settings.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": _oauth_header(request_token, request_secret, oauth_verifier=verifier),
            },
        )
    if response.status_code != 200:
        raise DiscogsError(f"Discogs sign-in failed ({response.status_code}).")
    data = dict(urllib.parse.parse_qsl(response.text))
    return data["oauth_token"], data["oauth_token_secret"]
