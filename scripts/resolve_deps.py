#!/usr/bin/env python3
"""Resolve the AUR-only dependency closure of an AUR package.

Given an AUR package name, walk its Depends/MakeDepends/CheckDepends (and,
recursively, the deps of every AUR-only dep we find) and return the set of
packages that must be built from AUR because no binary repo carries them.

Repos checked, in order (a dep satisfied by ANY of these is NOT vendored):
  - Arch core + extra (x86_64)
  - CachyOS x86_64:    cachyos
  - CachyOS x86_64_v3: cachyos-v3, cachyos-core-v3, cachyos-extra-v3,
                       cachyos-community-v3
  - Chaotic-AUR (x86_64)

Repo package sets are parsed from the live pacman .db files (tar.gz archives
of per-package `desc` entries). %NAME% and %PROVIDES% both count as satisfying
names, so e.g. a dep on `node` is satisfied by `nodejs` providing it.

Usage:  python3 scripts/resolve-deps.py <aur-package-name> [--json]
Prints the AUR-only closure (including the target itself), one per line,
in dependency order (deps before dependents).
"""
import io
import json
import os
import re
import sys
import tarfile
import urllib.parse
import urllib.request

UA = {"User-Agent": "personal-repo-builder/1.0"}

# (repo-name, db-url) pairs. Order only matters for logging which repo
# satisfied a dep.
REPO_DBS = [
    ("core",                  "https://mirror.rackspace.com/archlinux/core/os/x86_64/core.db"),
    ("extra",                 "https://mirror.rackspace.com/archlinux/extra/os/x86_64/extra.db"),
    ("cachyos",               "https://mirror.cachyos.org/repo/x86_64/cachyos/cachyos.db"),
    ("cachyos-v3",            "https://mirror.cachyos.org/repo/x86_64_v3/cachyos-v3/cachyos-v3.db"),
    ("cachyos-core-v3",       "https://mirror.cachyos.org/repo/x86_64_v3/cachyos-core-v3/cachyos-core-v3.db"),
    ("cachyos-extra-v3",      "https://mirror.cachyos.org/repo/x86_64_v3/cachyos-extra-v3/cachyos-extra-v3.db"),
    ("cachyos-community-v3",  "https://mirror.cachyos.org/repo/x86_64_v3/cachyos-community-v3/cachyos-community-v3.db"),
    ("chaotic-aur",           "https://cdn-mirror.chaotic.cx/chaotic-aur/x86_64/chaotic-aur.db"),
]

# dep strings look like: 'foo', 'foo>=1.2', 'foo=1.2-3', 'foo<2:1.0'
DEP_RE = re.compile(r"^\s*([A-Za-z0-9@._+\-]+?)\s*(?:[<>=].*)?$")


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def dep_name(dep):
    """Strip version constraint / trailing whitespace from a dep string."""
    m = DEP_RE.match(dep)
    return m.group(1) if m else dep.strip()


def load_repo_set():
    """Return (available:set[str], where:dict[name->repo]) from all REPO_DBS."""
    available = set()
    where = {}
    for repo, url in REPO_DBS:
        try:
            blob = fetch(url, binary=True)
        except Exception as e:
            print(f"warn: could not fetch {repo} db ({e}); skipping", file=sys.stderr)
            continue
        count = 0
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
            for member in tf:
                if not member.name.endswith("/desc"):
                    continue
                f = tf.extractfile(member)
                if f is None:
                    continue
                text = f.read().decode("utf-8", "replace")
                name = None
                provides = []
                lines = text.splitlines()
                i = 0
                while i < len(lines):
                    if lines[i] == "%NAME%" and i + 1 < len(lines):
                        name = lines[i + 1].strip()
                        i += 2
                        continue
                    if lines[i] == "%PROVIDES%":
                        j = i + 1
                        while j < len(lines) and lines[j] and not lines[j].startswith("%"):
                            provides.append(dep_name(lines[j]))
                            j += 1
                        i = j
                        continue
                    i += 1
                if name:
                    if name not in available:
                        where[name] = repo
                    available.add(name)
                    count += 1
                    for p in provides:
                        if p not in available:
                            where[p] = f"{repo} (provides of {name})"
                        available.add(p)
        print(f"repo {repo}: {count} packages", file=sys.stderr)
    return available, where


def aur_info(names):
    """Batch AUR RPC info query. Returns {Name: result-dict}."""
    if not names:
        return {}
    qs = "&".join("arg[]=" + urllib.parse.quote(n) for n in names)
    url = "https://aur.archlinux.org/rpc/v5/info?" + qs
    results = json.loads(fetch(url))["results"]
    return {r["Name"]: r for r in results}


def resolve(target):
    """BFS the AUR-only dep closure of target. Returns ordered list (deps first)."""
    available, where = load_repo_set()

    info = aur_info([target])
    if target not in info:
        raise SystemExit(f"error: '{target}' not found on AUR")
    if target in available:
        print(f"note: '{target}' itself is already in {where[target]} — "
              f"adding anyway per request", file=sys.stderr)

    closure = {}          # name -> aur info dict
    order = []            # topo order (deps before dependents)
    visiting = set()
    visited = set()

    def visit(name, stack, is_target=False):
        if name in visited:
            return
        if name in visiting:
            raise SystemExit(f"error: dependency cycle: {' -> '.join(stack + [name])}")
        if name in available and not is_target:
            print(f"  dep {name}: satisfied by {where[name]}", file=sys.stderr)
            return
        visiting.add(name)
        meta = closure.get(name)
        if meta is None:
            meta = aur_info([name]).get(name)
            if meta is None:
                print(f"  dep {name}: NOT in any repo and NOT on AUR — "
                      f"unresolvable, skipping", file=sys.stderr)
                visiting.discard(name)
                visited.add(name)
                return
            closure[name] = meta
        deps = []
        for key in ("Depends", "MakeDepends", "CheckDepends"):
            for d in (meta.get(key) or []):
                deps.append(dep_name(d))
        for d in deps:
            visit(d, stack + [name])
        visiting.discard(name)
        visited.add(name)
        if name not in order:
            order.append(name)

    visit(target, [], is_target=True)
    return order, closure, available, where


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: resolve-deps.py <aur-package> [--json]", file=sys.stderr)
        return 1
    target = args[0]
    order, closure, available, where = resolve(target)
    if "--json" in sys.argv:
        print(json.dumps({
            "target": target,
            "aur_packages": order,
            "versions": {n: closure[n]["Version"] for n in order},
        }, indent=2))
    else:
        for n in order:
            print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
