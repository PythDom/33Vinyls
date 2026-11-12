# 33Vinyls — App Proposal

**A private web app, installable on Android, that identifies a vinyl record, tells you which pressing it is and what it is worth, and keeps your collection and wantlist in one place.**

Status: Draft proposal · v0.9 · 2026-11-12

> **Project constraints**
> - **Web app required**, and it **must run on Android** → built as an installable web app (PWA) that runs in Chrome on Android and in any desktop browser.
> - **Private use:** for me and a few interested friends. **No Google Play release.**
> - **Free by default:** everything works on free APIs and self-hosting. Paid services are optional plug-ins.
> - **Final objective (must-haves):** (1) the app runs on **Android smartphones**; (2) each user's **collection can be searched and browsed fully offline**. See §3.6 for the acceptance tests.
> - **Hosted on my Windows home server** in Docker containers (Docker Desktop).
> - **Data synced outside the container to OneDrive**, using the same approach as my Syndic app, with automatic exports added (see §5.6).
> - **Sharing between friends is opt-in**, off by default.
> - **Prices in EUR.**
> - **Each friend links their own Discogs account.**
> - **Audio recognition is on hold** (see §9).

---

## 1. The problem

Every time I pick up a record, three questions come up:

1. **What is this, exactly?** The same album can exist in hundreds of pressings (country, label, year, reissue, colour). A first pressing can be worth 10–100x a later reissue.
2. **What is it worth?** Prices are scattered across Discogs, eBay and shop price tags, and condition changes the value a lot.
3. **Do I already own it / do I want it?** Without the collection at hand, it's easy to buy duplicates or miss something on the wantlist.

33Vinyls puts **identify → pressing → price → collection → wantlist** in one quick flow that works in a record shop.

## 2. Users

A small, invite-only group: me plus a handful of friends. Each person has their own account, collection and wantlist. No public sign-up, no ads, no shop features.

| Situation | Need |
|---|---|
| **Digging in a shop / flea market** | Decide in seconds if a bin record is worth buying; poor signal is common |
| **Cataloguing at home** | Scan a shelf quickly; edit details comfortably on a laptop |
| **Checking with friends** | If both have opted in, see whether a friend owns or wants a record |

## 3. Core features

### 3.1 Identify — "What is this record?"

| Mode | How it works | Notes |
|---|---|---|
| **Barcode scan** | Phone camera reads the UPC/EAN → Discogs barcode search | Exact for modern releases; most pre-~1980 records have no barcode |
| **Cover photo** | Text on the cover is read (OCR) → Discogs search → candidates re-ranked by comparing the photo with their cover images | No huge image database to build or host |
| **Label photo** | OCR of label name and catalogue number → Discogs search | Separates label variants |
| **Runout / matrix etching** | Photo of the dead-wax text + OCR, then the user corrects it → match against Discogs matrix data | The most reliable way to pin down a pressing; etched text is hard to OCR, so manual correction is expected |
| **Text search** | Artist / title / catalogue number | Always available |
| **AI photo identification** *(optional, paid)* | Send the photo to a vision-capable AI API to read the cover/label and suggest the release | Off by default; enabled per user with their own API key |
| ~~Listen (audio)~~ | ~~Audio fingerprint~~ | **On hold** |

### 3.2 Detect — "Which pressing is it?"

- Shows candidate pressings ranked by matching evidence (barcode, catalogue #, label text, matrix).
- Asks **one question at a time** to narrow it down ("Does the runout say *A1* or *A2*?", "Orange or black label?"), based on the differences between the candidates.
- Shows how confident the match is and flags valuable variants (e.g. first pressings).

### 3.3 Price check — "What is it worth?"

- **Price card in EUR:** low / median / high, number for sale, source and date of each figure. Prices listed in other currencies are converted to EUR, and the original is shown alongside.
- **Condition-aware:** pick media and sleeve grade (Goldmine scale: M, NM, VG+, VG, G+, G, F, P).
- **Deal check:** type the shop's price → green / amber / red verdict.
- **Sources:** Discogs marketplace data, fetched with each friend's own linked Discogs account and requested in EUR. Optionally, current eBay listings from euro marketplaces (e.g. eBay.de, .fr, .it, .es) via a free developer account.
- Prices are cached so repeat lookups are instant and work offline.

### 3.4 Collection

- Add from any scan; **bulk mode** for scanning a shelf, then a review queue to confirm pressings and grades.
- Fields: grade, purchase price/date/place, notes, photos, storage location.
- **Value dashboard:** total value, most valuable items, gain vs. purchase price.
- **Duplicate warning** when scanning something already owned.
- **Discogs link:** each friend connects their own Discogs account once (Discogs sign-in, no password shared with the app). Their Discogs collection and wantlist are imported, and records added in 33Vinyls can optionally be pushed back to Discogs.
- **CSV import/export**, so the data is never locked in.
- **Offline:** the whole collection can be searched and browsed with no connection (see §3.6).

### 3.5 Wantlist & finder

- Wantlist with target pressing (or "any") and max price.
- **In-shop match:** wanted records are highlighted while scanning.
- **Price watch** (later): a daily check that flags listings below your max price.
- **Shop list:** a simple shared list/map of record shops and fairs that friends add to.
- **Opt-in sharing with friends.** Nothing is shared by default. Each person chooses separately:
  - share my **collection** (on/off)
  - share my **wantlist** (on/off)
  - show **values and purchase prices** (off unless explicitly turned on)
  - hide individual records
  
  When both sides share, scans show "Alex owns this" / "Sam wants this", which helps with swaps. Sharing can be turned off at any time and takes effect immediately.

### 3.6 Offline-first collection (must-have)

The phone keeps a **complete local copy** of the user's own collection and wantlist. The app always reads from this local copy first; the server is only used to sync changes and fetch new data. Losing the connection never blocks search or browsing.

**What is stored on the phone (per user)**

| Data | Stored offline | Size estimate (2,000 records) |
|---|---|---|
| Collection + wantlist records (artist, title, label, cat#, year, country, format, matrix, grade, notes, location, purchase info) | All of it | ~5 MB |
| Cover thumbnails (~300 px JPEG/WebP) | All of them | ~30–40 MB |
| Last-known prices (EUR) | All of them, with date | < 1 MB |
| Full-size photos taken by the user | Only the most recent / pinned ones | optional |
| Friends' shared collections (opt-in) | Optional setting, off by default | — |

**What works offline**
- Open the installed app from the home screen without any connection (app shell cached by a service worker).
- **Search** as you type: artist, title, label, catalogue number, barcode, matrix/runout text, notes, storage location; tolerant of accents and small typos. Done on the phone with a local search index (e.g. MiniSearch), never on the server.
- **Browse, filter and sort:** by artist, label, genre, year, decade, country, format, grade, location, date added, value.
- Open a record's detail page with cover, details, notes and last-known price (shown with its date).
- **Scan a barcode** and check it against my **own collection and wantlist** ("You own this" / "On your wantlist").
- Add or edit records and notes: saved locally and queued, then synced automatically when back online.

**Needs a connection (server reachable via Tailscale)**
- Identifying a record that is not in my collection (Discogs lookups), fresh prices, OCR-to-Discogs search, Discogs import, sharing with friends.

**How it is guaranteed**
- **First sync downloads everything:** on first login the full collection, wantlist and thumbnails are downloaded; afterwards only changes are synced. The app shows "Offline ready ✓ — 1,234 records, synced 5 min ago".
- **Persistent storage:** the app requests persistent storage (`navigator.storage.persist()`), which Chrome grants to installed apps, so Android does not clear the data when space is low. Status shown in Settings.
- **Fixed address:** the offline data belongs to the app's web address, so the Tailscale address is fixed once and never changed (changing it would mean a new download).
- **No hanging:** when the server can't be reached (no signal, Tailscale off, server down), requests time out quickly and the app keeps running from local data.
- **Safe to lose:** the phone copy is a cache. If the app or Chrome data is wiped, everything is downloaded again from the server; unsynced edits are the only risk, so the app warns when edits are waiting to sync.

**Acceptance tests (on a real Android phone)**
1. Install the app, sign in, wait for "Offline ready".
2. Turn on **airplane mode**, close the app, reopen it from the home screen → it opens.
3. Search by artist, by catalogue number and with a typo → correct results in under 0.5 s with 2,000 records.
4. Browse by artist and by storage location, filter by decade, open 10 records → covers and details shown.
5. Scan the barcode of an owned record → "You own this".
6. Edit a note offline, reconnect → change appears on the server and in the next OneDrive export.
7. Repeat 2–4 on the oldest friend's phone (minimum Android 8 with current Chrome).

## 4. Key flows

**In the shop**
`Open app (installed on home screen) → camera opens → scan barcode or snap cover → pick pressing (snap runout if needed) → price card + deal verdict → add to collection / wantlist / skip`

**At home**
`Laptop or phone → bulk mode → scan cover after cover → review queue on the laptop → confirm pressings and grades → value updated`

## 5. Architecture

```
┌────────────────────────────────┐        ┌───────────────────────────────────┐
│ Web app (PWA)                  │        │ Small backend (Docker)            │
│ Android Chrome + desktop       │ HTTPS  │ - Accounts (invite-only)          │
│ - Camera, barcode, OCR         ├───────►│ - Collection / wantlist / sync    │
│ - Offline store (IndexedDB)    │        │ - Discogs/eBay proxy + cache      │
│ - Installable, home-screen icon│        │   (keeps API tokens off devices)  │
└────────────────────────────────┘        │ - Cover re-ranking, price watch   │
                                          │ - Optional paid AI plug-in        │
                                          └──────┬─────────────────┬──────────┘
                                                 │                 │
                                  ┌──────────────▼───────┐  ┌──────▼─────────────────┐
                                  │ Docker volume:       │  │ Discogs API (per-friend│
                                  │ live SQLite + photos │  │ OAuth, free)           │
                                  └──────────┬───────────┘  │ MusicBrainz / Cover Art│
                                             │ scheduled    │ Archive (free)         │
                                             ▼ export       │                        │
                                  ┌──────────────────────┐  │                        │
                                  │ Windows folder       │  │                        │
                                  │ OneDrive\…\33Vinyls  │  │                        │
                                  │ → OneDrive cloud     │  │ eBay API (optional)    │
                                  └──────────────────────┘  │ AI vision API (opt.)   │
                                                            └────────────────────────┘
```

### 5.1 Why a web app (PWA) for Android

One codebase covers both requirements:

- **Runs on Android** in Chrome and can be **installed to the home screen**: full screen, own icon, works offline. No Play Store needed.
- **Runs on any laptop/desktop browser** for comfortable bulk editing.
- Friends just open a link and accept an invite. Updates arrive on next launch; nothing to reinstall.
- Chrome on Android supports camera access and the built-in Barcode Detection API. A JavaScript fallback handles other browsers.

Trade-off: camera control and scanning speed are a little below a native app. That's acceptable for personal use. If it ever matters, the same web app can be wrapped as a sideloaded APK (e.g. a Trusted Web Activity or Capacitor build) without a rewrite.

### 5.2 Suggested stack (all free / open source)

| Layer | Choice | Why |
|---|---|---|
| Frontend | TypeScript + React (or SvelteKit), Vite, `vite-plugin-pwa` | Mature PWA tooling, works well on Android Chrome |
| Offline storage | IndexedDB via Dexie, persistent storage requested; service worker (Workbox) for the app shell and thumbnails | Whole collection usable with no signal |
| Offline search | MiniSearch (or FlexSearch) index built on the phone | Instant search as you type, no server needed |
| Barcode | Browser BarcodeDetector API, ZXing-js fallback | Fast on Android Chrome |
| OCR | Tesseract.js (in browser) | Free, offline; runout text needs manual correction anyway |
| Cover re-ranking | Small image-embedding model (e.g. CLIP via ONNX Runtime) on the backend | Compares the photo with a handful of candidate covers only |
| Backend | Python + FastAPI | Simple; good image/ML libraries |
| Database | SQLite inside a Docker volume | Plenty for a few users; snapshots exported to a Windows folder (§5.6) |
| Hosting | Docker Desktop (WSL 2) on my Windows home server, one `docker compose` file | Uses hardware I already have; €0/month |
| Remote access + HTTPS | Tailscale on the Windows host (`tailscale serve`); friends join the Tailscale network (§5.7) | Free; nothing exposed to the public internet; no router port-forwarding; HTTPS is **required** for camera access in the browser |
| Auth | Invite codes + passkeys or email/password; Discogs linked per user via OAuth | Keeps it private; each friend uses their own Discogs account |

### 5.3 Free vs. optional paid services

| Service | Free baseline | Optional paid upgrade |
|---|---|---|
| Release data & prices | Discogs API, each friend's own linked account (rate limit ~60 requests/min per account) | — |
| Metadata & cover art | MusicBrainz, Cover Art Archive | — |
| eBay listings | eBay developer account (free) | — |
| Photo identification | OCR + Discogs search + cover re-ranking | AI vision API with the user's own key (pay per use) |
| Hosting | Windows home server + Docker Desktop + Tailscale | — |
| Backups / sync | Snapshots + photos exported to the OneDrive folder; OneDrive uploads them | More OneDrive storage, only if photos outgrow the free/included space |

Each paid service is behind a setting and only turns on when an API key is entered. The app works fully without any of them.

### 5.4 Data source notes

- Discogs: each friend links their own account through Discogs' sign-in (OAuth). The app never sees their Discogs password; their access tokens are stored encrypted on the server and can be revoked from either the app or Discogs.
- Each friend's requests use their own token, so they each get their own rate limit. Public release data is still cached on the backend and shared, so the same record isn't fetched twice.
- Discogs price suggestions require the user to have filled in their Discogs seller settings; friends should set EUR there. If they haven't, the app falls back to marketplace stats requested in EUR.
- Attribution to Discogs is shown on release and price pages; personal, non-commercial use.
- Discogs marketplace **sold history** is not available through the API; prices are based on current listings and Discogs price suggestions.
- API tokens live on the backend, not in the browser, and are excluded from the sync-folder exports.

### 5.5 Home server setup (Windows + Docker), same layout as Syndic

```
Windows home server
├─ Docker Desktop (WSL 2 backend, starts with Windows)
│   ├─ Syndic           – port 7500 (existing)
│   └─ 33Vinyls (docker compose)  – port 7510
│       ├─ web      – serves the PWA + API (FastAPI)
│       └─ worker   – price cache refresh, scheduled sync, price watch
│       volumes:
│       ├─ 33vinyls-data → /data      named volume: live SQLite DB, photos, secret key
│       └─ .\Sync → /sync   bind mount (D:\OneDrive\Python\33Vinyls\Sync): copies only
├─ Tailscale (Windows app) → https://<server>.<tailnet>.ts.net → localhost:7510
└─ OneDrive client → uploads the sync folder to the cloud continuously
```

- Same pattern as Syndic: `compose.yaml` with `build: .`, `restart: unless-stopped`, an `.env` file read at start-up (never baked into the image), and a **named volume** for the live data.
- First start: the entrypoint creates an empty database in the volume and runs migrations; it never overwrites an existing database, even after a rebuild.
- Docker Desktop set to start at login; the PC's sleep setting turned off.
- Updating: `git pull && docker compose up -d --build`, run in `D:\OneDrive\Python\33Vinyls`.

### 5.5.1 Code location and GitHub

The code lives in **`D:\OneDrive\Python\33Vinyls`** and is a clone of the GitHub repository `PythDom/33Vinyls`. The `Sync` folder sits inside it but is **never committed** (it holds personal data and the repository is public).

```
D:\OneDrive\Python\33Vinyls\        ← git working copy (synced with GitHub)
├─ .git\
├─ .gitignore          ← excludes Sync\, .env, databases, build output
├─ .gitattributes      ← keeps shell scripts in Linux line endings for Docker
├─ compose.yaml        ← bind mount "./Sync:/sync"
├─ .env                ← secrets, local only, never committed
├─ app\ …              ← source code
├─ docs\PROPOSAL.md
└─ Sync\               ← data copies, local + OneDrive only, never committed
```

- **Two different syncs, two different jobs:** GitHub holds the **code** (pushed and pulled with git); OneDrive holds the **data copies** in `Sync\` (and, as a side effect, also uploads the code folder).
- **Dependencies stay inside Docker:** packages (Python, Node) are installed only while the Docker image builds, so there are no huge `node_modules` / `.venv` folders on the PC for OneDrive to upload.
- **Git inside OneDrive:** works fine for one PC. Avoid editing the same working copy from two PCs at once through OneDrive (that can corrupt `.git`); on another PC, clone from GitHub instead. If OneDrive locks a file during `git pull`, pause OneDrive syncing for a moment and retry.
- **Line endings:** `.gitattributes` forces Linux line endings for `*.sh` and `Dockerfile`, so Git on Windows doesn't break the container's start-up script.

### 5.6 Syncing data outside the container (based on Syndic's approach)

33Vinyls reuses what already works in Syndic, and closes the gaps found there.

**Kept from Syndic**
- Live data stays in a **named Docker volume** (fast, no Windows ↔ Docker file-locking problems).
- Copies are made with **SQLite's backup API**, so they are consistent even while the app is running.
- **One-way per run, direction chosen by me:** *container → folder* (export/backup) or *folder → container* (restore). No merging; the target is replaced.
- **Back up before replacing:** before any restore, the current container database is saved first as `db-before-restore-<date>.sqlite3`.
- **Same controls:** a **Sync** card in the app's admin page (pick direction, tick the confirmation box, click) and a command-line equivalent (`docker compose exec web python -m vinyls.sync export|restore`).
- The copies land in **OneDrive** (`D:\OneDrive\Python\33Vinyls\Sync`), so the OneDrive client uploads them to the cloud like Syndic's backups.

**Improved over Syndic (its gaps)**

| Syndic gap | 33Vinyls |
|---|---|
| Nothing leaves the container until someone runs a sync manually | **Automatic export** nightly (worker) and after bulk-scan sessions, plus the manual button |
| Uploaded files never copied out | **Photos are exported too**, alongside the database |
| Sync runs from the local server via `docker compose exec` (needs the PC session) | The container writes directly to the OneDrive folder through a bind mount, so a sync can be started from the phone |
| Backup files pile up (41 in Syndic) | **Retention:** keep 14 daily + 8 weekly + 12 monthly snapshots; older ones deleted automatically |
| Two independent databases (local + container) can diverge | **Only one live database** (the container); there is no second local server to keep in step |

**Folder layout**

```
D:\OneDrive\Python\33Vinyls\Sync\
├─ db\        33vinyls-2026-11-11T0300.sqlite3     – snapshots (with retention)
│             db-before-restore-<date>.sqlite3      – safety copy taken before a restore
├─ photos\    <user>\…                              – record photos (mirrored, new/changed files only)
├─ export\    <user>\collection.csv, wantlist.csv   – readable in Excel without the app
└─ restore\   put a snapshot here to restore it from the Sync card
```

- **OneDrive-safe writes:** each file is written under a temporary name and renamed when complete, so OneDrive never uploads a half-written snapshot.
- **OneDrive "Files On-Demand":** mark the `Sync` folder *Always keep on this device*, so a restore never hits a cloud-only placeholder.
- **Never exported:** the secret key, Discogs tokens, passwords and the `.env` file.
- **Privacy:** friends' data appears in the snapshots for backup only; it is never shown to other friends unless they opted in.

### 5.7 Friends' access via Tailscale

The app is **not reachable from the public internet**. Only devices on my Tailscale network can open it.

- **How friends join:** each friend installs the Tailscale app on their Android phone (and laptop if they want), signs in with their own free Tailscale account, and accepts my invitation.
- **Recommended: share only the server.** Use Tailscale's *machine sharing* to share just the Windows server with each friend. They can reach 33Vinyls, but not my other devices, and they keep their own Tailscale account. Shared machines don't count as extra users on my plan.
- **Alternative: invite them as users** of my Tailscale network. Then restrict them with access rules (ACLs) so they can only reach the server on the app's port. The free plan caps the number of users, so check Tailscale's current limits.
- **Address:** everyone opens the same HTTPS address, e.g. `https://vinyl-server.<tailnet>.ts.net`, served by `tailscale serve` from the Windows host to the app container. Then "Add to Home screen" in Chrome on Android.
- **Two locks:** being on the Tailscale network only lets a device *reach* the app; each friend still needs their 33Vinyls invite and login.
- **Removing someone:** stop sharing the server with them in Tailscale and disable their 33Vinyls account.
- **Note:** Tailscale must be switched on on the phone when using the app. Offline mode still works without it; changes sync once Tailscale is connected again.

## 6. MVP scope (≈ 6–8 weeks, part-time)

**In:**
- Installable PWA on Android + desktop, invite-only accounts
- Barcode, cover-photo (OCR + re-rank), label and text search identification
- Pressing picker with runout entry
- Discogs price card with condition and deal verdict
- Collection with value total (EUR), duplicate warning, per-friend Discogs link + import, CSV export
- Wantlist with in-shop highlight
- Offline mode + sync
- Windows + Docker Compose deployment, sync-folder exports and restore
- Opt-in sharing settings (sharing view itself can follow shortly after)

**Later:** price watch, shop list/map, push additions back to Discogs, eBay prices, optional AI identification, sideloaded APK wrapper.

**On hold:** audio recognition.

### Milestones

| Weeks | Deliverable |
|---|---|
| 1 | Docker Compose on the Windows server, Tailscale HTTPS, share the server with one friend and test the address from their phone, PWA shell installable on Android, Discogs app registration + OAuth sign-in test, data model |
| 2–3 | **Offline-first core:** local database on the phone, full first sync + change sync, offline search/browse, airplane-mode test; then barcode + text search → release page → add to collection; accounts and invites |
| 4–5 | Cover-photo and label OCR identification, pressing picker, runout entry, price card |
| 6 | Wantlist (offline too), Discogs collection/wantlist import, sync-folder exports + restore, sharing settings |
| 7–8 | Run the §3.6 acceptance tests on my phone and friends' Android phones, fixes, backups, short how-to-install guide |

## 7. What "good" looks like

- With the phone in **airplane mode**, I can open the app, search and browse my whole collection (§3.6 tests pass).
- I can get from opening the app to a price in about **10 seconds** for a record with a barcode, and **under 30 seconds** with a runout check.
- Correct album identified from the cover photo most of the time; exact pressing when the runout is entered.
- My full collection is in the app, backed up, and exportable.
- Running cost: **€0/month** (apart from the electricity for the home server).
- A copy of my collection (database, photos, CSV) is always in OneDrive, at most a day old.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Discogs rate limits or terms change | Backend cache; personal non-commercial use; CSV export so nothing is lost |
| Browser OCR struggles with covers/runouts | Quick manual correction; optional AI plug-in for hard cases |
| Camera blocked without HTTPS | HTTPS via Tailscale from day one |
| Friend forgets to switch Tailscale on | App works offline and shows "Can't reach server — is Tailscale on?"; syncs when reconnected |
| Android clears the app's data when storage is low | Persistent storage requested and shown in Settings; full re-download from the server if it happens anyway |
| Offline data lost if the app's address changes | Tailscale address fixed once and never changed |
| Home server offline (sleep, Windows updates, reboots) | Sleep disabled, containers auto-restart, Docker Desktop starts at login; phones keep working offline and sync later |
| OneDrive uploads a half-written file | Live DB stays in the Docker volume; snapshots are written under a temporary name and renamed when complete |
| Docker volume lost (`docker compose down -v`, Docker Desktop reset, WSL disk failure) | Nightly automatic export to OneDrive, so at most one day is lost (less after bulk scans) |
| A friend's Discogs link expires or is revoked | App shows "Reconnect Discogs"; cached data keeps working meanwhile |
| Pressing detection is hard | Combine signals, ask guided questions, let users correct |

## 9. On hold

- **Audio recognition ("Listen" mode):** paused. Free options (Chromaprint/AcoustID) are unreliable with a phone microphone in a noisy shop, and good options are paid or native-only. Revisit after the MVP.
- **Play Store release, public sign-up, monetisation, shop features:** out of scope for a private app.

## 10. Decisions

| Topic | Decision |
|---|---|
| Platform | Installable web app (PWA) for Android + desktop browsers; no Play Store |
| Offline | Offline-first: full collection + wantlist + thumbnails on the phone; search and browse with no connection |
| Hosting | Windows home server, Docker Desktop, Docker Compose |
| Remote access | Tailscale (HTTPS); friends join my Tailscale network, ideally via machine sharing of the server only; no public link |
| Data outside the container | Same approach as Syndic (named volume, SQLite backup API, one-way per run, back up before replace), plus nightly automatic export and photos, into the OneDrive folder |
| Port | 7510 (Syndic uses 7500) |
| Code location | `D:\OneDrive\Python\33Vinyls`, a git clone of `PythDom/33Vinyls`; `Sync\` inside it, ignored by git |
| Sharing | Opt-in per person (collection, wantlist, values separately), off by default |
| Currency | EUR |
| Discogs | Each friend links their own account (OAuth) |
| Paid services | Optional, off by default |
| Audio recognition | On hold |

## 11. Open questions

None blocking. Retention numbers (14 daily / 8 weekly / 12 monthly) and the 03:00 nightly export time can be adjusted in settings.

---

*Next step: link `D:\OneDrive\Python\33Vinyls` to GitHub (see README), set `Sync` to *Always keep on this device*, install Tailscale on the Windows server (Docker Desktop is already running Syndic), register a Discogs developer app (for the OAuth sign-in), and build the week-1 PWA shell.*
