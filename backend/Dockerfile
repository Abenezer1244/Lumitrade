# Stage 1: Dependency builder
FROM python:3.14-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.14-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends supervisor curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY backend/lumitrade/ /app/lumitrade/
COPY backend/supervisord.conf /etc/supervisor/conf.d/lumitrade.conf
RUN useradd --no-create-home --shell /bin/false lumitrade && \
    mkdir -p /var/log/lumitrade && \
    chown -R lumitrade:lumitrade /app /var/log/lumitrade
USER lumitrade
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/lumitrade.conf"]
