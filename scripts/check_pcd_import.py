import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


APP_IMAGE = "ghcr.io/dictionarry-hub/profilarr:2"
APP_PORT = 6868
READINESS_TIMEOUT = 180
IMPORT_TIMEOUT = 300
POLL_INTERVAL = 5
REQUEST_TIMEOUT = 10


class ImportCheckError(RuntimeError):
    """Raised when Profilarr cannot import and compile the PCD."""


class APIConnectionError(ImportCheckError):
    """Raised when the Profilarr API cannot be reached."""


def _validate_repository_url(repository_url: str) -> None:
    parsed_url = urlsplit(repository_url)
    segments = parsed_url.path.strip("/").split("/")
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "github.com"
        or len(segments) != 2
        or not all(segments)
    ):
        raise ImportCheckError(
            "Repository URL must be an HTTPS GitHub repository URL "
            "(https://github.com/owner/repository)"
        )


def _request_json(
    api_url: str,
    api_key: str,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    *,
    allow_service_unavailable: bool = False,
) -> tuple[int, dict[str, object]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{api_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            status_code = response.status
            response_body = response.read()
    except HTTPError as error:
        if not (allow_service_unavailable and error.code == 503):
            message = error.read().decode("utf-8", errors="replace")
            raise ImportCheckError(
                f"{method} {path} returned HTTP {error.code}: {message}"
            ) from error
        status_code = error.code
        response_body = error.read()
    except (URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise APIConnectionError(
            f"Unable to reach Profilarr at {api_url}: {reason}"
        ) from error

    try:
        response_json = json.loads(response_body)
    except json.JSONDecodeError as error:
        raise ImportCheckError(f"{method} {path} returned invalid JSON") from error
    if not isinstance(response_json, dict):
        raise ImportCheckError(f"{method} {path} returned a non-object JSON response")
    return status_code, response_json


def _wait_for_app(api_url: str, api_key: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_state = "no health response"
    while True:
        try:
            status_code, health = _request_json(
                api_url,
                api_key,
                "GET",
                "/api/v1/health",
                allow_service_unavailable=True,
            )
        except APIConnectionError as error:
            last_state = str(error)
        else:
            health_status = health.get("status")
            if status_code == 200 and health_status == "healthy":
                print("Profilarr is ready")
                return
            last_state = f"HTTP {status_code}, status {health_status!r}"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ImportCheckError(
                f"Profilarr did not become ready within {timeout:g}s: {last_state}"
            )
        time.sleep(min(POLL_INTERVAL, remaining))


def _status_for_database(
    api_url: str,
    api_key: str,
    database_id: int,
) -> dict[str, object]:
    _, status = _request_json(api_url, api_key, "GET", "/api/v1/status")
    databases = status.get("databases")
    if not isinstance(databases, list):
        raise ImportCheckError("Profilarr status response is missing its databases list")
    for database_status in databases:
        if isinstance(database_status, dict) and database_status.get("id") == database_id:
            return database_status
    raise ImportCheckError(
        f"Profilarr status response does not include database {database_id}"
    )


def _import_status(
    api_url: str,
    api_key: str,
    database_id: int,
) -> tuple[bool, str]:
    health_code, health = _request_json(
        api_url,
        api_key,
        "GET",
        "/api/v1/health",
        allow_service_unavailable=True,
    )
    health_status = health.get("status")
    if health_status == "unhealthy":
        raise ImportCheckError("Profilarr reports an unhealthy application state")
    if health_status not in {"healthy", "degraded"}:
        raise ImportCheckError(
            f"Profilarr returned an unexpected health status: {health_status!r}"
        )

    database_status = _status_for_database(api_url, api_key, database_id)
    counts = database_status.get("counts")
    if not isinstance(counts, dict):
        raise ImportCheckError("Profilarr status response is missing database counts")
    custom_formats = counts.get("customFormats")
    quality_profiles = counts.get("qualityProfiles")
    if not isinstance(custom_formats, int) or not isinstance(quality_profiles, int):
        raise ImportCheckError("Profilarr returned invalid PCD content counts")

    complete = (
        health_code == 200
        and health_status == "healthy"
        and custom_formats > 0
        and quality_profiles > 0
    )
    state = (
        f"health={health_status!r}, customFormats={custom_formats}, "
        f"qualityProfiles={quality_profiles}"
    )
    return complete, state


def _wait_for_import(
    api_url: str,
    api_key: str,
    database_id: int,
    timeout: float,
    poll_interval: float,
) -> None:
    deadline = time.monotonic() + timeout
    last_state = "sync has not started"
    while True:
        complete, last_state = _import_status(api_url, api_key, database_id)
        if complete:
            print(f"Profilarr imported and compiled the PCD: {last_state}")
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ImportCheckError(
                f"PCD import did not complete within {timeout:g}s: {last_state}"
            )
        time.sleep(min(poll_interval, remaining))


def check_import(
    api_url: str,
    api_key: str,
    repository_url: str,
    branch: str,
    *,
    readiness_timeout: float = READINESS_TIMEOUT,
    import_timeout: float = IMPORT_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
) -> None:
    _validate_repository_url(repository_url)
    if not api_key:
        raise ImportCheckError("A Profilarr API key is required")
    if not branch:
        raise ImportCheckError("A PCD branch name is required")
    if readiness_timeout <= 0 or import_timeout <= 0 or poll_interval <= 0:
        raise ImportCheckError("Timeouts and polling interval must be greater than zero")

    _wait_for_app(api_url, api_key, readiness_timeout)
    status_code, linked_database = _request_json(
        api_url,
        api_key,
        "POST",
        "/api/v1/databases",
        {
            "name": "PCD import acceptance",
            "repository_url": repository_url,
            "branch": branch,
        },
    )
    if status_code != 201:
        raise ImportCheckError(f"Profilarr linked the PCD with unexpected HTTP {status_code}")
    database_id = linked_database.get("id")
    if not isinstance(database_id, int) or isinstance(database_id, bool):
        raise ImportCheckError("Profilarr link response is missing a valid database ID")
    print(f"Linked PCD repository as database {database_id}; waiting for import")
    _wait_for_import(api_url, api_key, database_id, import_timeout, poll_interval)


def _docker(arguments: list[str], description: str, timeout: float) -> str:
    try:
        result = subprocess.run(
            ["docker", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise ImportCheckError("Docker is required for the Profilarr import check") from error
    except subprocess.TimeoutExpired as error:
        raise ImportCheckError(f"{description} timed out after {timeout:g}s") from error
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ImportCheckError(f"{description} failed: {detail}")
    return result.stdout.strip()


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _container_logs(container_name: str) -> None:
    result = subprocess.run(
        ["docker", "logs", "--tail", "200", container_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print("Profilarr container logs:", file=sys.stderr)
    print(result.stdout, file=sys.stderr)
    print(result.stderr, file=sys.stderr)


def run_import_check(
    repository_url: str,
    branch: str,
    *,
    image: str = APP_IMAGE,
    readiness_timeout: float = READINESS_TIMEOUT,
    import_timeout: float = IMPORT_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
) -> None:
    _validate_repository_url(repository_url)
    print(f"Pulling Profilarr image {image}")
    _docker(["pull", image], f"Unable to pull {image}", timeout=600)

    container_name = f"profilarr-pcd-import-{uuid.uuid4().hex[:12]}"
    api_key = secrets.token_urlsafe(32)
    port = _available_port()
    container_started = False
    failure: ImportCheckError | None = None
    cleanup_failure: ImportCheckError | None = None

    with tempfile.TemporaryDirectory(prefix="profilarr-pcd-import-") as config_dir:
        try:
            _docker(
                [
                    "run",
                    "--detach",
                    "--name",
                    container_name,
                    "--publish",
                    f"127.0.0.1:{port}:{APP_PORT}",
                    "--mount",
                    f"type=bind,source={config_dir},target=/config",
                    "--env",
                    f"PROFILARR_API_KEY={api_key}",
                    "--env",
                    f"PUID={os.getuid()}",
                    "--env",
                    f"PGID={os.getgid()}",
                    image,
                ],
                "Unable to start the Profilarr container",
                timeout=60,
            )
            container_started = True
            check_import(
                f"http://127.0.0.1:{port}",
                api_key,
                repository_url,
                branch,
                readiness_timeout=readiness_timeout,
                import_timeout=import_timeout,
                poll_interval=poll_interval,
            )
        except ImportCheckError as error:
            failure = error
            if container_started:
                _container_logs(container_name)
        finally:
            if container_started:
                try:
                    _docker(
                        ["rm", "--force", container_name],
                        "Unable to remove the Profilarr container",
                        timeout=30,
                    )
                except ImportCheckError as error:
                    cleanup_failure = error

    if failure is not None:
        if cleanup_failure is not None:
            print(f"Container cleanup also failed: {cleanup_failure}", file=sys.stderr)
        raise failure
    if cleanup_failure is not None:
        raise cleanup_failure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a PCD into the latest Profilarr v2 app")
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--image", default=APP_IMAGE)
    args = parser.parse_args(argv)
    try:
        run_import_check(args.repository_url, args.branch, image=args.image)
    except ImportCheckError as error:
        print(f"Profilarr import check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
