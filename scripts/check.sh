#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff..."
uv run ruff check .

echo "Running mypy..."
uv run mypy .

echo "Running pytest..."
uv run pytest
