import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.deps import get_db
from services.company import deauthorize_instagram_company, upsert_company, check_profile_exists
from services.instagram_oauth import exchange_code_for_token, get_me, exchange_long_lived

router = APIRouter()
logger = logging.getLogger(__name__)


class StatusResponse(BaseModel):
    status: str


def _oauth_result_html(success: bool, message: str) -> HTMLResponse:
    title = "Instagram подключен" if success else "Instagram не подключен"
    color = "#059669" if success else "#dc2626"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="ru">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>{title}</title>
            <style>
              body {{ font-family: Inter, system-ui, sans-serif; background: #f8fafc; color: #0f172a; display: grid; min-height: 100vh; place-items: center; margin: 0; }}
              main {{ max-width: 560px; margin: 24px; border: 1px solid #e2e8f0; border-radius: 28px; background: white; padding: 32px; box-shadow: 0 20px 50px rgba(15, 23, 42, .08); }}
              h1 {{ color: {color}; margin: 0 0 12px; }}
              p {{ line-height: 1.7; color: #475569; }}
              button {{ border: 0; border-radius: 16px; background: #020617; color: white; padding: 12px 18px; font-weight: 800; cursor: pointer; }}
            </style>
          </head>
          <body>
            <main>
              <h1>{title}</h1>
              <p>{message}</p>
              <button onclick="window.close()">Закрыть окно</button>
            </main>
          </body>
        </html>
        """,
        status_code=200 if success else 400,
    )


@router.get("/auth/callback", response_class=HTMLResponse)
async def callback(
    code: str = Query(...),
    state: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user_id: uuid.UUID | None = None
    if state:
        try:
            user_id = uuid.UUID(state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc

    try:
        api_token = await exchange_code_for_token(code)
        print(api_token)
        long_lived = await exchange_long_lived(api_token["access_token"])

        profile = await get_me(long_lived["access_token"])

        print(f"Profile {profile}")

        # if not profile.get("username") or not await check_profile_exists(profile.get("username")):
        #     logger.warning("OAuth callback failed detail=%s", "Not existing company provided!")
        #     return _oauth_result_html(
        #         False,
        #         "OAuth не завершился успешно, поэтому Instagram интеграция не была активирована. Попробуй подключить другой аккаунт.",
        #     )

        instagram_user_id = str(profile.get("user_id") or profile.get("id") or api_token.get("user_id"))

        linked_company_id = await upsert_company(
            db,
            user_id=user_id,
            instagram_account_id=instagram_user_id,
            username=profile.get("username"),
            name=profile.get("name") or profile.get("username"),
            token=long_lived["access_token"],
            expires_in=long_lived["expires_in"],
            account_type=profile.get("account_type"),
            profile_picture_url=profile.get("profile_picture_url"),
        )
    except HTTPException as exc:
        logger.warning("OAuth callback failed status=%s detail=%s", exc.status_code, exc.detail)
        return _oauth_result_html(
            False,
            "OAuth не завершился успешно, поэтому Instagram интеграция не была активирована. Попробуй подключить аккаунт еще раз.",
        )
    except Exception:
        logger.exception("OAuth callback failed unexpectedly")
        return _oauth_result_html(
            False,
            "OAuth не завершился успешно, поэтому Instagram интеграция не была активирована. Попробуй подключить аккаунт еще раз.",
        )

    logger.info("OAuth callback completed company_id=%s instagram_account_id=%s", linked_company_id, instagram_user_id)
    return _oauth_result_html(
        True,
        "OAuth прошел успешно. Instagram бот активирован для компании. Вернись в CRM и обнови страницу/сессию.",
    )


@router.post("/deauthorize", response_model=StatusResponse)
async def deauthorize(request: Request, db: AsyncSession = Depends(get_db)) -> StatusResponse:
    payload = await request.json()
    company_id_raw = payload.get("company_id")
    if company_id_raw:
        try:
            await deauthorize_instagram_company(db, uuid.UUID(str(company_id_raw)))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid company_id") from exc

    logger.info("Received deauthorize request")
    return StatusResponse(status="ok")


@router.post("/delete_data", response_model=StatusResponse)
async def delete_data(request: Request, db: AsyncSession = Depends(get_db)) -> StatusResponse:
    _ = await request.body()
    logger.info("Received delete_data request")
    return StatusResponse(status="ok")
