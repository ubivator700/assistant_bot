#!/bin/sh
set -e

echo "==> Running Alembic migrations..."
python3 -m alembic upgrade head

echo "==> Starting bot..."
exec python3 main.py
