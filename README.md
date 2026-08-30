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

Add a package: clone its AUR snapshot into `packages/<name>/`, add the key to
`packages.json`, and delete its `state.json` entry (or leave it — an empty/missing
state entry means it builds on the next poll). Then push.

Remove a package: delete the entry from `packages.json` and remove `packages/<name>/`.
The next build prunes it from the repo and the Pages site.

## Builds are fully automated

Push to `main` (or run the `Build personal pacman repo` workflow manually) to
force a build. Otherwise the scheduler does it every 15 minutes.

---

License: MIT
