"""Reverse lineage view: pick source column, see all downstream MARTs."""

# ruff: noqa: E501 (inline HTML templates exceed the line limit).

from __future__ import annotations

from flask import Blueprint, g, render_template_string, request

from sas_lineage.web_ui.db import find_columns, query

lineage_bp = Blueprint("lineage", __name__)

_TEMPLATE = """
<!doctype html><html><head><title>Downstream: {{ col_id }}</title></head><body>
<h2>Downstream from: {{ col_id }}</h2>
{% if rows %}
<table border="1" cellpadding="4">
<tr><th>MART Column</th><th>Step</th><th>Job</th><th>Layer</th></tr>
{% for r in rows %}
<tr>
  <td><a href="/provenance?col_id={{ r.mart_column_id }}">{{ r.col_name }}</a></td>
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
  <label>Source column name: <input name="col" value="{{ name or '' }}" size="40" placeholder="cust_id or raw_table.cust_id"></label>
  <button type="submit">Trace downstream</button>
</form>
{% if name %}
{% if matches %}
<p>{{ matches | length }} matches for "{{ name }}":</p>
<ul>
{% for m in matches %}
  <li><a href="/lineage?col_id={{ m.id }}">{{ m.libref }}.{{ m.table_name }}.{{ m.name }}</a></li>
{% endfor %}
</ul>
{% else %}
<p>No column named "{{ name }}".</p>
{% endif %}
{% endif %}
<p><a href="/">Home</a></p>
</body></html>
"""


@lineage_bp.route("/lineage")
def lineage() -> str:
    col_id = request.args.get("col_id", "").strip()
    name = request.args.get("col", "").strip()
    if not col_id and name:
        matches = find_columns(g.db, name)
        if len(matches) == 1:
            col_id = matches[0]["id"]
        else:
            return render_template_string(_PICKER, name=name, matches=matches)
    if not col_id:
        return render_template_string(_PICKER, name=None, matches=None)

    rows = query(
        g.db,
        """
        SELECT lc.mart_column_id, lc.step_name, lc.job_id, c.layer,
               c.name AS col_name
        FROM lineage_chain lc
        JOIN columns c ON c.id = lc.mart_column_id
        WHERE lc.source_column_id = ?
        ORDER BY c.layer, lc.mart_column_id
        """,
        (col_id,),
    )
    return render_template_string(_TEMPLATE, rows=rows, col_id=col_id)
