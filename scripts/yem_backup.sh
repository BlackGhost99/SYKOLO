#!/usr/bin/env bash
# YEM: encrypted non-destructive PostgreSQL logical backup. No secret is logged.
set -Eeuo pipefail
umask 077
for name in YEM_BACKUP_DATABASE_URL YEM_BACKUP_PASSPHRASE YEM_BACKUP_DIR; do
  if [[ -z "$(printenv "$name" || true)" ]]; then echo "Variable manquante : $name" >&2; exit 2; fi
done
if [[ "$(printf %s "$YEM_BACKUP_PASSPHRASE" | wc -c)" -lt 24 ]]; then
  echo "Refus : phrase secrète trop courte (24 caractères minimum)." >&2; exit 2
fi
for cmd in pg_dump pg_restore gpg sha256sum mktemp python3; do
  command -v "$cmd" >/dev/null || { echo "Outil absent : $cmd" >&2; exit 2; }
done
case "$YEM_BACKUP_DATABASE_URL" in
  postgresql://*|postgres://*) ;;
  *) echo "Refus : URL PostgreSQL invalide." >&2; exit 2 ;;
esac
mkdir -p -m 0700 -- "$YEM_BACKUP_DIR"
chmod 700 -- "$YEM_BACKUP_DIR"
OUT="$(cd -- "$YEM_BACKUP_DIR" && pwd -P)"
case "$OUT" in
  "$(pwd -P)"|"$(pwd -P)"/*)
    echo "Refus : ne pas stocker un dump d'enfants dans le dépôt de code." >&2; exit 2 ;;
esac
TMP="$(mktemp "$OUT/yem-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX.pgdump.gpg.partial")"
FINAL="$(echo "$TMP" | sed 's/\.partial$//')"
cleanup() { rm -f -- "$TMP"; }
trap cleanup EXIT
source "$(dirname "$0")/yem_pg_env.sh"
yem_set_pg_env "$YEM_BACKUP_DATABASE_URL"
pg_dump --no-owner --no-acl --format=custom |
  gpg --batch --yes --no-tty --pinentry-mode loopback --passphrase-fd 3 \
      --symmetric --cipher-algo AES256 --compress-algo none --output "$TMP" \
      3<<< "$YEM_BACKUP_PASSPHRASE"
test -s "$TMP"
gpg --batch --yes --no-tty --pinentry-mode loopback --passphrase-fd 3 \
    --decrypt "$TMP" 3<<< "$YEM_BACKUP_PASSPHRASE" |
    pg_restore --list >/dev/null
mv -- "$TMP" "$FINAL"
(cd "$OUT" && sha256sum "$(basename "$FINAL")" > "$(basename "$FINAL").sha256")
chmod 600 -- "$FINAL" "$FINAL.sha256"
printf 'Sauvegarde chiffrée et archive testée : %s\n' "$FINAL"
printf 'Somme SHA-256 : %s.sha256\n' "$FINAL"
printf 'COPIER en stockage externe sécurisé. Ne jamais envoyer sur GitHub ni dans un chat.\n'
