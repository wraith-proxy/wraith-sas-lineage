"""Column provenance view: pick a MART column, see full upstream chain."""

# ruff: noqa: E501 (inline HTML/mermaid templates exceed the line limit).

from __future__ import annotations

from flask import Blueprint, g, render_template_string, request

from sas_lineage.web_ui.db import query

provenance_bp = Blueprint("provenance", __name__)

_TEMPLATE = """
<!doctype html><html><head><title>Provenance: {{ col_name }}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head><body>
<h2>Provenance: {{ col_name }}</h2>
{% if chain %}
<div class="mermaid">
flowchart LR
{% for hop in chain %}
  {{ hop.source_column_id | replace('-','_') }}["{{ hop.step_name }}<br/>{{ hop.step_type }}"] --> {{ hop.mart_column_id | replace('-','_') }}["{{ col_name }}"]
{% endfor %}
</div>
<table border="1" cellpadding="4">
<tr><th>#</th><th>Source Column</th><th>Step</th><th>Type</th><th>Logic</th><th>Flag</th></tr>
{% for hop in chain %}
<tr>
  <td>{{ hop.chain_order }}</td>
  <td>{{ hop.source_column_id }}</td>
  <td>{{ hop.step_name }}</td>
  <td>{{ hop.step_type }}</td>
  <td><pre>{{ hop.transformation_logic }}</pre></td>
  <td>{{ hop.unmappable_reason or '' }}</td>
</tr>
{% endfor %}
</table>
{% else %}
<p>No lineage found for this column.</p>
{% endif %}
<p><a href="/">Home</a></p>
</body></html>
"""

_PICKER = """
<!doctype html><html><head><title>Pick a MART column</title></head><body>
<h2>Column Provenance</h2>
<form method="get" action="/provenance">
  <label>Column ID: <input name="col_id" value="{{ col_id or '' }}" size="40"></label>
  <button type="submit">Trace</button>
</form>
<p><a href="/">Home</a></p>
</body></html>
"""


@provenance_bp.route("/provenance")
def provenance() -> str:
    col_id = request.args.get("col_id", "").strip()
    if not col_id:
        return render_template_string(_PICKER, col_id=col_id)

    chain = query(
        g.db,
        """
        SELECT lc.*, c.name AS col_name
        FROM lineage_chain lc
        JOIN columns c ON c.id = lc.mart_column_id
        WHERE lc.mart_column_id = ?
        ORDER BY lc.chain_order
        """,
        (col_id,),
    )
    col_name = chain[0]["col_name"] if chain else col_id
    return render_template_string(_TEMPLATE, chain=chain, col_name=col_name)
