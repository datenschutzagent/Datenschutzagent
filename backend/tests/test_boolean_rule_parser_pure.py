"""Pure tests for the boolean rule parser (no DB, no IO)."""

from __future__ import annotations

import pytest

from app.services.boolean_rule_parser import (
    And,
    Identifier,
    Not,
    Or,
    collect_identifiers,
    evaluate,
    parse,
)

# ---------------------------------------------------------------------------
# Tokenisation / parser errors
# ---------------------------------------------------------------------------


def test_empty_expression_rejected():
    with pytest.raises(ValueError):
        parse("")


def test_unexpected_character_rejected():
    with pytest.raises(ValueError):
        parse("a $ b")


def test_unmatched_parenthesis_rejected():
    with pytest.raises(ValueError):
        parse("(a AND b")


def test_dangling_operator_rejected():
    with pytest.raises(ValueError):
        parse("a AND")
    with pytest.raises(ValueError):
        parse("OR b")


def test_trailing_tokens_rejected():
    with pytest.raises(ValueError):
        parse("a b")  # two atoms without an operator


# ---------------------------------------------------------------------------
# AST shape
# ---------------------------------------------------------------------------


def test_single_identifier_parses_to_identifier():
    ast = parse("foo")
    assert ast == Identifier(name="foo")


def test_and_left_associative():
    ast = parse("a AND b AND c")
    # Expect ((a AND b) AND c)
    assert ast == And(
        left=And(left=Identifier("a"), right=Identifier("b")),
        right=Identifier("c"),
    )


def test_or_left_associative():
    ast = parse("a OR b OR c")
    assert ast == Or(
        left=Or(left=Identifier("a"), right=Identifier("b")),
        right=Identifier("c"),
    )


def test_and_binds_tighter_than_or():
    ast = parse("a OR b AND c")
    # Expect (a OR (b AND c)), not ((a OR b) AND c)
    assert ast == Or(
        left=Identifier("a"),
        right=And(left=Identifier("b"), right=Identifier("c")),
    )


def test_parentheses_override_precedence():
    ast = parse("(a OR b) AND c")
    assert ast == And(
        left=Or(left=Identifier("a"), right=Identifier("b")),
        right=Identifier("c"),
    )


def test_not_nested():
    ast = parse("NOT NOT a")
    assert ast == Not(Not(Identifier("a")))


def test_not_binds_tighter_than_and():
    ast = parse("NOT a AND b")
    assert ast == And(left=Not(Identifier("a")), right=Identifier("b"))


def test_case_insensitive_operators():
    # All four forms must parse identically.
    asts = [
        parse("a and b"),
        parse("a And b"),
        parse("a AND b"),
        parse("A aNd B"),
    ]
    # Identifiers preserve original case; operators are normalised.
    assert asts[0] == And(Identifier("a"), Identifier("b"))
    assert asts[2] == And(Identifier("a"), Identifier("b"))
    assert asts[3] == And(Identifier("A"), Identifier("B"))


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def test_evaluate_basic():
    ast = parse("profiling AND special_categories")
    assert evaluate(ast, {"profiling", "special_categories"}) is True
    assert evaluate(ast, {"profiling"}) is False
    assert evaluate(ast, set()) is False


def test_evaluate_with_not_and_parens():
    ast = parse("a AND NOT (b OR c)")
    assert evaluate(ast, {"a"}) is True
    assert evaluate(ast, {"a", "b"}) is False
    assert evaluate(ast, {"a", "c"}) is False
    assert evaluate(ast, {"a", "b", "c"}) is False


def test_evaluate_short_circuit_does_not_throw():
    """An unsatisfiable AND should never look at the right-hand side."""
    ast = parse("never AND anything")
    assert evaluate(ast, set()) is False


def test_collect_identifiers_dedupes_and_walks_all_branches():
    ast = parse("a AND (b OR a) AND NOT c")
    assert collect_identifiers(ast) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Round-trip property: parsing produces identifiers that exist on the
# original input string.
# ---------------------------------------------------------------------------


def test_collect_identifiers_for_real_rule():
    ast = parse("(profiling OR systematic_monitoring) AND special_categories")
    ids = collect_identifiers(ast)
    assert ids == {"profiling", "systematic_monitoring", "special_categories"}
