#!/usr/bin/env python3
"""Validate an AUR package name, vendor its current snapshot into packages/<name>/,
and register it in packages.json so the poll workflow detects it and builds it.

Usage:  python3 scripts/add-package.py <aur-package-name>

Does NOT touch state.json. Leaving the package absent from state.json is what
makes poll.py report it as "changed" (never built), so the existing poll -> build
-> assemble pipeline picks it up and builds + deploys it automatically after this
script commits packages.json.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "packages.json")
PKGS_DIR = os.path.join(ROOT, "packages")
AUR_GIT = "https://aur.archlinux.org"

# AUR package names: lowercase start, then [a-z0-9@._+-]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9@._+-]*$")


def aur_info(name):
    url = "https://aur.archlinux.org/rpc/v5/info?" + urllib.parse.urlencode({"arg[]": name})
    req = urllib.request.Request(url, headers={"User-Agent": "personal-repo-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["results"]


def main():
    if len(sys.argv) < 2:
        print("usage: add-package.py <aur-package-name>", file=sys.stderr)
        return 1
    name = sys.argv[1].strip()
    if not NAME_RE.match(name):
        print(f"error: '{name}' is not a valid AUR package name", file=sys.stderr)
        return 1

    # Refuse to re-add an already-tracked package.
    manifest = json.load(open(MANIFEST))
    if name in manifest:
        print(f"error: '{name}' is already tracked in packages.json", file=sys.stderr)
        return 1

    # Confirm it exists on AUR.
    results = aur_info(name)
    if not results:
        print(f"error: '{name}' not found on AUR (https://aur.archlinux.org/packages/{name})",
              file=sys.stderr)
        return 1
    version = results[0]["Version"]
    print(f"OK: {name} found on AUR at version {version}")

    # Vendor a snapshot, mirroring scripts/sync-aur.py's clone-then-copy.
    dest = os.path.join(PKGS_DIR, name)
    if os.path.isdir(dest):
        for f in os.listdir(dest):
            p = os.path.join(dest, f)
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
    else:
        os.makedirs(dest, exist_ok=True)
    files = []
    with tempfile.TemporaryDirectory(prefix="aur-") as tmp:
        subprocess.run(["git", "clone", "--depth=1", f"{AUR_GIT}/{name}.git", tmp],
                       check=True)
        for f in sorted(os.listdir(tmp)):
            if f == ".git":
                continue
            src = os.path.join(tmp, f)
            dst = os.path.join(dest, f)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            files.append(f)

    # Register in the manifest (merge; keep existing entries).
    manifest[name] = {"pkgver": version, "files": files}
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print(f"registered {name} in packages.json with {len(files)} vendored files")
    print("state.json intentionally left unchanged: poll will see this as a new build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
