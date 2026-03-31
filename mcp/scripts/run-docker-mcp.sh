#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE="${RULE_BASED_DOCKER_IMAGE:-ghcr.io/kroq86/rule-based-verifier:latest}"
WORKDIR="/workspace"
if [ -d "${ROOT_DIR}/backend" ]; then
  WORKDIR="/workspace/backend"
fi

exec docker run --rm -i \
  -v "${ROOT_DIR}:/workspace" \
  -w "${WORKDIR}" \
  --entrypoint /app/mcp/.venv/bin/python \
  "${IMAGE}" \
  -u /app/mcp/run_server.py

