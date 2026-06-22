"""Reverse lineage view: pick source column, see all downstream MARTs."""

# ruff: noqa: E501 (inline HTML templates exceed the line limit).

from __future__ import annotations

from flask import Blueprint, g, render_template_string, request

from sas_lineage.web_ui.db import query

lineage_bp = Blueprint("lineage", __name__)

_TEMPLATE = """
<!doctype html><html><head><title>Downstream: {{ col_id }}</title></head><body>
<h2>Downstream from: {{ col_id }}</h2>
{% if rows %}
<table border="1" cellpadding="4">
<tr><th>MART Column</th><th>Step</th><th>Job</th><th>Layer</th></tr>
{% for r in rows %}
<tr>
  <td><a href="/provenance?col_id={{ r.mart_column_id }}">{{ r.mart_column_id }}</a></td>
  <td>{{ r.step_name }}</td>
  <td>{{ r.job_id }}</td>
  <td>{{ r.layer or '' }}</td>
</tr>
{% endfor %}
</table>
{% else %}<p>No downstream found.</p>{% endif %}
<p><a href="/">Home</a></p>
</body></html>
"""

_PICKER = """
<!doctype html><html><head><title>Reverse Lineage</title></head><body>
<h2>Reverse Lineage</h2>
<form method="get" action="/lineage">
  <label>Source Column ID: <input name="col_id" size="40"></label>
  <button type="submit">Trace downstream</button>
</form>
<p><a href="/">Home</a></p>
</body></html>
"""


@lineage_bp.route("/lineage")
def lineage() -> str:
    col_id = request.args.get("col_id", "").strip()
    if not col_id:
        return render_template_string(_PICKER)

    rows = query(
        g.db,
        """
        SELECT lc.mart_column_id, lc.step_name, lc.job_id, c.layer
        FROM lineage_chain lc
        JOIN columns c ON c.id = lc.mart_column_id
        WHERE lc.source_column_id = ?
        ORDER BY c.layer, lc.mart_column_id
        """,
        (col_id,),
    )
    return render_template_string(_TEMPLATE, rows=rows, col_id=col_id)
