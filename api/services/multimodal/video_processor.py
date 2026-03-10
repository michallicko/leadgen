"""Video processing pipeline (BL-268).

Extracts audio (ffmpeg) -> transcribes (Whisper API) -> extracts keyframes
(ffmpeg scene detection) -> describes keyframes (Claude vision) -> merges
into time-aligned summary.

External dependencies:
  - ffmpeg (system binary)
  - yt-dlp (pip package, for URL downloads)
  - openai (pip package, for Whisper API)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum video duration in minutes
DEFAULT_MAX_DURATION_MINUTES = 15

# Keyframe extraction: scene change threshold (0-1, lower = more frames)
SCENE_CHANGE_THRESHOLD = 0.3

# Target keyframes per minute
KEYFRAMES_PER_MINUTE = 2

# Max keyframes total
MAX_KEYFRAMES = 30

# Cost estimate per 10 minutes of video (USD)
COST_PER_10_MIN_LOW = 0.10
COST_PER_10_MIN_HIGH = 0.30

# Approximate tokens per minute of transcript
TOKENS_PER_MINUTE_TRANSCRIPT = 150

# Tokens per keyframe (Claude vision)
TOKENS_PER_KEYFRAME = 1600

# Cache directory
DEFAULT_CACHE_DIR = "/tmp/leadgen-video-cache"


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file."""

    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    codec: str = ""
    file_hash: str = ""
    file_path: str = ""


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio."""

    start_seconds: float = 0.0
    end_seconds: float = 0.0
    text: str = ""


@dataclass
class KeyframeInfo:
    """Information about an extracted keyframe."""

    timestamp_seconds: float = 0.0
    file_path: str = ""
    description: str = ""


@dataclass
class CostEstimate:
    """Estimated cost for processing a video."""

    whisper_cost_usd: float = 0.0
    vision_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    estimated_keyframes: int = 0
    duration_minutes: float = 0.0


@dataclass
class VideoProcessingResult:
    """Complete result of video processing."""

    metadata: Optional[VideoMetadata] = None
    transcript_text: str = ""
    transcript_segments: list[TranscriptSegment] = field(default_factory=list)
    keyframes: list[KeyframeInfo] = field(default_factory=list)
    transcript_summary: str = ""
    visual_summary: str = ""
    key_moments: list[dict] = field(default_factory=list)
    cost_estimate: Optional[CostEstimate] = None
    cached: bool = False
    error: Optional[str] = None


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available on the system."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_video_metadata(file_path: str) -> Optional[VideoMetadata]:
    """Extract metadata from a video file using ffprobe.

    Args:
        file_path: Path to the video file.

    Returns:
        VideoMetadata, or None on error.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            logger.error("ffprobe failed: %s", proc.stderr)
            return None

        data = json.loads(proc.stdout)

        meta = VideoMetadata(file_path=file_path)

        # Duration from format
        fmt = data.get("format", {})
        meta.duration_seconds = float(fmt.get("duration", 0))

        # Stream info
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                meta.width = int(stream.get("width", 0))
                meta.height = int(stream.get("height", 0))
                meta.codec = stream.get("codec_name", "")
                fps_parts = stream.get("r_frame_rate", "0/1").split("/")
                if len(fps_parts) == 2 and int(fps_parts[1]) > 0:
                    meta.fps = int(fps_parts[0]) / int(fps_parts[1])
            elif stream.get("codec_type") == "audio":
                meta.has_audio = True

        # File hash
        meta.file_hash = _compute_file_hash(file_path)

        return meta

    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("ffprobe not available: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Failed to get video metadata: %s", exc)
        return None


def estimate_cost(metadata: VideoMetadata) -> CostEstimate:
    """Estimate the processing cost for a video.

    Args:
        metadata: Video metadata with duration.

    Returns:
        CostEstimate with breakdown.
    """
    duration_min = metadata.duration_seconds / 60.0
    estimated_keyframes = min(
        int(duration_min * KEYFRAMES_PER_MINUTE) + 1,
        MAX_KEYFRAMES,
    )

    # Whisper API: ~$0.006 per minute
    whisper_cost = duration_min * 0.006 if metadata.has_audio else 0.0

    # Claude vision: ~$0.005 per image (1600 tokens at $3/MTok input)
    vision_cost = estimated_keyframes * 0.005

    return CostEstimate(
        whisper_cost_usd=round(whisper_cost, 4),
        vision_cost_usd=round(vision_cost, 4),
        total_cost_usd=round(whisper_cost + vision_cost, 4),
        estimated_keyframes=estimated_keyframes,
        duration_minutes=round(duration_min, 1),
    )


def extract_audio(video_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """Extract audio track from video using ffmpeg.

    Args:
        video_path: Path to the video file.
        output_dir: Directory for output file (default: temp).

    Returns:
        Path to extracted audio file (.wav), or None on error.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="leadgen-audio-")

    audio_path = os.path.join(output_dir, "audio.wav")

    try:
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-y",
            audio_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            logger.error("Audio extraction failed: %s", proc.stderr)
            return None

        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            return audio_path

        return None

    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("ffmpeg not available for audio extraction: %s", exc)
        return None


def transcribe_audio(
    audio_path: str,
    api_key: Optional[str] = None,
) -> list[TranscriptSegment]:
    """Transcribe audio using OpenAI Whisper API.

    Args:
        audio_path: Path to the audio file.
        api_key: OpenAI API key (default: from env).

    Returns:
        List of TranscriptSegments with timestamps.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set for Whisper transcription")
        return []

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)

        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        segments = []
        for seg in getattr(response, "segments", []):
            segments.append(
                TranscriptSegment(
                    start_seconds=seg.get("start", 0.0),
                    end_seconds=seg.get("end", 0.0),
                    text=seg.get("text", "").strip(),
                )
            )

        # Fallback: if no segments but has text
        if not segments and hasattr(response, "text") and response.text:
            segments.append(TranscriptSegment(text=response.text.strip()))

        return segments

    except ImportError:
        logger.error("openai package not installed")
        return []
    except Exception as exc:
        logger.exception("Whisper transcription failed: %s", exc)
        return []


def extract_keyframes(
    video_path: str,
    output_dir: Optional[str] = None,
    threshold: float = SCENE_CHANGE_THRESHOLD,
    max_frames: int = MAX_KEYFRAMES,
) -> list[KeyframeInfo]:
    """Extract keyframes from video using ffmpeg scene detection.

    Args:
        video_path: Path to the video file.
        output_dir: Directory for keyframe images.
        threshold: Scene change detection threshold (0-1).
        max_frames: Maximum number of keyframes to extract.

    Returns:
        List of KeyframeInfo with file paths and timestamps.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="leadgen-keyframes-")

    os.makedirs(output_dir, exist_ok=True)

    try:
        # Use scene detection filter to extract keyframes
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            "select=gt(scene\\,{}),showinfo".format(threshold),
            "-vsync",
            "vfr",
            "-frames:v",
            str(max_frames),
            "-y",
            os.path.join(output_dir, "keyframe_%04d.jpg"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Parse timestamps from showinfo output
        keyframes = []
        frame_idx = 0
        for line in proc.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    pts_str = line.split("pts_time:")[1].split()[0]
                    timestamp = float(pts_str)
                    frame_idx += 1
                    frame_path = os.path.join(
                        output_dir, "keyframe_{:04d}.jpg".format(frame_idx)
                    )
                    if os.path.exists(frame_path):
                        keyframes.append(
                            KeyframeInfo(
                                timestamp_seconds=timestamp,
                                file_path=frame_path,
                            )
                        )
                except (ValueError, IndexError):
                    continue

        # Fallback: if scene detection produced no frames, extract at intervals
        if not keyframes:
            keyframes = _extract_interval_frames(video_path, output_dir, max_frames)

        return keyframes[:max_frames]

    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("ffmpeg not available for keyframe extraction: %s", exc)
        return []


def download_video_url(url: str, output_dir: Optional[str] = None) -> Optional[str]:
    """Download a video from URL using yt-dlp.

    Args:
        url: Video URL (YouTube, Vimeo, etc.).
        output_dir: Directory for downloaded file.

    Returns:
        Path to downloaded video file, or None on error.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="leadgen-download-")

    output_template = os.path.join(output_dir, "video.%(ext)s")

    try:
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f",
            "best[filesize<100M]/best",
            "--max-filesize",
            "100M",
            "-o",
            output_template,
            url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if proc.returncode != 0:
            logger.error("yt-dlp download failed: %s", proc.stderr)
            return None

        # Find the downloaded file
        for fname in os.listdir(output_dir):
            if fname.startswith("video."):
                return os.path.join(output_dir, fname)

        return None

    except FileNotFoundError:
        logger.error("yt-dlp not installed -- run: pip install yt-dlp")
        return None
    except subprocess.TimeoutExpired:
        logger.error("Video download timed out")
        return None


def process_video(
    file_path: str,
    max_duration_minutes: float = DEFAULT_MAX_DURATION_MINUTES,
    skip_transcription: bool = False,
    skip_keyframes: bool = False,
    openai_api_key: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> VideoProcessingResult:
    """Full video processing pipeline.

    1. Get metadata and validate duration
    2. Check cache
    3. Extract audio and transcribe
    4. Extract keyframes
    5. Build combined result

    Note: Keyframe descriptions (via Claude vision) are NOT done here --
    they should be handled by the calling agent which has access to the
    Claude API. This processor returns keyframe image paths.

    Args:
        file_path: Path to video file.
        max_duration_minutes: Maximum allowed duration.
        skip_transcription: Skip audio transcription.
        skip_keyframes: Skip keyframe extraction.
        openai_api_key: OpenAI API key for Whisper.
        cache_dir: Directory for caching results.

    Returns:
        VideoProcessingResult with all extracted data.
    """
    result = VideoProcessingResult()

    # 1. Check ffmpeg
    if not check_ffmpeg():
        result.error = "ffmpeg not installed on this system"
        return result

    # 2. Get metadata
    metadata = get_video_metadata(file_path)
    if metadata is None:
        result.error = "Failed to read video metadata"
        return result

    result.metadata = metadata

    # 3. Check duration
    duration_min = metadata.duration_seconds / 60.0
    if duration_min > max_duration_minutes:
        result.error = (
            "Video duration ({:.1f} min) exceeds maximum ({:.0f} min)".format(
                duration_min, max_duration_minutes
            )
        )
        return result

    # 4. Cost estimate
    result.cost_estimate = estimate_cost(metadata)

    # 5. Check cache
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cached = _load_from_cache(metadata.file_hash, cache_dir)
    if cached:
        cached.cached = True
        cached.metadata = metadata
        cached.cost_estimate = result.cost_estimate
        return cached

    # 6. Audio transcription
    if not skip_transcription and metadata.has_audio:
        audio_path = extract_audio(file_path)
        if audio_path:
            segments = transcribe_audio(audio_path, api_key=openai_api_key)
            result.transcript_segments = segments
            result.transcript_text = " ".join(s.text for s in segments)

            # Clean up audio file
            try:
                os.unlink(audio_path)
            except OSError:
                pass

    # 7. Keyframe extraction
    if not skip_keyframes:
        keyframes = extract_keyframes(file_path)
        result.keyframes = keyframes

    # 8. Save to cache
    _save_to_cache(metadata.file_hash, result, cache_dir)

    return result


def build_combined_summary(
    transcript_text: str,
    keyframe_descriptions: list[dict],
    duration_seconds: float,
) -> dict:
    """Build a time-aligned combined summary from transcript + visual descriptions.

    Args:
        transcript_text: Full transcript text.
        keyframe_descriptions: List of {timestamp_seconds, description}.
        duration_seconds: Total video duration.

    Returns:
        Dict with transcript_summary, visual_summary, key_moments.
    """
    key_moments = []

    for kf in keyframe_descriptions:
        ts = kf.get("timestamp_seconds", 0)
        minutes = int(ts // 60)
        seconds = int(ts % 60)
        key_moments.append(
            {
                "time": "{:02d}:{:02d}".format(minutes, seconds),
                "timestamp_seconds": ts,
                "visual": kf.get("description", ""),
            }
        )

    # Sort by timestamp
    key_moments.sort(key=lambda x: x["timestamp_seconds"])

    return {
        "transcript_summary": transcript_text[:2000] if transcript_text else "",
        "visual_summary": "\n".join(
            "- [{time}] {visual}".format(**m) for m in key_moments
        ),
        "key_moments": key_moments,
        "duration_formatted": "{:02d}:{:02d}".format(
            int(duration_seconds // 60), int(duration_seconds % 60)
        ),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _extract_interval_frames(
    video_path: str, output_dir: str, max_frames: int
) -> list[KeyframeInfo]:
    """Extract frames at regular intervals (fallback when scene detection fails)."""
    try:
        # Get duration
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        duration = float(proc.stdout.strip())

        interval = duration / (max_frames + 1)
        keyframes = []

        for i in range(1, max_frames + 1):
            timestamp = interval * i
            frame_path = os.path.join(output_dir, "interval_{:04d}.jpg".format(i))
            cmd = [
                "ffmpeg",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-y",
                frame_path,
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)
            if os.path.exists(frame_path):
                keyframes.append(
                    KeyframeInfo(
                        timestamp_seconds=timestamp,
                        file_path=frame_path,
                    )
                )

        return keyframes

    except Exception as exc:
        logger.warning("Interval frame extraction failed: %s", exc)
        return []


def _get_cache_path(file_hash: str, cache_dir: str) -> str:
    """Get the cache file path for a given hash."""
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "{}.json".format(file_hash))


def _save_to_cache(
    file_hash: str, result: VideoProcessingResult, cache_dir: str
) -> None:
    """Save processing result to cache."""
    try:
        cache_path = _get_cache_path(file_hash, cache_dir)
        cache_data = {
            "transcript_text": result.transcript_text,
            "transcript_segments": [
                {
                    "start_seconds": s.start_seconds,
                    "end_seconds": s.end_seconds,
                    "text": s.text,
                }
                for s in result.transcript_segments
            ],
            "key_moments": result.key_moments,
            "transcript_summary": result.transcript_summary,
            "visual_summary": result.visual_summary,
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)
    except Exception as exc:
        logger.warning("Failed to save video cache: %s", exc)


def _load_from_cache(file_hash: str, cache_dir: str) -> Optional[VideoProcessingResult]:
    """Load processing result from cache."""
    try:
        cache_path = _get_cache_path(file_hash, cache_dir)
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, "r") as f:
            data = json.load(f)

        result = VideoProcessingResult(
            transcript_text=data.get("transcript_text", ""),
            transcript_segments=[
                TranscriptSegment(**s) for s in data.get("transcript_segments", [])
            ],
            key_moments=data.get("key_moments", []),
            transcript_summary=data.get("transcript_summary", ""),
            visual_summary=data.get("visual_summary", ""),
        )
        return result

    except Exception as exc:
        logger.warning("Failed to load video cache: %s", exc)
        return None
