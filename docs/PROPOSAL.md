# 33Vinyls — App Proposal

**A private web app, installable on Android, that identifies a vinyl record, tells you which pressing it is and what it is worth, and keeps your collection and wantlist in one place.**

Status: Draft proposal · v0.4 · 2026-11-11

> **Project constraints**
> - **Web app required**, and it **must run on Android** → built as an installable web app (PWA) that runs in Chrome on Android and in any desktop browser.
> - **Private use:** for me and a few interested friends. **No Google Play release.**
> - **Free by default:** everything works on free APIs and self-hosting. Paid services are optional plug-ins.
> - **Hosted on my Windows home server** in Docker containers (Docker Desktop).
> - **Data syncable outside the container:** a plain Windows folder holds backups and exports, so a file-sync app can copy it elsewhere (see §5.6).
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
- **Offline:** collection, wantlist and cached prices are stored on the device and sync when back online.

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
                                  │ D:\33Vinyls\sync     │  │                        │
                                  │ → file-sync app      │  │ eBay API (optional)    │
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
| Offline storage | IndexedDB via Dexie | Collection usable with no signal |
| Barcode | Browser BarcodeDetector API, ZXing-js fallback | Fast on Android Chrome |
| OCR | Tesseract.js (in browser) | Free, offline; runout text needs manual correction anyway |
| Cover re-ranking | Small image-embedding model (e.g. CLIP via ONNX Runtime) on the backend | Compares the photo with a handful of candidate covers only |
| Backend | Python + FastAPI | Simple; good image/ML libraries |
| Database | SQLite inside a Docker volume | Plenty for a few users; snapshots exported to a Windows folder (§5.6) |
| Hosting | Docker Desktop (WSL 2) on my Windows home server, one `docker compose` file | Uses hardware I already have; €0/month |
| Remote access + HTTPS | Tailscale on the Windows host (`tailscale serve`, or Funnel for friends without Tailscale) | Free; no router port-forwarding; HTTPS is **required** for camera access in the browser |
| Auth | Invite codes + passkeys or email/password; Discogs linked per user via OAuth | Keeps it private; each friend uses their own Discogs account |

### 5.3 Free vs. optional paid services

| Service | Free baseline | Optional paid upgrade |
|---|---|---|
| Release data & prices | Discogs API, each friend's own linked account (rate limit ~60 requests/min per account) | — |
| Metadata & cover art | MusicBrainz, Cover Art Archive | — |
| eBay listings | eBay developer account (free) | — |
| Photo identification | OCR + Discogs search + cover re-ranking | AI vision API with the user's own key (pay per use) |
| Hosting | Windows home server + Docker Desktop + Tailscale | — |
| Backups / sync | Sync folder + free file-sync app (e.g. Syncthing) to another PC or drive | Cloud storage, if the sync app supports it |

Each paid service is behind a setting and only turns on when an API key is entered. The app works fully without any of them.

### 5.4 Data source notes

- Discogs: each friend links their own account through Discogs' sign-in (OAuth). The app never sees their Discogs password; their access tokens are stored encrypted on the server and can be revoked from either the app or Discogs.
- Each friend's requests use their own token, so they each get their own rate limit. Public release data is still cached on the backend and shared, so the same record isn't fetched twice.
- Discogs price suggestions require the user to have filled in their Discogs seller settings; friends should set EUR there. If they haven't, the app falls back to marketplace stats requested in EUR.
- Attribution to Discogs is shown on release and price pages; personal, non-commercial use.
- Discogs marketplace **sold history** is not available through the API; prices are based on current listings and Discogs price suggestions.
- API tokens live on the backend, not in the browser, and are excluded from the sync-folder exports.

### 5.5 Home server setup (Windows + Docker)

```
Windows home server
├─ Docker Desktop (WSL 2 backend, starts with Windows)
│   └─ docker compose
│       ├─ web      – serves the PWA + API (FastAPI)
│       └─ worker   – price cache refresh, scheduled exports, price watch
│       volumes:
│       ├─ 33vinyls-data  → live SQLite DB + photos (Docker volume, fast and safe)
│       └─ D:\33Vinyls\sync → /sync (Windows folder, bind mount)
├─ Tailscale (Windows app) → https://<server>.<tailnet>.ts.net
└─ File-sync app watching D:\33Vinyls\sync
```

- Containers use `restart: unless-stopped`, so they come back after reboots and Windows updates.
- Docker Desktop set to start at login; the PC's sleep setting turned off (or "wake on LAN").
- Secrets (encryption key, Discogs app key/secret, optional eBay/AI keys) live in a `.env` file next to `docker-compose.yml`, never in the sync folder.
- Updating: `docker compose pull && docker compose up -d`.
- Any folder/drive letter works; `D:\33Vinyls` is just an example.

### 5.6 Syncing data outside the container

The **live database stays inside a Docker volume**. Putting a live SQLite file directly in a Windows folder that a sync app is copying risks corruption (the file can be copied halfway through a write, and file locking across the Windows ↔ Docker boundary is unreliable). Instead, the app **writes consistent copies** to a normal Windows folder, and any sync app can take it from there:

```
D:\33Vinyls\sync\
├─ db\        33vinyls-2026-11-11.sqlite   – consistent snapshot (last N kept)
├─ export\    <user>\collection.csv, wantlist.csv, collection.json
├─ photos\    <user>\…                    – your record photos
└─ import\    drop a CSV or snapshot here to import / restore
```

- **When:** nightly, plus after bulk-scan sessions, plus an "Export now" button.
- **Readable without the app:** CSV/JSON per user, so the collection can be opened in Excel even if the app is gone.
- **Restore / move:** drop a snapshot into `import\` (or point a fresh install at the folder) to restore everything on another machine.
- **Sync app:** works with any folder-sync tool, e.g. Syncthing (free, peer-to-peer) to another PC or NAS, or a cloud-drive client (OneDrive, Google Drive) if preferred.
- **Direction:** export is one-way by default (container → folder) to keep it safe. Changes made outside, such as an edited CSV, are brought back in deliberately through the `import\` folder, with a preview before anything is overwritten.
- **Privacy:** exports never include Discogs tokens or passwords. Friends' data is exported only for the server owner's backup; it is never shared with other friends unless they opted in.

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
| 1 | Docker Compose on the Windows server, Tailscale HTTPS, PWA shell installable on Android, Discogs app registration + OAuth sign-in test, data model |
| 2–3 | Barcode + text search → release page → add to collection; accounts and invites |
| 4–5 | Cover-photo and label OCR identification, pressing picker, runout entry, price card |
| 6 | Wantlist, offline store + sync, Discogs collection/wantlist import, sync-folder exports + restore, sharing settings |
| 7–8 | Testing on my phone and friends' Android phones, fixes, backups, short how-to-install guide |

## 7. What "good" looks like

- I can get from opening the app to a price in about **10 seconds** for a record with a barcode, and **under 30 seconds** with a runout check.
- Correct album identified from the cover photo most of the time; exact pressing when the runout is entered.
- My full collection is in the app, backed up, and exportable.
- Running cost: **€0/month** (apart from the electricity for the home server).
- A copy of my collection is always in the sync folder, readable without the app.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Discogs rate limits or terms change | Backend cache; personal non-commercial use; CSV export so nothing is lost |
| Browser OCR struggles with covers/runouts | Quick manual correction; optional AI plug-in for hard cases |
| Camera blocked without HTTPS | HTTPS via Tailscale from day one |
| Home server offline (sleep, Windows updates, reboots) | Sleep disabled, containers auto-restart, Docker Desktop starts at login; phones keep working offline and sync later |
| Sync app copies a half-written database | Live DB stays in a Docker volume; only finished snapshots are written to the sync folder |
| A friend's Discogs link expires or is revoked | App shows "Reconnect Discogs"; cached data keeps working meanwhile |
| Pressing detection is hard | Combine signals, ask guided questions, let users correct |

## 9. On hold

- **Audio recognition ("Listen" mode):** paused. Free options (Chromaprint/AcoustID) are unreliable with a phone microphone in a noisy shop, and good options are paid or native-only. Revisit after the MVP.
- **Play Store release, public sign-up, monetisation, shop features:** out of scope for a private app.

## 10. Decisions

| Topic | Decision |
|---|---|
| Platform | Installable web app (PWA) for Android + desktop browsers; no Play Store |
| Hosting | Windows home server, Docker Desktop, Docker Compose |
| Remote access | Tailscale (HTTPS) |
| Data outside the container | Scheduled snapshots + CSV/JSON + photos in a Windows sync folder, picked up by a file-sync app |
| Sharing | Opt-in per person (collection, wantlist, values separately), off by default |
| Currency | EUR |
| Discogs | Each friend links their own account (OAuth) |
| Paid services | Optional, off by default |
| Audio recognition | On hold |

## 11. Open questions

1. Which sync app do you use ("syndic" — Syncthing, or another one)? The design works with any folder-sync tool, but this decides the folder layout details.
2. Should friends reach the app by joining your Tailscale network, or through a public Tailscale Funnel link (simpler for them, but reachable from the internet behind the app's login)?

---

*Next step: install Docker Desktop and Tailscale on the Windows server, register a Discogs developer app (for the OAuth sign-in), and build the week-1 PWA shell.*
