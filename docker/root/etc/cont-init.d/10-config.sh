#!/usr/bin/with-contenv sh
# Run gunicorn as the abc user (PUID/PGID remapped by LSIO base at startup)
chown -R abc:abc /app
