# 33Vinyls — App Proposal

**A private web app, installable on Android, that identifies a vinyl record, tells you which pressing it is and what it is worth, and keeps your collection and wantlist in one place.**

Status: Draft proposal · v0.3 · 2026-11-11

> **Project constraints**
> - **Web app required**, and it **must run on Android** → built as an installable web app (PWA) that runs in Chrome on Android and in any desktop browser.
> - **Private use:** for me and a few interested friends. **No Google Play release.**
> - **Free by default:** everything works on free APIs and self-hosting. Paid services are optional plug-ins.
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
| **Checking with friends** | (Optional) see whether a friend owns or wants a record |

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

- **Price card:** low / median / high, number for sale, source and date of each figure.
- **Condition-aware:** pick media and sleeve grade (Goldmine scale: M, NM, VG+, VG, G+, G, F, P).
- **Deal check:** type the shop's price → green / amber / red verdict.
- **Sources:** Discogs marketplace data (free with a personal token). eBay current listings optional (free developer account).
- Prices are cached so repeat lookups are instant and work offline.

### 3.4 Collection

- Add from any scan; **bulk mode** for scanning a shelf, then a review queue to confirm pressings and grades.
- Fields: grade, purchase price/date/place, notes, photos, storage location.
- **Value dashboard:** total value, most valuable items, gain vs. purchase price.
- **Duplicate warning** when scanning something already owned.
- **Discogs import** and CSV import/export, so the data is never locked in.
- **Offline:** collection, wantlist and cached prices are stored on the device and sync when back online.

### 3.5 Wantlist & finder

- Wantlist with target pressing (or "any") and max price.
- **In-shop match:** wanted records are highlighted while scanning.
- **Price watch** (later): a daily check that flags listings below your max price.
- **Shop list:** a simple shared list/map of record shops and fairs that friends add to.
- **Friends** (optional, opt-in): "Alex owns this" / "Sam wants this", which helps with swaps.

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
                                       ┌─────────▼──────┐  ┌───────▼────────────────┐
                                       │ SQLite + photo │  │ Discogs API (free)     │
                                       │ folder, nightly│  │ MusicBrainz / Cover Art│
                                       │ backup         │  │ Archive (free)         │
                                       └────────────────┘  │ eBay API (optional)    │
                                                           │ AI vision API (opt.)   │
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
| Database | SQLite (+ nightly backup) | Plenty for a few users; one file, easy to back up |
| Hosting | Docker Compose on a home server / Raspberry Pi / old PC, or a cheap VPS | No mandatory monthly cost |
| Remote access + HTTPS | Tailscale (private network) or Cloudflare Tunnel | Free tiers; HTTPS is **required** for camera access in the browser |
| Auth | Invite codes + passkeys or email/password | Keeps it private |

### 5.3 Free vs. optional paid services

| Service | Free baseline | Optional paid upgrade |
|---|---|---|
| Release data & prices | Discogs API with a personal token (rate-limited, ~60 requests/min) | — |
| Metadata & cover art | MusicBrainz, Cover Art Archive | — |
| eBay listings | eBay developer account (free) | — |
| Photo identification | OCR + Discogs search + cover re-ranking | AI vision API with the user's own key (pay per use) |
| Hosting | Home server + Tailscale / Cloudflare Tunnel | Small VPS (a few €/$ per month) |
| Backups | Local disk / USB | Cloud storage bucket |

Each paid service is behind a setting and only turns on when an API key is entered. The app works fully without any of them.

### 5.4 Data source notes

- Discogs: requires attribution, respects rate limits, personal non-commercial use. Responses are cached on the backend so friends share one cache and don't hit the limits.
- Discogs marketplace **sold history** is not available through the API; prices are based on current listings and Discogs price suggestions.
- API tokens live on the backend, not in the browser.

## 6. MVP scope (≈ 6–8 weeks, part-time)

**In:**
- Installable PWA on Android + desktop, invite-only accounts
- Barcode, cover-photo (OCR + re-rank), label and text search identification
- Pressing picker with runout entry
- Discogs price card with condition and deal verdict
- Collection with value total, duplicate warning, Discogs import, CSV export
- Wantlist with in-shop highlight
- Offline mode + sync
- Self-hosted deployment with backups

**Later:** price watch, shop list/map, friends' view, eBay prices, optional AI identification, sideloaded APK wrapper.

**On hold:** audio recognition.

### Milestones

| Weeks | Deliverable |
|---|---|
| 1 | Discogs token + API test, data model, PWA shell installable on Android, hosting with HTTPS (Tailscale/Cloudflare) |
| 2–3 | Barcode + text search → release page → add to collection; accounts and invites |
| 4–5 | Cover-photo and label OCR identification, pressing picker, runout entry, price card |
| 6 | Wantlist, offline store + sync, Discogs import / CSV export |
| 7–8 | Testing on my phone and friends' Android phones, fixes, backups, short how-to-install guide |

## 7. What "good" looks like

- I can get from opening the app to a price in about **10 seconds** for a record with a barcode, and **under 30 seconds** with a runout check.
- Correct album identified from the cover photo most of the time; exact pressing when the runout is entered.
- My full collection is in the app, backed up, and exportable.
- Running cost: **€0/month** in the default setup.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Discogs rate limits or terms change | Backend cache; personal non-commercial use; CSV export so nothing is lost |
| Browser OCR struggles with covers/runouts | Quick manual correction; optional AI plug-in for hard cases |
| Camera blocked without HTTPS | HTTPS via Tailscale or Cloudflare Tunnel from day one |
| Home server offline | Phones keep working offline and sync later; nightly backups |
| Pressing detection is hard | Combine signals, ask guided questions, let users correct |

## 9. On hold

- **Audio recognition ("Listen" mode):** paused. Free options (Chromaprint/AcoustID) are unreliable with a phone microphone in a noisy shop, and good options are paid or native-only. Revisit after the MVP.
- **Play Store release, public sign-up, monetisation, shop features:** out of scope for a private app.

## 10. Open questions

1. Hosting: home server/Raspberry Pi, or a small VPS?
2. Should friends see each other's collections/wantlists by default, or only when they opt in?
3. Which currency to show by default?
4. Is Discogs account linking required for each friend, or just one shared backend token for lookups?

---

*Next step: decide hosting, create a Discogs personal token, and build the week-1 PWA shell.*
