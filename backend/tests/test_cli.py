"""Tests for ``python -m app.cli`` (argparse based).

Commands are exercised through ``main()`` with a patched ``sys.argv`` so the
argument parser and the async dispatcher are covered end to end. DB-bound
commands (``users list``, ``users set-role``, ``audit verify``) talk to the
real test database and carry the ``requires_db`` marker; ``config check`` is
run against a patched ``check_all_connections`` so no external services are
contacted.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app import cli

DEFAULT_USER_ID = uuid.UUID(cli.DEFAULT_USER_ID_STR)


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["app.cli", *argv])
    return cli.main()


async def _create_user(role: str = "viewer") -> uuid.UUID:
    from app.database import async_session_factory
    from app.models.db import UserModel

    async with async_session_factory() as session:
        user = UserModel(
            oidc_sub=f"cli-{uuid.uuid4()}",
            display_name="CLI Test",
            email=None,
            role=role,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _user_role(user_id: uuid.UUID) -> str | None:
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.db import UserModel

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserModel.role).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        (),  # command required
        ("users",),  # users sub-command required
        ("config",),
        ("audit",),
        ("bogus",),
        ("users", "set-role"),  # user_id + role required
        ("users", "set-role", cli.DEFAULT_USER_ID_STR, "superuser"),  # invalid choice
    ],
)
def test_parse_args_rejects_incomplete_or_invalid_commands(monkeypatch, argv):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, *argv)
    assert exc.value.code == 2


def test_help_exits_zero(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, "--help")
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "users" in out and "config" in out and "audit" in out


def test_valid_roles_match_user_role_enum():
    assert set(cli.VALID_ROLES) == {"viewer", "editor", "admin"}


def test_module_entrypoint_exits_with_command_result(monkeypatch, capsys):
    """``python -m app.cli …`` goes through the ``__main__`` guard and ``sys.exit``."""
    import runpy
    import warnings

    monkeypatch.setattr("sys.argv", ["app.cli", "users", "show-default"])
    with pytest.raises(SystemExit) as exc, warnings.catch_warnings():
        # runpy warns that app.cli is already imported (by this test module).
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("app.cli", run_name="__main__", alter_sys=True)
    assert exc.value.code == 0
    assert cli.DEFAULT_USER_ID_STR in capsys.readouterr().out


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


def test_users_show_default_prints_id_and_hint(monkeypatch, capsys):
    assert _run(monkeypatch, "users", "show-default") == 0
    out = capsys.readouterr().out
    assert cli.DEFAULT_USER_ID_STR in out
    assert f"users set-role {cli.DEFAULT_USER_ID_STR} editor" in out


@pytest.mark.requires_db
def test_users_list_prints_one_line_per_user(monkeypatch, capsys):
    import asyncio

    user_id = asyncio.run(_create_user(role="editor"))

    assert _run(monkeypatch, "users", "list") == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert "No users found." not in out
    mine = next(ln for ln in lines if ln.startswith(str(user_id)))
    cols = mine.split("\t")
    assert cols[1] == "CLI Test"
    assert cols[2] == ""  # email None -> empty
    assert cols[3] == "editor"
    assert cols[4].startswith("cli-")
    assert not cols[4].endswith("...")  # oidc_sub shorter than 40 chars


@pytest.mark.requires_db
async def test_users_list_truncates_long_oidc_sub(capsys):
    from app.database import async_session_factory
    from app.models.db import UserModel

    long_sub = f"cli-long-{uuid.uuid4()}-{'x' * 40}"
    async with async_session_factory() as session:
        user = UserModel(oidc_sub=long_sub, display_name="", email=None, role="viewer")
        session.add(user)
        await session.commit()
        user_id = user.id

    assert await cli._cmd_users_list() == 0
    out = capsys.readouterr().out
    mine = next(ln for ln in out.splitlines() if ln.startswith(str(user_id)))
    cols = mine.split("\t")
    assert cols[1] == ""  # empty display_name stays empty
    assert cols[4] == long_sub[:40] + "..."


async def test_users_list_without_users_prints_hint(capsys):
    """Empty result branch — the session is patched so no rows come back."""
    from unittest.mock import MagicMock

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with patch("app.cli.async_session_factory", return_value=session):
        assert await cli._cmd_users_list() == 0
    assert capsys.readouterr().out.strip() == "No users found."


@pytest.mark.requires_db
def test_users_set_role_updates_user(monkeypatch, capsys):
    import asyncio

    user_id = asyncio.run(_create_user(role="viewer"))

    assert _run(monkeypatch, "users", "set-role", str(user_id), "admin") == 0
    out = capsys.readouterr().out
    assert f"Role for user {user_id} (CLI Test) set to admin." in out
    assert asyncio.run(_user_role(user_id)) == "admin"


@pytest.mark.requires_db
def test_users_set_role_unknown_user_returns_1(monkeypatch, capsys):
    missing = uuid.uuid4()
    assert _run(monkeypatch, "users", "set-role", str(missing), "editor") == 1
    captured = capsys.readouterr()
    assert f"User not found: {missing}" in captured.err
    assert captured.out == ""


def test_users_set_role_invalid_uuid_returns_1(monkeypatch, capsys):
    assert _run(monkeypatch, "users", "set-role", "not-a-uuid", "editor") == 1
    err = capsys.readouterr().err
    assert "Invalid user_id: 'not-a-uuid' is not a valid UUID." in err


async def test_users_set_role_invalid_role_returns_1(capsys):
    """argparse blocks this via ``choices``; the function guards it independently."""
    assert await cli._cmd_users_set_role(str(uuid.uuid4()), "root") == 1
    err = capsys.readouterr().err
    assert "Invalid role: 'root'" in err


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def test_config_show_prints_settings_without_secrets(monkeypatch, capsys):
    from app.config import settings

    assert _run(monkeypatch, "config", "show") == 0
    out = capsys.readouterr().out
    values = dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)
    assert values["app_name"] == settings.app_name
    assert values["ollama_enabled"] == str(settings.ollama_enabled)
    assert values["storage_backend"] == settings.storage_backend
    assert values["rbac_default_role"] == settings.rbac_default_role
    assert set(values) >= {
        "ollama_base_url",
        "ollama_model",
        "weaviate_url",
        "weaviate_indexing_enabled",
        "storage_local_path",
        "s3_configured",
        "s3_bucket",
        "celery_enabled",
        "celery_broker_configured",
        "oidc_enabled",
    }
    assert values["s3_configured"] in {"True", "False"}
    assert values["celery_broker_configured"] in {"True", "False"}
    # No secret material must ever be printed.
    for secret_name in ("s3_secret_key", "database_url", "session_secret"):
        assert secret_name not in out


def test_config_show_storage_local_path_only_for_local_backend(monkeypatch, capsys):
    from app.config import settings

    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_bucket", "bucket-x")
    assert _run(monkeypatch, "config", "show") == 0
    out = capsys.readouterr().out
    assert "storage_local_path: None" in out
    assert "s3_bucket: bucket-x" in out

    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "s3_endpoint_url", "")
    assert _run(monkeypatch, "config", "show") == 0
    out = capsys.readouterr().out
    assert f"storage_local_path: {settings.storage_local_path}" in out
    assert "s3_bucket: None" in out


def test_config_check_prints_status_per_service(monkeypatch, capsys):
    results = {
        "ollama": {"status": "disabled", "message": "OLLAMA_ENABLED=false"},
        "postgres": {"status": "ok", "message": ""},
        "redis": {"status": "error", "message": "connection refused"},
        "weird": {},
    }
    with patch(
        "app.cli.check_all_connections", AsyncMock(return_value=results)
    ) as check:
        assert _run(monkeypatch, "config", "check") == 0
    check.assert_awaited_once()
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "ollama: disabled (OLLAMA_ENABLED=false)",
        "postgres: ok",
        "redis: error (connection refused)",
        "weird: ?",
    ]


# ---------------------------------------------------------------------------
# audit verify
# ---------------------------------------------------------------------------


@pytest.mark.requires_db
def test_audit_verify_ok_exits_zero(monkeypatch, capsys):
    assert _run(monkeypatch, "audit", "verify") == 0
    out = capsys.readouterr().out
    assert out.startswith("audit chain OK:")
    assert "entries verified" in out
    assert "pre-chain entries skipped" in out


def test_audit_verify_broken_chain_exits_one(monkeypatch, capsys):
    from app.services.audit_service import ChainVerification

    broken = ChainVerification(
        ok=False,
        checked=7,
        skipped_unhashed=0,
        first_broken_seq=42,
        reason="entry_hash mismatch (row modified?)",
    )
    with patch(
        "app.services.audit_service.verify_audit_chain",
        AsyncMock(return_value=broken),
    ):
        assert _run(monkeypatch, "audit", "verify") == 1
    out = capsys.readouterr().out
    assert "audit chain BROKEN at seq=42: entry_hash mismatch (row modified?)" in out
    assert "(7 entries verified before the break)" in out


def test_audit_verify_reports_skipped_entries(monkeypatch, capsys):
    from app.services.audit_service import ChainVerification

    ok = ChainVerification(ok=True, checked=3, skipped_unhashed=2)
    with patch(
        "app.services.audit_service.verify_audit_chain",
        AsyncMock(return_value=ok),
    ):
        assert _run(monkeypatch, "audit", "verify") == 0
    assert (
        capsys.readouterr().out.strip()
        == "audit chain OK: 3 entries verified, 2 pre-chain entries skipped"
    )


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------


async def test_main_async_unknown_command_returns_1():
    import argparse

    args = argparse.Namespace(command="nope")
    assert await cli._main_async(args) == 1

    args = argparse.Namespace(command="users", users_command="nope")
    assert await cli._main_async(args) == 1

    args = argparse.Namespace(command="config", config_command="nope")
    assert await cli._main_async(args) == 1

    args = argparse.Namespace(command="audit", audit_command="nope")
    assert await cli._main_async(args) == 1
