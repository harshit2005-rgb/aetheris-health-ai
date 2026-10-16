"""Provision a hospital and invite its first administrator, from the command line.

``make provision-hospital name=... slug=... admin_email=... admin_first=... admin_last=...``

For the operators onboarding a clinic. It runs exactly what
``POST /api/v1/admin/hospitals`` runs, :class:`HospitalProvisioningService`,
as a platform principal, against the database in ``DATABASE_URL``.

It never prints a credential. The administrator's one-time activation link
goes only to their mailbox; with no mail transport configured the account
stays invited, and the invitation is sent again once email works.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import ValidationError as PydanticValidationError

from app.api.dependencies import repositories as repos
from app.api.dependencies import services as svc
from app.core.exceptions import AtherisError
from app.database.session import create_session_factory, initialize_database
from app.schemas.hospital_provisioning import InitialAdmin, ProvisionHospitalRequest


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="provision-hospital",
        description="Create a hospital and invite its first administrator.",
    )
    parser.add_argument("--name", required=True, help="Full name, e.g. 'City Care Clinic'.")
    parser.add_argument("--slug", required=True, help="Permanent URL id, e.g. 'city-care'.")
    parser.add_argument("--timezone", default="Asia/Kolkata")
    parser.add_argument("--currency", default="INR")
    parser.add_argument("--email", default=None, help="The hospital's contact email.")
    parser.add_argument("--phone", default=None, help="The hospital's contact phone.")
    parser.add_argument("--line1", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--postal-code", default=None)
    parser.add_argument("--country", default="India")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-first", required=True)
    parser.add_argument("--admin-last", required=True)
    parser.add_argument("--admin-phone", default=None)
    return parser.parse_args(argv)


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value else None


async def _run(args: argparse.Namespace) -> int:
    address = {
        key: value
        for key, value in {
            "line1": _blank_to_none(args.line1),
            "city": _blank_to_none(args.city),
            "state": _blank_to_none(args.state),
            "postal_code": _blank_to_none(args.postal_code),
            "country": _blank_to_none(args.country),
        }.items()
        if value
    }
    try:
        payload = ProvisionHospitalRequest(
            name=args.name,
            slug=args.slug,
            timezone=args.timezone,
            currency=args.currency,
            email=_blank_to_none(args.email),
            phone=_blank_to_none(args.phone),
            address=address,
            admin=InitialAdmin(
                email=args.admin_email,
                first_name=args.admin_first,
                last_name=args.admin_last,
                phone=_blank_to_none(args.admin_phone),
            ),
        )
    except PydanticValidationError as error:
        for problem in error.errors():
            field = ".".join(str(part) for part in problem["loc"])
            sys.stderr.write(f"{field}: {problem['msg']}\n")
        return 2

    initialize_database()
    factory = create_session_factory()
    async with factory() as session:
        users = repos.get_user_repository(session)
        roles = repos.get_role_repository(session)
        hospitals = repos.get_hospital_repository(session)
        password_resets = repos.get_password_reset_token_repository(session)
        uow = svc.get_unit_of_work(session)
        audit = svc.get_audit_sink(session, repos.get_audit_log_repository(session), users)
        notifier = svc.get_notifier(
            svc.get_notification_service(
                repos.get_notification_repository(session), users, hospitals, session, audit
            )
        )
        auth = svc.get_auth_service(
            users,
            repos.get_refresh_token_repository(session),
            password_resets,
            uow,
            audit,
            notifier,
            repos.get_auth_throttle_repository(session),
            repos.get_trusted_device_repository(session),
        )
        user_service = svc.get_user_service(
            users,
            roles,
            repos.get_permission_repository(session),
            auth,
            uow,
            audit,
            password_resets,
            notifier,
        )
        service = svc.get_hospital_provisioning_service(hospitals, roles, user_service, audit)
        try:
            result = await service.provision(payload, actor_id=None, actor_permissions=None)
        except AtherisError as error:
            await session.rollback()
            sys.stderr.write(f"Not provisioned: {error.message}\n")
            return 1

    sys.stdout.write(
        f"Provisioned '{result.name}' (slug {result.slug}, id {result.hospital_id}).\n"
        f"First administrator: {result.admin_email} (user {result.admin_user_id}).\n"
    )
    if result.invitation == "queued":
        sys.stdout.write("Their activation email is queued; the worker sends it.\n")
    else:
        sys.stdout.write(
            "No email transport is configured, so no activation link exists yet. "
            "Configure email, then resend the invitation from Users.\n"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    return asyncio.run(_run(_parse(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    raise SystemExit(main())
