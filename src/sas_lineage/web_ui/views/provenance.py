"""Column provenance view: pick a MART column, see full upstream chain."""

# ruff: noqa: E501 (inline HTML/mermaid templates exceed the line limit).

from __future__ import annotations

from flask import Blueprint, g, render_template_string, request

from sas_lineage.web_ui.db import find_columns, query

provenance_bp = Blueprint("provenance", __name__)

_TEMPLATE = """
<!doctype html><html><head><title>Provenance: {{ col_name }}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head><body>
<h2>Provenance: {{ col_name }}</h2>
<p>
{% if hide_intermediates %}
<a href="/provenance?col_id={{ col_id }}">Show intermediate (work.W*) hops</a>
{% else %}
<a href="/provenance?col_id={{ col_id }}&hide_intermediates=1">Hide intermediate (work.W*) hops</a>
{% endif %}
</p>
{% if chain %}
<div class="mermaid">
flowchart LR
{% for hop in chain %}
  {{ hop.source_column_id | replace('-','_') }}["{{ hop.source_col_name }}<br/>{{ hop.step_name }} ({{ hop.step_type }})"] --> {{ hop.mart_column_id | replace('-','_') }}["{{ col_name }}"]
{% endfor %}
</div>
<table border="1" cellpadding="4">
<tr><th>#</th><th>Source Column</th><th>Step</th><th>Type</th><th>Logic</th><th>Flag</th></tr>
{% for hop in chain %}
<tr>
  <td>{{ hop.chain_order }}</td>
  <td>{{ hop.source_col_name }}</td>
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
  <label>Column name: <input name="col" value="{{ name or '' }}" size="40" placeholder="cust_id or mart_table.cust_id"></label>
  <button type="submit">Trace</button>
</form>
{% if name %}
{% if matches %}
<p>{{ matches | length }} matches for "{{ name }}":</p>
<ul>
{% for m in matches %}
  <li><a href="/provenance?col_id={{ m.id }}">{{ m.libref }}.{{ m.table_name }}.{{ m.name }}</a></li>
{% endfor %}
</ul>
{% else %}
<p>No column named "{{ name }}".</p>
{% endif %}
{% endif %}
<p><a href="/">Home</a></p>
</body></html>
"""


@provenance_bp.route("/provenance")
def provenance() -> str:
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

    hide = request.args.get("hide_intermediates", "").strip() == "1"
    sql = """
        SELECT lc.*, c.name AS col_name, sc.name AS source_col_name
        FROM lineage_chain lc
        JOIN columns c ON c.id = lc.mart_column_id
        JOIN columns sc ON sc.id = lc.source_column_id
        JOIN tables st ON st.id = sc.table_id
        WHERE lc.mart_column_id = ?
        """
    if hide:
        sql += " AND st.is_intermediate = 0"
    sql += " ORDER BY lc.chain_order"
    chain = query(g.db, sql, (col_id,))
    col_name = chain[0]["col_name"] if chain else col_id
    return render_template_string(
        _TEMPLATE,
        chain=chain,
        col_name=col_name,
        col_id=col_id,
        hide_intermediates=hide,
    )
