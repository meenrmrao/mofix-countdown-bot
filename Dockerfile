FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/backups

# Railway injects the port to bind to as the $PORT environment variable at
# CONTAINER RUNTIME (not at build time), and a different value on every
# deploy. This MUST be read with a shell, so we use the shell ("string")
# form of CMD below rather than the JSON/exec-array form.
#
# Using the exec form, e.g. CMD ["gunicorn", "-b", "0.0.0.0:$PORT", ...],
# never invokes /bin/sh, so "$PORT" is passed to gunicorn literally as the
# four-character string "$PORT" instead of being substituted with a real
# number -> gunicorn fails with: "'$PORT' is not a valid port number".
#
# The shell form below runs via `/bin/sh -c "..."`, which DOES expand
# environment variables, and ${PORT:-5000} falls back to 5000 for local
# `docker run` testing where PORT isn't set.
#
# This is the WEB service's default command. The bot service (run as a
# separate Railway service from the same image) should override the start
# command to: python run_bot.py
CMD gunicorn -w 2 --timeout 120 --log-file - -b 0.0.0.0:${PORT:-5000} run_web:app
