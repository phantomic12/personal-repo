#!/usr/bin/env python3
"""Validate an AUR package name, resolve its AUR-only dependency closure
(deps not satisfied by Arch core/extra, CachyOS, or Chaotic-AUR repos),
vendor each one's current snapshot into packages/<name>/, and register all
of them in packages.json so the poll workflow detects and builds them.

Usage:  python3 scripts/add-package.py <aur-package-name>

Does NOT touch state.json. Leaving the packages absent from state.json is
what makes poll.py report them as "changed" (never built), so the existing
poll -> build -> assemble pipeline picks them up and builds + deploys them
automatically after this script commits packages.json.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_deps

# AUR package names: lowercase start, then [a-z0-9@._+-]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9@._+-]*$")


def aur_info(name):
    url = "https://aur.archlinux.org/rpc/v5/info?" + urllib.parse.urlencode({"arg[]": name})
    req = urllib.request.Request(url, headers={"User-Agent": "personal-repo-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["results"]


def vendor(name):
    """Clone the AUR repo for `name` into packages/<name>/, replacing any
    existing vendored files. Returns the sorted list of vendored filenames."""
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
    return files


def main():
    if len(sys.argv) < 2:
        print("usage: add-package.py <aur-package-name>", file=sys.stderr)
        return 1
    name = sys.argv[1].strip()
    if not NAME_RE.match(name):
        print(f"error: '{name}' is not a valid AUR package name", file=sys.stderr)
        return 1

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
    print(f"OK: {name} found on AUR at version {results[0]['Version']}")

    # Resolve the AUR-only dep closure: target plus every dep that Arch /
    # CachyOS / Chaotic repos don't already carry. Order is deps-first.
    print("resolving AUR-only dependency closure against Arch/CachyOS/Chaotic repos...")
    order, closure, _available, _where = resolve_deps.resolve(name)
    new_pkgs = [p for p in order if p not in manifest]
    already = [p for p in order if p in manifest]
    if already:
        print(f"already tracked, skipping: {', '.join(already)}")
    print(f"to vendor ({len(new_pkgs)}): {', '.join(new_pkgs)}")

    for pkg in new_pkgs:
        version = closure[pkg]["Version"]
        files = vendor(pkg)
        manifest[pkg] = {"pkgver": version, "files": files}
        print(f"vendored {pkg} {version} ({len(files)} files)")

    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print(f"registered {len(new_pkgs)} package(s) in packages.json")
    print("state.json intentionally left unchanged: poll will see these as new builds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
