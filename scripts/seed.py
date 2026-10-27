"""Seed script: populate the database with demo data.

Idempotent: safe to run multiple times — existing records are skipped.

Usage:
    # Against local DB (uses .env)
    uv run python scripts/seed.py

    # Against production (Neon) — pass env vars explicitly:
    POSTGRES_HOST=... POSTGRES_PASSWORD=... uv run python scripts/seed.py
"""

import asyncio
import sys
from datetime import UTC, datetime, time, timedelta

from app.core.security import hash_password
from app.db.session import create_quiet_session_maker
from app.models.doctor import Doctor
from app.models.specialization import Specialization
from app.models.user import UserRole
from app.repositories.doctor import DoctorRepository
from app.repositories.slot import SlotRepository
from app.repositories.specialization import SpecializationRepository
from app.repositories.user import UserRepository

# ============================================
# Seed data
# ============================================

SPECIALIZATIONS = [
    {
        "name": "Терапевт",
        "description": "Врач общей практики, диагностика и лечение внутренних болезней.",
    },
    {
        "name": "Кардиолог",
        "description": "Специалист по заболеваниям сердечно-сосудистой системы.",
    },
    {
        "name": "Невролог",
        "description": "Специалист по заболеваниям нервной системы.",
    },
]

DOCTORS = [
    {
        "email": "ivanov@medbook.dev",
        "password": "doctor12345",
        "full_name": "Иванов Иван Иванович",
        "specialization": "Терапевт",
        "bio": (
            "Врач-терапевт с 15-летним опытом. Специализируется на диагностике "
            "и лечении заболеваний внутренних органов."
        ),
        "experience_years": 15,
        "avatar_url": "https://i.pravatar.cc/150?img=12",
    },
    {
        "email": "petrova@medbook.dev",
        "password": "doctor12345",
        "full_name": "Петрова Анна Сергеевна",
        "specialization": "Кардиолог",
        "bio": (
            "Врач-кардиолог, кандидат медицинских наук. Проводит диагностику "
            "и лечение сердечно-сосудистых заболеваний."
        ),
        "experience_years": 12,
        "avatar_url": "https://i.pravatar.cc/150?img=45",
    },
    {
        "email": "sidorov@medbook.dev",
        "password": "doctor12345",
        "full_name": "Сидоров Пётр Алексеевич",
        "specialization": "Невролог",
        "bio": (
            "Врач-невролог с 8-летним опытом. Специализируется на лечении "
            "головных болей и заболеваний нервной системы."
        ),
        "experience_years": 8,
        "avatar_url": "https://i.pravatar.cc/150?img=68",
    },
]


async def seed_specializations(session) -> dict[str, Specialization]:
    """Create specializations if they don't exist. Returns name -> Specialization map."""
    repo = SpecializationRepository(session)
    result: dict[str, Specialization] = {}
    for spec_data in SPECIALIZATIONS:
        existing = await repo.get_by_name(spec_data["name"])
        if existing is not None:
            print(f"  [=] Специализация '{spec_data['name']}' уже существует")
            result[spec_data["name"]] = existing
        else:
            spec = await repo.create(
                name=spec_data["name"],
                description=spec_data["description"],
            )
            print(f"  [+] Создана специализация '{spec_data['name']}'")
            result[spec_data["name"]] = spec
    return result


async def seed_doctors(session, specs: dict[str, Specialization]) -> list[tuple[Doctor, str]]:
    """Create doctors if they don't exist. Returns list of (Doctor, full_name) tuples."""
    user_repo = UserRepository(session)
    doctor_repo = DoctorRepository(session)
    result: list[tuple[Doctor, str]] = []

    for doc_data in DOCTORS:
        email = doc_data["email"].lower()
        existing_user = await user_repo.get_by_email(email)
        if existing_user is not None:
            doctor = await doctor_repo.get_by_user_id(existing_user.id)
            if doctor is not None:
                print(f"  [=] Врач '{doc_data['full_name']}' уже существует")
                result.append((doctor, doc_data["full_name"]))
                continue
            print(f"  [!] Пользователь {email} существует, но без профиля врача — пропускаем")
            continue

        user = await user_repo.create(
            email=email,
            password_hash=hash_password(doc_data["password"]),
            full_name=doc_data["full_name"],
            role=UserRole.DOCTOR,
            is_active=True,
        )
        spec = specs[doc_data["specialization"]]
        doctor = await doctor_repo.create(
            user_id=user.id,
            specialization_id=spec.id,
            bio=doc_data["bio"],
            experience_years=doc_data["experience_years"],
            avatar_url=doc_data["avatar_url"],
        )
        print(f"  [+] Создан врач '{doc_data['full_name']}' ({doc_data['specialization']})")
        result.append((doctor, doc_data["full_name"]))

    return result


async def seed_slots(session, doctors: list[tuple[Doctor, str]]) -> None:
    """Create schedule slots for each doctor for the next 2 weeks (weekdays only)."""
    slot_repo = SlotRepository(session)
    now = datetime.now(UTC)
    today = now.date()

    start_date = today + timedelta(days=1)
    end_date = start_date + timedelta(days=13)

    work_start = time(9, 0)
    work_end = time(18, 0)
    break_start = time(13, 0)
    break_end = time(14, 0)
    slot_duration = timedelta(minutes=30)

    total_created = 0
    total_skipped = 0

    for doctor, full_name in doctors:
        doctor_created = 0
        doctor_skipped = 0

        current_date = start_date
        while current_date <= end_date:
            # Skip weekends (isoweekday: 6=Sat, 7=Sun)
            if current_date.isoweekday() in (6, 7):
                current_date += timedelta(days=1)
                continue

            day_start = datetime.combine(current_date, work_start, tzinfo=UTC)
            day_end = datetime.combine(current_date, work_end, tzinfo=UTC)
            b_start = datetime.combine(current_date, break_start, tzinfo=UTC)
            b_end = datetime.combine(current_date, break_end, tzinfo=UTC)

            cursor = day_start
            while cursor + slot_duration <= day_end:
                slot_start = cursor
                slot_end = cursor + slot_duration
                cursor = slot_end

                # Skip break
                if slot_start < b_end and slot_end > b_start:
                    continue

                overlap = await slot_repo.find_overlapping(doctor.id, slot_start, slot_end)
                if overlap is not None:
                    doctor_skipped += 1
                    continue

                await slot_repo.create(
                    doctor_id=doctor.id,
                    start_time=slot_start,
                    end_time=slot_end,
                    is_booked=False,
                )
                doctor_created += 1

            current_date += timedelta(days=1)

        print(f"  [+] {full_name}: создано {doctor_created} слотов, пропущено {doctor_skipped}")
        total_created += doctor_created
        total_skipped += doctor_skipped

    print(f"\n  Итого: создано {total_created}, пропущено {total_skipped}")


async def main() -> None:
    """Run the seed script."""
    print("=" * 60)
    print("MedBook API — seed data")
    print("=" * 60)

    session_maker = create_quiet_session_maker()
    async with session_maker() as session:
        print("\n[1/3] Специализации...")
        specs = await seed_specializations(session)
        await session.commit()

        print("\n[2/3] Врачи...")
        doctors = await seed_doctors(session, specs)
        await session.commit()

        print("\n[3/3] Слоты на 2 недели вперёд...")
        await seed_slots(session, doctors)
        await session.commit()

    print("\n" + "=" * 60)
    print("[+] Seed завершён успешно")
    print("=" * 60)
    print("\nДанные для входа врачей (пароль у всех одинаковый):")
    for doc in DOCTORS:
        role = doc["specialization"]
        name = doc["full_name"]
        email = doc["email"]
        pwd = doc["password"]
        print(f"  {email} / {pwd}  ({name}, {role})")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Прервано пользователем")
        sys.exit(1)
