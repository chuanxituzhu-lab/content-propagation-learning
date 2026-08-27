"""Local video decomposition with optional yt-dlp, FFmpeg, Whisper and scenes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field

from core.contracts.models import ContractModel, FrozenContractModel
from core.contracts.runtime import CostLevel, CostProfile, PluginManifest, PluginRequirements, PluginType, TokenCost
from core.registry.provenance import create_provenance, sha256_bytes


class ExtractionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractionRequest(FrozenContractModel):
    sample_id: UUID
    video_path: str
    output_dir: str = "data"
    transcribe: bool = True
    detect_scenes: bool = True
    extract_keyframes: bool = True
    ocr: bool = False
    whisper_model: str = "tiny"


class ExtractionArtifact(FrozenContractModel):
    artifact_type: str
    storage_uri: str
    sha256: str | None = None
    mime_type: str | None = None


class ExtractionResult(ContractModel):
    sample_id: UUID
    status: ExtractionStatus
    observations: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ExtractionArtifact] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: Any = None


class LocalVideoExtractor:
    """Best-effort local extractor; unavailable optional tools become evidence."""

    def __init__(self, *, default_output_dir: str | Path = "data") -> None:
        self.default_output_dir = Path(default_output_dir)
        self.manifest = PluginManifest(
            plugin_id="world.local-video.extractor",
            type=PluginType.EXTRACTOR,
            version="0.1.0",
            capabilities=[
                "extract.transcript",
                "extract.scenes",
                "extract.keyframes",
                "extract.audio_features",
            ],
            platforms=[],
            requirements=PluginRequirements(network=False, auth="none"),
            cost_profile=CostProfile(compute=CostLevel.MEDIUM, token=TokenCost.NONE, network=False),
            priority=10,
        )

    def execute(self, request: ExtractionRequest) -> ExtractionResult:
        return self.extract(request)

    def dependencies(self) -> dict[str, bool]:
        return {
            "yt-dlp": importlib.util.find_spec("yt_dlp") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None,
            "faster-whisper": importlib.util.find_spec("faster_whisper") is not None,
            "PySceneDetect": importlib.util.find_spec("scenedetect") is not None,
        }

    def download(self, url: str, output_dir: str | Path, *, filename: str | None = None) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp is required to download a media URL") from exc
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        stem = filename or "%(id)s"
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(destination / f"{stem}.%(ext)s"),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            downloaded = Path(downloader.prepare_filename(info))
        if downloaded.exists():
            return downloaded
        candidates = sorted(destination.glob(f"{stem}.*"))
        if not candidates:
            raise FileNotFoundError("yt-dlp reported success but no media file was found")
        return candidates[0]

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        video_path = Path(request.video_path)
        output_root = Path(request.output_dir or self.default_output_dir)
        errors: list[str] = []
        artifacts: list[ExtractionArtifact] = []
        observations: dict[str, Any] = {"dependencies": self.dependencies()}
        if not video_path.exists() or not video_path.is_file():
            return ExtractionResult(
                sample_id=request.sample_id,
                status=ExtractionStatus.FAILED,
                errors=[f"video not found: {video_path}"],
                observations=observations,
                provenance=create_provenance(self.manifest.plugin_id, self.manifest.version, input_value=request),
            )

        sample_root = output_root / "samples" / str(request.sample_id)
        sample_root.mkdir(parents=True, exist_ok=True)
        digest = _file_sha256(video_path)
        observations["video_path"] = str(video_path)
        observations["video_sha256"] = digest
        observations["size_bytes"] = video_path.stat().st_size

        probe = self._probe(video_path)
        if probe is None:
            errors.append("ffprobe unavailable or failed; duration/stream facts not extracted")
        else:
            observations.update(probe)

        if request.extract_keyframes:
            frame_artifact = self._keyframes(video_path, sample_root / "frames", errors)
            if frame_artifact:
                artifacts.append(frame_artifact)

        if request.detect_scenes:
            scene_artifact = self._scenes(video_path, sample_root / "scene_map.json", errors)
            if scene_artifact:
                artifacts.append(scene_artifact)

        if request.transcribe:
            transcript_artifact = self._transcript(
                video_path,
                sample_root / "transcript.json",
                request.whisper_model,
                errors,
            )
            if transcript_artifact:
                artifacts.append(transcript_artifact)

        features_path = sample_root / "local_features.json"
        features_path.write_text(json.dumps(observations, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        artifacts.append(
            ExtractionArtifact(
                artifact_type="local_features",
                storage_uri=str(features_path),
                sha256=_file_sha256(features_path),
                mime_type="application/json",
            )
        )
        if request.ocr:
            errors.append("OCR is optional and was not executed by the v0.1 extractor")

        status = ExtractionStatus.SUCCESS if not errors else ExtractionStatus.PARTIAL
        return ExtractionResult(
            sample_id=request.sample_id,
            status=status,
            observations=observations,
            artifacts=artifacts,
            errors=errors,
            provenance=create_provenance(
                self.manifest.plugin_id,
                self.manifest.version,
                input_value=request,
                output_value={"observations": observations, "artifacts": artifacts},
                contract_version=self.manifest.contract_version,
            ),
        )

    def _probe(self, video_path: Path) -> dict[str, Any] | None:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return None
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return None
        format_info = payload.get("format", {})
        streams = payload.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
        return {
            "duration_sec": _float_or_none(format_info.get("duration")),
            "bit_rate": _int_or_none(format_info.get("bit_rate")),
            "video_width": video_stream.get("width"),
            "video_height": video_stream.get("height"),
            "video_codec": video_stream.get("codec_name"),
            "audio_codec": audio_stream.get("codec_name"),
            "audio_channels": audio_stream.get("channels"),
        }

    def _keyframes(self, video_path: Path, frame_dir: Path, errors: list[str]) -> ExtractionArtifact | None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            errors.append("ffmpeg unavailable; keyframes not extracted")
            return None
        frame_dir.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video_path), "-vf", "fps=1/10", "-q:v", "2", str(frame_dir / "%06d.jpg")],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            errors.append(f"ffmpeg keyframe extraction failed: {completed.stderr.strip()[:300]}")
            return None
        return ExtractionArtifact(artifact_type="keyframes", storage_uri=str(frame_dir), mime_type="image/jpeg")

    def _scenes(self, video_path: Path, output_path: Path, errors: list[str]) -> ExtractionArtifact | None:
        try:
            from scenedetect import ContentDetector, SceneManager, open_video
        except ImportError:
            errors.append("PySceneDetect unavailable; scene map not extracted")
            return None
        try:
            video = open_video(str(video_path))
            manager = SceneManager()
            manager.add_detector(ContentDetector())
            manager.detect_scenes(video=video)
            scenes = [
                {"start": start.get_seconds(), "end": end.get_seconds()}
                for start, end in manager.get_scene_list()
            ]
            output_path.write_text(json.dumps(scenes, indent=2), encoding="utf-8")
            return ExtractionArtifact(
                artifact_type="scene_map",
                storage_uri=str(output_path),
                sha256=_file_sha256(output_path),
                mime_type="application/json",
            )
        except Exception as exc:
            errors.append(f"PySceneDetect failed: {type(exc).__name__}: {exc}")
            return None

    def _transcript(
        self,
        video_path: Path,
        output_path: Path,
        model_size: str,
        errors: list[str],
    ) -> ExtractionArtifact | None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            errors.append("faster-whisper unavailable; transcript not extracted")
            return None
        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments, info = model.transcribe(str(video_path))
            transcript = {
                "language": getattr(info, "language", None),
                "segments": [
                    {"start": segment.start, "end": segment.end, "text": segment.text}
                    for segment in segments
                ],
            }
            output_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
            return ExtractionArtifact(
                artifact_type="transcript",
                storage_uri=str(output_path),
                sha256=_file_sha256(output_path),
                mime_type="application/json",
            )
        except Exception as exc:
            errors.append(f"faster-whisper failed: {type(exc).__name__}: {exc}")
            return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

