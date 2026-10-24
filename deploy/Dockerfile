# The CIP portal for one Linux server (deploy/compose.yml): the FastAPI API and the ETL (one image, the repo's own
# requirements.txt, so the image runs exactly what the tests ran), and nginx serving the React + Vite files and the
# ETL-published payloads.
#   docker build -f deploy/Dockerfile --target api -t cip-portal .      (the API; also the etl and backup services)
#   docker build -f deploy/Dockerfile --target nginx -t cip-web .
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build \
 && node -e "const c=require('crypto'),h=require('fs').readFileSync('dist/index.html','utf8');\
process.stdout.write([...h.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>\"'sha256-\"+c.createHash('sha256').update(m[1]).digest('base64')+\"'\").join(' '))" > /w/csp-hashes.txt

# bookworm, not trixie: MySQL's own client (mysqldump, for the backup service) is published for bookworm; Debian's is
# MariaDB's, which scripts/backup_db.py's options do not fit
FROM python:3.13-slim-bookworm AS api
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -fsSL https://repo.mysql.com/RPM-GPG-KEY-mysql-2023 | gpg --dearmor -o /usr/share/keyrings/mysql.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/mysql.gpg] http://repo.mysql.com/apt/debian bookworm mysql-8.4-lts" > /etc/apt/sources.list.d/mysql.list \
 && apt-get update && apt-get install -y --no-install-recommends mysql-community-client \
 && apt-get purge -y curl gnupg && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
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
COPY --from=web /w/dist web/dist
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
COPY --from=web /w/csp-hashes.txt /tmp/csp-hashes.txt
RUN sed -i "s|__SCRIPT_HASHES__|$(cat /tmp/csp-hashes.txt)|" /etc/nginx/cip_headers.conf
COPY --from=web /w/dist /srv/cip/web
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/8080'
