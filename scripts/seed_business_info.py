#!/usr/bin/env python3
"""Seed the business_info table with AURACORE's company data.

Run:
    python scripts/seed_business_info.py

Safe to run multiple times — updates if a record already exists.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session
from app.models.business import BusinessInfo
from sqlalchemy import select


async def main():
    async with async_session() as session:
        result = await session.execute(
            select(BusinessInfo).where(BusinessInfo.is_active is True)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✅ Business info already exists (id={existing.id}).")
            print(f"   Empresa: {existing.company_name}")
            print(f"   RUC: {existing.ruc}")
            print(f"   Banco: {existing.bank_name} — {existing.account_type} #{existing.account_number}")
            return

        info = BusinessInfo(
            company_name="AURACORE SOLUCIONES S.A.S.",
            ruc="0195160252001",
            bank_name="Produbanco",
            account_type="ahorros",
            account_number="27059108040",
            support_email="patriciovalarezo@gmail.com",
        )
        session.add(info)
        await session.commit()
        await session.refresh(info)

        print(f"✅ Business info creado (id={info.id}).")
        print(f"   Empresa: {info.company_name}")
        print(f"   RUC: {info.ruc}")
        print(f"   Banco: {info.bank_name} — {info.account_type} #{info.account_number}")


if __name__ == "__main__":
    asyncio.run(main())
