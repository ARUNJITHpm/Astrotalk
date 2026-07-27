"""Grant a console role from the command line — the first-owner bootstrap.

Everyone after the first owner is invited from the console. That first owner
has a chicken-and-egg problem (inviting requires being an owner), so this exists
and is deliberately NOT a route: creating an owner must require shell access to
the deployment, not merely a valid HTTP request.

    python scripts/grant_role.py --email you@example.com --role owner
    python scripts/grant_role.py --phone 9876543210 --role temple_admin \
        --temple tvm-padmanabhaswamy
    python scripts/grant_role.py --email staff@x.com --set-password

Idempotent: re-running with the same arguments creates nothing new. An operator
created here has no password until you pass --set-password (prompted, never
taken as an argument, so it stays out of your shell history) or they redeem an
invite.
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.modules.admin import operators as ops  # noqa: E402
from app.modules.admin.models import ROLES, Operator  # noqa: E402
from app.modules.identity.service import hash_password  # noqa: E402
from app.platform.db import async_session_factory  # noqa: E402


async def _run(args: argparse.Namespace) -> int:
    email = args.email.strip().lower() if args.email else None
    phone = args.phone.strip() if args.phone else None
    if not email and not phone:
        print("error: pass --email or --phone", file=sys.stderr)
        return 2

    password = None
    if args.set_password:
        password = getpass.getpass("New console password: ")
        if password != getpass.getpass("Confirm: "):
            print("error: passwords did not match", file=sys.stderr)
            return 2
        if len(password) < ops.MIN_PASSWORD_LEN:
            print(
                f"error: password must be at least {ops.MIN_PASSWORD_LEN} characters",
                file=sys.stderr,
            )
            return 2

    async with async_session_factory() as session:
        where = Operator.email == email if email else Operator.phone == phone
        operator = (await session.execute(select(Operator).where(where))).scalar_one_or_none()

        if operator is None:
            operator = Operator(email=email, phone=phone, name=args.name or "", active=True)
            session.add(operator)
            await session.flush()
            print(f"created operator #{operator.id} ({email or phone})")
        else:
            print(f"found operator #{operator.id} ({operator.email or operator.phone})")

        if password is not None:
            operator.password_hash = hash_password(password)
            print("password set")

        if args.role:
            try:
                grant = await ops.grant(
                    session, operator_id=operator.id, role=args.role, temple_id=args.temple
                )
            except ops.OperatorError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            scope = f" scoped to {grant.temple_id}" if grant.temple_id else ""
            print(f"granted {grant.role}{scope}")

        await session.commit()

    if operator.password_hash is None:
        print("\nNote: no password set yet — this operator cannot sign in.")
        print("Re-run with --set-password, or invite them from the console.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email")
    parser.add_argument("--phone")
    parser.add_argument("--name", default="")
    parser.add_argument("--role", choices=ROLES, help="role to grant")
    parser.add_argument("--temple", help="temple id, required for temple_admin")
    parser.add_argument(
        "--set-password", action="store_true", help="prompt for a password"
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
