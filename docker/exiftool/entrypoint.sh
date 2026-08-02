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
    curl -sS --max-time 20 --max-filesize 20971520 -o /output/input "$2"
    ;;
  --file)
    ;;
  *)
    echo "usage: --url <url> | --file" >&2
    exit 2
    ;;
esac

exec exiftool -json -n -- /output/input
