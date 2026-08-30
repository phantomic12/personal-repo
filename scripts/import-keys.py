#!/usr/bin/env python3
"""Import PGP verification keys needed by the current PKGBUILD into the builder's
GPG keyring, so `makepkg` can validate upstream signatures (signed git tags and
.asc sources) without hitting an unreachable keyserver mid-build.

Strategy:
  1. Import any vendored key files (*.asc / *.gpg / *.pgp under keys/ and the
     package dir).
  2. Recursively read `validpgpkeys=(...)` from PKGBUILD and fetch any key not
     yet present from a public keyserver.
"""
import os
import re
import subprocess
import sys

BUILDER = "builder"
HOMEDIR = f"/home/{BUILDER}/.gnupg"
KEYSERVERS = ["hkps://keyserver.ubuntu.com", "hkp://pool.sks-keyservers.net"]


def gpg(*args):
    base = ["gpg", "--batch", "--homedir", HOMEDIR]
    return subprocess.run(base + list(args), capture_output=True, text=True)


def importer_run(prepend):
    return subprocess.run(prepend + ["gpg", "--batch", "--homedir", HOMEDIR, "--list-keys"],
                       capture_output=True, text=True)


def main():
    pkgdir = os.getcwd()  # workflow cds into packages/<name>
    os.makedirs("/home/%s/.gnupg" % BUILDER, exist_ok=True)
    os.chmod("/home/%s/.gnupg" % BUILDER, 0o700)

    # 1) Vendored key files
    keys = []
    for root, dirs, files in os.walk(pkgdir):
        dirs[:] = [d for d in dirs if d not in ("pkg", "src")]
        for f in files:
            if f.endswith((".asc", ".gpg", ".pgp", ".key")):
                keys.append(os.path.join(root, f))
    if keys:
        gpg("--import", *keys)

    # 2) validpgpkeys from the PKGBUILD
    m = re.search(r"validpgpkeys=\((.*?)\)", open("PKGBUILD").read(), re.S)
    if m:
        fps = [a or b for a, b in re.findall(r"'([0-9A-F]{16,})'|\"([0-9A-F]{16,})\"", m.group(1))]
        for fp in fps:
            listed = gpg("--list-keys", fp).returncode == 0
            if listed:
                continue
            for ks in KEYSERVERS:
                r = gpg("--keyserver", ks, "--recv-keys", fp)
                if r.returncode == 0:
                    print(f"imported key {fp} from {ks}")
                    break
            else:
                print(f"could not fetch key {fp} from any keyserver")

    print("key import done")


if __name__ == "__main__":
    main()
