# ── Stage 1: 构建 MkDocs ──────────────────────────────────────────────────────
FROM python:3.12-alpine AS builder
WORKDIR /build
RUN apk add --no-cache cargo rust \
	&& cargo install svgbob_cli --locked \
	&& ln -sf /root/.cargo/bin/svgbob_cli /root/.cargo/bin/svgbob
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdocs build

# ── Stage 2: Nginx 提供静态文件 ───────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /build/site /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
