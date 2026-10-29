#!/bin/sh
# Rebuild the public static site from the latest published pipeline data and refresh the live snapshot the API serves.
# Run after each weekly publish so /this-week, /data and the home stats carry the newest wave. No API restart needed:
# the API reads web-live from disk on each request.
set -e
cd "$(dirname "$0")/../web-next"
npm run build
rm -rf "$HOME/.config/cip/web-live"
cp -R out "$HOME/.config/cip/web-live"
echo "site refreshed from latest pipeline → ~/.config/cip/web-live"
