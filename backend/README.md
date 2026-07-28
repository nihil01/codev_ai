# AI CRM Bot Platform

Multi-tenant CRM + automated Instagram/WhatsApp bot scaffold.

## What this project proves

- Every customer has an isolated CRM space (`tenant_id`).
- Instagram/WhatsApp webhooks are normalized into one internal message model.
- Incoming webhook events are mapped to the correct tenant through `channels.platform + channels.external_account_id`.
- Duplicate external messages are ignored safely.
- Bot settings, system prompt and conversation state are tenant-scoped.
- FastAPI backend + PostgreSQL + Redis + React CRM run directly on explicit IP/ports.

## Run locally by IP/ports

```bash
# Backend
cd backend
uv venv
uv pip install -e '.[dev]'
uv run uvicorn src.main:app --host 0.0.0.0 --port 8100

# Frontend
cd ../frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

- CRM: http://<server-ip>:5174
- API: http://<server-ip>:8100/docs
- PostgreSQL/Redis: standalone services configured through environment variables

## Local backend dev without Docker

```bash
cd backend
uv venv
uv pip install -e '.[dev]'
uv run pytest
uv run uvicorn app.main:app --reload
```

Default local DB is SQLite (`sqlite:///./dev.db`) so smoke tests don't require Postgres. Production/staging should point `DATABASE_URL` at standalone PostgreSQL.

## Webhook tenant mapping

Meta webhook payloads contain account/page/phone identifiers. We store those identifiers in `channels.external_account_id`.

Example:

```json
{
  "platform": "instagram",
  "account_id": "ig_account_001",
  "conversation_id": "dm_42",
  "message_id": "msg_100",
  "sender_id": "instagram_user_5",
  "text": "Привет, есть доставка?"
}
```

The backend resolves:

```text
platform + account_id -> channel -> tenant_id -> tenant CRM space
```

Then it stores:

- raw webhook event;
- contact;
- conversation;
- inbound message;
- placeholder bot reply if bot is enabled and no operator owns the chat.

This is the core sync mechanism.
