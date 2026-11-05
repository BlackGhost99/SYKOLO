#!/usr/bin/env bash
# YEM: restore only to a brand-new LOCAL PostgreSQL database named yem_drill_*.
set -Eeuo pipefail
umask 077
for name in YEM_BACKUP_DATABASE_URL YEM_DRILL_DATABASE_URL YEM_BACKUP_PASSPHRASE YEM_RESTORE_ARCHIVE; do
  if [[ -z "$(printenv "$name" || true)" ]]; then echo "Variable manquante : $name" >&2; exit 2; fi
done
for cmd in pg_restore gpg psql sha256sum python3; do
  command -v "$cmd" >/dev/null || { echo "Outil absent : $cmd" >&2; exit 2; }
done
test -r "$YEM_RESTORE_ARCHIVE" && test -r "$YEM_RESTORE_ARCHIVE.sha256" ||
  { echo "Archive chiffrée et fichier .sha256 obligatoires." >&2; exit 2; }
python3 - <<'PY'
import os, sys
from urllib.parse import urlsplit
src = urlsplit(os.environ["YEM_BACKUP_DATABASE_URL"])
dest = urlsplit(os.environ["YEM_DRILL_DATABASE_URL"])
db = dest.path.strip("/")
if dest.scheme not in ("postgres", "postgresql") or dest.hostname not in ("localhost", "127.0.0.1", "::1"):
    sys.exit("Refus : restauration autorisée uniquement sur un serveur local.")
if not db.startswith("yem_drill_") or not db.replace("_", "").isalnum():
    sys.exit("Refus : nom de base cible obligatoire yem_drill_*.")
if (src.hostname, src.port or 5432, src.path) == (dest.hostname, dest.port or 5432, dest.path):
    sys.exit("Refus : base de restauration identique à la source.")
PY
(cd "$(dirname "$YEM_RESTORE_ARCHIVE")" &&
  sha256sum -c "$(basename "$YEM_RESTORE_ARCHIVE").sha256" >/dev/null)
source "$(dirname "$0")/yem_pg_env.sh"
yem_set_pg_env "$YEM_DRILL_DATABASE_URL"
COUNT="$(psql -X -A -t -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")"
if [[ "$COUNT" != "0" ]]; then
  echo "Refus : la base de restauration doit être vide." >&2; exit 2
fi
gpg --batch --yes --no-tty --pinentry-mode loopback --passphrase-fd 3 \
    --decrypt "$YEM_RESTORE_ARCHIVE" 3<<< "$YEM_BACKUP_PASSPHRASE" |
  pg_restore --exit-on-error --no-owner --no-acl --dbname="$PGDATABASE"
for table in accounts_user institutions_school institutions_schoolmember \
             institutions_student institutions_enrollment institutions_schoolreport \
             institutions_feepayment institutions_cashclosing; do
  SQL="SELECT count(*) FROM public.$table;"
  yem_set_pg_env "$YEM_BACKUP_DATABASE_URL"
  ORIGINAL="$(psql -X -A -t -v ON_ERROR_STOP=1 -c "$SQL")"
  yem_set_pg_env "$YEM_DRILL_DATABASE_URL"
  RESTORED="$(psql -X -A -t -v ON_ERROR_STOP=1 -c "$SQL")"
  if [[ "$ORIGINAL" != "$RESTORED" ]]; then
    echo "ECHEC pour $table : $ORIGINAL / $RESTORED lignes" >&2; exit 1
  fi
  printf 'OK: %s (%s lignes)\n' "$table" "$RESTORED"
done
printf 'RESTAURATION : PASS — PostgreSQL local isolé uniquement.\n'
