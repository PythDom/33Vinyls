# 33Vinyls — guide for friends

33Vinyls is a private app to identify records, check what they're worth (in EUR) and keep your collection on your phone, even without a connection. It runs on a private home server; only invited friends can use it.

## 1. Get access (once)

1. Install **Tailscale** from the Play Store and sign in (a free account is fine).
2. Accept the Tailscale invitation you were sent. The server then appears in your Tailscale app.
3. Keep Tailscale switched on when you want to sync or look up records.

## 2. Install the app (once)

1. Open the invite link you were sent, in **Chrome** (or Brave, see the tip below).
2. Choose a username and a password (at least 8 characters).
3. Chrome menu **⋮ → Install app** (or *Add to Home screen*).
4. In the app: **Settings → Protect storage**, so Android keeps your offline copy.

**Brave users:** if the page says *Site can't be reached*, open `brave://net-internals/#dns`, tap **Clear host cache**, and try again.

## 3. Link your Discogs account (optional, recommended)

Needed to look up records and prices.

1. On discogs.com: **Settings → Developers → Generate new token**, and copy it.
2. In 33Vinyls: **Settings → Discogs account**, paste the token, **Link with token**.
3. Already on Discogs? **Settings → Import collection & wantlist** copies everything over, grades and notes included.
4. For prices per condition: on discogs.com, fill in your **seller settings** with currency **EUR** (you don't have to sell anything).

## 4. Everyday use

- **Records**: your collection and wantlist. Search works offline: artist, title, label, catalogue number, barcode, runout, notes, storage location. Filters for decade, country, format, grade, location.
- **Scan**: scan a barcode, or photograph the cover or centre label. Tap the words it read if the first matches aren't right.
- **Which pressing?**: type the runout (the text scratched near the label), the catalogue number or barcode, or answer the quick questions.
- **Price**: pick the condition, type the shop's price → *Is it a deal?*
- **Add** to your collection or wantlist: saved on your phone at once, synced when you're connected.

## 5. Sharing (off unless you turn it on)

**Settings → Sharing with friends**: share your collection and/or wantlist. You see friends' records only if you share something too. Estimated values are a separate choice; purchase prices, notes and locations are never shared. When it's on, you'll see "Alex has this" or "Sam wants this" on records, and **Friends' records** in Settings.

## 6. Good to know

- The status chip at the top shows *Synced*, *Offline*, or how many changes are waiting.
- Your records stay on your phone if you sign out or the server is off; unsynced changes are the only thing at risk, and the app warns you.
- **Settings → Download my records** gives you CSV files for Excel.
