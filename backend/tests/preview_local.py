"""Browser QA harness for the projects hub and requirement board.

Boots the real app with a throwaway SQLite database (demo seed included) and
serves the built frontend from ../dist. Never touches backend/data or real
external services; local projects created here live only in the temp database.
"""
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from werkzeug.middleware.shared_data import SharedDataMiddleware

from pmo import create_app

if __name__ == "__main__":
    temp = tempfile.TemporaryDirectory()
    url = "sqlite:///" + temp.name.replace("\\", "/") + "/preview.db"
    app = create_app(dict(TESTING=True, DATABASE_URL=url))
    dist = Path(__file__).resolve().parents[2] / "dist"

    static_app = SharedDataMiddleware(app.wsgi_app, {
        "/index.html": str(dist / "index.html"),
        "/assets": str(dist / "assets"),
        "/brand": str(dist / "brand"),
    }, cache=False)

    def preview(environ, start_response):
        if environ["PATH_INFO"] == "/":
            environ["PATH_INFO"] = "/index.html"
        return static_app(environ, start_response)

    app.wsgi_app = preview
    print("Preview on http://127.0.0.1:5102 (temp db: {})".format(url), flush=True)
    try:
        app.run(host="127.0.0.1", port=5102, use_reloader=False)
    finally:
        app.extensions["engine"].dispose()
        temp.cleanup()
