#!/bin/sh
set -e

echo "Apply database migrations…"
python manage.py migrate --noinput

echo "Collect static files…"
python manage.py collectstatic --noinput

echo "Starting Gunicorn…"
exec gunicorn veilgram.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class sync \
    --log-level info
