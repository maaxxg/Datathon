#!/usr/bin/env bash
# Poll /api/health until every *_loaded flag is true, or give up after 120 s.
# Usage: scripts/wait_healthy.sh            (BASE_URL defaults to https://localhost)
#        BASE_URL=https://example.org scripts/wait_healthy.sh
# -k: locally Caddy uses its internal CA (self-signed).
set -uo pipefail

BASE_URL="${BASE_URL:-https://localhost}"
DEADLINE=$((SECONDS + 120))
body=""

while [ $SECONDS -lt $DEADLINE ]; do
  body="$(curl -ksf --max-time 5 "$BASE_URL/api/health" || true)"
  if [ -n "$body" ]; then
    result="$(printf '%s' "$body" | python3 -c '
import json, sys
d = json.load(sys.stdin)
bad = sorted(k for k, v in d.items() if k.endswith("_loaded") and v is not True)
print(",".join(bad))
' 2>/dev/null || echo "?")"
    if [ -z "$result" ]; then
      echo "OK: svi slojevi učitani ($BASE_URL)"
      exit 0
    fi
  fi
  sleep 3
done

echo "Isteklo vrijeme (120 s) za $BASE_URL" >&2
if [ -z "$body" ]; then
  echo "API ne odgovara." >&2
else
  echo "Slojevi koji nisu učitani: ${result:-?}" >&2
fi
exit 1
