#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Seed company settings, Resend API key, and default email templates
python manage.py setup_mailer

python seed_data.py
