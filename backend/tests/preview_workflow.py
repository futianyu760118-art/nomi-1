"""Isolated browser QA with simulated providers; never uses the workspace database."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from werkzeug.middleware.shared_data import SharedDataMiddleware
from test_integrations import IntegrationWorkflowTests


if __name__ == "__main__":
    fixture = IntegrationWorkflowTests()
    fixture.setUp()
    try:
        fixture.import_project()
        dist = Path(__file__).resolve().parents[2] / "dist"

        static_app = SharedDataMiddleware(fixture.app.wsgi_app, {
            "/index.html": str(dist / "index.html"),
            "/assets": str(dist / "assets"),
            "/brand": str(dist / "brand"),
        }, cache=False)

        def preview(environ, start_response):
            if environ["PATH_INFO"] == "/":
                environ["PATH_INFO"] = "/index.html"
            return static_app(environ, start_response)

        fixture.app.wsgi_app = preview
        fixture.app.run(host="127.0.0.1", port=5101, use_reloader=False)
    finally:
        fixture.tearDown()
