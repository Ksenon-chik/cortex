#!/usr/bin/env python3
"""
Create the first admin user (or promote an existing one).

Usage
-----
From the repository root (or inside the running container):

    # Create a brand-new admin account
    PYTHONPATH=/app python scripts/create_admin.py \
        --email admin@example.com \
        --password supersecret

    # Promote an already-registered user to admin
    PYTHONPATH=/app python scripts/create_admin.py \
        --email existing@example.com \
        --promote-only

Environment
-----------
The script reads DATABASE_URL from the environment (or falls back to the
default in app.config.Settings).  Set it before running if needed:

    export DATABASE_URL=postgresql://user:pass@host:5432/cortex
"""

import argparse
import asyncio
import sys

# Ensure the app package is importable when running from the backend/ dir.
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.user import User
from app.services.auth import hash_password


async def create_or_promote_admin(email: str, password: str | None, promote_only: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if user:
            if not promote_only and password:
                print(f"User '{email}' already exists — updating password and granting admin.")
                user.hashed_password = hash_password(password)
            else:
                print(f"User '{email}' already exists — granting admin privileges.")
            user.is_admin = True
            user.whitelisted = True
            user.is_active = True
        else:
            if promote_only:
                print(f"Error: user '{email}' not found. Remove --promote-only to create them.", file=sys.stderr)
                await engine.dispose()
                sys.exit(1)
            if not password:
                print("Error: --password is required when creating a new admin user.", file=sys.stderr)
                await engine.dispose()
                sys.exit(1)
            print(f"Creating new admin user '{email}'.")
            user = User(
                email=email.lower(),
                hashed_password=hash_password(password),
                is_admin=True,
                whitelisted=True,
                is_active=True,
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)
        print(f"Done. Admin user id={user.id} email={user.email}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote a Cortex admin user.")
    parser.add_argument("--email", required=True, help="Admin user e-mail address")
    parser.add_argument("--password", default=None, help="Password (required for new users)")
    parser.add_argument(
        "--promote-only",
        action="store_true",
        help="Only promote an existing user; do not create a new one",
    )
    args = parser.parse_args()

    asyncio.run(create_or_promote_admin(args.email, args.password, args.promote_only))


if __name__ == "__main__":
    main()
