#!/bin/sh
set -eu
cd /app/backend
python manage.py migrate --noinput
python manage.py bootstrap_platform_admin
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 2 --timeout 60 --access-logfile - --error-logfile -
