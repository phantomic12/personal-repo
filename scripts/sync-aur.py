#!/usr/bin/env python3
"""Pull the latest PKGBUILD and associated files from AUR for packages whose
upstream version has changed, replacing the vendored copies in packages/<name>/.

Called in the build job BEFORE makepkg, so the build always uses the current
AUR source — not a stale snapshot committed to the repo.

Usage:  python3 scripts/sync-aur.py <pkg1> [pkg2 ...]
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKGS_DIR = os.path.join(ROOT, "packages")

AUR_GIT = "https://aur.archlinux.org"


def sync_one(name):
    dest = os.path.join(PKGS_DIR, name)
    if not os.path.isdir(dest):
        os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aur-") as tmp:
        subprocess.run(
            ["git", "clone", "--depth=1", f"{AUR_GIT}/{name}.git", tmp],
            check=True,
        )
        # Wipe old vendored files (they may reference old sources/patches)
        for f in os.listdir(dest):
            full = os.path.join(dest, f)
            if os.path.isfile(full):
                os.remove(full)
            elif os.path.isdir(full):
                shutil.rmtree(full)
        # Copy everything from the fresh AUR clone
        for f in os.listdir(tmp):
            if f == ".git":
                continue
            src = os.path.join(tmp, f)
            dst = os.path.join(dest, f)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    print(f"synced {name} from AUR")


def main():
    if len(sys.argv) < 2:
        print("usage: sync-aur.py <pkg> [pkg ...]", file=sys.stderr)
        return 1
    for name in sys.argv[1:]:
        sync_one(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
