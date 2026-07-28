from sqlalchemy import select

from models.models import InstagramCompany, InstagramSystemPrompt, InstagramToken


async def get_company_runtime(session, instagram_account_id: str):
    result = await session.execute(
        select(
            InstagramCompany.id,
            InstagramCompany.instagram_account_id,
            InstagramToken.access_token,
            InstagramSystemPrompt.prompt_text,
        )
        .join(
            InstagramToken,
            (InstagramToken.company_id == InstagramCompany.id) & InstagramToken.is_active.is_(True),
        )
        .outerjoin(InstagramSystemPrompt, InstagramSystemPrompt.company_id == InstagramCompany.id)
        .where(InstagramCompany.instagram_account_id == instagram_account_id)
        .limit(1)
    )
    return result.mappings().first()
