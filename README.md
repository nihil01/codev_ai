# Codev

Private course-platform CRM for one operator, with Instagram, WhatsApp, TikTok and LinkedIn workflows.

See [PROJECT_SCOPE.md](PROJECT_SCOPE.md) for the locked product decisions and isolation rules.

## Local runtime

```bash
cp .env.example .env
# Replace all placeholder secrets before starting.
docker compose up -d --build
```

Default loopback endpoints:

- Frontend: `http://127.0.0.1:8300`
- Backend: `http://127.0.0.1:8301`
- PostgreSQL: `127.0.0.1:5465`

The local `.env` file is the single environment source used by Docker Compose and is ignored by Git.
