#!/usr/bin/env bash
# Lint + format for NixOS (where ruff binary won't run from pip).
# On Mac/Windows, just use: pre-commit run --all-files
set -e

echo "=== ruff check ==="
nix-shell -p ruff --run "ruff check --fix ."

echo "=== ruff format ==="
nix-shell -p ruff --run "ruff format ."
