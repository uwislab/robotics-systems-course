# ── Stage 1: 构建 MkDocs ──────────────────────────────────────────────────────
FROM python:3.12-alpine AS builder
WORKDIR /build
RUN pip install --no-cache-dir mkdocs mkdocs-material
COPY . .
RUN mkdocs build

# ── Stage 2: Nginx 提供静态文件 ───────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /build/site /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
