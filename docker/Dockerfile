FROM lscr.io/linuxserver/baseimage-alpine:3.21

RUN apk add --no-cache python3 py3-pip && \
	pip install --no-cache-dir --break-system-packages flask gpxpy gunicorn

COPY docker/root/ /

COPY heart_rate_drift.py webapp.py /app/
COPY templates/ /app/templates/

EXPOSE 5000
