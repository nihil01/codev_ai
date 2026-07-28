# Codev

Private course-platform CRM for one operator, with Instagram, WhatsApp, TikTok and LinkedIn workflows.

See [PROJECT_SCOPE.md](PROJECT_SCOPE.md) for the locked product decisions and isolation rules.

## Local runtime

```bash
cp .env.docker.example .env.docker
cp .env.docker .env
# Replace all placeholder secrets before starting.
docker compose up -d --build
```

Default loopback endpoints:

- Frontend: `http://127.0.0.1:8300`
- Backend: `http://127.0.0.1:8301`
- PostgreSQL: `127.0.0.1:5465`

The generated local `.env` and `.env.docker` files are ignored by Git.
