#!/bin/sh
# The database, covers and secret key live in the named volume mounted at /data.
# The schema is created/upgraded automatically at start-up; existing data is never overwritten.
set -e
mkdir -p "${VINYLS_DATA_DIR:-/data}"
exec "$@"
