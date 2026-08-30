#!/usr/bin/env bash
# Runs INSIDE the CachyOS makepkg container before building one package.
# CachyOS docker-makepkg images come with base-devel + CachyOS repos, so
# everything the vendored PKGBUILDs need (electron*, xrt, xrt-plugin-amdxdna,
# dotnet, qt6, etc.) is already available. We just sync and create the builder
# account if the image's defaults aren't usable.
set -euo pipefail

echo ">> image: $(grep '^NAME' /etc/os-release || echo unknown)"
echo ">> repos: $(grep -h '^\[' /etc/pacman.conf | tr '\n' ' ')"

# Sync fresh (CachyOS mirrors) so deps resolve to current versions
pacman -Syu --noconfirm || { sleep 8; pacman -Syy --noconfirm; }
pacman -S --noconfirm --needed base-devel git jq 2>/dev/null || true

# Ensure a non-root makepkg user exists.
if ! id builder >/dev/null 2>&1; then
  useradd -m -G wheel builder
  echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder
  chmod 440 /etc/sudoers.d/builder
fi

# Sanity: confirm the NPU runtime resolves (fastflowlm-git depends on it)
if ! pacman -Si xrt-plugin-amdxdna >/dev/null 2>&1; then
  echo "WARNING: xrt-plugin-amdxdna not in container repos (fastflowlm may fail)"
fi

echo ">> build env ready"
