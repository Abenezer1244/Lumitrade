# Stage 1: Dependency builder
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime (cache-bust: pw-v3)
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
# System deps + Playwright Chromium — all in one layer to ensure cache coherence
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libx11-xcb1 libxfixes3 fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/pw-browsers \
    && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers playwright install chromium \
    && chmod -R o+rX /opt/pw-browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
# lumitrade user has no home dir — point matplotlib and fontconfig caches to writable /tmp
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV FC_CACHEDIR=/tmp/fontconfig
COPY backend/lumitrade/ /app/lumitrade/
COPY backend/supervisord.conf /etc/supervisor/conf.d/lumitrade.conf
RUN useradd --no-create-home --shell /bin/false lumitrade && \
    mkdir -p /var/log/lumitrade && \
    chown -R lumitrade:lumitrade /app /var/log/lumitrade
USER lumitrade
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/lumitrade.conf"]
# Cache bust 2026-04-21T08:11:13Z
# repo reconnected test 2026-04-21T08:21:02Z
