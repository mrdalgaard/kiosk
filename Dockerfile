FROM python:alpine

WORKDIR /app

# Create a non-root user and ensure directories exist
RUN adduser -D appuser && \
    mkdir -p /app/kiosk/static/images && \
    chown -R appuser:appuser /app

COPY requirements.txt .

RUN apk add --no-cache curl

RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . .

# Ensure appuser owns everything
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 5000
CMD ["gunicorn", "--worker-class", "gthread", "--threads", "4", "--timeout", "60", "--bind", "0.0.0.0:5000", "--logger-class", "gunicorn_logger.IgnoreHealthCheckLogger", "--access-logfile", "-", "--access-logformat", "%({x-forwarded-for}i)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\"", "run:app"]
