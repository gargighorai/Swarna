#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -o errexit

# Run migrations
python -m flask db upgrade

# Start the Gunicorn server with 4 workers and a timeout of 120 seconds.
# The `ghorai_app:app` part points to your app instance.
exec gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 app:app