"""Background work inside the app process (runs every minute):

- complete imported records with full Discogs data (barcodes, runouts, tracklist → offline search),
- refresh prices of records in collections, so collection values stay current,
- automatic exports to the Sync folder (nightly, and after a burst of changes).

Discogs allows 60 requests per minute per account; these jobs use at most ~20,
leaving room for what people do in the app.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from . import backup, catalog, db, discogs, prices
from .config import settings

log = logging.getLogger("33vinyls.jobs")
ENRICH_PER_RUN = 8
PRICES_PER_RUN = 5          # 2 requests each
PRICE_MAX_AGE_DAYS = 7


def _creds_for_release(release_id: int) -> discogs.Credentials | None:
    for row in db.all_("SELECT DISTINCT user_id FROM items WHERE release_id=? AND deleted=0", (release_id,)):
        try:
            return discogs.get_credentials(row["user_id"])
        except discogs.NotLinked:
            continue
    return None


async def enrich_batch(limit: int = ENRICH_PER_RUN) -> int:
    rows = db.all_("SELECT id FROM releases WHERE complete=0 AND id IN (SELECT release_id FROM items WHERE deleted=0) LIMIT ?", (limit,))
    done = 0
    for row in rows:
        creds = _creds_for_release(row["id"])
        if creds is None:
            continue
        try:
            await catalog.get_release(creds, row["id"], refresh=True)
            done += 1
        except discogs.DiscogsError as exc:
            log.info("enrich %s: %s", row["id"], exc)
            if exc.status == 429:
                break
    return done


async def refresh_prices_batch(limit: int = PRICES_PER_RUN) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=PRICE_MAX_AGE_DAYS)).isoformat(timespec="seconds")
    rows = db.all_(
        "SELECT DISTINCT i.release_id FROM items i LEFT JOIN prices p ON p.release_id = i.release_id "
        "WHERE i.deleted=0 AND i.kind='collection' AND (p.fetched_at IS NULL OR p.fetched_at < ?) "
        "ORDER BY p.fetched_at IS NOT NULL, p.fetched_at LIMIT ?", (cutoff, limit))
    done = 0
    for row in rows:
        creds = _creds_for_release(row["release_id"])
        if creds is None:
            continue
        try:
            await prices.price_card(creds, row["release_id"], refresh=True)
            done += 1
        except discogs.DiscogsError as exc:
            log.info("price %s: %s", row["release_id"], exc)
            if exc.status == 429:
                break
    return done


def export_if_due(now: datetime | None = None) -> str | None:
    reason = backup.due_for_export(now or datetime.now().astimezone())
    if reason is None:
        return None
    ok, problem = backup.available()
    if not ok:
        return None
    try:
        backup.export(reason)
        return reason
    except Exception as exc:  # keep the loop alive
        log.warning("export failed: %s", exc)
        return None


async def tick() -> None:
    await enrich_batch()
    await refresh_prices_batch()
    await asyncio.to_thread(export_if_due)


async def loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await tick()
        except Exception as exc:  # pragma: no cover
            log.warning("background jobs: %s", exc)
        await asyncio.sleep(60)
