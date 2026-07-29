from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.deps import get_db
from services.zernio_webhooks import persist_zernio_webhook_event
from config.app_config import settings

router = APIRouter(tags=["zernio-webhooks"])
logger = logging.getLogger(__name__)


@router.get("/zernio")
@router.get("/zernio/{path:path}")
async def zernio_webhook_health(request: Request, path: str = "") -> Any:
    if path == "callback":
        platform = str(request.query_params.get("platform") or "social").strip().lower()
        account_id = request.query_params.get("accountId") or request.query_params.get("account_id") or ""
        safe_account_id = html.escape(account_id, quote=True)
        platform_label = {
            "instagram": "Instagram",
            "whatsapp": "WhatsApp",
            "tiktok": "TikTok",
            "linkedin": "LinkedIn",
        }.get(platform, "Social network")
        safe_account_line = f"<p class='muted'>Account ID: <code>{safe_account_id}</code></p>" if safe_account_id else ""
        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="az">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{platform_label} qoşuldu</title>
                <style>
                  body {{
                    margin: 0;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                    background: #f8fafc;
                    color: #0f172a;
                  }}
                  .card {{
                    width: min(92vw, 520px);
                    border: 1px solid #dbeafe;
                    border-radius: 28px;
                    background: white;
                    box-shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
                    padding: 32px;
                    text-align: center;
                  }}
                  .icon {{
                    width: 72px;
                    height: 72px;
                    border-radius: 999px;
                    display: grid;
                    place-items: center;
                    margin: 0 auto 18px;
                    background: #dcfce7;
                    color: #15803d;
                    font-size: 42px;
                    font-weight: 900;
                  }}
                  h1 {{ margin: 0; font-size: 28px; line-height: 1.15; }}
                  p {{ margin: 12px 0 0; line-height: 1.65; color: #475569; }}
                  .muted {{ color: #64748b; font-size: 13px; }}
                  code {{ background: #f1f5f9; border-radius: 8px; padding: 3px 6px; }}
                  button {{
                    margin-top: 24px;
                    border: 0;
                    border-radius: 999px;
                    background: #2563eb;
                    color: white;
                    padding: 12px 20px;
                    font-weight: 800;
                    cursor: pointer;
                  }}
                </style>
              </head>
              <body>
                <main class="card">
                  <div class="icon">✓</div>
                  <h1>{platform_label} qoşuldu</h1>
                  <p>Bağlantı uğurla tamamlandı. CRM panelinə qayıdıb statusu yeniləyə bilərsiniz.</p>
                  {safe_account_line}
                  <button onclick="window.close(); setTimeout(() => location.href='/', 150)">CRM panelinə qayıt</button>
                </main>
              </body>
            </html>
            """
        )

    return {"ok": True, "provider": "zernio", "path": path}



def verify_payload(headers, body: bytes) -> bool:
    signature = headers.get("X-Zernio-Signature")
    secret = settings.zernio_webhook_secret

    if not signature or not secret:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    # если Zernio шлет формат sha256=xxxx
    if signature.startswith("sha256="):
        signature = signature.removeprefix("sha256=")

    return hmac.compare_digest(signature, expected)

@router.post("/zernio")
@router.post("/zernio/{path:path}")
async def zernio_webhook(
    request: Request,
    path: str = "",
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:

    headers = request.headers
    body = await request.body()

    if not verify_payload(headers, body):
        raise HTTPException(status_code=400, detail="Invalid signature!")

    if not body:
        payload: dict[str, Any] = {}
    else:
        try:
            parsed_payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Zernio webhook invalid JSON path=%s", path, exc_info=True)
            raise HTTPException(status_code=400, detail="Invalid JSON webhook payload") from exc

        if isinstance(parsed_payload, dict):
            payload = parsed_payload
        else:
            payload = {"value": parsed_payload}

    if path:
        payload.setdefault("_zernio_webhook_path", path)

    stored = await persist_zernio_webhook_event(db, payload=payload, headers=dict(request.headers))
    return {
        "ok": True,
        "provider": "zernio",
        "handled": 0,
        "skipped": 1,
        "stored": True,
        **stored,
    }
