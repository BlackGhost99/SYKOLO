#!/usr/bin/env bash
# Production scheduler entrypoint. Two verified copies; no automatic deletion.
set -Eeuo pipefail
umask 077
for name in YEM_BACKUP_DIR YEM_BACKUP_EXTERNAL_DIR; do
  [[ -n "${!name:-}" ]] || { echo "Variable manquante : $name" >&2; exit 2; }
done
for cmd in flock mountpoint sha256sum mktemp cp mv cmp; do
  command -v "$cmd" >/dev/null || { echo "Outil absent : $cmd" >&2; exit 2; }
done
ROOT="$(cd -- "$(dirname "$0")/.." && pwd -P)"
mkdir -p -m 0700 -- "$YEM_BACKUP_DIR"
LOCAL="$(cd -- "$YEM_BACKUP_DIR" && pwd -P)"
EXTERNAL="$(cd -- "$YEM_BACKUP_EXTERNAL_DIR" && pwd -P)"
for dest in "$LOCAL" "$EXTERNAL"; do
  case "$dest" in /|"$ROOT"|"$ROOT"/*) echo "Refus : stockage dans le dépôt ou à la racine." >&2; exit 2;; esac
done
case "$EXTERNAL/" in "$LOCAL/"*) echo "Refus : destinations imbriquées." >&2; exit 2;; esac
case "$LOCAL/" in "$EXTERNAL/"*) echo "Refus : destinations imbriquées." >&2; exit 2;; esac
# A missing mount must not silently write another copy onto the local filesystem.
mountpoint -q -- "$EXTERNAL" || { echo "Refus : stockage externe non monté." >&2; exit 2; }
chmod 700 -- "$LOCAL"
exec 9>"$LOCAL/.yem-backup.lock"
flock -n 9 || { echo "Refus : sauvegarde déjà en cours." >&2; exit 1; }
RUN="$(mktemp -d "$LOCAL/run-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
cd -- "$ROOT"
YEM_BACKUP_DIR="$RUN" bash scripts/yem_backup.sh
shopt -s nullglob
archives=("$RUN"/*.pgdump.gpg)
[[ "${#archives[@]}" == 1 ]] || { echo "Archive unique attendue." >&2; exit 1; }
ARCHIVE="${archives[0]##*/}"
(cd -- "$RUN" && sha256sum -c -- "$ARCHIVE.sha256" >/dev/null)
mountpoint -q -- "$EXTERNAL" || { echo "Stockage externe indisponible ; copie locale conservée." >&2; exit 1; }
STAGE="$(mktemp -d "$EXTERNAL/.partial-XXXXXXXX")"
cp -- "$RUN/$ARCHIVE" "$RUN/$ARCHIVE.sha256" "$STAGE/"
chmod 600 -- "$STAGE/$ARCHIVE" "$STAGE/$ARCHIVE.sha256"
(cd -- "$STAGE" && sha256sum -c -- "$ARCHIVE.sha256" >/dev/null)
cmp -s -- "$RUN/$ARCHIVE" "$STAGE/$ARCHIVE"
mountpoint -q -- "$EXTERNAL" || { echo "Stockage externe perdu ; copie locale conservée." >&2; exit 1; }
FINAL="$EXTERNAL/${RUN##*/}"
[[ ! -e "$FINAL" ]] || { echo "Destination déjà présente." >&2; exit 1; }
mv -T -- "$STAGE" "$FINAL"
(cd -- "$FINAL" && sha256sum -c -- "$ARCHIVE.sha256" >/dev/null)
printf 'YEM BACKUP PASS — deux copies chiffrées vérifiées ; restauration réelle à tester séparément.\n'
