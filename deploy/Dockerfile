# The CIP portal for one Debian server: React + Vite static files and the FastAPI API in one container.
#   docker build -f deploy/Dockerfile -t cip-portal .
#   docker run --cpus 1 --memory 4g --env-file /etc/cip/api.env -p 8000:8000 cip-portal
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.13-slim-trixie
RUN pip install --no-cache-dir "fastapi==0.150.0" "uvicorn[standard]==0.54.0" "gunicorn==26.2.0" \
      "sqlalchemy>=2.0.46" "pymysql>=1.1.0" "cryptography>=46.0.0" "python-dotenv>=1.0.0" "pyyaml>=6.0" \
 && useradd --system --create-home --uid 10001 cip
WORKDIR /srv/cip
COPY api/ api/
COPY app/ app/
COPY etl/ etl/
COPY config/ config/
COPY --from=web /w/dist web/dist
RUN chmod -R a+rX /srv/cip   # sources may arrive owner-only from the build machine
USER cip
EXPOSE 8000
# 2 workers on 1 core: one keeps answering while the other waits on the database. The default soft limit of
# 1,024 open files caps a worker at about a thousand open connections; raise it up to the hard limit.
ENV WEB_CONCURRENCY=2
CMD ["sh", "-c", "ulimit -n $(ulimit -Hn); exec gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY} -b 0.0.0.0:8000 --access-logfile - --timeout 30 --graceful-timeout 20"]
