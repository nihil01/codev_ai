
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Import config
sys.path.insert(0, '/var/www/instagram_assistant/ai-crm-bot/backend/src')

from config.app_config import settings
from services.auth import hash_password


async def init_admin():
    """Initialize the first admin user"""
    print(settings.database_url)
    engine = create_async_engine(settings.database_url, echo=False, future=True)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if any admin exists
            result = await session.execute(
                text("SELECT COUNT(*) as cnt FROM users WHERE role = 'admin'")
            )
            count = result.scalar()
            
            if count and count > 0:
                print(f"✓ Admin user already exists ({count} admin(s) found)")
                return
            
            # Get admin credentials
            email = input("Enter admin email: ").strip()
            if not email:
                print("✗ Email is required")
                return
            
            password = input("Enter admin password: ").strip()
            if not password or len(password) < 6:
                print("✗ Password must be at least 6 characters")
                return
            
            confirm_password = input("Confirm password: ").strip()
            if password != confirm_password:
                print("✗ Passwords don't match")
                return
            
            # Create admin user
            admin_id = uuid.uuid4()
            password_hash = hash_password(password)
            now = datetime.now(timezone.utc)
            
            await session.execute(
                text("""
                    INSERT INTO users 
                    (id, email, password_hash, role, company_id, is_active, created_at, updated_at)
                    VALUES (:id, :email, :password_hash, 'admin', NULL, true, :created_at, :updated_at)
                """),
                {
                    "id": admin_id,
                    "email": email,
                    "password_hash": password_hash,
                    "created_at": now,
                    "updated_at": now
                }
            )
            
            await session.commit()
            
            print(f"\n✓ Admin user created successfully!")
            print(f"  Email: {email}")
            print(f"  Role: admin")
            print(f"\nNow you can login at http://localhost:5174 (or your app URL)")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_admin())

