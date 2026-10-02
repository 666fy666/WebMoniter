# syntax=docker/dockerfile:1.7
ARG MODEL_SOURCE=downloaded-models
ARG PYTHON_IMAGE=python:3.11.15-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3
FROM node:24.14.0-bookworm-slim@sha256:d8e448a56fc63242f70026718378bd4b00f8c82e78d20eefb199224a4d8e33d8 AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS dependencies
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.26
RUN apt-get update && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY docker/prune-dependencies.sh /tmp/prune-dependencies.sh

FROM dependencies AS slim-dependencies
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --no-editable
RUN sh /tmp/prune-dependencies.sh

FROM dependencies AS full-dependencies
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --no-editable --extra rainyun
RUN sh /tmp/prune-dependencies.sh
RUN /app/.venv/bin/python -c "import numpy, onnxruntime, cv2, ddddocr"
FROM full-dependencies AS downloaded-models
COPY src/tasks/ikuuu_models.py /tmp/ikuuu_models.py
RUN python /tmp/ikuuu_models.py --directory /app/models/ikuuu

FROM ${MODEL_SOURCE} AS model-assets
USER root
RUN chmod -R a+rX /app/models

FROM ${PYTHON_IMAGE} AS runtime
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
    PYTHONPATH=/app PATH="/app/.venv/bin:$PATH" WEBMONITER_DOCKER=1 \
    WEBMONITER_DATA_DIR=/app/data WEBMONITER_LOG_DIR=/app/logs \
    WEBMONITER_CONFIG_FILE=/app/config/config.yml \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 webmoniter && useradd --uid 10001 --gid webmoniter --create-home webmoniter \
    && mkdir -p /app/data /app/logs /app/config \
    && chown webmoniter:webmoniter /app/data /app/logs /app/config
WORKDIR /app
COPY --chown=webmoniter:webmoniter main.py pyproject.toml ./
COPY --chown=webmoniter:webmoniter src/ ./src/
COPY --chown=webmoniter:webmoniter config/config.yml.sample ./config/config.yml.sample
COPY --from=frontend --chown=webmoniter:webmoniter /ui/dist ./frontend/dist
COPY --chmod=755 docker/docker-entrypoint.sh ./docker-entrypoint.sh
EXPOSE 8866
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8866/health/ready', timeout=3)"
CMD ["/app/docker-entrypoint.sh"]

FROM runtime AS slim
COPY --from=slim-dependencies /app/.venv /app/.venv
USER webmoniter

FROM runtime AS browser-runtime
ARG TARGETARCH
ARG CHROME_VERSION=150.0.7871.100
ARG CHROMIUM_DEB_VERSION=154.0.8037.92-1~deb12u1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 fonts-liberation libgl1 \
    && if [ "${TARGETARCH:-amd64}" = "arm64" ]; then \
        apt-get install -y --no-install-recommends "chromium=${CHROMIUM_DEB_VERSION}" "chromium-driver=${CHROMIUM_DEB_VERSION}"; \
    fi \
    && rm -rf /var/lib/apt/lists/*
# Download/extract in a builder so archives and tooling never enter the runtime layers.
FROM ${PYTHON_IMAGE} AS chrome-download
ARG TARGETARCH
ARG CHROME_VERSION=150.0.7871.100
RUN mkdir -p /browser && if [ "${TARGETARCH:-amd64}" = "amd64" ]; then \
    python -c "import io,zipfile,urllib.request; version='${CHROME_VERSION}'; [zipfile.ZipFile(io.BytesIO(urllib.request.urlopen('https://storage.googleapis.com/chrome-for-testing-public/'+version+'/linux64/'+name+'-linux64.zip',timeout=120).read())).extractall('/browser') for name in ('chrome','chromedriver')]" \
    && chmod -R a+rX /browser && chmod +x /browser/chrome-linux64/chrome /browser/chrome-linux64/chrome_crashpad_handler /browser/chromedriver-linux64/chromedriver; fi

FROM browser-runtime AS full
COPY --from=chrome-download /browser/ /opt/browser/
RUN if [ -f /opt/browser/chrome-linux64/chrome ]; then \
    ln -s /opt/browser/chrome-linux64/chrome /usr/bin/chromium \
    && ln -s /opt/browser/chromedriver-linux64/chromedriver /usr/bin/chromedriver; fi
COPY --from=full-dependencies /app/.venv /app/.venv
COPY --from=model-assets /app/models /app/models
RUN /app/.venv/bin/python -c "from pathlib import Path; from src.tasks.ikuuu_models import MODELS, verified_model; [verified_model(Path('/app/models/ikuuu'), name) for name in MODELS]"
ENV CHROME_BIN=/usr/bin/chromium CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    WEBMONITER_IKUUU_MODEL_DIR=/app/models/ikuuu WEBMONITER_PREFLIGHT_BROWSER_SMOKE=1
USER webmoniter

# A build without --target continues to produce the slim image.
FROM slim AS default
