from config.app_config import settings


def test_replicate_video_model_setting_exists():
    assert isinstance(settings.replicate_video_model, str)
    assert "/" in settings.replicate_video_model
