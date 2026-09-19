#!/usr/bin/env bash
# Build + install any AUR-only deps of packages/$1 that aren't resolvable
# from the configured pacman repos (Arch + Chaotic + personal). Run INSIDE
# the build container, after sync-aur.py, before the real makepkg.
#
# Deps are discovered from the PKGBUILD's own .SRCINFO (depends/makedepends).
# A dep that pacman can't see but exists under packages/ is built with
# `makepkg -i` (which installs it), recursively resolving ITS deps first.
#
# Usage:  bash scripts/build-aur-deps.sh <pkg>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKGS_DIR="$ROOT/packages"
declare -A DONE=()

dep_names() {
  # Print depends+makedepends from a package dir's PKGBUILD/.SRCINFO.
  # Prefer .SRCINFO (pre-parsed); fall back to makepkg --printsrcinfo.
  local dir="$1"
  if [ -f "$dir/.SRCINFO" ]; then
    awk '/^\s*(make)?depends\s*=/ {print $3}' "$dir/.SRCINFO"
  else
    (cd "$dir" && makepkg --printsrcinfo 2>/dev/null) \
      | awk '/^\s*(make)?depends\s*=/ {print $3}'
  fi | sed -E 's/[<>=].*$//' | sort -u
}

build_one() {
  local name="$1"
  [ -n "${DONE[$name]:-}" ] && return 0
  DONE[$name]=1

  if pacman -Si "$name" >/dev/null 2>&1; then
    return 0  # resolvable from a configured repo — makepkg -s handles it
  fi
  if [ ! -d "$PKGS_DIR/$name" ]; then
    echo "!! dep $name not in any repo and not vendored under packages/ — skipping"
    return 0
  fi

  echo ">> AUR dep: $name (building from packages/$name)"
  # Recurse into this dep's own deps first.
  local sub
  while read -r sub; do
    [ -n "$sub" ] && build_one "$sub"
  done < <(dep_names "$PKGS_DIR/$name")

  (cd "$PKGS_DIR/$name" \
    && sudo -u builder env BUILDDIR=/tmp/makepkg PKGDEST=/tmp/makepkg \
         makepkg --noconfirm -sif --needed)
}

main() {
  local target="$1"
  local d
  while read -r d; do
    [ -n "$d" ] && build_one "$d"
  done < <(dep_names "$PKGS_DIR/$target")
}

main "$@"
