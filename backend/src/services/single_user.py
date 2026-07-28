import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from config.app_config import settings
from db.db import SessionLocal
from models.models import User
from services.auth import hash_password, verify_password
from services.company import ensure_user_company
from services.subscriptions import ensure_company_subscription

logger = logging.getLogger(__name__)


async def ensure_single_user() -> User | None:
    """Provision the configured Codev owner and disable every other account.

    The password is environment-owned. Changing SINGLE_USER_PASSWORD and
    restarting Codev rotates the login without putting credentials in Git.
    """
    email = settings.single_user_email.strip().lower()
    password = settings.single_user_password

    if not email and not password:
        logger.warning("Single-user provisioning is disabled: credentials are not configured")
        return None
    if not email or not password:
        raise RuntimeError("SINGLE_USER_EMAIL and SINGLE_USER_PASSWORD must be configured together")
    if len(password) < 12:
        raise RuntimeError("SINGLE_USER_PASSWORD must contain at least 12 characters")

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email).limit(1))
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=hash_password(password),
                role="company_user",
                instagram_company_id=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            await db.flush()
        else:
            user.role = "company_user"
            user.is_active = True
            user.updated_at = now
            if not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)

        await db.commit()
        await db.refresh(user)

        company_id = await ensure_user_company(db, user, settings.single_user_display_name)
        await ensure_company_subscription(db, company_id, "full")
        await db.execute(
            update(User)
            .where(User.id != user.id, User.is_active.is_(True))
            .values(is_active=False, updated_at=now)
        )
        await db.commit()
        await db.refresh(user)

        logger.info("Single Codev owner is ready: user_id=%s company_id=%s", user.id, company_id)
        return user
