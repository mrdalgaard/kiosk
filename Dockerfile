FROM python:alpine

WORKDIR /app

# Create a non-root user and ensure directories exist
RUN adduser -D appuser && \
    mkdir -p /app/kiosk/static/images && \
    chown -R appuser:appuser /app

COPY kiosk/requirements.txt .

RUN apk add --no-cache curl su-exec

RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . .

# Copy entrypoint script and make sure it has execute permissions
COPY kiosk/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Ensure appuser owns the regular application files (excluding the dynamic volume)
RUN chown -R appuser:appuser /app

# We omit "USER appuser" here so the container initially boots as root.
# The entrypoint script drops permissions to "appuser" right before launching Gunicorn.

EXPOSE 5000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--worker-class", "gthread", "--threads", "4", "--timeout", "60", "--bind", "0.0.0.0:5000", "--logger-class", "kiosk.gunicorn_logger.IgnoreHealthCheckLogger", "--access-logfile", "-", "--access-logformat", "%({x-forwarded-for}i)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\"", "kiosk.run:app"]
