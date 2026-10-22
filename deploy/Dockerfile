# The CIP portal for one Debian server (deploy/compose.yml): the FastAPI API, and nginx serving the React + Vite
# files and the ETL-published payloads.
#   docker build -f deploy/Dockerfile --target api -t cip-portal .      (also serves the web files on its own)
#   docker build -f deploy/Dockerfile --target nginx -t cip-web .
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.13-slim-trixie AS api
RUN pip install --no-cache-dir "fastapi==0.150.0" "uvicorn[standard]==0.54.0" "gunicorn==26.2.0" \
      "sqlalchemy>=2.0.46" "pymysql>=1.1.0" "cryptography>=46.0.0" "python-dotenv>=1.0.0" "pyyaml>=6.0" \
      "openpyxl>=3.1.5" "python-pptx==1.0.2" "anthropic==2.0.0" \
 && useradd --system --create-home --uid 10001 cip
WORKDIR /srv/cip
COPY api/ api/
COPY app/ app/
COPY etl/ etl/
COPY config/ config/
COPY DigiCertGlobalRootG2.crt.pem ./
COPY --from=web /w/dist web/dist
RUN chmod -R a+rX /srv/cip   # sources may arrive owner-only from the build machine
USER cip
EXPOSE 8000
# 2 workers on 1 core: one keeps answering while the other waits on the database. The default soft limit of
# 1,024 open files caps a worker at about a thousand open connections; raise it up to the hard limit.
ARG CIP_BUILD=unknown
# nginx caches every repeated answer (deploy/nginx.conf), so the API's own cache only needs the few it is asked for:
# 2 workers × (≈110 MB code + 32 MB of answers) ≈ 300 MB
ENV WEB_CONCURRENCY=2 CIP_BUILD=$CIP_BUILD CIP_CACHE_MB=32
CMD ["sh", "-c", "ulimit -n $(ulimit -Hn); exec gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY} -b 0.0.0.0:8000 --access-logfile - --timeout 30 --graceful-timeout 20"]

FROM nginx:1.29-trixie AS nginx
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/cip_proxy.conf /etc/nginx/cip_proxy.conf
COPY deploy/cip_headers.conf /etc/nginx/cip_headers.conf
COPY deploy/cip_auth.js /etc/nginx/cip_auth.js
COPY --from=web /w/dist /srv/cip/web
