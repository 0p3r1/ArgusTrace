#!/bin/sh
# Two modes, chosen by the plugin depending on how the image was supplied:
#   --url <url>   fetch the image ourselves (network access stays inside
#                 this hardened, read-only container, never on the host)
#   --file        the image is already at /output/input (host wrote it there
#                 via the mounted volume, for the base64-upload case)
# Either way, exiftool only ever reads /output/input.
set -eu

case "${1:-}" in
  --url)
    # Some sites (verified against a real .gov server) block curl's default
    # User-Agent outright — a plain browser-like UA is enough to pass.
    curl -sS --max-time 45 --max-filesize 104857600 \
      -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
      -o /output/input "$2"
    ;;
  --file)
    ;;
  *)
    echo "usage: --url <url> | --file" >&2
    exit 2
    ;;
esac

exec exiftool -json -n -- /output/input
