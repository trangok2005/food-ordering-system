#!/usr/bin/env sh
set -eu

python -m flask --app 'app:create_app()' db upgrade
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" 'app:create_app()'
