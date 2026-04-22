#!/bin/bash
set -e

export PYTHONPATH=/app

echo "Running database migrations..."
alembic upgrade head

echo "Starting Cortex API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
