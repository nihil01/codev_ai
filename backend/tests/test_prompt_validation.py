import pytest
from pydantic import ValidationError

from models.auxilary_models import AdminBotPromptUpdate, CommentPromptUpdate


@pytest.mark.parametrize("model", [AdminBotPromptUpdate, CommentPromptUpdate])
def test_prompt_update_rejects_whitespace_only_prompt(model):
    with pytest.raises(ValidationError):
        model(system_prompt=" \n\t ")


@pytest.mark.parametrize("model", [AdminBotPromptUpdate, CommentPromptUpdate])
def test_prompt_update_normalizes_prompt_and_title(model):
    payload = model(system_prompt="  Keep this prompt  ", title="  Prompt title  ")

    assert payload.system_prompt == "Keep this prompt"
    assert payload.title == "Prompt title"
