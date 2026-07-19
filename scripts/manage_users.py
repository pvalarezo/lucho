#!/usr/bin/env python3
"""Manage Lucho users — activate, deactivate, list, show details.

Usage:
    python scripts/manage_users.py --list
    python scripts/manage_users.py --show 593987654321
    python scripts/manage_users.py --activate 593987654321
    python scripts/manage_users.py --deactivate 593987654321
    python scripts/manage_users.py --activate-telegram 123456789
    python scripts/manage_users.py --deactivate-telegram 123456789

Activation means setting is_active=True so the user can interact.
Deactivation means is_active=False (blocks all access).
"""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session
from app.models.user import User
from app.models.subscription import Subscription
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def list_users():
    """List all users with their status."""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.subscription).selectinload(Subscription.plan_ref)
            )
            .order_by(User.created_at.desc())
            .limit(50)
        )
        users = result.scalars().all()

        if not users:
            print("No users found.")
            return

        print(f"\n{'Name':<25} {'Channel':<15} {'Active':<8} {'Status':<12} {'Plan':<10}")
        print("-" * 70)
        for u in users:
            channel = "Telegram" if u.telegram_id else "WhatsApp" if u.whatsapp_id else "—"
            active = "✅" if u.is_active else "❌"
            sub_status = u.subscription.status.value if u.subscription else "—"
            plan_name = u.subscription.plan_ref.name if u.subscription and u.subscription.plan_ref else "—"
            print(
                f"{u.first_name[:24]:<25} "
                f"{channel:<15} "
                f"{active:<8} "
                f"{sub_status:<12} "
                f"{plan_name:<10}"
            )
        print(f"\nTotal: {len(users)} users shown.")


async def show_user(identifier: str):
    """Show detailed info for a user by phone or telegram_id."""
    async with async_session() as session:
        user = await _find_user(session, identifier)
        if not user:
            print(f"❌ User not found: {identifier}")
            return

        sub = user.subscription
        plan = sub.plan_ref if sub else None

        print(f"\n{'='*50}")
        print(f"User: {user.first_name} {user.last_name or ''}")
        print(f"ID: {user.id}")
        print(f"Telegram: {user.telegram_id or '—'}")
        print(f"WhatsApp: {user.whatsapp_id or '—'}")
        print(f"Phone: {user.phone_number or '—'}")
        print(f"Preferred name: {user.preferred_name or '—'}")
        print(f"Active: {'✅' if user.is_active else '❌'}")
        print(f"Onboarding: {'✅' if user.onboarding_complete else '❌'}")
        print(f"Language: {user.language}")
        print(f"Created: {user.created_at}")
        print(f"{'='*50}")
        if sub:
            print(f"Subscription: {sub.status.value}")
            print(f"Plan: {plan.name if plan else '—'}")
            print(f"Trial ends: {sub.trial_ends_at or '—'}")
            print(f"Period: {sub.current_period_start or '—'} → {sub.current_period_end or '—'}")
            print(f"Payment method: {sub.payment_method.value if sub.payment_method else '—'}")
            print(f"Renewal: {sub.renewal_type.value if sub.renewal_type else '—'}")
        else:
            print("Subscription: —")
        print(f"{'='*50}\n")


async def activate_user(identifier: str, active: bool = True):
    """Activate or deactivate a user."""
    async with async_session() as session:
        user = await _find_user(session, identifier)
        if not user:
            print(f"❌ User not found: {identifier}")
            return

        user.is_active = active
        await session.commit()

        status = "activated ✅" if active else "deactivated ❌"
        print(f"User {user.first_name} ({identifier}) {status}")


async def _find_user(session, identifier: str) -> User | None:
    """Find user by whatsapp_id, telegram_id, phone_number, or UUID prefix."""
    from sqlalchemy.orm import selectinload

    # Try UUID first
    if len(identifier) > 30:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.subscription).selectinload(Subscription.plan_ref)
            )
            .where(User.id == identifier)
        )
        return result.scalar_one_or_none()

    # Try phone/whatsapp
    phone = identifier.lstrip("+")
    result = await session.execute(
        select(User)
        .options(
            selectinload(User.subscription).selectinload(Subscription.plan_ref)
        )
        .where(
            (User.whatsapp_id == phone)
            | (User.phone_number == phone)
            | (User.telegram_id == identifier)
        )
    )
    return result.scalar_one_or_none()


async def main():
    parser = argparse.ArgumentParser(description="Manage Lucho users")
    parser.add_argument("--list", action="store_true", help="List all users")
    parser.add_argument("--show", type=str, metavar="ID", help="Show user details")
    parser.add_argument("--activate", type=str, metavar="PHONE", help="Activate user by phone")
    parser.add_argument("--deactivate", type=str, metavar="PHONE", help="Deactivate user by phone")
    parser.add_argument(
        "--activate-telegram", type=str, metavar="TG_ID", help="Activate user by telegram_id"
    )
    parser.add_argument(
        "--deactivate-telegram", type=str, metavar="TG_ID", help="Deactivate user by telegram_id"
    )
    args = parser.parse_args()

    if args.list:
        await list_users()
    elif args.show:
        await show_user(args.show)
    elif args.activate:
        await activate_user(args.activate, active=True)
    elif args.deactivate:
        await activate_user(args.deactivate, active=False)
    elif args.activate_telegram:
        await activate_user(args.activate_telegram, active=True)
    elif args.deactivate_telegram:
        await activate_user(args.deactivate_telegram, active=False)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
