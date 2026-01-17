#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"

if [[ ! -d "$ROOT/.githooks" ]]; then
  echo "Missing .githooks directory at $ROOT/.githooks" >&2
  exit 1
fi

chmod +x "$ROOT/.githooks/pre-commit"

git config core.hooksPath "$ROOT/.githooks"
echo "Git hooks installed. Hooks path set to $ROOT/.githooks"
