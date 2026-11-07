ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.3.0@sha256:01448978e65c3320030d97e9c9d59ed93e4173d54696ab4bc3eabe4439bff1ee
FROM node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9 AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ${BUILD_FROM}
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv nginx postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/* \
    && python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" VOLLEYCREW_STATE_DIR=/data VOLLEYCREW_ENV_FILE=/dev/null \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend S6_BEHAVIOUR_IF_STAGE2_FAILS=2
WORKDIR /app/backend
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY --from=frontend-build /build/dist /app/frontend
COPY rootfs/ /
# Keep s6, but do not require Supervisor APIs for cosmetic base-image helpers.
# Configuration comes only from /data/options.json, also in standalone tests.
RUN for helper in base-app-banner base-app-log-level base-app-timezone; do \
      printf '#!/bin/sh\nexit 0\n' > /package/admin/s6-overlay-3.2.2.0/etc/s6-rc/scripts/$helper; \
    done
RUN chmod +x /etc/cont-init.d/* /etc/services.d/*/run /etc/services.d/*/finish /usr/local/bin/volleycrew-* \
    && mkdir -p /run/nginx /data
ARG BUILD_ARCH
ARG BUILD_VERSION=0.1.0
RUN printf "%s" "$BUILD_VERSION" > /app/VERSION
LABEL io.hass.name="Volleycrew" io.hass.description="Tuesday volleyball group" \
      io.hass.type="addon" io.hass.arch="${BUILD_ARCH}" io.hass.version="${BUILD_VERSION}" \
      org.opencontainers.image.source="https://github.com/arkadiusz-dalecki/volleycrew"
EXPOSE 8200 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8200/api/v1/health/ready > /dev/null || exit 1
