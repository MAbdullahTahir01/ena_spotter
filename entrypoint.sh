#!/bin/sh
set -e

python manage.py migrate --noinput

# Idempotent: safe to run on every start, on SQLite or Postgres alike --
# it just re-upserts the same rows by pk, so the app always has station
# data even on a container's first (empty) boot.
python manage.py loaddata fuel_stations

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
