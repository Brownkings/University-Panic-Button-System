#!/usr/bin/env bash
# Build script for Render Deployment (University Panic Button System)
set -o errexit

echo "==> [1/4] Installing Python dependencies..."
pip install -r requirements.txt

echo "==> [2/4] Collecting static assets via WhiteNoise..."
python manage.py collectstatic --no-input

echo "==> [3/4] Applying database migrations (Supabase PostgreSQL / SQLite)..."
MAX_RETRIES=5
RETRY_DELAY=4
MIGRATE_SUCCESS=false

for i in $(seq 1 $MAX_RETRIES); do
    echo "Attempt $i of $MAX_RETRIES: Running database migrations..."
    if python manage.py migrate --no-input; then
        MIGRATE_SUCCESS=true
        echo "✓ Database migrations applied successfully."
        break
    else
        echo "==> [WARN] Migration attempt $i failed."
        if [ "$i" -lt "$MAX_RETRIES" ]; then
            echo "Waiting ${RETRY_DELAY}s for connection pool slots to clear before retry..."
            sleep $RETRY_DELAY
        fi
    fi
done

if [ "$MIGRATE_SUCCESS" != "true" ]; then
    echo "==> [ERROR] Database migrations failed after $MAX_RETRIES attempts."
    exit 1
fi

echo "==> [4/4] Initializing UPBS institutional roles..."
python manage.py seed_upbs || echo "==> [WARN] seed_upbs encountered a non-fatal error; continuing build..."

echo "==> Build complete successfully!"

