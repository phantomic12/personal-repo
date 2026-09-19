# personal pacman repo

A personal Arch Linux binary repository, hosted on GitHub Pages and built
automatically by GitHub Actions.

- Polls the [AUR](https://aur.archlinux.org) every **15 minutes** for updates
  to the tracked packages.
- Rebuilds only the packages whose version changed, **in parallel** (up to 6 at
  a time) inside CachyOS build containers.
- Publishes the resulting packages + `personal.db.tar.gz` as a GitHub **Release**
  and serves the repository root at the GitHub **Pages** URL.
- **Prunes obsolete packages** when they disappear from the AUR or from the
  tracked manifest.

This is specifically a *binary* repo so you don't have to compile AUR packages
by hand. The vendored PKGBUILDs live in [`packages/`](packages/).

## Install (one-liner)

Runs the included `install-repo.sh`: adds the `[personal]` block to
`/etc/pacman.conf` and syncs the package database:

    curl -fsSL https://raw.githubusercontent.com/phantomic12/personal-repo/main/install-repo.sh | sudo bash -s -- --apply

Safe to re-run (idempotent). To preview first without touching anything, drop
the `--apply`:

    curl -fsSL https://raw.githubusercontent.com/phantomic12/personal-repo/main/install-repo.sh | bash

## The repo URL (direct link)

The Pages site root **is** the pacman repository root. Packages, the database and
`index.html` are all served from:

    https://phantomic12.github.io/personal-repo/

So the `Server` line points straight at it.

## Setup on a client

Add this block to `/etc/pacman.conf` (for example after the `[extra]` block):

    [personal]
    SigLevel = Optional TrustAll
    Server = https://phantomic12.github.io/personal-repo/

Then sync and install:

    sudo pacman -Sy
    sudo pacman -S --needed antigravity devin-desktop eddie-cli teamviewer tun2socks

## Tracked packages

| Package | Build notes |
|---|---|
| `antigravity` | Google Antigravity, repacked from upstream .deb |
| `devin-desktop` | Devin Desktop, repacked from .deb |
| `devin-desktop-next` | Devin Desktop next channel, repacked from .deb |
| `eddie-cli` | Eddie VPN CLI (dotnet) |
| `eddie-ui` | Eddie VPN GUI |
| `fastflowlm-git` | FastFlowLM for AMD Ryzen AI NPU (needs `xrt-plugin-amdxdna`) |
| `jack` | JACK1 low-latency audio server |
| `litehtml0.9` | LiteHTML rendering engine |
| `openssl-1.1` | OpenSSL 1.1 (legacy ABI) |
| `simplescreenrecorder` | Screen recorder (git build) |
| `teamviewer` | TeamViewer remote support |
| `tun2socks` | gVisor-based tun2socks |

## How it works

```
.-----------------.    poll AUR rpc/v5 every 15 min    .--------------------.
|  GH Action cron | -----------------------------------> | scripts/poll.py    |
'-----------------'                                     | diff vs state.json |
                                                        '--------------------'
                                                            | changed pkgs
                                                            v
                                          .------------------------------------.
                                          |  build job (matrix, parallel, CachyOS) |
                                          '------------------------------------'
                                                            | .pkg.tar.zst
                                                            v
                                          .-------------------------------------.
                                          | assemble: repo-add db, drop obsolete,|
                                          | gen index.html, deploy Pages, release|
                                          '-------------------------------------'
```

- `packages/<name>/` — vendored AUR PKGBUILDs (the build source of truth).
- `packages.json` — the manifest of tracked packages.
- `state.json` — last-published `pkgver-pkgrel` per package (drives the poll diff).
- `scripts/poll.py` — queries AUR, diffs against `state.json`, emits the matrix.
- `scripts/gen-state.py` — merges freshly built versions into `state.json`, drops obsolete.
- `repo/<...>.pkg.tar.zst` + `repo/personal.db.tar.gz` + `repo/index.html` — the served repository.

## Adding / removing a package

Add a package: run the `Add AUR package` workflow (or `scripts/add-package.py
<name>` locally). It resolves the package's AUR-only dependency closure —
deps that Arch core/extra, CachyOS (x86_64 + v3), and Chaotic-AUR do NOT
already carry — vendors each one into `packages/<name>/`, and registers all
of them in `packages.json`. Deps already in those repos are skipped, so the
repo only builds what binary repos can't provide. Missing `state.json`
entries mean everything new builds on the next poll.

Inside the build container, `scripts/build-aur-deps.sh` builds+installs any
vendored dep that isn't published yet (first-build race), and
`scripts/patches/<pkg>.sh` applies downstream-only PKGBUILD fixups after
each AUR re-sync.

Remove a package: delete the entry from `packages.json` and remove `packages/<name>/`.
The next build prunes it from the repo and the Pages site.

## Builds are fully automated

Push to `main` (or run the `Build personal pacman repo` workflow manually) to
force a build. Otherwise the scheduler does it every 15 minutes.

---

License: MIT
