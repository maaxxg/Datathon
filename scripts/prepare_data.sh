#!/usr/bin/env bash
# Prepare the local data/ directory needed for a full report. Idempotent: every step
# is skipped when its output already exists.
#
# Usage:
#   scripts/prepare_data.sh [--data DIR] [--force]
#   DIR defaults to $GEORIZIK_DATA, else <repo>/data.
# Python: $PYTHON, else backend/.venv/bin/python if present, else python3.
# Run it on the host (the compose api service mounts data/ read-only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${GEORIZIK_DATA:-$ROOT/data}"
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --data) DATA="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "Nepoznata opcija: $1" >&2; exit 2 ;;
  esac
done

if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"
elif [ -x "$ROOT/backend/.venv/bin/python" ]; then PY="$ROOT/backend/.venv/bin/python"
else PY=python3; fi

# Layer catalogue: in the repo it is backend/app/layers.yaml, in the image /app/app/layers.yaml.
LAYERS="$ROOT/backend/app/layers.yaml"
[ -f "$LAYERS" ] || LAYERS="$ROOT/app/layers.yaml"

ZIP="$DATA/raw/INSPIRE_Addresses_(AD).zip"
GEO_FILES="landslide liquefaction sinkhole unfavourable groundwater"

mkdir -p "$DATA"

geo_done() {
  for n in $GEO_FILES; do [ -s "$DATA/geohazards/$n.geojson" ] || return 1; done
}
efas_done() {
  for n in rp10 rp100 rp500; do [ -s "$DATA/efas/$n.tif" ] || return 1; done
}
# run NAME DONE_FUNC_OR_FILE COMMAND...
skip_or_run() {
  local name="$1" check="$2"; shift 2
  if [ "$FORCE" -eq 0 ] && $check; then
    echo "== $name: preskočeno (već postoji)"
  else
    echo "== $name"
    "$@"
  fi
}
file_done() { [ -s "$DATA/seismic/eshm20_pga475.json" ]; }
sqlite_done() { [ -s "$DATA/addresses.sqlite" ]; }

download_zip() {
  local url
  url="$("$PY" -I -c "import sys,yaml; print(yaml.safe_load(open(sys.argv[1], encoding='utf-8'))['layers']['addresses']['download'])" "$LAYERS")"
  mkdir -p "$DATA/raw"
  if [ "$FORCE" -eq 0 ] && [ -s "$ZIP" ]; then
    echo "   zip već postoji: $ZIP"
    return
  fi
  echo "   preuzimanje $url"
  "$PY" -I - "$url" "$ZIP" <<'PYEOF'
import sys, httpx
from pathlib import Path
url, dest = sys.argv[1], Path(sys.argv[2])
part = dest.with_name(dest.name + ".part")
try:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
except Exception as e:
    part.unlink(missing_ok=True)
    sys.exit(f"Preuzimanje nije uspjelo: {type(e).__name__}")
import zipfile
if part.stat().st_size < 1_000_000 or not zipfile.is_zipfile(part):
    part.unlink()
    sys.exit("Preuzeta datoteka nije ispravan zip; ne koristim je.")
part.replace(dest)
PYEOF
}

build_addresses() {
  download_zip
  "$PY" "$ROOT/pipeline/build_address_index.py" "$ZIP" --out "$DATA/addresses.sqlite"
}

skip_or_run "1/5 geohazardi (MPGI)" geo_done "$PY" "$ROOT/pipeline/fetch_geohazards.py" --out "$DATA/geohazards"
skip_or_run "2/5 seizmika (ESHM20)" file_done "$PY" "$ROOT/pipeline/fetch_seismic.py" --out "$DATA/seismic/eshm20_pga475.json"
skip_or_run "3/5 EFAS" efas_done "$PY" "$ROOT/pipeline/fetch_efas.py" --out "$DATA/efas"
skip_or_run "4/5 adrese (DGU)" sqlite_done build_addresses

echo "== 5/5 slojevi karte"
if [ -f "$ROOT/pipeline/build_map_layers.py" ]; then
  "$PY" "$ROOT/pipeline/build_map_layers.py" --data "$DATA"
else
  echo "   preskočeno: build_map_layers.py još nije na main"
fi

echo
echo "== Sažetak ($DATA)"
status=0
report() {  # report PATH
  if [ -s "$1" ]; then
    printf "  OK       %-45s %s\n" "${1#"$DATA"/}" "$(du -h "$1" | cut -f1)"
  else
    printf "  MISSING  %s\n" "${1#"$DATA"/}"; status=1
  fi
}
for n in $GEO_FILES; do report "$DATA/geohazards/$n.geojson"; done
report "$DATA/seismic/eshm20_pga475.json"
for n in rp10 rp100 rp500; do report "$DATA/efas/$n.tif"; done
report "$DATA/addresses.sqlite"
[ -d "$DATA/map" ] && echo "  (data/map postoji: $(ls "$DATA/map" | wc -l | tr -d ' ') datoteka)"
exit $status
