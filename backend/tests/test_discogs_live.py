"""The live Discogs client, against a simulated Discogs server (no network)."""
import asyncio

import httpx

from vinyls import discogs


def test_live_search_sends_token_and_parses_results(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["agent"] = request.headers.get("User-Agent")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"results": [{"id": 1, "type": "release", "title": "A - B", "year": "1999", "label": ["L"], "catno": "X1", "format": ["Vinyl"], "thumb": "", "cover_image": ""}]},
                              headers={"X-Discogs-Ratelimit-Remaining": "55"})

    monkeypatch.setattr(discogs, "_client", httpx.AsyncClient(base_url=discogs.API, transport=httpx.MockTransport(handler)))
    creds = discogs.Credentials("token", "abc123token")
    results = asyncio.run(discogs.search(creds, q="kestrel union"))
    assert results[0]["title"] == "A - B"
    assert seen["auth"] == "Discogs token=abc123token"
    assert seen["agent"].startswith("33Vinyls/")
    assert seen["params"]["q"] == "kestrel union" and seen["params"]["type"] == "release"


def test_live_unauthorised_asks_to_relink(monkeypatch):
    monkeypatch.setattr(discogs, "_client", httpx.AsyncClient(base_url=discogs.API, transport=httpx.MockTransport(lambda r: httpx.Response(401, json={}))))
    try:
        asyncio.run(discogs.search(discogs.Credentials("token", "bad-token-xx"), q="x"))
    except discogs.DiscogsError as exc:
        assert exc.status == 409 and "reconnect" in str(exc)
    else:
        raise AssertionError("expected DiscogsError")
