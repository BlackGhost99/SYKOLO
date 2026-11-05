#!/usr/bin/env bash
# Convert trusted PostgreSQL URL to libpq env (no passwords in CLI args).
yem_set_pg_env() {
  local uri="$1"
  local -a parts=()
  mapfile -d '' -t parts < <(YEM_PARSE_DATABASE_URL="$uri" python3 - <<'PY'
import os, sys
from urllib.parse import parse_qs, unquote, urlsplit
url = urlsplit(os.environ["YEM_PARSE_DATABASE_URL"])
if url.scheme not in ("postgres", "postgresql") or not url.hostname or not url.path.strip("/"):
    sys.exit(2)
values = [url.hostname, str(url.port or 5432),
          unquote(url.username or ""), unquote(url.password or ""),
          unquote(url.path.lstrip("/")),
          parse_qs(url.query).get("sslmode", ["prefer"])[0]]
sys.stdout.buffer.write(chr(0).join(values).encode() + bytes([0]))
PY
  )
  if [[ "${#parts[@]}" -ne 6 ]]; then echo "URL PostgreSQL invalide." >&2; return 2; fi
  export PGHOST="${parts[0]}" PGPORT="${parts[1]}" PGUSER="${parts[2]}"
  export PGPASSWORD="${parts[3]}" PGDATABASE="${parts[4]}" PGSSLMODE="${parts[5]}"
}
