"""
Integration test fixtures — database sessions, test users, and cleanup.

All tests run against lucho_test database (separate from development DB).
Each test rolls back its transaction, so tests are isolated and repeatable.
"""

import uuid
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database — separate from development to avoid data corruption
TEST_DATABASE_URL = "postgresql+asyncpg://lucho:lucho@localhost:5434/lucho_test"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide an async database session wrapped in a transaction.

    All changes are rolled back after the test, so the database stays clean.
    Uses a fresh engine per test to ensure isolation.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        async with session.begin() as tx:
            yield session
            # Rollback so tests don't contaminate each other
            await tx.rollback()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Provide a raw async engine (for operations outside sessions)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession):
    """
    Create a test Telegram user with a trial subscription.

    Returns the User ORM object. Auto-cleaned via rollback.
    """
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.subscription_plan import SubscriptionPlan

    # Ensure a basic plan exists for trial creation
    from sqlalchemy import select
    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == "basic")
    )
    plan = result.scalar_one_or_none()

    if not plan:
        plan = SubscriptionPlan(
            slug="basic",
            name="Básico",
            price_monthly_usd=4.99,
            price_annual_usd=49.90,
            trial_days=7,
            features={
                "max_vehicles": 2,
                "max_documents": 10,
                "max_projects": 3,
                "file_storage_mb": 100,
            },
        )
        db_session.add(plan)
        await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        telegram_id=str(uuid.uuid4().int)[:10],
        first_name="TestUser",
        is_active=True,
        onboarding_complete=True,
        onboarding_step=0,
    )
    db_session.add(user)
    await db_session.flush()

    # Create trial subscription
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.trial,
        trial_ends_at=None,  # No expiry for tests
    )
    db_session.add(sub)
    await db_session.flush()

    return user


@pytest_asyncio.fixture(scope="function")
async def test_user_whatsapp(db_session: AsyncSession):
    """
    Create a test WhatsApp user.

    Returns the User ORM object.
    """
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionStatus
    from sqlalchemy import select
    from app.models.subscription_plan import SubscriptionPlan

    result = await db_session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == "basic")
    )
    plan = result.scalar_one_or_none()
    if not plan:
        plan = SubscriptionPlan(
            slug="basic", name="Básico",
            price_monthly_usd=4.99, price_annual_usd=49.90, trial_days=7,
            features={"max_vehicles": 2},
        )
        db_session.add(plan)
        await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        whatsapp_id="593987654321",
        first_name="WAUser",
        is_active=True,
        onboarding_complete=True,
        onboarding_step=0,
    )
    db_session.add(user)
    await db_session.flush()

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.trial,
    )
    db_session.add(sub)
    await db_session.flush()

    return user
