# Every stack in the benchmark, on Debian 13 (trixie). Build context: scripts/ui_benchmark
#   docker build -f stacks/Dockerfile --target py   -t bench-py   .
#   docker build -f stacks/Dockerfile --target node -t bench-node .
#   docker build -f stacks/Dockerfile --target load -t bench-load .
FROM node:26-trixie-slim AS web
WORKDIR /w
COPY stacks/vite-app/package.json vite/
RUN cd vite && npm install --no-audit --no-fund
COPY stacks/vite-app vite/
RUN cd vite && npm run build
COPY stacks/next-app/package.json next/
RUN cd next && npm install --no-audit --no-fund
COPY stacks/next-app next/
RUN cd next && npx next build && mkdir -p /out && cp -r .next/standalone /out/ssr && cp -r .next/static /out/ssr/.next/static \
 && cp static/page.tsx app/page.tsx && rm -rf .next && NEXT_OUTPUT=export npx next build && cp -r out /out/next-static \
 && cp -r /w/vite/dist /out/vite
RUN { cd /w/next && npm ls next react; cd /w/vite && npm ls vite react echarts; } > /out/versions.txt || true

FROM python:3.13-slim-trixie AS py
RUN pip install --no-cache-dir "streamlit==1.55.0" fastapi "uvicorn[standard]" gunicorn dash pandas \
 && pip freeze | grep -iE "^(streamlit|fastapi|uvicorn|gunicorn|dash|pandas|starlette)==" > /versions.txt
WORKDIR /b
COPY api_page.py dash_page.py streamlit_sql.py streamlit_naive.py matched.html ./
COPY --from=web /out/vite /static/vite
COPY --from=web /out/next-static /static/next
COPY --from=web /out/versions.txt /versions-web.txt

FROM node:26-trixie-slim AS node
WORKDIR /b
COPY node_page.mjs matched.html ./
COPY --from=web /out/vite /static/vite
COPY --from=web /out/ssr /ssr

FROM debian:trixie-slim AS load
RUN apt-get update && apt-get install -y --no-install-recommends wrk curl ca-certificates && rm -rf /var/lib/apt/lists/*
