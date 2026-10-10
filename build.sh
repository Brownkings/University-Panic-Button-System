#!/usr/bin/env bash
# Build script for Render Deployment (University Panic Button System)
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Collecting static assets via WhiteNoise..."
python manage.py collectstatic --no-input

echo "==> Applying database migrations (Supabase PostgreSQL / SQLite)..."
python manage.py migrate

echo "==> Seeding initial roles, admin, security, and demo accounts..."
python manage.py seed_upbs

echo "==> Build complete successfully!"
