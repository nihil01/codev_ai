import uuid

from services.object_storage import build_object_key, normalize_public_object_url, public_object_url, sanitize_filename


def test_build_object_key_scopes_company_images_without_raw_filename_traversal():
    company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    key = build_object_key(company_id=company_id, folder="knowledge-base", filename="../My Cake.PNG")

    assert key.startswith("knowledge-base/11111111-1111-1111-1111-111111111111/")
    assert key.endswith("-my-cake.png")
    assert ".." not in key
    assert " " not in key


def test_public_object_url_prefers_public_base_url():
    assert public_object_url(
        key="knowledge-base/company/file.png",
        public_base_url="https://cdn.example.com/media/",
        endpoint_url="https://account.r2.cloudflarestorage.com",
        bucket="crm-media",
    ) == "https://cdn.example.com/media/knowledge-base/company/file.png"


def test_public_object_url_falls_back_to_endpoint_bucket_url():
    assert public_object_url(
        key="custom-products/file.png",
        public_base_url="",
        endpoint_url="https://account.r2.cloudflarestorage.com/",
        bucket="crm-media",
    ) == "https://account.r2.cloudflarestorage.com/crm-media/custom-products/file.png"


def test_sanitize_filename_keeps_safe_extension():
    assert sanitize_filename("Ürün Фото.WEBP").endswith("urun-foto.webp")
    assert sanitize_filename("bad.exe") == "file.jpg"


def test_normalize_public_object_url_rewrites_r2_api_url_to_public_url():
    from services.object_storage import ObjectStorageConfig

    config = ObjectStorageConfig(
        endpoint_url="https://8013d168b9448e95956baf4a8607a919.r2.cloudflarestorage.com",
        access_key_id="key",
        secret_access_key="secret",
        bucket="ai-assistants",
        public_base_url="https://pub-9ab9c736801b44c08e0f939a34cf42c1.r2.dev",
    )

    assert normalize_public_object_url(
        url="https://8013d168b9448e95956baf4a8607a919.r2.cloudflarestorage.com/ai-assistants/knowledge-base/company/file.jpg",
        config=config,
    ) == "https://pub-9ab9c736801b44c08e0f939a34cf42c1.r2.dev/knowledge-base/company/file.jpg"
