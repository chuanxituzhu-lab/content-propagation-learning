"""Dependency-free local WebUI server.

The WebUI is an interface adapter over existing CLI/Core operations. It binds
to loopback by default and does not add a second data model or a background
worker.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from core.contracts.models import ContentSample, DiscoveryQuery, MetricSnapshot
from core.scoring.scorer import CreatorHistoryItem, score_sample
from plugins.extractors.local_video.extractor import ExtractionRequest

from cli.proof01 import run_fixture, run_live
from cli.runtime import build_registry


class WebApplication:
    """HTTP-independent application surface, kept testable without a browser."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.registry = build_registry(self.repo_root)

    def health(self) -> dict[str, Any]:
        manifests = self.registry.manifests()
        return {
            "status": "ok",
            "service": "content-propagation-learning-webui",
            "contract_version": "world-loop/v0.1",
            "project_root": str(self.repo_root),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "plugins": [
                {
                    "manifest": manifest.model_dump(mode="json"),
                    "health": self.registry.health(manifest.plugin_id).model_dump(mode="json"),
                }
                for manifest in manifests
            ],
        }

    def get(self, path: str) -> tuple[int, dict[str, Any]]:
        parsed = urlparse(path)
        if parsed.path == "/api/health" or parsed.path == "/api/plugins":
            return HTTPStatus.OK, self.health()
        return HTTPStatus.NOT_FOUND, {"error": "not found"}

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if path == "/api/proof/fixture":
            return HTTPStatus.OK, run_fixture(self.repo_root)
        if path == "/api/proof/live":
            report = run_live(
                self.repo_root,
                youtube_url=str(payload.get("youtube_url") or "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                bilibili_url=str(payload.get("bilibili_url") or "https://www.bilibili.com/video/BV1GJ411x7h7"),
                video_paths=[str(item) for item in payload.get("video_paths", [])],
            )
            return HTTPStatus.OK, report
        if path == "/api/score":
            try:
                sample = ContentSample.model_validate(payload["sample"])
                current = MetricSnapshot.model_validate(payload["current_snapshot"])
                snapshots = [MetricSnapshot.model_validate(item) for item in payload.get("sample_snapshots", [])]
                history = [CreatorHistoryItem.model_validate(item) for item in payload.get("creator_history", [])]
                result = score_sample(sample, current, sample_snapshots=snapshots, creator_history=history)
            except (KeyError, ValueError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"invalid score input: {exc}"}
            return HTTPStatus.OK, result.model_dump(mode="json")
        if path == "/api/extract":
            try:
                request_payload = dict(payload)
                request_payload.setdefault("sample_id", str(uuid4()))
                request_payload.setdefault("output_dir", str(self.repo_root / "data"))
                request = ExtractionRequest.model_validate(request_payload)
                result = self.registry.execute("extract.transcript", request)
            except (ValueError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"invalid extraction input: {exc}"}
            return HTTPStatus.OK, result.model_dump(mode="json")
        return HTTPStatus.NOT_FOUND, {"error": "not found"}


class RequestHandler(BaseHTTPRequestHandler):
    server: "WebServer"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            status, payload = self.server.application.get(self.path)
            self._send_json(status, payload)
            return
        self._send_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2 * 1024 * 1024:
                raise ValueError("request body too large")
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            status, response = self.server.application.post(parsed.path, payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            status, response = HTTPStatus.BAD_REQUEST, {"error": f"invalid request: {exc}"}
        except Exception as exc:  # keep server alive and isolate operation failures
            status, response = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"operation failed: {type(exc).__name__}: {exc}"}
        self._send_json(status, response)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[webui] {self.address_string()} - {format % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_static(self, path: str) -> None:
        static_name = "index.html" if path in {"", "/"} else path.lstrip("/")
        if static_name not in {"index.html", "styles.css", "app.js"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        file_path = Path(__file__).resolve().parent / static_name
        if not file_path.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "asset not found"})
            return
        data = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class WebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], application: WebApplication):
        self.application = application
        super().__init__(server_address, RequestHandler)


def create_server(repo_root: str | Path = ".", host: str = "127.0.0.1", port: int = 8765) -> WebServer:
    return WebServer((host, port), WebApplication(repo_root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="world-loop-web", description="Local WebUI for Content Propagation Learning")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    server = create_server(args.repo_root, args.host, args.port)
    print(f"World Learning Loop WebUI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

