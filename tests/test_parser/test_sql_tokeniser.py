"""
Unit tests for sas_lineage.parser.sql_tokeniser.

Covers:
  scan_tokens  — string-literal skipping, paren depth tracking,
                 comma classification, &macro as single ident,
                 LIB.TBL as single ident
  extract_sql_tables — TableRef tuples for all Batch-B F2/F3/F5/F6 cases
"""

from sas_lineage.parser.sql_tokeniser import (
    extract_sql_tables,
    scan_tokens,
)

# ---------------------------------------------------------------------------
# scan_tokens — string literal skipping
# ---------------------------------------------------------------------------


class TestScanTokensStringLiterals:
    def test_single_quoted_literal_skipped(self):
        tokens = scan_tokens("'hello, world'")
        assert tokens == [], "nothing inside a quoted literal should emit"

    def test_double_quoted_literal_skipped(self):
        tokens = scan_tokens('"foo,bar"')
        assert tokens == []

    def test_comma_inside_literal_no_comma_token(self):
        """The comma inside 'a,b' must not produce a comma token."""
        tokens = scan_tokens("'a,b'")
        kinds = [t.kind for t in tokens]
        assert "comma" not in kinds

    def test_comma_outside_literal_emitted(self):
        # "x, 'a,b', y" has TWO outer commas: one after x and one after the
        # closing quote. The literal is skipped but both surrounding commas
        # remain. Asserting >=1 confirms the literal's inner comma is gone.
        tokens = scan_tokens("x, 'a,b', y")
        comma_tokens = [t for t in tokens if t.kind == "comma"]
        assert len(comma_tokens) == 2, (
            "both outer commas should appear; the one inside 'a,b' is skipped"
        )

    def test_literal_between_idents_leaves_both_idents(self):
        tokens = scan_tokens("A 'ignored' B")
        idents = [t.value for t in tokens if t.kind == "ident"]
        assert idents == ["a", "b"]

    def test_empty_string_literal(self):
        tokens = scan_tokens("''")
        assert tokens == []

    def test_in_list_commas_not_emitted(self):
        """CASE WHEN k IN ('A','B','C') THEN ... — no commas from the list."""
        expr = "CASE WHEN k IN ('A','B','C') THEN 1 END as flag, other"
        comma_depth0 = [
            t for t in scan_tokens(expr) if t.kind == "comma" and t.depth == 0
        ]
        assert len(comma_depth0) == 1, (
            "only the top-level comma between 'flag' and 'other' should appear"
        )

    def test_bare_ampersand_no_word_skipped(self):
        """'&' not followed by a word character should not emit a token."""
        tokens = scan_tokens("& + 1")
        ident_vals = [t.value for t in tokens if t.kind == "ident"]
        assert "&" not in ident_vals
        assert "+" not in ident_vals


# ---------------------------------------------------------------------------
# scan_tokens — paren depth tracking
# ---------------------------------------------------------------------------


class TestScanTokensParenDepth:
    def test_open_paren_increases_depth(self):
        tokens = scan_tokens("(")
        assert tokens[0].kind == "open"
        assert tokens[0].depth == 1

    def test_close_paren_decreases_depth(self):
        tokens = scan_tokens("()")
        close = tokens[1]
        assert close.kind == "close"
        assert close.depth == 0

    def test_tokens_inside_parens_have_positive_depth(self):
        tokens = scan_tokens("(a, b)")
        inner = [t for t in tokens if t.kind == "ident"]
        assert all(t.depth == 1 for t in inner)

    def test_depth_returns_to_zero_after_close(self):
        tokens = scan_tokens("(a) b")
        b_token = [t for t in tokens if t.value == "b"][0]
        assert b_token.depth == 0

    def test_nested_parens_track_depth(self):
        tokens = scan_tokens("((x))")
        open1, open2, ident, close1, close2 = tokens
        assert open1.depth == 1
        assert open2.depth == 2
        assert ident.depth == 2
        assert close1.depth == 1
        assert close2.depth == 0

    def test_comma_at_depth_zero(self):
        tokens = scan_tokens("a, b")
        comma = [t for t in tokens if t.kind == "comma"][0]
        assert comma.depth == 0

    def test_comma_at_depth_one(self):
        tokens = scan_tokens("(a, b)")
        comma = [t for t in tokens if t.kind == "comma"][0]
        assert comma.depth == 1

    def test_semi_emitted_at_depth_zero(self):
        tokens = scan_tokens("a;")
        semi = tokens[-1]
        assert semi.kind == "semi"
        assert semi.depth == 0


# ---------------------------------------------------------------------------
# scan_tokens — &macro and dotted LIB.TBL as single idents
# ---------------------------------------------------------------------------


class TestScanTokensIdentForms:
    def test_macro_ref_is_single_ident(self):
        tokens = scan_tokens("&macro_name")
        assert len(tokens) == 1
        assert tokens[0].kind == "ident"
        assert tokens[0].value == "&macro_name"

    def test_macro_ref_value_keeps_ampersand(self):
        tokens = scan_tokens("&SRC")
        assert tokens[0].value == "&src"

    def test_dotted_ref_is_single_ident(self):
        tokens = scan_tokens("LIB.TBL")
        assert len(tokens) == 1
        assert tokens[0].kind == "ident"
        assert tokens[0].value == "lib.tbl"

    def test_dotted_ref_in_context(self):
        tokens = scan_tokens("select * from RISKODS.SOURCE")
        ident_vals = [t.value for t in tokens if t.kind == "ident"]
        assert "riskods.source" in ident_vals
        assert "riskods" not in ident_vals
        assert "source" not in ident_vals

    def test_macro_ref_in_from_clause(self):
        tokens = scan_tokens("from &SRC")
        ident_vals = [t.value for t in tokens if t.kind == "ident"]
        assert "&src" in ident_vals


# ---------------------------------------------------------------------------
# extract_sql_tables — basic FROM parsing
# ---------------------------------------------------------------------------


class TestExtractSqlTablesBasic:
    def test_simple_from(self):
        refs = extract_sql_tables("select * from MYLIB.MYTBL;")
        assert len(refs) == 1
        libref, table, alias = refs[0]
        assert libref == "MYLIB"
        assert table == "MYTBL"
        assert alias is None

    def test_unqualified_table(self):
        refs = extract_sql_tables("select * from WORK_TBL;")
        assert refs[0] == (None, "WORK_TBL", None)

    def test_table_with_alias(self):
        refs = extract_sql_tables("select * from A a;")
        assert refs[0][2] == "a"

    def test_table_with_as_alias(self):
        refs = extract_sql_tables("select * from MYTBL as t;")
        assert refs[0][2] == "t"

    def test_semi_closes_context(self):
        """Semicolon must flush any open FROM context."""
        refs = extract_sql_tables("select * from A; select * from B;")
        names = [r[1] for r in refs]
        assert "A" in names
        assert "B" in names

    def test_no_from_no_refs(self):
        refs = extract_sql_tables("select 1 as x;")
        assert refs == []


# ---------------------------------------------------------------------------
# extract_sql_tables — F5: comma-join and aliases
# ---------------------------------------------------------------------------


class TestExtractSqlTablesF5:
    def test_three_comma_joined_tables(self):
        """from A, B, C → 3 distinct TableRefs."""
        refs = extract_sql_tables("from A, B, C;")
        names = [r[1] for r in refs]
        assert sorted(names) == ["A", "B", "C"]

    def test_comma_join_with_aliases(self):
        """from A a, B b → both captured with their aliases."""
        refs = extract_sql_tables("from A a, B b where a.k=b.k;")
        by_name = {r[1]: r[2] for r in refs}
        assert "A" in by_name
        assert "B" in by_name
        assert by_name["A"] == "a"
        assert by_name["B"] == "b"

    def test_comma_depth_zero_only_splits_from(self):
        """A comma inside a subquery should not split the outer FROM list."""
        refs = extract_sql_tables("from A, (select x, y from SUB) as d;")
        top_names = [r[1] for r in refs]
        assert "A" in top_names
        assert "SUB" in top_names
        # the derived table placeholder '(' must not appear as a table name
        assert not any(n.startswith("(") for n in top_names)


# ---------------------------------------------------------------------------
# extract_sql_tables — F2: subquery FROM harvested separately
# ---------------------------------------------------------------------------


class TestExtractSqlTablesF2:
    def test_subquery_table_captured(self):
        """Inner FROM inside a subquery must produce its own TableRef."""
        sql = "select x, (select max(v) from SUB) as m from MAIN;"
        refs = extract_sql_tables(sql)
        names = [r[1] for r in refs]
        assert "MAIN" in names
        assert "SUB" in names

    def test_subquery_inner_from_not_outer(self):
        """The subquery's FROM does not steal the outer FROM's tables."""
        sql = "select x, (select max(v) from SUB) as m from MAIN;"
        refs = extract_sql_tables(sql)
        # MAIN must be emitted (it's the outer FROM's table)
        assert any(r[1] == "MAIN" for r in refs)

    def test_derived_table_itself_not_emitted(self):
        """The subquery pseudo-table '(select …)' must not appear as a ref."""
        sql = "select * from (select id from INNER_TBL) as d;"
        refs = extract_sql_tables(sql)
        names = [r[1] for r in refs]
        # only the inner table should appear, not the derived-table placeholder
        assert "INNER_TBL" in names
        assert not any(n.startswith("(") for n in names)


# ---------------------------------------------------------------------------
# extract_sql_tables — F6: macro table refs
# ---------------------------------------------------------------------------


class TestExtractSqlTablesMacro:
    def test_macro_table_ref_kept_with_ampersand(self):
        """A &macro source table keeps the & so callers can flag it."""
        refs = extract_sql_tables("from &SRC;")
        assert len(refs) == 1
        assert refs[0][1].startswith("&")

    def test_real_table_alongside_macro(self):
        """Mixed list: REAL is captured; &SRC is captured with leading &."""
        refs = extract_sql_tables("from &SRC, REAL;")
        names = [r[1] for r in refs]
        assert "REAL" in names
        macro_refs = [n for n in names if n.startswith("&")]
        assert macro_refs, "macro table should be present with leading &"

    def test_macro_has_no_libref(self):
        refs = extract_sql_tables("from &SRC;")
        libref, table, alias = refs[0]
        assert libref is None
        assert table.startswith("&")


# ---------------------------------------------------------------------------
# extract_sql_tables — JOIN keyword support
# ---------------------------------------------------------------------------


class TestExtractSqlTablesJoin:
    def test_inner_join(self):
        refs = extract_sql_tables("from A inner join B on a.k = b.k;")
        names = [r[1] for r in refs]
        assert "A" in names
        assert "B" in names

    def test_left_join(self):
        refs = extract_sql_tables("from A a left join LIB.B b on a.k=b.k;")
        names = [r[1] for r in refs]
        assert "A" in names
        assert "B" in names

    def test_bare_join_table_names_captured(self):
        # A bare 'join' (no preceding 'left'/'inner') still closes the FROM
        # context cleanly: A keeps no spurious 'join' alias, B is captured.
        refs = extract_sql_tables("from A join B on a.k=b.k;")
        by_name = {r[1]: r[2] for r in refs}
        assert by_name.get("A") is None
        assert "B" in by_name

    def test_join_alias_captured(self):
        # A JOIN context now harvests its table AND alias at the terminator,
        # so both aliases survive: from A a join B b on … → A->a, B->b.
        refs = extract_sql_tables("from A a join B b on a.k=b.k;")
        by_name = {r[1]: r[2] for r in refs}
        assert by_name.get("A") == "a"
        assert by_name.get("B") == "b"

    def test_multiple_joins(self):
        refs = extract_sql_tables(
            "from A inner join B on a.k=b.k inner join C on b.k=c.k;"
        )
        names = {r[1] for r in refs}
        assert names >= {"A", "B", "C"}


# ---------------------------------------------------------------------------
# extract_sql_tables — close_top when list_start is None (line 145)
# ---------------------------------------------------------------------------


class TestExtractSqlTablesEdgeCases:
    def test_from_keyword_with_no_table_before_where(self):
        """FROM immediately followed by WHERE: list_start stays None;
        close_top must not crash (covers the early-return branch at line 145).
        """
        # Contrived but valid trigger: FROM with no ident before WHERE.
        refs = extract_sql_tables("from where x = 1;")
        # No valid table ref → either empty or harmless
        assert isinstance(refs, list)

    def test_empty_buffer(self):
        refs = extract_sql_tables("")
        assert refs == []

    def test_no_semi_at_end_still_returns_refs(self):
        """Stack is flushed even without a trailing semicolon."""
        refs = extract_sql_tables("from A")
        names = [r[1] for r in refs]
        assert "A" in names

    def test_where_closes_from_context(self):
        refs = extract_sql_tables("from MYTBL where x = 1;")
        assert any(r[1] == "MYTBL" for r in refs)

    def test_group_closes_from_context(self):
        refs = extract_sql_tables("from MYTBL group by x;")
        assert any(r[1] == "MYTBL" for r in refs)


# ---------------------------------------------------------------------------
# scan_tokens — doubled-quote escape in string literals (finding 4)
# ---------------------------------------------------------------------------


class TestScanTokensDoubledQuoteEscape:
    def test_single_quoted_with_escaped_quote_skipped(self):
        """'it''s' is one SAS string; the inner '' must not end it early."""
        tokens = scan_tokens("'it''s'")
        assert tokens == [], (
            "nothing inside a doubled-quote string should emit"
        )

    def test_double_quoted_with_escaped_quote_skipped(self):
        """\"he\"\"said\" is one string; inner \"\" must not end it early."""
        tokens = scan_tokens('"he""said"')
        assert tokens == []

    def test_comma_inside_doubled_quote_string_not_emitted(self):
        """'a,''b' — comma inside the string must not produce a comma token."""
        tokens = scan_tokens("'a,''b'")
        assert not any(t.kind == "comma" for t in tokens)

    def test_ident_after_doubled_quote_string_emitted(self):
        """Token after a doubled-quote string must still appear."""
        tokens = scan_tokens("'it''s' x")
        idents = [t.value for t in tokens if t.kind == "ident"]
        assert idents == ["x"]


# ---------------------------------------------------------------------------
# extract_sql_tables — FULL OUTER JOIN and CROSS JOIN (finding 8)
# ---------------------------------------------------------------------------


class TestExtractSqlTablesJoinExtra:
    def test_full_outer_join(self):
        """FULL OUTER JOIN must harvest both tables."""
        refs = extract_sql_tables(
            "from A full outer join B on a.k = b.k;"
        )
        names = [r[1] for r in refs]
        assert "A" in names
        assert "B" in names

    def test_full_outer_join_with_aliases(self):
        refs = extract_sql_tables(
            "from A a full outer join B b on a.k = b.k;"
        )
        by_name = {r[1]: r[2] for r in refs}
        assert by_name.get("A") == "a"
        assert by_name.get("B") == "b"

    def test_cross_join(self):
        """CROSS JOIN must harvest both tables."""
        refs = extract_sql_tables("from A cross join B;")
        names = [r[1] for r in refs]
        assert "A" in names
        assert "B" in names

    def test_cross_join_with_aliases(self):
        refs = extract_sql_tables("from A a cross join B b;")
        by_name = {r[1]: r[2] for r in refs}
        assert by_name.get("A") == "a"
        assert by_name.get("B") == "b"


# ---------------------------------------------------------------------------
# _parse_slice — three-part dotted ident guard (finding 5)
# ---------------------------------------------------------------------------


class TestParsesliceThreePartIdent:
    def test_three_part_ref_returns_sentinel(self):
        """A.B.C must produce the __UNPARSEABLE__ sentinel, not a valid ref."""
        from sas_lineage.parser.sql_tokeniser import _parse_slice

        result = _parse_slice("A.B.C")
        assert result is not None
        libref, table, alias = result
        assert libref == "__UNPARSEABLE__"
        assert table == "A.B.C"

    def test_two_part_ref_returns_normally(self):
        from sas_lineage.parser.sql_tokeniser import _parse_slice

        result = _parse_slice("LIB.TBL")
        assert result == ("LIB", "TBL", None)

    def test_unqualified_ref_returns_normally(self):
        from sas_lineage.parser.sql_tokeniser import _parse_slice

        result = _parse_slice("MYTBL")
        assert result == (None, "MYTBL", None)
