"""
Entry point: run the MOFIX web dashboard + public site.

Local dev:
    python run_web.py

Production (Railway/Render/Docker), via Gunicorn:
    gunicorn -w 2 -b 0.0.0.0:$PORT run_web:app

Gunicorn imports this file as a module and looks up the "app" attribute
below (the "run_web:app" target) — it never executes the __main__ block,
so the port logic there only matters for local development.
"""
import os

from web.app import create_app
from common.config import config

# Flask application object, exposed at module level so Gunicorn (and any
# other WSGI server) can import it directly as "run_web:app".
app = create_app()

if __name__ == "__main__":
    # Railway (and most cloud platforms) provide the port to bind to via
    # the PORT environment variable at container runtime. Always resolve
    # it to an int here — never pass the raw "$PORT" string to anything
    # that opens a socket, and always fall back to 5000 for local runs.
    port = int(os.environ.get("PORT", 5000))
    app.run(host=config.WEB_HOST, port=port, debug=config.DEBUG)
