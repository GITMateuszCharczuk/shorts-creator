# The ONE shared image (ADR 0015 D2): entrypoint selects a stage or the conductor.
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml
COPY shared/ shared/
COPY stages/ stages/
COPY shorts/ shorts/
COPY schemas/ schemas/
COPY formats/ formats/
COPY profiles/ profiles/
ENTRYPOINT ["python", "-m"]
CMD ["shorts.run_batch"]
# NOTE (honest scope): the Remotion/Node render layer is NOT in this image — the CI gate runs
# the offline DAG with fakes (render is integration). A `render` build stage is added when the
# k8s profile (0015a M7) needs in-cluster rendering.

# The CI-proof stage (ADR 0015 D2): dev deps + tests, used by `make build` and the workflow.
FROM base AS ci
RUN uv pip install --system pytest jsonschema numpy pillow soundfile
COPY tests/ tests/
