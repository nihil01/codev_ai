from services.openai_messaging import (
    PRODUCT_DESCRIPTION_LANGUAGES,
    normalize_product_description_language,
    product_photo_description_fallback,
)


def test_product_description_language_defaults_to_az():
    assert normalize_product_description_language(None) == "az"
    assert normalize_product_description_language("AZ") == "az"
    assert normalize_product_description_language("unsupported") == "az"


def test_product_description_prompts_cover_supported_languages():
    assert set(PRODUCT_DESCRIPTION_LANGUAGES) == {"az", "en", "ru"}
    assert "Azərbaycan" in PRODUCT_DESCRIPTION_LANGUAGES["az"][1]
    assert "English" in PRODUCT_DESCRIPTION_LANGUAGES["en"][1]
    assert "русском" in PRODUCT_DESCRIPTION_LANGUAGES["ru"][1]


def test_product_description_fallback_matches_requested_language():
    assert "fotonu" in product_photo_description_fallback("az")
    assert "could not" in product_photo_description_fallback("en")
    assert "не смог" in product_photo_description_fallback("ru")
