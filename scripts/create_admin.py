"""CLI script to create an admin user.

Usage:
    uv run python scripts/create_admin.py
    uv run python scripts/create_admin.py --email admin@clinic.ru --password secret123 --name "Админ"
"""

import argparse
import asyncio
import sys

from app.core.security import hash_password
from app.db.session import create_quiet_session_maker
from app.models.user import UserRole
from app.repositories.user import UserRepository


async def create_admin(email: str, password: str, full_name: str) -> None:
    """Create an admin user in the database."""
    session_maker = create_quiet_session_maker()
    async with session_maker() as session:
        repo = UserRepository(session)

        email_normalized = email.lower()
        if await repo.email_exists(email_normalized):
            print(f"[!] Пользователь с email {email_normalized} уже существует.")
            sys.exit(1)

        user = await repo.create(
            email=email_normalized,
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        await session.commit()
        print("[+] Админ создан:")
        print(f"    id:    {user.id}")
        print(f"    email: {user.email}")
        print(f"    name:  {user.full_name}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars)")
    parser.add_argument("--name", required=True, help="Admin full name")
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    if len(args.password) < 8:
        print("[!] Пароль должен содержать минимум 8 символов.")
        sys.exit(1)
    asyncio.run(create_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
