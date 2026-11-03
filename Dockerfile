FROM python:3.12-slim

# Infisical CLI (pinned release, checksum-verified): secrets reach the app at start through `infisical run`.
ARG INFISICAL_VERSION=0.43.145
ARG TARGETARCH
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl ffmpeg poppler-utils libglib2.0-0 libgomp1; \
    arch="${TARGETARCH:-amd64}"; \
    case "$arch" in \
      amd64) sha="36732e9c108feb3916eabd5be35db7a56431c383b766a6c3b1afa05cb27696ae" ;; \
      arm64) sha="9b559ed2bd639c59999eb181270aca975554ca45fcdf2eaf118d53a8fce4b98c" ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/infisical.deb \
      "https://github.com/Infisical/cli/releases/download/v${INFISICAL_VERSION}/infisical_${INFISICAL_VERSION}_linux_${arch}.deb"; \
    echo "${sha}  /tmp/infisical.deb" | sha256sum -c -; \
    apt-get install -y --no-install-recommends /tmp/infisical.deb; \
    rm -f /tmp/infisical.deb; \
    apt-get purge -y curl; apt-get autoremove -y; rm -rf /var/lib/apt/lists/*; \
    infisical --version

WORKDIR /app
COPY pyproject.toml README.md ./
COPY billradar ./billradar
COPY scripts ./scripts
COPY tests/__init__.py tests/synth.py ./tests/
COPY tests/fixtures ./tests/fixtures
COPY eval/packs/work ./eval/packs/work

RUN pip install --no-cache-dir -e .
# The hospitals' public policies, forms and price files: read from their own sites at build, never shipped in the repo.
# The policies are required. A price file that cannot be downloaded (a hospital site that drops the connection) leaves
# that hospital's price checks off instead of failing the build; `prices.load` then returns None and says so.
RUN python scripts/fetch_policies.py && { python scripts/fetch_prices.py || echo "some price files could not be downloaded: their price checks stay off"; }
# The examples, built once here from the recordings, on one thread (the build shares its machine); the volume on
# /app/runs gets a copy at the first request.
RUN python -c "from pathlib import Path; from billradar import example; example.ensure(Path('/app/runs-seed'), Path('/nowhere'))"

RUN useradd --create-home --uid 10001 appuser && mkdir -p runs && chown -R appuser:appuser /app
USER appuser

# A public copy: fictional examples, questions and voice live, nobody's own papers.
ENV BILLRADAR_PUBLIC=1 BILLRADAR_TRUST_PROXY=1 PYTHONUNBUFFERED=1 PORT=8080 SECRETS_SOURCE=infisical
EXPOSE 8080

# Wraps the command in `infisical run` when SECRETS_SOURCE=infisical; fails closed on missing or empty secrets.
COPY --chmod=0755 tools/docker-entrypoint.sh /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn billradar.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
