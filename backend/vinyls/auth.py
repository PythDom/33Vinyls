"""Accounts: invite-only registration, login sessions (cookie), invites, Discogs linking."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import db, discogs
from .config import settings
from .security import hash_password, hash_token, new_token, verify_password

COOKIE = "v33_session"
router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    invite: str | None = None
    display_name: str | None = None


def _user_dict(row) -> dict[str, Any]:
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"] or row["username"],
            "is_admin": bool(row["is_admin"])}


def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    if token:
        row = db.one(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash=? AND s.expires_at > ?",
            (hash_token(token), db.now()),
        )
        if row:
            return _user_dict(row)
    raise HTTPException(401, "Not signed in")


def admin_user(user: dict = Depends(current_user)) -> dict[str, Any]:
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only")
    return user


def _start_session(response: Response, user_id: int) -> None:
    token = new_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.session_days)
    db.run("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
           (hash_token(token), user_id, db.now(), expires.isoformat(timespec="seconds")))
    response.set_cookie(COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
                        samesite="lax", secure=settings.secure_cookies, path="/")


@router.get("/status")
def status() -> dict[str, Any]:
    has_users = db.one("SELECT 1 FROM users LIMIT 1") is not None
    return {"ok": True, "needs_setup": not has_users, "demo": settings.demo, "currency": settings.currency,
            "oauth_available": settings.oauth_enabled}


@router.post("/register")
def register(body: Credentials, response: Response) -> dict[str, Any]:
    username = body.username.strip()
    if not re.fullmatch(r"[\w.\-]+", username):
        raise HTTPException(400, "Username: letters, digits, dot, dash or underscore only.")
    first_user = db.one("SELECT 1 FROM users LIMIT 1") is None
    conn = db.connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not first_user:
            invite = db.one("SELECT * FROM invites WHERE code=? AND used_by IS NULL", ((body.invite or "").strip(),))
            if invite is None:
                raise HTTPException(403, "A valid invite code is needed.")
        if db.one("SELECT 1 FROM users WHERE username=?", (username,)):
            raise HTTPException(409, "That username is taken.")
        cur = conn.execute(
            "INSERT INTO users(username, display_name, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
            (username, (body.display_name or username).strip(), hash_password(body.password), 1 if first_user else 0, db.now()),
        )
        user_id = cur.lastrowid
        if not first_user:
            conn.execute("UPDATE invites SET used_by=?, used_at=? WHERE code=?", (user_id, db.now(), body.invite.strip()))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    _start_session(response, user_id)
    return _user_dict(db.one("SELECT * FROM users WHERE id=?", (user_id,)))


@router.post("/login")
def login(body: Credentials, response: Response) -> dict[str, Any]:
    row = db.one("SELECT * FROM users WHERE username=?", (body.username.strip(),))
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong username or password.")
    _start_session(response, row["id"])
    return _user_dict(row)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(COOKIE)
    if token:
        db.run("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict[str, Any]:
    return {**user, "discogs": discogs.link_status(user["id"]), "demo": settings.demo, "currency": settings.currency}


# ---------------------------------------------------------------- invites (admin)

@router.post("/invites")
def create_invite(user: dict = Depends(admin_user)) -> dict[str, str]:
    code = new_token(6)
    db.run("INSERT INTO invites(code, created_by, created_at) VALUES (?,?,?)", (code, user["id"], db.now()))
    return {"code": code}


@router.get("/invites")
def list_invites(user: dict = Depends(admin_user)) -> list[dict[str, Any]]:
    rows = db.all_("SELECT i.code, i.created_at, i.used_at, u.username AS used_by FROM invites i "
                   "LEFT JOIN users u ON u.id = i.used_by ORDER BY i.created_at DESC")
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- Discogs link

class TokenBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/discogs/token")
async def link_with_token(body: TokenBody, user: dict = Depends(current_user)) -> dict[str, Any]:
    creds = discogs.Credentials("token", body.token.strip())
    try:
        ident = await discogs.identity(creds)
    except discogs.DiscogsError as exc:
        raise HTTPException(400, f"Token not accepted by Discogs: {exc}") from exc
    discogs.save_link(user["id"], "token", ident.get("username", ""), body.token.strip())
    return discogs.link_status(user["id"])


@router.get("/discogs/oauth/start")
async def oauth_start(user: dict = Depends(current_user)) -> dict[str, str]:
    if not settings.oauth_enabled:
        raise HTTPException(400, "Discogs sign-in is not configured on the server (DISCOGS_CONSUMER_KEY/SECRET).")
    if not settings.public_url:
        raise HTTPException(400, "PUBLIC_URL is not set on the server.")
    try:
        token, secret = await discogs.oauth_request_token(settings.public_url + "/api/discogs/oauth/callback")
    except discogs.DiscogsError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    db.run("DELETE FROM oauth_pending WHERE user_id=?", (user["id"],))
    db.run("INSERT INTO oauth_pending(request_token, request_secret, user_id, created_at) VALUES (?,?,?,?)",
           (token, secret, user["id"], db.now()))
    return {"url": f"{discogs.AUTHORIZE_URL}?oauth_token={token}"}


@router.get("/discogs/oauth/callback")
async def oauth_callback(oauth_token: str, oauth_verifier: str, user: dict = Depends(current_user)):
    pending = db.one("SELECT * FROM oauth_pending WHERE request_token=? AND user_id=?", (oauth_token, user["id"]))
    if pending is None:
        return RedirectResponse("/#/settings?discogs=failed")
    db.run("DELETE FROM oauth_pending WHERE request_token=?", (oauth_token,))
    try:
        token, secret = await discogs.oauth_access_token(oauth_token, pending["request_secret"], oauth_verifier)
        ident = await discogs.identity(discogs.Credentials("oauth", token, secret))
    except discogs.DiscogsError:
        return RedirectResponse("/#/settings?discogs=failed")
    discogs.save_link(user["id"], "oauth", ident.get("username", ""), token, secret)
    return RedirectResponse("/#/settings?discogs=linked")


@router.delete("/discogs/link")
def unlink(user: dict = Depends(current_user)) -> dict[str, Any]:
    db.run("DELETE FROM discogs_links WHERE user_id=?", (user["id"],))
    return discogs.link_status(user["id"])
