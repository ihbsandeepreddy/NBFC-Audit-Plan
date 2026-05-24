"""Seed initial admin user and sample data"""
import asyncio
import uuid
from core.database import AsyncSessionLocal, init_db
from models.user import User, UserRole
from core.security import hash_password


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        # Create default admin user
        result = await db.execute(select(User).where(User.email == "admin@nbfc.local"))
        if not result.scalar_one_or_none():
            admin = User(
                id=uuid.uuid4(),
                email="admin@nbfc.local",
                full_name="Admin User",
                hashed_password=hash_password("admin123"),
                role=UserRole.MANAGER,
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)

            # Create sample team members
            for email, name, role in [
                ("partner@nbfc.local", "Engagement Partner", UserRole.PARTNER),
                ("manager@nbfc.local", "Engagement Manager", UserRole.MANAGER),
                ("senior1@nbfc.local", "Senior Auditor 1", UserRole.SENIOR_AUDITOR),
                ("senior2@nbfc.local", "Senior Auditor 2", UserRole.SENIOR_AUDITOR),
                ("it@nbfc.local", "IT Auditor", UserRole.IT_AUDITOR),
            ]:
                r = await db.execute(select(User).where(User.email == email))
                if not r.scalar_one_or_none():
                    u = User(id=uuid.uuid4(), email=email, full_name=name,
                             hashed_password=hash_password("password123"), role=role, is_active=True)
                    db.add(u)

            await db.commit()
            print("Seed data created successfully.")
        else:
            print("Seed data already exists.")


if __name__ == "__main__":
    asyncio.run(seed())
