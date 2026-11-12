# 33Vinyls

A private music record **identifier, pressing detector & finder** for price checks and album collection, for me and a few friends.

**Platform:** installable web app (PWA): runs on Android (Chrome, home-screen install) and any desktop browser. Not released on Google Play. Self-hosted on a Windows home server with Docker; free by default, paid services optional. Prices in EUR.

- Scan a barcode, cover, label or runout → identify the exact pressing
- Condition-aware price check with a quick "is it a deal?" verdict
- Collection searchable and browsable fully offline on the phone, with total value and duplicate warnings
- Wantlist highlighted while digging in shops
- Each friend links their own Discogs account; sharing with friends is opt-in
- Private: friends reach the app through the owner's Tailscale network only
- Data backed up automatically to OneDrive (same approach as the Syndic app, plus nightly exports and photos)

Audio recognition is on hold.

See the full app proposal: [docs/PROPOSAL.md](docs/PROPOSAL.md)

## Local setup (Windows home server)

Code lives in `D:\OneDrive\Python\33Vinyls` and syncs with GitHub. The `Sync` folder inside it holds data copies and is ignored by git.

The folder already exists (it contains `Sync`), so link it to GitHub instead of cloning. In PowerShell:

```powershell
cd D:\OneDrive\Python\33Vinyls
git init
git remote add origin https://github.com/PythDom/33Vinyls.git
git fetch origin
git checkout -t origin/main
```

Afterwards: `git pull` to get updates, `git status` should never list anything under `Sync\`.
