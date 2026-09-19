#!/usr/bin/env bash
# Downstream fix for cline-desktop: `tauri build --bundles deb` panics with
# "Can't detect any appindicator library" when libayatana-appindicator isn't
# installed at BUILD time (tauri-cli probes for it during bundling, even
# though it's only a runtime optdep). Upstream PKGBUILD keeps it in
# optdepends only, so the build container lacks it. Add it to makedepends
# (and depends, so the tray icon actually works after install).
set -euo pipefail

sed -i \
  -e "s/^makedepends=(/makedepends=(\n  'libayatana-appindicator'/" \
  -e "s/^depends=(/depends=(\n  'libayatana-appindicator'/" \
  PKGBUILD

echo "patched: libayatana-appindicator added to depends + makedepends"
