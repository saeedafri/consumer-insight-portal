# The CIP portal for one Linux server (deploy/compose.yml): the FastAPI API and the ETL (one image, the repo's own
# requirements.txt, so the image runs exactly what the tests ran), and nginx serving the Next.js static export and the
# ETL-published payloads.
#   docker build -f deploy/Dockerfile --target api -t cip-portal .      (the API; also the etl and backup services)
#   docker build -f deploy/Dockerfile --target nginx -t cip-web .
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY deploy/csp_map.mjs ./
# the CSP hashes of each page's inline scripts (Next.js's own and the theme one): api/main.py policy() does the same
RUN npm run build && node csp_map.mjs out > /w/cip_csp_map.conf

# bookworm, not trixie: MySQL's own client (mysqldump, for the backup service) is published for bookworm; Debian's is
# MariaDB's, which scripts/backup_db.py's options do not fit. MySQL publishes it for amd64 only (the Azure VM): an ARM
# build, such as a test on the dev Mac, skips it and so has no backup service
FROM python:3.13-slim-bookworm AS api
RUN [ "$(dpkg --print-architecture)" != amd64 ] || { apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -fsSL https://repo.mysql.com/RPM-GPG-KEY-mysql-2025 | gpg --dearmor -o /usr/share/keyrings/mysql.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/mysql.gpg] http://repo.mysql.com/apt/debian bookworm mysql-8.4-lts" > /etc/apt/sources.list.d/mysql.list \
 && apt-get update && apt-get install -y --no-install-recommends mysql-community-client \
 && apt-get purge -y curl gnupg && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; }
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && useradd --system --create-home --uid 10001 cip
WORKDIR /srv/cip
COPY api/ api/
COPY app/ app/
COPY etl/ etl/
COPY config/ config/
COPY scripts/ scripts/
COPY sql/ sql/
COPY deploy/etl-loop.sh deploy/backup.sh deploy/
COPY DigiCertGlobalRootG2.crt.pem ./
COPY --from=web /w/out web/dist
RUN mkdir -p logs backups && chown cip logs backups && chmod -R a+rX /srv/cip   # sources may arrive owner-only
USER cip
EXPOSE 8000
# 2 workers on 1 core: one keeps answering while the other waits on the database. The default soft limit of
# 1,024 open files caps a worker at about a thousand open connections; raise it up to the hard limit.
ARG CIP_BUILD=unknown
# nginx caches every repeated answer (deploy/nginx.conf), so the API's own cache only needs the few it is asked for:
# 2 workers × (≈110 MB code + 32 MB of answers) ≈ 300 MB
ENV WEB_CONCURRENCY=2 CIP_BUILD=$CIP_BUILD CIP_CACHE_MB=32 APP_ENV=production
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["sh", "-c", "ulimit -n $(ulimit -Hn); exec gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY} -b 0.0.0.0:8000 --access-logfile - --timeout 30 --graceful-timeout 20 --forwarded-allow-ips '*'"]

FROM nginx:1.29-trixie AS nginx
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/cip_proxy.conf deploy/cip_headers.conf deploy/cip_locations.conf deploy/cip_auth.js /etc/nginx/
COPY --from=web /w/cip_csp_map.conf /etc/nginx/
COPY deploy/cip_tls.conf /etc/nginx/tls.d/
COPY deploy/cip_logs_off.conf /etc/nginx/logs.d/
COPY --from=web /w/out /srv/cip/web
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/8080'

# Azure App Service: one web app runs one container on one port, so nginx, the API and the ETL share this image
# (deploy/start.sh). Built on the same nginx image as above (its njs module checks the sign-in cookie); Debian trixie
# brings Python 3.13. Everything runs as the unprivileged user cip; the platform ends TLS in front of port 8080.
# logs/ and the open-ended coding (CIP_CODED_DIR) live in /home/cip via /tmp/cip-keep (deploy/start.sh): App Service keeps /home
#   docker build -f deploy/Dockerfile --target app --build-arg CIP_BUILD=$(git rev-parse --short HEAD) -t cip-portal-app .
FROM nginx:1.29-trixie AS app
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --create-home --uid 10001 cip
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
# mysqlclient: the API's and publish's reads decode rows in C (4.5x less CPU than PyMySQL, app/core/database.c_driver);
# maxminddb: reads the location file below (api/logs.py place_of). Both compiled here, then the compiler removed in the
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
COPY app/ app/
COPY etl/ etl/
COPY config/ config/
COPY scripts/ scripts/
COPY sql/ sql/
COPY deploy/etl-loop.sh deploy/start.sh deploy/machine-log.sh deploy/
COPY DigiCertGlobalRootG2.crt.pem ./
COPY data/coded/ data/coded/
COPY --from=web /w/out web/
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/cip_proxy.conf deploy/cip_headers.conf deploy/cip_locations.conf deploy/cip_auth.js /etc/nginx/
COPY --from=web /w/cip_csp_map.conf /etc/nginx/
COPY deploy/cip_logs.conf /etc/nginx/logs.d/
# the API is in this container, not a compose service; nginx keeps its pid where user cip may write it
RUN sed -i 's|server api:8000|server 127.0.0.1:8000|; s|^worker_processes 1;|pid /tmp/nginx.pid;\nworker_processes 1;|' /etc/nginx/nginx.conf \
 && mkdir -p published state /var/cache/nginx/data /home/cip/logs && ln -s /tmp/cip-keep/logs logs \
 && chown -R cip /srv/cip/published /srv/cip/state /var/cache/nginx /home/cip \
 && chmod -R a+rX /srv/cip /etc/nginx
ARG CIP_BUILD=unknown
ENV PATH=/opt/venv/bin:$PATH CIP_BUILD=$CIP_BUILD APP_ENV=production WEB_CONCURRENCY=1 CIP_CACHE_MB=32 \
    CIP_WEB_DIR=/srv/cip/web CIP_PUBLISH_DIR=/srv/cip/published CIP_REVOKED_FILE=/srv/cip/state/revoked.txt \
    CIP_TEAM_STAMP=/srv/cip/state/team.stamp CIP_NGINX_CACHE=/var/cache/nginx/data CIP_NGINX_URL=http://127.0.0.1:8080 \
    CIP_CODED_DIR=/tmp/cip-keep/coded CIP_LOG_DIR=/srv/cip/logs \
    STG_DB_SSL_CA=/srv/cip/DigiCertGlobalRootG2.crt.pem PYTHONDONTWRITEBYTECODE=1
USER cip
EXPOSE 8080
CMD ["bash", "deploy/start.sh"]
