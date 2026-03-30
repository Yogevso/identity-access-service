from __future__ import annotations

import argparse
import getpass
import sys

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.services.bootstrap import BootstrapAdminPayload, BootstrapConflictError, BootstrapService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap or recover a system administrator account.",
    )
    parser.add_argument("--tenant-name", required=True, help="Tenant name for the system admin.")
    parser.add_argument("--tenant-slug", required=True, help="Tenant slug for the system admin.")
    parser.add_argument("--full-name", required=True, help="Display name for the system admin.")
    parser.add_argument("--email", required=True, help="Email address for the system admin.")
    parser.add_argument(
        "--password",
        help="Password for the system admin. If omitted, the command prompts securely.",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Rotate the password if the system administrator already exists.",
    )
    return parser


def prompt_for_password() -> str:
    password = getpass.getpass("System admin password: ")
    password_confirmation = getpass.getpass("Confirm system admin password: ")
    if not password:
        raise ValueError("Password cannot be empty.")
    if password != password_confirmation:
        raise ValueError("Passwords do not match.")
    return password


def main() -> int:
    args = build_parser().parse_args()
    try:
        password = args.password or prompt_for_password()
    except ValueError as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1

    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    try:
        with session_factory() as session:
            result = BootstrapService(session).ensure_system_admin(
                BootstrapAdminPayload(
                    tenant_name=args.tenant_name,
                    tenant_slug=args.tenant_slug,
                    full_name=args.full_name,
                    email=args.email,
                    password=password,
                    rotate_password=args.reset_password,
                )
            )
    except BootstrapConflictError as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(
        "System admin ready: "
        f"tenant_slug={result.tenant_slug} "
        f"email={result.email} "
        f"tenant_created={result.tenant_created} "
        f"user_created={result.user_created} "
        f"password_rotated={result.password_rotated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
