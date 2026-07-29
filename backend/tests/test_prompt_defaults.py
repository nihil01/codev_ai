import inspect
import re
from pathlib import Path

from services.automation import DEFAULT_REMINDER_MESSAGE, generate_contextual_reminder
from services.chat_runtime import get_company_runtime
from services.prompt_defaults import DEFAULT_COMMENT_SYSTEM_PROMPT_AZ, DEFAULT_SYSTEM_PROMPT_AZ


CYRILLIC = re.compile(r"[А-Яа-яЁё]")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_default_system_prompts_are_azerbaijani_only() -> None:
    for prompt in (DEFAULT_SYSTEM_PROMPT_AZ, DEFAULT_COMMENT_SYSTEM_PROMPT_AZ):
        assert "Yalnız Azərbaycan dilində" in prompt
        assert not CYRILLIC.search(prompt)


def test_reminder_fallback_and_generation_instructions_are_azerbaijani_only() -> None:
    source = inspect.getsource(generate_contextual_reminder)
    assert "Yalnız Azərbaycan dilində" in source
    assert "dilində cavab" not in source
    assert not CYRILLIC.search(DEFAULT_REMINDER_MESSAGE)
    assert not CYRILLIC.search(source)


def test_runtime_selects_only_the_latest_prompt() -> None:
    source = inspect.getsource(get_company_runtime)
    assert "left join lateral" in source
    assert "order by version desc, updated_at desc" in source
    assert "limit 1" in source


def test_corrective_migration_preserves_custom_prompt_precedence() -> None:
    migrations = PROJECT_ROOT / "backend/infra/flyway/sql"
    translation = (migrations / "V3_26__azerbaijani_default_prompts.sql").read_text(encoding="utf-8")
    correction = (migrations / "V3_28__demote_migrated_default_prompts.sql").read_text(encoding="utf-8")

    translated_prompt = re.search(r"set prompt_text = '([^']+)'", translation, re.IGNORECASE)
    corrected_prompt = re.search(r"WHERE prompt_text = '([^']+)'", correction)
    assert translated_prompt is not None
    assert corrected_prompt is not None
    assert corrected_prompt.group(1) == translated_prompt.group(1)
    assert "SET version = 0" in correction
    assert "title =" not in correction


def test_reminder_migration_updates_only_the_historical_default() -> None:
    migrations = PROJECT_ROOT / "backend/infra/flyway/sql"
    original = (migrations / "V3_16__automation_settings_and_calendar.sql").read_text(encoding="utf-8")
    correction = (migrations / "V3_29__azerbaijani_reminder_defaults.sql").read_text(encoding="utf-8")

    old_default = re.search(r"client_reminder_message text not null default '([^']+)'", original)
    update_predicate = re.search(r"WHERE client_reminder_message = '([^']+)'", correction)
    new_default = re.search(r"SET DEFAULT '([^']+)'", correction)
    assert old_default is not None
    assert update_predicate is not None
    assert new_default is not None
    assert update_predicate.group(1) == old_default.group(1)
    assert new_default.group(1) == DEFAULT_REMINDER_MESSAGE
