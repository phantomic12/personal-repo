#!/usr/bin/env python3
"""Poll AUR RPC and return the set of tracked packages whose upstream version
has changed since the last successful build (recorded in state.json)."""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state.json")
MANIFEST = os.path.join(ROOT, "packages.json")

def aur_info(names):
    url = "https://aur.archlinux.org/rpc/v5/info?" + "&".join(f"arg[]={n}" for n in names)
    req = urllib.request.Request(url, headers={"User-Agent": "personal-repo-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["results"]

def main():
    tracked = json.load(open(MANIFEST))
    try:
        state = json.load(open(STATE))
    except FileNotFoundError:
        state = {}
    names = sorted(tracked.keys())
    now = {}
    try:
        for res in aur_info(names):
            now[res["Name"]] = res["Version"]
    except Exception as e:
        # On transient AUR failure, be conservative: report nothing changed so
        # we don't burn a build cycle, but surface the error as a marker.
        print(json.dumps({"error": str(e), "changed": []}))
        return 1

    changed = [n for n in names if now.get(n) != state.get(n)]
    # Also detect packages being tracked that have vanished from AUR entirely
    # (obsolete) and packages we no longer track (removed from manifest).
    obsolete = [n for n in names if n not in now]
    untracked_now = [n for n in now if n not in tracked]

    out = {
        "tracked": names,
        "changed": changed,
        "obsolete": obsolete,
        "untracked_now": untracked_now,
        "versions": now,
        "last_built": state,
    }
    print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
