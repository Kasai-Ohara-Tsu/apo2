#!/bin/sh
set -e

echo "Apply database migrations"
python manage.py migrate --noinput

echo "Create superuser if not exists"
python manage.py create_admin

echo "Start gunicorn"
exec gunicorn reception_system.wsgi:application --bind 0.0.0.0:$PORT
