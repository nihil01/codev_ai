from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.deps import get_db
from services.chat_runtime import MAX_PROMPT_LENGTH, set_active_prompt_by_username

static_router = APIRouter()

BASE_HTML_STYLE = """
<style>
    :root {
        --bg: #f6f8fb;
        --card: #ffffff;
        --text: #172033;
        --muted: #5b6475;
        --border: #e4e9f2;
        --accent: #2563eb;
        --accent-hover: #1d4ed8;
        --shadow: 0 10px 30px rgba(23, 32, 51, 0.08);
    }

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        padding: 32px 16px;
        font-family: Arial, Helvetica, sans-serif;
        background: var(--bg);
        color: var(--text);
    }

    .container {
        max-width: 860px;
        margin: 0 auto;
    }

    .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 32px;
        box-shadow: var(--shadow);
    }

    h1 {
        margin: 0 0 20px;
        font-size: 32px;
        line-height: 1.2;
    }

    h2 {
        margin: 28px 0 12px;
        font-size: 20px;
        line-height: 1.3;
    }

    p {
        margin: 0 0 14px;
        line-height: 1.7;
        color: var(--muted);
        font-size: 16px;
    }

    ul {
        margin: 0 0 16px 22px;
        padding: 0;
        color: var(--muted);
        line-height: 1.7;
    }

    li {
        margin-bottom: 8px;
    }

    a {
        color: var(--accent);
        text-decoration: none;
    }

    a:hover {
        color: var(--accent-hover);
        text-decoration: underline;
    }

    .badge {
        display: inline-block;
        margin-bottom: 16px;
        padding: 8px 12px;
        border-radius: 999px;
        background: #e8f0ff;
        color: var(--accent);
        font-weight: 700;
        font-size: 13px;
    }

    .footer {
        margin-top: 28px;
        padding-top: 20px;
        border-top: 1px solid var(--border);
        font-size: 14px;
        color: var(--muted);
    }

    .note {
        margin-top: 18px;
        padding: 14px 16px;
        background: #f8fafc;
        border: 1px solid var(--border);
        border-radius: 12px;
        color: var(--muted);
    }

    .btn {
        display: inline-block;
        margin-top: 8px;
        padding: 12px 18px;
        border-radius: 12px;
        background: var(--accent);
        color: #fff !important;
        font-weight: 700;
        text-decoration: none;
    }

    .btn:hover {
        background: var(--accent-hover);
        text-decoration: none;
    }

    code {
        background: #f1f5f9;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 14px;
        color: #0f172a;
    }

    @media (max-width: 640px) {
        .card {
            padding: 22px;
        }

        h1 {
            font-size: 26px;
        }

        h2 {
            font-size: 18px;
        }
    }
</style>
"""


@static_router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return f"""
    <html lang="az">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Məxfilik Siyasəti</title>
        {BASE_HTML_STYLE}
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="badge">Məxfilik Siyasəti</div>
                <h1>Məxfilik Siyasəti</h1>

                <p>
                    Bu xidmət Instagram Direct üzərindən istifadəçilərə avtomatik cavab vermək üçün nəzərdə tutulmuşdur.
                    Biz istifadəçi məlumatlarının qorunmasına ciddi yanaşırıq.
                </p>

                <h2>Hansı məlumatları toplayırıq</h2>
                <ul>
                    <li>Instagram istifadəçi identifikatoru (ID)</li>
                    <li>İstifadəçinin göndərdiyi mesaj məzmunu</li>
                    <li>Mesajların vaxtı və texniki sessiya məlumatları</li>
                </ul>

                <h2>Məlumatlar necə istifadə olunur</h2>
                <ul>
                    <li>İstifadəçilərə avtomatik cavab vermək üçün</li>
                    <li>Dialoqun kontekstini qorumaq üçün</li>
                    <li>Xidmətin keyfiyyətini və cavabların uyğunluğunu yaxşılaşdırmaq üçün</li>
                </ul>

                <h2>Məlumatların saxlanılması</h2>
                <p>
                    Məlumatlar xidmətin işləməsi və sessiyanın davamlılığını təmin etmək məqsədilə müəyyən müddət saxlanıla bilər.
                </p>

                <h2>Məlumatların üçüncü tərəflərlə paylaşılması</h2>
                <p>
                    Məlumatlar yalnız xidmətin texniki işləməsi üçün istifadə olunur və qanuni zərurət istisna olmaqla üçüncü tərəflərə satılmır.
                </p>

                <h2>Məlumatların silinməsi</h2>
                <p>
                    İstifadəçi öz məlumatlarının silinməsini tələb edə bilər. Bunun üçün aşağıdakı səhifədən istifadə edə bilərsiniz:
                </p>

                <a class="btn" href="/delete_data">Məlumatların silinməsi</a>

                <div class="footer">
                    Əlaqə e-poçtu: <a href="mailto:orkhanar@gmail.com">orkhanar@gmail.com</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@static_router.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return f"""
    <html lang="az">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>İstifadə Şərtləri</title>
        {BASE_HTML_STYLE}
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="badge">İstifadə Şərtləri</div>
                <h1>İstifadə Şərtləri</h1>

                <p>
                    Bu xidmətdən istifadə etməklə siz aşağıdakı şərtlərlə razılaşmış olursunuz.
                </p>

                <h2>Xidmətin təyinatı</h2>
                <p>
                    Xidmət Instagram Direct üzərindən gələn mesajlara avtomatik və ya yarı-avtomatik cavab vermək üçün istifadə olunur.
                </p>

                <h2>İstifadə qaydaları</h2>
                <ul>
                    <li>Xidmətdən qanunsuz məqsədlər üçün istifadə etmək olmaz.</li>
                    <li>İstifadəçilərə göndərilən cavablar avtomatik sistem tərəfindən formalaşdırıla bilər.</li>
                    <li>Xidmətin fəaliyyətinə müdaxilə etmək və ya onu pozmaq qadağandır.</li>
                </ul>

                <h2>Məsuliyyətin məhdudlaşdırılması</h2>
                <p>
                    Cavablar süni intellekt tərəfindən yaradıldığı üçün onların tam dəqiqliyinə hər zaman zəmanət verilmir.
                    Xidmətdən istifadənin nəticələrinə görə tam məsuliyyət istifadəçiyə aiddir.
                </p>

                <h2>Dəyişikliklər</h2>
                <p>
                    Bu şərtlər əvvəlcədən xəbərdarlıq edilmədən yenilənə bilər. Yenilənmiş versiya bu səhifədə yerləşdiriləcək.
                </p>

                <div class="footer">
                    Əlaqə e-poçtu: <a href="mailto:orkhanar@gmail.com">orkhanar@gmail.com</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@static_router.get("/delete_data", response_class=HTMLResponse)
async def delete_data_page():
    return f"""
    <html lang="az">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Məlumatların Silinməsi</title>
        {BASE_HTML_STYLE}
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="badge">Məlumatların Silinməsi</div>
                <h1>Məlumatların Silinməsi</h1>

                <p>
                    Əgər bu xidmət tərəfindən saxlanılan məlumatlarınızın silinməsini istəyirsinizsə, bunu aşağıdakı üsullarla tələb edə bilərsiniz.
                </p>

                <h2>Silinmə sorğusu necə verilir</h2>
                <ul>
                    <li>Facebook və ya Instagram hesab ayarlarında tətbiqin girişini ləğv edin</li>
                    <li>Və ya bizə e-poçt vasitəsilə sorğu göndərin:
                        <a href="mailto:orkhanar@gmail.com">orkhanar@gmail.com</a>
                    </li>
                </ul>

                <h2>Hansı məlumatlar silinir</h2>
                <ul>
                    <li>İstifadəçi identifikatorları</li>
                    <li>Mesaj tarixçəsi</li>
                    <li>Sessiya məlumatları</li>
                    <li>Tətbiq daxilində saxlanılan əlaqəli texniki məlumatlar</li>
                </ul>

                <div class="note">
                    Sorğu təsdiqləndikdən sonra məlumatlar mümkün olan ən qısa müddətdə sistemdən silinəcək.
                </div>

                <div class="footer">
                    Əlaqə e-poçtu: <a href="mailto:orkhanar@gmail.com">orkhanar@gmail.com</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """