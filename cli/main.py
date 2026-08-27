from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from core.contracts.models import ContentSample, DiscoveryMode, DiscoveryQuery, MetricSnapshot
from core.registry.registry import PluginRegistry
from core.scoring.scorer import CreatorHistoryItem, score_sample
from plugins.extractors.local_video.extractor import ExtractionRequest
from plugins.storage.sqlite_store.store import SQLiteCoreStore

from .proof01 import run_fixture, run_live, write_report
from .runtime import build_registry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _json(value):
    text = json.dumps(value.model_dump(mode="json") if hasattr(value, "model_dump") else value, ensure_ascii=False, indent=2, default=str)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="world-loop", description="World Learning Loop MVP v0.1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize the local SQLite Core Store")
    init.add_argument("--db-path", default=None)

    sub.add_parser("plugins", help="list declared plugins and health")

    discover = sub.add_parser("discover", help="discover metadata through a platform plugin")
    discover.add_argument("--platform", choices=["youtube", "bilibili"], required=True)
    discover.add_argument("--mode", choices=[mode.value for mode in DiscoveryMode], required=True)
    discover.add_argument("--value", required=True)
    discover.add_argument("--limit", type=int, default=10)

    collect = sub.add_parser("collect", help="collect one canonical metadata record")
    collect.add_argument("--platform", choices=["youtube", "bilibili"], required=True)
    collect.add_argument("--url", required=True)

    score = sub.add_parser("score", help="score one sample from a JSON input bundle")
    score.add_argument("--input", required=True, help="JSON with sample, current_snapshot, sample_snapshots, creator_history")

    extract = sub.add_parser("extract", help="run local video extraction")
    extract.add_argument("--sample-id", default=None)
    extract.add_argument("--video-path", required=True)
    extract.add_argument("--output-dir", default=None)
    extract.add_argument("--no-transcribe", action="store_true")
    extract.add_argument("--no-scenes", action="store_true")
    extract.add_argument("--no-keyframes", action="store_true")
    extract.add_argument("--ocr", action="store_true")

    proof = sub.add_parser("proof01", help="run Integration Proof 01")
    proof.add_argument("--live", action="store_true", help="also call live public platform adapters")
    proof.add_argument("--youtube-url", default="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    proof.add_argument("--bilibili-url", default="https://www.bilibili.com/video/BV1GJ411x7h7")
    proof.add_argument("--video-path", action="append", default=[])
    proof.add_argument("--report", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _repo_root()
    if args.command == "init":
        path = Path(args.db_path) if args.db_path else root / "data" / "db" / "core.sqlite3"
        with SQLiteCoreStore(path):
            pass
        _json({"status": "initialized", "db_path": str(path)})
        return 0

    if args.command == "plugins":
        registry = build_registry(root)
        _json({"plugins": [manifest.model_dump(mode="json") for manifest in registry.manifests()], "health": [registry.health(manifest.plugin_id).model_dump(mode="json") for manifest in registry.manifests()]})
        return 0

    registry = build_registry(root)
    if args.command == "discover":
        result = registry.execute(
            "discover",
            DiscoveryQuery(mode=args.mode, value=args.value, limit=args.limit),
            platform=args.platform,
        )
        _json(result)
        return 0 if result.status == "success" else 2
    if args.command == "collect":
        result = registry.execute("collect", args.url, platform=args.platform)
        _json(result)
        return 0 if result.status == "success" else 2
    if args.command == "score":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        sample = ContentSample.model_validate(payload["sample"])
        current_snapshot = MetricSnapshot.model_validate(payload["current_snapshot"])
        sample_snapshots = [MetricSnapshot.model_validate(item) for item in payload.get("sample_snapshots", [])]
        history = [CreatorHistoryItem.model_validate(item) for item in payload.get("creator_history", [])]
        _json(score_sample(sample, current_snapshot, sample_snapshots=sample_snapshots, creator_history=history))
        return 0
    if args.command == "extract":
        request = ExtractionRequest(
            sample_id=uuid4() if args.sample_id is None else args.sample_id,
            video_path=args.video_path,
            output_dir=args.output_dir or str(root / "data"),
            transcribe=not args.no_transcribe,
            detect_scenes=not args.no_scenes,
            extract_keyframes=not args.no_keyframes,
            ocr=args.ocr,
        )
        result = registry.execute("extract.transcript", request)
        _json(result)
        return 0 if result.status in {"success", "failed"} and result.data and result.data.status != "failed" else 2
    if args.command == "proof01":
        report = run_live(root, youtube_url=args.youtube_url, bilibili_url=args.bilibili_url, video_paths=args.video_path) if args.live else run_fixture(root)
        path = Path(args.report) if args.report else root / "patterns" / "candidates" / "integration-proof-01.json"
        write_report(report, path)
        _json({"report": str(path), "proof": report})
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
