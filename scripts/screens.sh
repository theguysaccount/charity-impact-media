#!/usr/bin/env bash
# Screenshots of the key pages at desktop (1280px) and phone (390px) widths -> docs/screens/
#   scripts/screens.sh https://theguysaccount.github.io/charity-impact-media
# Uses headless Chrome with a throwaway profile (CHROME=/path/to/chrome to override).
set -euo pipefail
base="${1:?site base URL}"
chrome="${CHROME:-}"
if [ -z "$chrome" ]; then
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "$(command -v google-chrome || true)" "$(command -v chromium-browser || true)"; do
    if [ -n "$c" ] && [ -x "$c" ]; then chrome="$c"; break; fi
  done
fi
out="$(cd "$(dirname "$0")/.." && pwd)/docs/screens"
mkdir -p "$out"
profile="$(mktemp -d)"
trap 'rm -rf "$profile"' EXIT
shoot() {  # name path width height
  "$chrome" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="$profile" --force-device-scale-factor=1 \
    --window-size="$3,$4" --screenshot="$out/$1.png" "$base$2" >/dev/null 2>&1
  echo "$out/$1.png"
}
shoot home-desktop / 1280 1400
shoot home-phone / 390 1700
shoot charity-desktop /charity/530196605/ 1280 2600
shoot charity-phone /charity/530196605/ 390 3000
shoot category-desktop /category/food-agriculture-nutrition/ 1280 1400
shoot compare-desktop "/compare/?e=530196605,363673599,131788491" 1280 1100
shoot guide-phone /guides/givingtuesday-checklist/ 390 1500
shoot embed /embed/?ein=363673599 460 360
