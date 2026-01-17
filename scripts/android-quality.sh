#!/usr/bin/env bash
set -euo pipefail

FORMAT=false
CI=false

for arg in "$@"; do
  case "$arg" in
    --format)
      FORMAT=true
      ;;
    --ci)
      CI=true
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "${SKIP_ANDROID_QUALITY:-}" == "1" ]]; then
  echo "SKIP_ANDROID_QUALITY=1 set; skipping Android quality checks."
  exit 0
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/gradlew" ]]; then
  echo "gradlew not found; skipping Android quality checks."
  exit 0
fi

chmod +x "$ROOT/gradlew"

gradle_args=()
if $CI; then
  gradle_args+=(--no-daemon)
fi

if $FORMAT; then
  "$ROOT/gradlew" "${gradle_args[@]}" ktlintFormat
fi

"$ROOT/gradlew" "${gradle_args[@]}" ktlintCheck lint testDebugUnitTest
