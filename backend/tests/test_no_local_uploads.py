from fastapi.routing import Mount

from main import app


def test_backend_does_not_mount_local_uploads_route():
    mounted_paths = {route.path for route in app.routes if isinstance(route, Mount)}

    assert "/uploads" not in mounted_paths
