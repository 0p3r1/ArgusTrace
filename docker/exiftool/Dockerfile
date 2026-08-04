FROM alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc

# Pinned exiftool=12.80-r0 explicitly — the base image digest alone doesn't
# freeze this: v3.20/community is a live, in-branch-updated apk repo, so an
# unpinned `apk add exiftool` could silently install a different exiftool
# version on a future rebuild of the exact same digest. Bump this alongside
# registry.py's exif "pinned_version" when upgrading.
RUN apk add --no-cache exiftool=12.80-r0 curl

COPY docker/exiftool/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
