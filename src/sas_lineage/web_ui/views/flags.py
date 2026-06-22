"""Flag dashboard: all flagged items grouped by reason for human review."""

from __future__ import annotations

from flask import Blueprint, g, render_template_string

from sas_lineage.web_ui.db import query

flags_bp = Blueprint("flags", __name__)

_TEMPLATE = """
<!doctype html><html><head><title>Flag Dashboard</title></head><body>
<h2>Flag Dashboard ({{ total }} items)</h2>
{% for reason, items in grouped.items() %}
<h3>{{ reason }} ({{ items | length }})</h3>
<table border="1" cellpadding="4">
<tr><th>Ref</th><th>Context</th><th>Snippet</th></tr>
{% for f in items %}
<tr>
  <td>{{ f.ref_id }}</td>
  <td>{{ f.context }}</td>
  <td><pre>{{ f.snippet[:100] }}</pre></td>
</tr>
{% endfor %}
</table>
{% endfor %}
<p><a href="/">Home</a></p>
</body></html>
"""


@flags_bp.route("/flags")
def flags() -> str:
    rows = query(g.db, "SELECT * FROM flags ORDER BY reason, ref_id")
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["reason"], []).append(row)
    return render_template_string(_TEMPLATE, grouped=grouped, total=len(rows))
