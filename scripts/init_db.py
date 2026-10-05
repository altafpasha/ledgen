import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import logger
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import async_engine, AsyncSessionLocal


async def init_db():
    logger.info("Initializing database schema...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        stmt = select(User).where(User.email == settings.admin_email.lower().strip())
        res = await session.execute(stmt)
        admin = res.scalars().first()
        if not admin:
            admin_user = User(
                email=settings.admin_email.lower().strip(),
                hashed_password=hash_password(settings.admin_password),
                full_name="Platform Administrator",
                is_active=True,
                is_superuser=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Created default admin account: {settings.admin_email}")
        else:
            logger.info(f"Admin account already exists: {settings.admin_email}")


if __name__ == "__main__":
    asyncio.run(init_db())
