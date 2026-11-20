import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from scripts.check_pcd_import import ImportCheckError, check_import


class _ProfilarrHandler(BaseHTTPRequestHandler):
    import_complete: ClassVar[bool] = True
    linked_repository: ClassVar[dict[str, str] | None] = None

    def do_GET(self) -> None:
        if self.path == "/api/v1/health":
            is_ready = self.linked_repository is None or self.import_complete
            body = {"status": "healthy" if is_ready else "degraded"}
        elif self.path == "/api/v1/status":
            body = {
                "databases": [
                    {
                        "id": 42,
                        "lastSyncedAt": None,
                        "counts": {
                            "customFormats": 1 if self.import_complete else 0,
                            "qualityProfiles": 1 if self.import_complete else 0,
                        },
                    }
                ]
            }
        else:
            self.send_error(404)
            return
        self._send_json(200, body)

    def do_POST(self) -> None:
        self.linked_repository = json.loads(
            self.rfile.read(int(self.headers["Content-Length"]))
        )
        type(self).linked_repository = self.linked_repository
        self._send_json(201, {"id": 42})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@pytest.fixture
def profilarr_server():
    _ProfilarrHandler.import_complete = True
    _ProfilarrHandler.linked_repository = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ProfilarrHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_check_import_accepts_compiled_pcd_without_sync_timestamp(
    profilarr_server: str,
) -> None:
    check_import(
        profilarr_server,
        "test-api-key",
        "https://github.com/example/trash-pcd",
        "test-branch",
        readiness_timeout=1,
        import_timeout=1,
        poll_interval=0.001,
    )

    assert _ProfilarrHandler.linked_repository == {
        "name": "PCD import acceptance",
        "repository_url": "https://github.com/example/trash-pcd",
        "branch": "test-branch",
    }


def test_check_import_fails_if_import_never_completes(profilarr_server: str) -> None:
    _ProfilarrHandler.import_complete = False

    with pytest.raises(ImportCheckError, match="did not complete"):
        check_import(
            profilarr_server,
            "test-api-key",
            "https://github.com/example/trash-pcd",
            "test-branch",
            readiness_timeout=1,
            import_timeout=0.01,
            poll_interval=0.001,
        )
