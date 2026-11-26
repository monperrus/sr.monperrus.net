#!/bin/bash
# Serve the app on 127.0.0.1:8000; search indexes are read from $SEARCH_DB_DIR (default db/).
cd "$(dirname "$0")"
source bin/activate
exec gunicorn --bind 127.0.0.1:8000 app:app
