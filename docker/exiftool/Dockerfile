FROM alpine@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40

# exiftool is installed from its own git tag rather than Alpine's package.
# It ships roughly weekly, so any distro package trails upstream by several
# releases permanently — pinning the tag ourselves keeps the version exact,
# reproducible, and actually reachable when the version badge says we're
# behind. Same pattern as theHarvester's pinned-tag clone. exiftool is pure
# Perl, so this is just a checkout on PATH; bump this tag alongside
# registry.py's exif "pinned_version".
RUN apk add --no-cache perl curl git \
    && git clone --depth 1 --branch 13.59 https://github.com/exiftool/exiftool.git /opt/exiftool \
    && rm -rf /opt/exiftool/.git /opt/exiftool/t \
    && apk del git

ENV PATH="/opt/exiftool:${PATH}"

COPY docker/exiftool/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
