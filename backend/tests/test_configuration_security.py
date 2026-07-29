from pathlib import Path


CONFIG_PATH = Path(__file__).parents[1] / "src" / "config" / "app_config.py"
COMPOSE_PATH = Path(__file__).parents[2] / "docker-compose.yml"


def test_configuration_has_no_embedded_provider_credentials() -> None:
    source = CONFIG_PATH.read_text(encoding="utf-8")

    forbidden_defaults = (
        'TELEGRAM_BOT_TOKEN", "7',
        'OPENAI_API_KEY", "sk-',
        'ZERNIO_KEY", "sk_',
        'OBJECT_STORAGE_ACCESS_KEY_ID", "7',
        'OBJECT_STORAGE_SECRET_ACCESS_KEY", "8',
    )

    assert not any(value in source for value in forbidden_defaults)


def test_codev_compose_is_isolated_from_integrator_runtime() -> None:
    source = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "ai-crm-bot_default" not in source
    assert "ai-crm-bot_postgres_data" not in source
    assert "127.0.0.1:8200:80" not in source
    assert "127.0.0.1:8201:8000" not in source


def test_codev_compose_uses_single_dotenv_source() -> None:
    source = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "- ./.env\n" in source
    assert ".env.docker" not in source
