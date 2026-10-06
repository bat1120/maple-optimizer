# 2단계 빌드: (1) 웹 빌드 (2) Python 런타임. 베이스 이미지는 amd64·arm64(Oracle Ampere) 모두 지원한다.
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY engine/ engine/
COPY nexon/ nexon/
COPY server/ server/
COPY agent/ agent/
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist web/dist
# NEXON_API_KEY는 실행 시 환경변수(.env → docker compose env_file)로 넣는다. 이미지에 넣지 않는다.
VOLUME ["/app/.cache"]
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "server.app:default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
