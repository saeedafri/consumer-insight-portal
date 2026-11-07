# The CIP portal as one Azure App Service container: nginx (the website and the published answers) in front of the
# FastAPI API, with the ETL scheduler beside them (deploy/start.sh starts all three). bitbucket-pipelines.yml builds
# the `app` target for staging (branch stg-deploy) and production (pro-deploy):
#   docker build -f deploy/Dockerfile --target app --build-arg CIP_BUILD=$(git rev-parse --short HEAD) -t cip-portal-app .
# Stage `web` builds the website (Next.js static export) that `app` copies in.
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY deploy/csp_map.mjs ./
# the CSP hashes of each page's inline scripts (Next.js's own and the theme one): api/main.py policy() does the same
RUN npm run build && node csp_map.mjs out > /w/cip_csp_map.conf

# Azure App Service: one web app runs one container on one port, so nginx, the API and the ETL share this image
# (deploy/start.sh). Built on the official nginx image (its njs module checks the sign-in cookie); Debian trixie
# brings Python 3.13. Everything runs as the unprivileged user cip; the platform ends TLS in front of port 8080.
# logs/ and the open-ended coding (CIP_CODED_DIR) live in /home/cip via /tmp/cip-keep (deploy/start.sh): App Service keeps /home
#   docker build -f deploy/Dockerfile --target app --build-arg CIP_BUILD=$(git rev-parse --short HEAD) -t cip-portal-app .
FROM nginx:1.29-trixie AS app
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --create-home --uid 10001 cip
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
# mysqlclient: the API's and publish's reads decode rows in C (4.5x less CPU than PyMySQL, shared/core/database.c_driver);
# maxminddb: reads the location file below (api/metrics.py place_of). Both compiled here, then the compiler removed in the
# same layer: only the 1 MB client library stays
RUN apt-get update && apt-get install -y --no-install-recommends gcc pkg-config libmariadb-dev python3-dev \
 && /opt/venv/bin/pip install --no-cache-dir mysqlclient==2.3.0 maxminddb==2.6.2 \
 && apt-get purge -y gcc pkg-config libmariadb-dev python3-dev && apt-get autoremove -y \
 && apt-get install -y --no-install-recommends libmariadb3 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/cip
# the visitors' city on the Logs page, looked up here (about 130 MB on disk, read on demand, not loaded into memory)
COPY deploy/geo-download.py /tmp/
RUN mkdir -p geo && python3 /tmp/geo-download.py geo/dbip-city-lite.mmdb
COPY api/ api/
COPY shared/ shared/
COPY etl/ etl/
COPY config/ config/
COPY scripts/ scripts/
COPY sql/ sql/
COPY deploy/etl-loop.sh deploy/start.sh deploy/machine-log.sh deploy/archive-log.py deploy/
COPY DigiCertGlobalRootG2.crt.pem ./
COPY data/coded/ data/coded/
COPY --from=web /w/out web/
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/cip_proxy.conf deploy/cip_headers.conf deploy/cip_locations.conf deploy/cip_auth.js /etc/nginx/
COPY --from=web /w/cip_csp_map.conf /etc/nginx/
COPY deploy/cip_logs.conf /etc/nginx/logs.d/
RUN mkdir -p published state /var/cache/nginx/data /home/cip/logs && ln -s /tmp/cip-keep/logs logs \
 && chown -R cip /srv/cip/published /srv/cip/state /var/cache/nginx /home/cip \
 && chmod -R a+rX /srv/cip /etc/nginx
ARG CIP_BUILD=unknown
ENV PATH=/opt/venv/bin:$PATH CIP_BUILD=$CIP_BUILD APP_ENV=production WEB_CONCURRENCY=1 CIP_CACHE_MB=32 \
    CIP_WEB_DIR=/srv/cip/web CIP_PUBLISH_DIR=/srv/cip/published CIP_REVOKED_FILE=/srv/cip/state/revoked.txt \
    CIP_TEAM_STAMP=/srv/cip/state/team.stamp CIP_NGINX_CACHE=/var/cache/nginx/data CIP_NGINX_URL=http://127.0.0.1:8080 \
    CIP_CODED_DIR=/tmp/cip-keep/coded CIP_FIELDWORK_DIR=/tmp/cip-keep/fieldwork CIP_LOG_DIR=/srv/cip/logs \
    STG_DB_SSL_CA=/srv/cip/DigiCertGlobalRootG2.crt.pem PYTHONDONTWRITEBYTECODE=1
USER cip
EXPOSE 8080
CMD ["bash", "deploy/start.sh"]
