ARG BUILDER_IMAGE=cgr.dev/chainguard/python:latest-dev@sha256:95d8cc85fad8acc8ebad357e1972f2a975c498a65406cd9b00bb2233371a94a2
ARG RUNTIME_IMAGE=cgr.dev/chainguard/python:latest@sha256:bf06e09413bec94d6489f0be783b8f9349339907b89e0f759d190d0b95ab2d8f
FROM ${BUILDER_IMAGE} AS build
USER 0
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install pip==26.2.2 \
    && /opt/venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
COPY pyproject.toml ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip /opt/venv/bin/python -m pip install --no-deps . \
    && mkdir /data && chown 10001:10001 /data \
    && /opt/venv/bin/python -m pip uninstall -y pip setuptools wheel

FROM build AS verify
COPY requirements-build-ci.txt ./
RUN --mount=type=cache,target=/root/.cache/pip PYYAML_FORCE_LIBYAML=0 python -m pip install \
    --target=/test-tools --no-deps --only-binary=:all: --no-binary=pyyaml -r requirements-build-ci.txt
COPY tests ./tests
COPY scripts ./scripts
COPY dags ./dags
COPY infra/main.tf ./infra/main.tf
ENV PYTHONPATH=/test-tools PYTHONDONTWRITEBYTECODE=1
RUN --network=none /opt/venv/bin/python scripts/build_verify.py

FROM ${RUNTIME_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PATH=/opt/venv/bin:/usr/bin
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=10001:10001 /data /data
COPY --from=verify /tmp/settlement-build-proof/receipt.json /opt/build-verification/receipt.json
USER 10001:10001
EXPOSE 8000
ENTRYPOINT []
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=3)"]
CMD ["python", "-m", "settlement_recon.entrypoint"]
