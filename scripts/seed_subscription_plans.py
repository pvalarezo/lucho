#!/usr/bin/env python3
"""Seed the subscription_plans table with the initial 'Básico' plan.

Run once after migration:
    python scripts/seed_subscription_plans.py

Safe to run multiple times — skips if 'basic' slug already exists.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session
from app.models.subscription_plan import SubscriptionPlan
from sqlalchemy import select

BASIC_PLAN = {
    "name": "Básico",
    "slug": "basic",
    "description": "Plan personal — asistente de segundo cerebro para el día a día.",
    "price_monthly_usd": 0.0,  # TODO: define real pricing
    "price_annual_usd": 0.0,    # TODO: define real pricing
    "trial_days": 7,
    "features": {
        "vehicles": True,
        "documents": True,
        "events": True,
        "reminders": True,
        "lists": True,
        "notes": True,
        "projects": True,
        "contacts": True,
        "expenses": True,
        "web_search": True,
        "skills_ecuador": True,
        "daily_digest": True,
        "file_storage_mb": 100,
        "messages_per_day": 50,
    },
    "is_active": True,
}


async def main():
    async with async_session() as session:
        # Check if basic plan already exists
        result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == "basic")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✅ Plan 'Básico' already exists (id={existing.id}).")
            print(f"   Features: {existing.features}")
            print(f"   Trial days: {existing.trial_days}")
            return

        # Create basic plan
        plan = SubscriptionPlan(**BASIC_PLAN)
        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        print(f"✅ Plan 'Básico' created (id={plan.id}).")
        print(f"   Features: {plan.features}")
        print(f"   Trial: {plan.trial_days} days")
        print(f"   Price: ${plan.price_monthly_usd}/month | ${plan.price_annual_usd}/year")


if __name__ == "__main__":
    asyncio.run(main())
