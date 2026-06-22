import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, Base, AsyncSessionLocal
from app.models import User, Account
from app.security import get_password_hash

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) #для тестов чистым каждый раз
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Тестовый пользователь
        user = User(
            id = 1,
            email="user@test.com",
            full_name="Test User",
            hashed_password=get_password_hash("user123"),
            is_admin=False
        )
        # Тестовый администратор 
        admin = User(
            id = 2,
            email="admin@test.com",
            full_name="Super Admin",
            hashed_password=get_password_hash("admin123"),
            is_admin=True
        )
        
        session.add_all([admin,user])
        await session.commit()
        await session.refresh(user)

        # Счет для тестового пользователя с id = 1
        account = Account(id=1, user_id=user.id, balance=0.0)
        session.add(account)
        await session.commit()
        
    print("Database initialized successfully with test user, admin, and account!")

if __name__ == "__main__":
    asyncio.run(init_db())