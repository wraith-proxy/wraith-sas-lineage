"""
Flask web UI for lineage exploration: sparse by design.

Six views backed by flat SQL queries. No heavy JS framework.
Markdown and mermaid diagrams rendered server-side.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, g, render_template_string

from sas_lineage.web_ui.db import get_connection
from sas_lineage.web_ui.views.flags import flags_bp
from sas_lineage.web_ui.views.lineage import lineage_bp
from sas_lineage.web_ui.views.provenance import provenance_bp

_INDEX = """
<!doctype html><html><head><title>SAS Lineage Explorer</title></head><body>
<h1>SAS Lineage Explorer</h1>
<p>Trace column provenance across your SAS estate.</p>
<ul>
  <li><a href="/provenance">Column Provenance</a> &ndash; upstream chain</li>
  <li><a href="/lineage">Reverse Lineage</a> &ndash; downstream to MARTs</li>
  <li><a href="/flags">Flag Dashboard</a> &ndash; unresolved references</li>
</ul>
</body></html>
"""


def create_app(db_path: Path | None = None) -> Flask:
    """Create the Flask app. DB_PATH env var or arg sets the database."""
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or Path(
        os.environ.get("DB_PATH", "lineage.db")
    )

    @app.before_request
    def open_db() -> None:
        g.db = get_connection(app.config["DB_PATH"])

    @app.teardown_appcontext
    def close_db(exc: BaseException | None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.route("/")
    def index() -> str:
        return render_template_string(_INDEX)

    app.register_blueprint(provenance_bp)
    app.register_blueprint(lineage_bp)
    app.register_blueprint(flags_bp)

    return app


def main() -> None:
    port = int(os.environ.get("FLASK_PORT", 5000))
    create_app().run(port=port, debug=True)
