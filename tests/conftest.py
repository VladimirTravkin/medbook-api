"""Pytest fixtures for the test suite."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.user import User, UserRole

# ============================================
# Test database
# ============================================

# Use a separate database on the same Postgres instance.
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/medbook_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator:
    """Create a session-scoped async engine for the test database."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    # Drop and recreate schema for a clean start
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


# ============================================
# Database session with savepoint isolation
# ============================================


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session, rolled back after each test.

    Uses a nested transaction (SAVEPOINT) so that commits made by the
    application code do not persist between tests.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with session_maker() as session:
        yield session

    await transaction.rollback()
    await connection.close()


# ============================================
# Fake Redis
# ============================================


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.aioredis.FakeRedis:
    """Replace the global Redis client with an in-memory fake."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis._redis_client", fake)
    monkeypatch.setattr("app.services.auth.get_redis_client", lambda: fake)
    return fake


# ============================================
# HTTP client
# ============================================


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client bound to the test app with overridden DB dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


# ============================================
# Users
# ============================================


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test patient user."""
    from app.core.security import hash_password

    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        full_name="Test Patient",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    from app.core.security import hash_password

    user = User(
        email="admin@test.com",
        password_hash=hash_password("adminpassword123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    """Log in as the test patient and return Authorization headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client: AsyncClient, test_admin: User) -> dict[str, str]:
    """Log in as the test admin and return Authorization headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "adminpassword123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_specialization(db_session: AsyncSession):
    """Create a test specialization."""
    from app.models.specialization import Specialization

    spec = Specialization(
        name="Терапевт",
        description="Врач общей практики",
    )
    db_session.add(spec)
    await db_session.flush()
    return spec


@pytest.fixture
async def test_doctor(db_session: AsyncSession, test_specialization):
    """Create a test doctor: User (role=doctor) + Doctor profile."""
    from app.core.security import hash_password
    from app.models.doctor import Doctor

    user = User(
        email="doctor@test.com",
        password_hash=hash_password("doctorpassword123"),
        full_name="Доктор Тестов",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialization_id=test_specialization.id,
        bio="Опытный специалист",
        experience_years=10,
    )
    db_session.add(doctor)
    await db_session.flush()
    return doctor


@pytest.fixture
async def doctor_headers(client: AsyncClient, test_doctor) -> dict[str, str]:
    """Log in as the test doctor and return Authorization headers."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@test.com", "password": "doctorpassword123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def future_slot(db_session: AsyncSession, test_doctor):
    """Create a free slot in the future (2 days from now)."""
    from datetime import UTC, datetime, timedelta

    from app.models.schedule_slot import ScheduleSlot

    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=2)
    end = start + timedelta(minutes=30)

    slot = ScheduleSlot(
        doctor_id=test_doctor.id,
        start_time=start,
        end_time=end,
        is_booked=False,
    )
    db_session.add(slot)
    await db_session.flush()
    return slot


@pytest.fixture
async def booked_slot(db_session: AsyncSession, test_doctor, test_user):
    """Create a slot already booked by test_user."""
    from datetime import UTC, datetime, timedelta

    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.schedule_slot import ScheduleSlot

    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=3)
    end = start + timedelta(minutes=30)

    slot = ScheduleSlot(
        doctor_id=test_doctor.id,
        start_time=start,
        end_time=end,
        is_booked=True,
    )
    db_session.add(slot)
    await db_session.flush()

    appointment = Appointment(
        patient_id=test_user.id,
        doctor_id=test_doctor.id,
        slot_id=slot.id,
        status=AppointmentStatus.PENDING,
    )
    db_session.add(appointment)
    await db_session.flush()
    return slot
