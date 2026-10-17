#!/usr/bin/env bash
# Build script for Render Deployment (University Panic Button System)
set -o errexit

echo "==> [1/4] Installing Python dependencies..."
pip install -r requirements.txt

echo "==> [2/4] Collecting static assets via WhiteNoise..."
python manage.py collectstatic --no-input

echo "==> [3/4] Applying database migrations (Supabase PostgreSQL / SQLite)..."
python manage.py migrate --no-input

echo "==> [4/4] Initializing UPBS institutional roles..."
python manage.py seed_upbs || echo "==> [WARN] seed_upbs encountered a non-fatal error; continuing build..."

echo "==> Build complete successfully!"

