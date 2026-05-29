"""Small safe boolean parser for DSFA screening rules.

Grammar
-------
    expression := or_expr
    or_expr    := and_expr ('OR' and_expr)*
    and_expr   := not_expr ('AND' not_expr)*
    not_expr   := 'NOT' not_expr | atom
    atom       := IDENTIFIER | '(' expression ')'

Identifiers must match factor ids from ``DsfaScreeningConfig.factors``.
Operators are case-insensitive (``and`` / ``AND`` both work).

Why a custom parser instead of ``eval()``? The YAML is admin-editable. A
careless ``eval`` would let any admin execute arbitrary Python on the
server — and the bar to fix that retroactively is extremely high. The
parser handles AND/OR/NOT + parentheses, which is all the EDSA-style
combinator logic we need.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class Not:
    operand: "Expr"


@dataclass(frozen=True)
class And:
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Or:
    left: "Expr"
    right: "Expr"


Expr = Identifier | Not | And | Or


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"\s*(?:(\()|(\))|([A-Za-z_][A-Za-z0-9_]*))")


def _tokenize(expression: str) -> list[str]:
    """Return a flat list of tokens: '(', ')', identifiers, and uppercase keywords.

    Raises ``ValueError`` on any unexpected character so admins get a clear
    error message at config-validation time.
    """
    tokens: list[str] = []
    pos = 0
    while pos < len(expression):
        # skip whitespace
        while pos < len(expression) and expression[pos].isspace():
            pos += 1
        if pos >= len(expression):
            break
        m = _TOKEN_RE.match(expression, pos)
        if not m:
            raise ValueError(
                f"Unexpected character at position {pos} in expression: {expression!r}"
            )
        if m.group(1):
            tokens.append("(")
        elif m.group(2):
            tokens.append(")")
        elif m.group(3):
            ident = m.group(3)
            upper = ident.upper()
            if upper in ("AND", "OR", "NOT"):
                tokens.append(upper)
            else:
                tokens.append(ident)
        pos = m.end()
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Cursor:
    __slots__ = ("tokens", "i")

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def consume(self) -> str:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, expected: str) -> None:
        if self.i >= len(self.tokens):
            raise ValueError(f"Expected {expected!r} but reached end of expression")
        actual = self.tokens[self.i]
        if actual != expected:
            raise ValueError(f"Expected {expected!r} but got {actual!r} at token {self.i}")
        self.i += 1


def _parse_atom(c: _Cursor) -> Expr:
    tok = c.peek()
    if tok is None:
        raise ValueError("Expected identifier or '(' but reached end of expression")
    if tok == "(":
        c.consume()
        inner = _parse_or(c)
        c.expect(")")
        return inner
    if tok in ("AND", "OR", "NOT", ")"):
        raise ValueError(f"Unexpected token {tok!r} at position {c.i}")
    c.consume()
    return Identifier(name=tok)


def _parse_not(c: _Cursor) -> Expr:
    if c.peek() == "NOT":
        c.consume()
        return Not(operand=_parse_not(c))
    return _parse_atom(c)


def _parse_and(c: _Cursor) -> Expr:
    left = _parse_not(c)
    while c.peek() == "AND":
        c.consume()
        left = And(left=left, right=_parse_not(c))
    return left


def _parse_or(c: _Cursor) -> Expr:
    left = _parse_and(c)
    while c.peek() == "OR":
        c.consume()
        left = Or(left=left, right=_parse_and(c))
    return left


def parse(expression: str) -> Expr:
    """Parse an expression string into an Expr AST.

    Raises ValueError on any syntax error.
    """
    tokens = _tokenize(expression)
    if not tokens:
        raise ValueError("Empty expression")
    cursor = _Cursor(tokens)
    expr = _parse_or(cursor)
    if cursor.i != len(tokens):
        raise ValueError(f"Trailing tokens after expression: {tokens[cursor.i:]}")
    return expr


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def evaluate(expr: Expr, satisfied: Iterable[str]) -> bool:
    """Evaluate an AST against the set of satisfied identifier names."""
    s = set(satisfied)

    def _eval(node: Expr) -> bool:
        if isinstance(node, Identifier):
            return node.name in s
        if isinstance(node, Not):
            return not _eval(node.operand)
        if isinstance(node, And):
            return _eval(node.left) and _eval(node.right)
        if isinstance(node, Or):
            return _eval(node.left) or _eval(node.right)
        raise TypeError(f"Unknown AST node type: {type(node).__name__}")

    return _eval(expr)


def collect_identifiers(expr: Expr) -> set[str]:
    """Return all identifier names referenced by ``expr`` (de-duplicated)."""
    out: set[str] = set()

    def _walk(node: Expr) -> None:
        if isinstance(node, Identifier):
            out.add(node.name)
        elif isinstance(node, Not):
            _walk(node.operand)
        elif isinstance(node, (And, Or)):
            _walk(node.left)
            _walk(node.right)

    _walk(expr)
    return out
