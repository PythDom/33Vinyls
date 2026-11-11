# 33Vinyls — App Proposal

**An Android app that identifies a vinyl record in seconds, tells you which pressing it is, what it is worth, and keeps your collection and wantlist in one place.**

Status: Draft proposal · v0.2 · 2026-11-11

> **Platform requirement:** 33Vinyls **must run on Android**. Android is the launch platform; iOS is optional and only considered after launch (see §5.1).

---

## 1. The problem

Record collectors and crate-diggers face the same three questions every time they pick up a record:

1. **What is this, exactly?** The same album can exist in hundreds of pressings (country, label, year, reissue, colour variant). The value difference between a first pressing and a later reissue can be 10x–100x.
2. **What is it worth?** Prices are scattered across Discogs, eBay, and shop price tags. Condition (media and sleeve grade) changes the value dramatically.
3. **Do I already own it / do I want it?** Collectors routinely buy duplicates or miss items on their wantlist because their collection lives in a spreadsheet or in their head.

Existing tools solve pieces of this (Discogs has a database and a barcode scanner; audio apps identify songs), but nobody combines **identification → pressing detection → price → collection → finding** in a single fast, in-store-friendly flow.

## 2. Target users

| Persona | Need | Key moment |
|---|---|---|
| **Crate digger** | Decide in seconds whether a $5 bin record is a gem | Standing in a shop or flea market, poor signal |
| **Collector** | Catalogue and value a growing collection; track wantlist | At home, scanning 200 records on a Sunday |
| **Casual inheritor** | "I got my parents' records — are any valuable?" | One-off bulk scan, wants a simple total |
| **Small seller / shop** | Price stock quickly and consistently | Pricing a just-bought box lot |

## 3. Core features

### 3.1 Identify — "What is this record?"

Multiple input modes, used together to raise confidence:

| Mode | How it works | Strength |
|---|---|---|
| **Cover photo** | On-device crop + image embedding, matched against a vector index of cover art | Fastest, works on most records |
| **Barcode scan** | UPC/EAN lookup | Exact for modern releases; most pre-~1980 records have no barcode |
| **Label photo** | OCR of label text (label name, catalogue number, side, rights society) | Distinguishes label variants |
| **Runout / matrix etching** | Guided macro photo + OCR of the dead-wax inscription; user can correct text | The definitive pressing identifier |
| **Listen** | Audio fingerprint of a track playing in the shop or on your turntable | Identifies unknown/blank-sleeve records |
| **Text search** | Artist / title / cat# manual search | Fallback |

### 3.2 Detect — "Which pressing is it?"

After the album (master release) is identified, the **Pressing Detector** narrows down to the exact release:

- Shows the candidate pressings as a short list ranked by evidence matched (barcode, cat#, label text, matrix).
- Asks **one question at a time** to disambiguate ("Does the runout say *A1* or *A2*?", "Is the label orange or black?") — a guided decision tree generated from the differences between candidate releases.
- Displays a confidence level and flags valuable variants ("First UK pressing — check for *Sold in UK* text on label").

### 3.3 Price check — "What is it worth?"

- **Price card** per release: low / median / high, number currently for sale, and recent trend.
- **Condition-aware:** user picks media and sleeve grade (Goldmine scale: M, NM, VG+, VG, G+, G, F, P); the estimate adjusts accordingly.
- **Sources:** Discogs marketplace data, eBay listings, and (later) opt-in anonymised sales reported by users/shops. Each price shows its source and date — no black-box numbers.
- **"Is it a deal?" mode:** enter the shop's price tag and get a green / amber / red verdict instantly.
- **Currency + fees:** shown in local currency, with an optional "net after selling fees and shipping" view for sellers.

### 3.4 Collection

- One-tap **Add to collection** from any scan; bulk-scan mode for cataloguing a shelf quickly.
- Per-item fields: grade, purchase price/date/place, notes, photos, storage location (shelf / box).
- **Collection value** dashboard: total value over time, most valuable items, gain vs. purchase price.
- **Duplicate warning:** scanning something you already own shows "In your collection (NM, 2nd pressing)" immediately.
- Import/export: Discogs collection sync, CSV import/export.
- Works **offline**; syncs when connectivity returns (record shops are often basements).

### 3.5 Wantlist & Finder

- **Wantlist** with target pressing (or "any pressing") and max price.
- **Price alerts** when a wanted item is listed below your target.
- **In-store match:** while scanning a bin, items on your wantlist light up.
- **Shop finder:** map of nearby record shops and record fairs (user-contributed listings + public data), with opening hours and genres.
- **Missing pieces:** "You own 7 of 9 studio albums by this artist" — suggests what to look for next.

### 3.6 Nice-to-have (later)

- Shared/family collections and insurance-ready PDF valuation report.
- Shop mode: batch pricing, printable price stickers, inventory export.
- Listening log: scrobble what you play from your own collection.
- Community corrections to improve matrix/label data.

## 4. Key user flows

**In the shop (target: < 5 seconds to a verdict)**
`Open app → camera already live → point at cover → match → (optional) "flip it & snap the runout" → price card with deal verdict → Add to collection / wantlist / skip`

**At home (bulk cataloguing)**
`Bulk mode → scan cover after cover → each auto-added to a review queue → confirm pressings & grades in one pass → collection value updated`

## 5. Proposed architecture

```
┌──────────────────────────┐        ┌──────────────────────────────────────┐
│  Android app (Kotlin)    │        │  Backend API                         │
│  - Camera + on-device    │  HTTPS │  - Auth, collection, wantlist        │
│    crop/OCR/embedding    ├───────►│  - Identification service            │
│  - Offline DB (Room)     │        │    (vector search over cover art)    │
│  - Sync queue            │        │  - Pressing detector (rules + data)  │
└──────────────────────────┘        │  - Pricing service (aggregation,     │
                                    │    caching, condition model)         │
                                    │  - Alerts/notifications worker       │
                                    └──────┬───────────────┬───────────────┘
                                           │               │
                           ┌───────────────▼───┐   ┌───────▼──────────────────┐
                           │ Postgres + pgvector│   │ External data sources    │
                           │ Redis (cache/queue)│   │ Discogs API, MusicBrainz,│
                           │ Object storage     │   │ Cover Art Archive, eBay  │
                           └────────────────────┘   │ Browse API, audio-ID SDK │
                                                    └──────────────────────────┘
```

**Suggested stack**

| Layer | Choice | Why |
|---|---|---|
| Android app | Kotlin + Jetpack Compose, CameraX | Native camera performance and the best support for Android's on-device ML tools |
| On-device ML | Google ML Kit (text recognition, barcode scanning) + small image-embedding model on LiteRT (TensorFlow Lite) | Fast, works offline, runs on mid-range phones |
| Local data | Room (SQLite) + WorkManager for background sync | Offline collection and queued lookups that survive app restarts |
| Backend | Python (FastAPI) | Strong ML/image ecosystem |
| Database | PostgreSQL + pgvector | Relational data + cover-art similarity search in one place |
| Cache / jobs | Redis + worker queue | Rate-limited API calls, price refresh, alerts |
| Storage | S3-compatible object storage | User photos, cover thumbnails |
| Audio ID | ShazamKit for Android or Chromaprint/AcoustID | Identify from sound |

### 5.1 Android requirements

| Item | Target |
|---|---|
| Minimum Android version | Android 8.0 (API 26), which covers the vast majority of active devices |
| Target SDK | Latest API level required by Google Play at release time |
| Devices | Phones first; tablet layout later. Must work well on mid-range phones (3–4 GB RAM), not just flagships |
| Permissions | Camera (scanning), microphone (Listen mode, only when used), location (shop finder, optional, "while in use" only), notifications (price alerts) |
| Distribution | Google Play (internal → closed testing → production); signed APK for sideloading during beta if needed |
| Offline | Full collection, wantlist and last-known prices usable with no connection |
| Performance budget | Camera ready < 1 s; on-device cover match < 1.5 s on a mid-range phone; APK/AAB < 40 MB (download the ML model on first launch if needed) |

**Why native Kotlin rather than cross-platform:** the app is camera- and ML-heavy, and CameraX + ML Kit give the fastest, most reliable scanning on Android. If iOS is wanted later, business logic (networking, pricing, sync, data models) can be shared via **Kotlin Multiplatform**, with only the UI and camera layer rewritten for iOS.

**Data sources (to validate during discovery)**

- **Discogs API** — release/master data, barcodes, matrix/runout identifiers, marketplace stats & price suggestions, collection/wantlist sync via OAuth. Rate-limited and governed by Discogs' API terms; caching and attribution rules must be respected.
- **MusicBrainz + Cover Art Archive** — open metadata and cover images for building the image index.
- **eBay Browse API** — current listings. (Historical sold-price data is restricted; needs partner access or alternative.)
- **User-contributed data** — opt-in purchase prices and corrections, which become a long-term moat.

## 6. MVP scope (≈ 10–12 weeks)

**In:**
- Cover-photo + barcode + text search identification
- Pressing picker with cat# / runout text matching
- Price card (Discogs-based) with condition selector and deal verdict
- Collection with value total, duplicates warning, CSV export, Discogs import
- Wantlist with in-store highlight
- Offline collection + cached prices

**Out (post-MVP):** iOS version, audio identification, price alerts, shop map, eBay pricing, shop mode, social features.

### Milestones

| Weeks | Deliverable |
|---|---|
| 1–2 | Data-source validation (API terms, rate limits), schema, cover-art index prototype |
| 3–5 | Scan → identify flow; collection CRUD; auth |
| 6–7 | Pressing detector + runout OCR; price service |
| 8–9 | Wantlist, offline sync, Discogs import |
| 10–12 | Closed beta on Google Play with ~50 collectors (testing track), accuracy tuning on a range of devices, Play Store release |

## 7. Success metrics

- **Identification accuracy:** ≥ 90% top-1 for album from cover photo; ≥ 70% exact pressing with runout.
- **Time to verdict:** median < 5 s from camera open to price card.
- **Retention:** % of users with ≥ 25 items in collection after 30 days.
- **Engagement:** scans per active user per week; wantlist matches found.

## 8. Business model

- **Free:** unlimited identification, collection up to ~500 items, basic price card.
- **Pro subscription:** unlimited collection, price history & alerts, bulk mode, valuation PDF, multi-device sync.
- **Shop tier:** batch pricing, sticker printing, inventory export.
- **Partnerships (optional):** affiliate links to marketplaces / shops — clearly labelled, never affecting the price verdict.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| API terms / rate limits restrict price data use | Validate terms in week 1; cache responsibly; attribute sources; build own opt-in price dataset |
| Pressing detection is hard (similar covers, worn labels) | Combine signals; guided questions; let users correct and feed fixes back |
| Prices are noisy / misleading | Show ranges, sample size and source date; never a single "true" value |
| Poor connectivity in shops | On-device first pass, offline cache, queued lookups |
| Copyright of cover images | Use licensed/open sources (Cover Art Archive), store embeddings + thumbnails per source terms |
| Competition from established databases | Differentiate on speed, pressing guidance, and in-store "deal" UX; integrate rather than compete (Discogs sync) |

## 10. Open questions

1. Is Discogs account linking required, or optional for users who don't use Discogs?
2. Which markets/currencies at launch?
3. Do we want a web companion for bulk collection editing in the MVP?
4. Budget for third-party audio-ID SDK vs. open-source fingerprinting?

---

*Next step: confirm MVP scope and the open questions above, then start week-1 data-source validation and UI wireframes.*
