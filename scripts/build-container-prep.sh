#!/usr/bin/env bash
# Runs INSIDE the archlinux build container before compiling one package.
# All deps the tracked packages need (electron*, xrt/xrt-plugin-amdxdna for the
# NPU build, dotnet, qt6, etc.) are in stock Arch [extra]/[core], so a plain
# archlinux base with a refreshed keyring is sufficient.
set -euo pipefail

echo ">> image: $(grep '^PRETTY_NAME' /etc/os-release | cut -d= -f2)"

# Fresh keyring + full update from current mirrors.
pacman-key --init
pacman-key --populate archlinux
pacman -Syy
pacman -Syu --noconfirm
pacman -S --noconfirm --needed base-devel git jq sudo

# Add Chaotic-AUR + this personal repo so makepkg -s can install AUR deps
# that were already published (either prebuilt by Chaotic or built here in a
# previous run). Deps added in the SAME add-package run still race — matrix
# jobs run in parallel — but on the next poll cycle they resolve.
cat >> /etc/pacman.conf <<'EOF'

[chaotic-aur]
SigLevel = Optional TrustAll
Server = https://cdn-mirror.chaotic.cx/chaotic-aur/x86_64

[personal]
SigLevel = Optional TrustAll
Server = https://phantomic12.github.io/personal-repo/
EOF
# Sync the extra repos but don't die if a CDN 503s — deps that only live in
# chaotic/personal will just fail later in makepkg with a clearer error, and
# most builds don't need them at all. Retry once after a short wait.
pacman -Syy --noconfirm || { sleep 10; pacman -Syy --noconfirm; } \
  || echo "WARN: repo sync failed (transient CDN error?) — continuing"

# Non-root builder for makepkg (refuses to run as root).
if ! id builder >/dev/null 2>&1; then
  useradd -m -G wheel builder
  echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder
  chmod 440 /etc/sudoers.d/builder
fi

# Sanity checks: confirm the deps resolve from stock repos.
for probe in electron39 electron42 xrt-plugin-amdxdna dotnet-sdk; do
  if pacman -Si "$probe" >/dev/null 2>&1; then
    echo "dep OK: $probe = $(pacman -Si "$probe" | awk '/^Version/{print $3}')"
  else
    echo "WARN: $probe not resolvable in this container"
  fi
done

echo ">> build env ready"
