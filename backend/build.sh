#!/usr/bin/env bash
# Render runs this on every deploy (see render.yaml).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create the admin account once, from the DJANGO_SUPERUSER_* settings in Render.
# On later deploys it already exists, so the error is ignored.
if [ -n "${DJANGO_SUPERUSER_PHONE:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --no-input || echo "Admin account already exists, skipping."
fi
