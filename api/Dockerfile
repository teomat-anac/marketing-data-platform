# The KPI API image, built by Cloud Build (cloudbuild.yaml) and run on Cloud Run.
# Two stages: uv installs the locked dependencies into a virtualenv, then only that
# virtualenv is copied into a clean image: no uv, no source tree, no dev tools (W3).
# Base images are pinned by version and digest; Python matches the local uv one.

FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv

# Compile .pyc now (faster cold starts); copy files rather than link them into the venv;
# use the image's Python, never a downloaded one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, in their own layer: it is reused until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

# Then the app itself, installed into the venv as a regular package.
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app

# Cloud Run sends requests to port 8080 (the service's container port).
EXPOSE 8080
CMD ["uvicorn", "mdp_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
