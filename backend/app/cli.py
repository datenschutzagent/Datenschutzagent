"""CLI for role and system settings management. Run with: python -m app.cli <command> ..."""

import argparse
import asyncio
import logging
import sys
import uuid

from sqlalchemy import select

from app.config import settings
from app.constants import UserRole
from app.database import async_session_factory
from app.models.db import UserModel
from app.services.connection_checks import check_all_connections

# Basic logging setup for CLI context (not via main.py's _configure_logging)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app.cli")

VALID_ROLES = tuple(UserRole)
DEFAULT_USER_ID_STR = "00000000-0000-4000-8000-000000000001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Datenschutzagent CLI: manage users/roles and show/check system config.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # users
    users_p = subparsers.add_parser("users", help="User and role management")
    users_sub = users_p.add_subparsers(dest="users_command", required=True)
    users_sub.add_parser(
        "list", help="List all users (id, display_name, email, role, oidc_sub)"
    )
    set_role_p = users_sub.add_parser(
        "set-role", help="Set user role (viewer | editor | admin)"
    )
    set_role_p.add_argument("user_id", help="User UUID")
    set_role_p.add_argument("role", choices=VALID_ROLES, help="Role to set")
    users_sub.add_parser(
        "show-default",
        help="Show default user ID and hint for setting role when OIDC is disabled",
    )

    # config
    config_p = subparsers.add_parser("config", help="System configuration (read-only)")
    config_sub = config_p.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Show current settings (no secrets)")
    config_sub.add_parser(
        "check", help="Run connection checks (Ollama, Weaviate, Postgres, MinIO, Redis)"
    )

    return parser.parse_args()


async def _cmd_users_list() -> int:
    async with async_session_factory() as session:
        result = await session.execute(select(UserModel).order_by(UserModel.created_at))
        users = result.scalars().all()
    if not users:
        print("No users found.")
        return 0
    for u in users:
        oidc = (u.oidc_sub or "")[:40] + (
            "..." if (u.oidc_sub and len(u.oidc_sub) > 40) else ""
        )
        print(f"{u.id}\t{u.display_name or ''}\t{u.email or ''}\t{u.role}\t{oidc}")
    return 0


async def _cmd_users_set_role(user_id_str: str, role: str) -> int:
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        print(f"Invalid user_id: {user_id_str!r} is not a valid UUID.", file=sys.stderr)
        return 1
    if role not in VALID_ROLES:
        print(f"Invalid role: {role!r}. Must be one of {VALID_ROLES}.", file=sys.stderr)
        return 1
    async with async_session_factory() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            print(f"User not found: {user_id}", file=sys.stderr)
            return 1
        user.role = role
        await session.commit()
    print(f"Role for user {user_id} ({user.display_name or 'n/a'}) set to {role}.")
    logger.warning("CLI: user role changed to '%s' for user %s", role, user_id)
    return 0


def _cmd_users_show_default() -> int:
    print(f"Default user ID (used when OIDC is disabled): {DEFAULT_USER_ID_STR}")
    print("To grant write access (create/edit cases, playbooks), run:")
    print(f"  python -m app.cli users set-role {DEFAULT_USER_ID_STR} editor")
    return 0


async def _cmd_config_show() -> int:
    s = settings
    data = {
        "app_name": s.app_name,
        "ollama_base_url": s.ollama_base_url,
        "ollama_enabled": s.ollama_enabled,
        "ollama_model": s.ollama_model,
        "weaviate_url": s.weaviate_url,
        "weaviate_indexing_enabled": getattr(s, "weaviate_indexing_enabled", False),
        "storage_backend": s.storage_backend,
        "storage_local_path": (
            s.storage_local_path if s.storage_backend == "local" else None
        ),
        "s3_configured": bool(
            s.s3_endpoint_url and s.s3_access_key and s.s3_secret_key
        ),
        "s3_bucket": s.s3_bucket if s.s3_endpoint_url else None,
        "celery_enabled": s.celery_enabled,
        "celery_broker_configured": bool((s.celery_broker_url or "").strip()),
        "oidc_enabled": s.oidc_enabled,
        "rbac_default_role": s.rbac_default_role,
    }
    for k, v in data.items():
        print(f"{k}: {v}")
    return 0


async def _cmd_config_check() -> int:
    results = await check_all_connections()
    for name, r in results.items():
        status = r.get("status", "?")
        msg = r.get("message", "")
        line = f"{name}: {status}"
        if msg:
            line += f" ({msg})"
        print(line)
    return 0


async def _main_async(args: argparse.Namespace) -> int:
    if args.command == "users":
        if args.users_command == "list":
            return await _cmd_users_list()
        if args.users_command == "set-role":
            return await _cmd_users_set_role(args.user_id, args.role)
        if args.users_command == "show-default":
            return _cmd_users_show_default()
    if args.command == "config":
        if args.config_command == "show":
            return await _cmd_config_show()
        if args.config_command == "check":
            return await _cmd_config_check()
    return 1


def main() -> int:
    args = _parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
