#!/usr/bin/env bash
# Install the personal pacman repo on this Arch machine.
# Adds the [personal] block to /etc/pacman.conf and syncs the package DB.
#
# Usage:
#   ./install-repo.sh            # dry-run: show what would change, change nothing
#   ./install-repo.sh --apply    # actually modify /etc/pacman.conf and pacman -Sy
#
# Safe to re-run: the [personal] block is idempotent.

set -euo pipefail

REPO_NAME="personal"
SERVER="https://phantomic12.github.io/personal-repo/"
PACMAN_CONF="/etc/pacman.conf"

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
    APPLY=1
fi

if ! command -v pacman >/dev/null 2>&1; then
    echo "error: pacman not found — this is for Arch Linux." >&2
    exit 1
fi

# The block we'll ensure is present.
read -r -d '' BLOCK <<EOF || true
[${REPO_NAME}]
SigLevel = Optional TrustAll
Server = ${SERVER}
EOF

proc_file() {
    # Print the file content with the [personal] block ensured (or unchanged).
    local f="$1" out
    out=$(cat "$f")
    if grep -q "^\[${REPO_NAME}\]" <<<"$out"; then
        echo "$out"
    else
        out+=$'\n\n'"$BLOCK"$'\n'
        echo "$out"
    fi
}

if [[ $APPLY -ne 1 ]]; then
    echo "Dry-run. The [${REPO_NAME}] block would be added to ${PACMAN_CONF}:"
    echo
    echo "$BLOCK"
    echo
    echo "Re-run with --apply to write it and run 'sudo pacman -Sy'."
    exit 0
fi

if [[ $EUID -ne 0 ]]; then
    # If we're root we can write directly; otherwise re-exec with sudo (or pkexec).
    if command -v sudo >/dev/null 2>&1; then
        exec sudo "$0" --apply
    elif command -v pkexec >/dev/null 2>&1; then
        exec pkexec "$0" --apply
    else
        echo "error: need root (no sudo or pkexec available)." >&2
        exit 1
    fi
fi

new=$(proc_file "$PACMAN_CONF")
if [[ "$new" == "$(cat "$PACMAN_CONF")" ]]; then
    echo "Already configured in ${PACMAN_CONF} — nothing to add."
else
    cp "$PACMAN_CONF" "$PACMAN_CONF.bak"
    printf '%s\n' "$new" > "$PACMAN_CONF"
    echo "Added [${REPO_NAME}] to ${PACMAN_CONF} (backup: ${PACMAN_CONF}.bak)."
fi

echo "Syncing package database..."
pacman -Sy

echo "Done. Install packages with:  pacman -S --needed <package>"
