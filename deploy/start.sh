#!/bin/sh
set -eu
cd /app/backend
python manage.py migrate --noinput
python manage.py bootstrap_platform_admin
worker_pid=""
web_pid=""
shutdown() {
    [ -z "$worker_pid" ] || kill -TERM "$worker_pid" 2>/dev/null || true
    [ -z "$web_pid" ] || kill -TERM "$web_pid" 2>/dev/null || true
}
trap shutdown TERM INT EXIT
if [ "${YEM_SINGPAY_RECONCILIATION_ENABLED:-false}" = "true" ]; then
    python manage.py yem_singpay_worker &
    worker_pid=$!
fi
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 2 --timeout 60 --access-logfile - --error-logfile - &
web_pid=$!
set +e
wait "$web_pid"
status=$?
shutdown
wait 2>/dev/null
exit "$status"
