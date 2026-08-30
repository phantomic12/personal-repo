#!/usr/bin/env python3
"""Merge freshly-built package versions into state.json (last-published record).

state.json maps pkgname -> "pkgver-pkgrel" for every package currently served
by the repo. On each assemble:
  * update entries for packages that were just built (from the .pkg.tar.zst)
  * keep entries for packages we already published but did not rebuild this cycle
  * drop obsolete packages (present in manifest but vanished from AUR)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.join(ROOT, "repo")

def load(path, default):
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def main():
    tracked = load(os.path.join(ROOT, "packages.json"), {})
    prev = load(os.path.join(ROOT, "state.json"), {})
    obsolete = set(sys.argv[1:]) if len(sys.argv) > 1 else set()

    built = {}
    for f in glob.glob(os.path.join(REPO_DIR, "*.pkg.tar.zst")):
        base = os.path.basename(f)[: -len(".pkg.tar.zst")]
        if "-debug" in base:
            continue  # skip debug variants, they are not separate tracked packages
        # Longest name match first so devin-desktop-next wins over devin-desktop.
        for n in sorted(tracked, key=len, reverse=True):
            if base.startswith(n + "-"):
                rest = base[len(n) + 1:]
                rest = rest.rsplit("-", 1)[0]   # drop arch -> "pkgver-pkgrel"
                built[n] = rest
                break

    # Merge: newly-built wins, previously-published kept, obsolete dropped.
    merged = dict(prev)
    merged.update(built)
    for o in obsolete:
        merged.pop(o, None)

    # Only retain keys we actually track.
    merged = {k: v for k, v in merged.items() if k in tracked}

    json.dump(merged, open(os.path.join(ROOT, "state.json"), "w"), indent=2)
    print(json.dumps(merged, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
