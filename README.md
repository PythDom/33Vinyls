# 33Vinyls

A private music record **identifier, pressing detector & finder** for price checks and album collection, for me and a few friends.

**Platform:** installable web app (PWA) for Android phones (Chrome → *Add to Home screen*) and desktop browsers. Not on Google Play. Self-hosted on a Windows home server with Docker. Prices in EUR. Free by default.

- Scan a barcode, photograph a cover or label, or search by text → find the record on Discogs
- Pin down the exact pressing from the runout, catalogue number, barcode or a few quick questions
- Condition-aware price card and an instant "is it a deal?" verdict
- Whole collection and wantlist **searchable and browsable offline** on the phone
- Each friend links their own Discogs account; invite-only accounts; Tailscale-only access

Status: weeks 1–5 of the [proposal](docs/PROPOSAL.md) are built (see §12 there for what differs from the plan).

---

## 1. Run it on the Windows server

You need Docker Desktop (already running Syndic) and Git.

```powershell
cd D:\OneDrive\Python\33Vinyls
git pull
copy .env.example .env        # first time only, then edit .env (see below)
docker compose up -d --build  # first build takes a few minutes
```

Check it's running: open <http://localhost:7510/api/health> on the server. It should say `"ok": true`.

**`.env` for a first test:** keep `DISCOGS_MODE=demo`. Demo mode uses built-in fictional records, so you can try everything without a Discogs account. Set `PUBLIC_URL` once Tailscale is set up (step 2).

Data lives in the Docker volume `33vinyls_vinyls-data` (database, covers, secret key). It survives `docker compose down` and rebuilds. **Never run `docker compose down -v`**: that deletes the volume.

Update later with `git pull` then `docker compose up -d --build`.

## 2. Make it reachable from phones (Tailscale, HTTPS)

The container only listens on the server itself (`127.0.0.1:7510`). Phones reach it through Tailscale with HTTPS, which Android needs for the camera and for installing the app.

1. In the Tailscale admin console → **DNS**: turn on **MagicDNS** and **HTTPS Certificates**.
2. On the Windows server, in PowerShell (as administrator):
   ```powershell
   tailscale serve --bg 7510
   ```
   It prints the address, e.g. `https://vinyl-server.your-tailnet.ts.net`.
3. Put that address in `.env` as `PUBLIC_URL=…`, then `docker compose up -d`.
4. Share the server with each friend (Tailscale admin → Machines → the server → **Share**). They install the Tailscale app on their phone and accept.

Keep this address fixed: the phones' offline copy belongs to it.

## 3. Install on an Android phone

1. Turn Tailscale on, open the HTTPS address in **Chrome**.
2. First visit on your phone: create the **admin account** (the first account is the admin; everyone after needs an invite).
3. Chrome menu ⋮ → **Add to Home screen / Install app**.
4. Settings → **Protect storage**, so Android doesn't clear the offline copy when space is low.
5. Invite friends: Settings → **New invite** copies a link to send them.

## 4. Switch to real Discogs data

1. In `.env` set `DISCOGS_MODE=live`, then `docker compose up -d`.
2. Each person links their own Discogs account in **Settings**:
   - **Personal token** (works straight away): on discogs.com → Settings → Developers → *Generate new token*, paste it in 33Vinyls.
   - **Sign in with Discogs** (optional, nicer for friends): register an app at discogs.com → Settings → Developers, with callback URL `<PUBLIC_URL>/api/discogs/oauth/callback`, and put its key and secret in `.env` (`DISCOGS_CONSUMER_KEY`, `DISCOGS_CONSUMER_SECRET`).
3. For per-condition price suggestions, each person fills in their **Discogs seller settings** with currency **EUR**. Without that, the app shows the cheapest current listing only.

Records added in demo mode use fictional IDs: remove them, or start with a fresh volume, before going live.

## 5. Test checklist (on a real phone)

In demo mode:

1. **Find** → search `velvet static` → open *Neon Harbour (Harbourline HL 2001)* → price card in EUR → type `60` → *Is it a deal?* → green.
2. **Which pressing?** → runout `HL 2001 A2` → *Compare* → the repress is matched → *Add to collection*.
3. **Scan** → type barcode `5054197012341` → it finds the 2015 reissue. Try the camera on any real record barcode too (it will show "no match" in demo mode, which proves the scanner works).
4. Settings shows **✓ Offline ready**.
5. **Airplane mode** → close the app → reopen from the home screen → search, filter, open records with covers, edit a note → turn airplane mode off → the chip goes back to *Synced*.

The same checks run automatically: see *Development* below.

## Local setup (Windows home server, first time)

Code lives in `D:\OneDrive\Python\33Vinyls` and syncs with GitHub. The `Sync` folder inside it holds data copies and is ignored by git.

The folder already exists (it contains `Sync`), so link it to GitHub instead of cloning. In PowerShell:

```powershell
cd D:\OneDrive\Python\33Vinyls
git init
git remote add origin https://github.com/PythDom/33Vinyls.git
git fetch origin
git checkout -t origin/main
```

Afterwards: `git pull` to get updates. `git status` should never list anything under `Sync\`.

## Development

```
backend/   FastAPI + SQLite API (Python 3.13), Discogs client, demo catalogue, OCR, pressing detector
frontend/  React + Vite PWA, Dexie (IndexedDB) offline store, MiniSearch offline search
e2e/       Browser test of the offline must-have (Playwright, Android phone emulation)
```

```bash
# backend tests (demo mode, no network needed; OCR tests need the tesseract binary)
cd backend && pip install -r requirements-dev.txt && python -m pytest -q

# frontend: unit tests and build
cd frontend && npm ci && npm test && npm run build

# run locally: API serving the built app, demo data
cd backend && VINYLS_DATA_DIR=./.data VINYLS_STATIC_DIR=../frontend/dist DISCOGS_MODE=demo SECURE_COOKIES=false uvicorn vinyls.main:app --port 8000

# end-to-end offline test (needs Playwright + Chromium), against a fresh server
node e2e/offline.mjs http://localhost:8000
```

API docs: `/api/docs` on a running server.
