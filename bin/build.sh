#!/bin/bash
set -e

echo "--- Ghost Stack: SAS Lineage Build ---"

if [ ! -f .env ]; then
    echo "Creating default .env from example..."
    cp .env.example .env
fi

if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

echo "Syncing Python environment..."
uv sync --all-extras

echo "Building container..."
docker compose build

echo "--- Build complete. Run with 'docker compose up' ---"
