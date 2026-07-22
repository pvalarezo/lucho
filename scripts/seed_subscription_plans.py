#!/usr/bin/env python3
"""Seed the subscription_plans table with Lucho's plan catalog.

Plans:
  - Básico:    $4.99/mes  | $49.90/año  | 7 días trial
  - Premium:   $9.99/mes  | $99.90/año  | 7 días trial
  - Familia:   $14.99/mes | $149.90/año | 7 días trial

Run:
    python scripts/seed_subscription_plans.py

Safe to run multiple times — updates existing plans by slug.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session
from app.models.subscription_plan import SubscriptionPlan
from sqlalchemy import select

PLANS = [
    {
        "name": "Básico",
        "slug": "basic",
        "description": "Asistente personal de segundo cerebro para el día a día. Organizá tu vida sin esfuerzo.",
        "price_monthly_usd": 4.99,
        "price_annual_usd": 49.90,
        "trial_days": 7,
        "features": {
            # Functional modules
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
            # Limits
            "max_vehicles": 2,
            "max_documents": 10,
            "max_projects": 3,
            "max_budgets": 3,
            "max_contacts": 20,
            "file_storage_mb": 100,
            "messages_per_day": 50,
            # Premium features
            "caregiver_mode": False,
            "priority_support": False,
        },
        "is_active": True,
    },
    {
        "name": "Premium",
        "slug": "premium",
        "description": "Para los que quieren todo. Más capacidad, más proyectos, soporte prioritario.",
        "price_monthly_usd": 9.99,
        "price_annual_usd": 99.90,
        "trial_days": 7,
        "features": {
            # Functional modules — all enabled
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
            # Higher limits
            "max_vehicles": 4,
            "max_documents": 50,
            "max_projects": 10,
            "max_budgets": 10,
            "max_contacts": 999,  # ilimitado
            "file_storage_mb": 500,
            "messages_per_day": 200,
            # Premium features
            "caregiver_mode": False,
            "priority_support": True,
        },
        "is_active": True,
    },
    {
        "name": "Familia",
        "slug": "family",
        "description": "Toda la familia organizada. Modo cuidado para adultos mayores, almacenamiento ampliado, y todas las funciones premium.",
        "price_monthly_usd": 14.99,
        "price_annual_usd": 149.90,
        "trial_days": 7,
        "features": {
            # Functional modules — all enabled
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
            # Highest limits
            "max_vehicles": 4,
            "max_documents": 100,
            "max_projects": 20,
            "max_budgets": 999,  # ilimitado
            "max_contacts": 999,  # ilimitado
            "file_storage_mb": 1024,  # 1 GB
            "messages_per_day": 500,
            # Family-specific
            "caregiver_mode": True,
            "priority_support": True,
        },
        "is_active": True,
    },
]


async def main():
    async with async_session() as session:
        created = 0
        updated = 0

        for plan_data in PLANS:
            slug = plan_data["slug"]
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.slug == slug)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing plan
                for key, value in plan_data.items():
                    if key == "slug":
                        continue
                    setattr(existing, key, value)
                updated += 1
                print(f"🔄 Plan '{plan_data['name']}' actualizado (id={existing.id}).")
            else:
                plan = SubscriptionPlan(**plan_data)
                session.add(plan)
                created += 1
                print(f"✅ Plan '{plan_data['name']}' creado (id={plan.id}).")

        await session.commit()

        # Print summary
        print()
        print("=" * 60)
        print(f"  {created} plan(es) creados, {updated} actualizado(s)")
        print("=" * 60)
        print()

        # Show current catalog
        result = await session.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)
            .order_by(SubscriptionPlan.price_monthly_usd)
        )
        for p in result.scalars():
            annual_savings = (p.price_monthly_usd * 12) - p.price_annual_usd
            print(f"  📦 {p.name} ({p.slug})")
            print(f"     ${p.price_monthly_usd:.2f}/mes  |  ${p.price_annual_usd:.2f}/año (ahorras ${annual_savings:.2f})")
            print(f"     Trial: {p.trial_days} días")
            feats = p.features
            limits = {k: v for k, v in feats.items() if k.startswith("max_") or k.endswith("_mb") or k.endswith("_per_day")}
            bools = {k: v for k, v in feats.items() if isinstance(v, bool) and v}
            print(f"     Features: {', '.join(bools.keys())}")
            print(f"     Limits: {limits}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
