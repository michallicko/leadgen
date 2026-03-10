"""Tests for video processor (BL-268).

All external dependencies (ffmpeg, Whisper API, yt-dlp) are mocked.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest


class TestCheckFfmpeg:
    def test_ffmpeg_available(self):
        from api.services.multimodal.video_processor import check_ffmpeg

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_ffmpeg() is True

    def test_ffmpeg_not_available(self):
        from api.services.multimodal.video_processor import check_ffmpeg

        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert check_ffmpeg() is False


class TestGetVideoMetadata:
    def test_successful_metadata_extraction(self):
        from api.services.multimodal.video_processor import get_video_metadata

        ffprobe_output = json.dumps(
            {
                "format": {"duration": "120.5"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 1920,
                        "height": 1080,
                        "codec_name": "h264",
                        "r_frame_rate": "30/1",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                    },
                ],
            }
        )

        with (
            patch("subprocess.run") as mock_run,
            patch(
                "api.services.multimodal.video_processor._compute_file_hash",
                return_value="abc123",
            ),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=ffprobe_output)
            meta = get_video_metadata("/fake/video.mp4")

        assert meta is not None
        assert meta.duration_seconds == 120.5
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.has_audio is True
        assert meta.codec == "h264"
        assert meta.fps == 30.0

    def test_metadata_no_audio(self):
        from api.services.multimodal.video_processor import get_video_metadata

        ffprobe_output = json.dumps(
            {
                "format": {"duration": "60.0"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 1280,
                        "height": 720,
                        "codec_name": "h264",
                        "r_frame_rate": "24/1",
                    },
                ],
            }
        )

        with (
            patch("subprocess.run") as mock_run,
            patch(
                "api.services.multimodal.video_processor._compute_file_hash",
                return_value="def456",
            ),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=ffprobe_output)
            meta = get_video_metadata("/fake/silent.mp4")

        assert meta is not None
        assert meta.has_audio is False

    def test_metadata_ffprobe_fails(self):
        from api.services.multimodal.video_processor import get_video_metadata

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            meta = get_video_metadata("/fake/bad.mp4")

        assert meta is None

    def test_metadata_ffprobe_not_found(self):
        from api.services.multimodal.video_processor import get_video_metadata

        with patch("subprocess.run", side_effect=FileNotFoundError):
            meta = get_video_metadata("/fake/video.mp4")

        assert meta is None


class TestEstimateCost:
    def test_cost_estimate_10min_video(self):
        from api.services.multimodal.video_processor import (
            VideoMetadata,
            estimate_cost,
        )

        meta = VideoMetadata(duration_seconds=600, has_audio=True)
        cost = estimate_cost(meta)

        assert cost.duration_minutes == 10.0
        assert cost.whisper_cost_usd > 0
        assert cost.vision_cost_usd > 0
        assert (
            abs(cost.total_cost_usd - (cost.whisper_cost_usd + cost.vision_cost_usd))
            < 0.001
        )
        assert cost.estimated_keyframes > 0

    def test_cost_estimate_no_audio(self):
        from api.services.multimodal.video_processor import VideoMetadata, estimate_cost

        meta = VideoMetadata(duration_seconds=300, has_audio=False)
        cost = estimate_cost(meta)

        assert cost.whisper_cost_usd == 0
        assert cost.vision_cost_usd > 0

    def test_keyframe_cap(self):
        from api.services.multimodal.video_processor import (
            MAX_KEYFRAMES,
            VideoMetadata,
            estimate_cost,
        )

        # Very long video -- keyframes should be capped
        meta = VideoMetadata(duration_seconds=3600, has_audio=True)
        cost = estimate_cost(meta)
        assert cost.estimated_keyframes <= MAX_KEYFRAMES


class TestExtractAudio:
    def test_successful_audio_extraction(self):
        from api.services.multimodal.video_processor import extract_audio

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake audio output file
            expected_path = os.path.join(tmpdir, "audio.wav")

            def fake_run(cmd, **kwargs):
                # Create the output file as ffmpeg would
                with open(expected_path, "wb") as f:
                    f.write(b"fake wav data")
                return MagicMock(returncode=0)

            with patch("subprocess.run", side_effect=fake_run):
                result = extract_audio("/fake/video.mp4", output_dir=tmpdir)

            assert result == expected_path

    def test_audio_extraction_failure(self):
        from api.services.multimodal.video_processor import extract_audio

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = extract_audio("/fake/video.mp4")

        assert result is None

    def test_ffmpeg_not_found(self):
        from api.services.multimodal.video_processor import extract_audio

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = extract_audio("/fake/video.mp4")

        assert result is None


class TestTranscribeAudio:
    def test_successful_transcription(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            pytest.skip("openai not installed")

        from api.services.multimodal.video_processor import transcribe_audio

        mock_response = MagicMock()
        mock_response.segments = [
            {"start": 0.0, "end": 5.0, "text": "Hello world"},
            {"start": 5.0, "end": 10.0, "text": "This is a test"},
        ]
        mock_response.text = "Hello world This is a test"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI", return_value=mock_client),
            patch("builtins.open", mock_open(read_data=b"audio data")),
        ):
            segments = transcribe_audio("/fake/audio.wav")

        assert len(segments) == 2
        assert segments[0].text == "Hello world"
        assert segments[0].start_seconds == 0.0
        assert segments[1].text == "This is a test"

    def test_no_api_key(self):
        from api.services.multimodal.video_processor import transcribe_audio

        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if it exists
            os.environ.pop("OPENAI_API_KEY", None)
            segments = transcribe_audio("/fake/audio.wav")

        assert segments == []


class TestExtractKeyframes:
    def test_successful_keyframe_extraction(self):
        from api.services.multimodal.video_processor import extract_keyframes

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake keyframe files
            for i in range(1, 4):
                path = os.path.join(tmpdir, "keyframe_{:04d}.jpg".format(i))
                with open(path, "wb") as f:
                    f.write(b"fake jpeg data")

            stderr_output = (
                "[Parsed_showinfo] pts_time:10.5\n"
                "[Parsed_showinfo] pts_time:25.3\n"
                "[Parsed_showinfo] pts_time:42.1\n"
            )

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr=stderr_output)
                keyframes = extract_keyframes("/fake/video.mp4", output_dir=tmpdir)

        assert len(keyframes) == 3
        assert keyframes[0].timestamp_seconds == 10.5
        assert keyframes[1].timestamp_seconds == 25.3
        assert keyframes[2].timestamp_seconds == 42.1


class TestDownloadVideoUrl:
    def test_successful_download(self):
        from api.services.multimodal.video_processor import download_video_url

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake downloaded file
            fake_path = os.path.join(tmpdir, "video.mp4")
            with open(fake_path, "wb") as f:
                f.write(b"fake video data")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = download_video_url(
                    "https://youtube.com/watch?v=abc", output_dir=tmpdir
                )

            assert result is not None
            assert result.endswith("video.mp4")

    def test_download_failure(self):
        from api.services.multimodal.video_processor import download_video_url

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = download_video_url("https://youtube.com/watch?v=bad")

        assert result is None

    def test_ytdlp_not_installed(self):
        from api.services.multimodal.video_processor import download_video_url

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = download_video_url("https://youtube.com/watch?v=abc")

        assert result is None


class TestProcessVideo:
    def test_duration_limit_exceeded(self):
        from api.services.multimodal.video_processor import (
            VideoMetadata,
            process_video,
        )

        meta = VideoMetadata(
            duration_seconds=1200,  # 20 minutes
            has_audio=True,
            file_hash="abc",
        )

        with (
            patch(
                "api.services.multimodal.video_processor.check_ffmpeg",
                return_value=True,
            ),
            patch(
                "api.services.multimodal.video_processor.get_video_metadata",
                return_value=meta,
            ),
            patch(
                "api.services.multimodal.video_processor._load_from_cache",
                return_value=None,
            ),
        ):
            result = process_video("/fake/video.mp4", max_duration_minutes=15)

        assert result.error is not None
        assert "exceeds maximum" in result.error

    def test_ffmpeg_not_available(self):
        from api.services.multimodal.video_processor import process_video

        with patch(
            "api.services.multimodal.video_processor.check_ffmpeg", return_value=False
        ):
            result = process_video("/fake/video.mp4")

        assert result.error is not None
        assert "ffmpeg" in result.error

    def test_metadata_failure(self):
        from api.services.multimodal.video_processor import process_video

        with (
            patch(
                "api.services.multimodal.video_processor.check_ffmpeg",
                return_value=True,
            ),
            patch(
                "api.services.multimodal.video_processor.get_video_metadata",
                return_value=None,
            ),
        ):
            result = process_video("/fake/video.mp4")

        assert result.error is not None
        assert "metadata" in result.error

    def test_cache_hit(self):
        from api.services.multimodal.video_processor import (
            VideoMetadata,
            VideoProcessingResult,
            process_video,
        )

        meta = VideoMetadata(
            duration_seconds=60, has_audio=True, file_hash="cached_hash"
        )
        cached_result = VideoProcessingResult(transcript_text="cached transcript")

        with (
            patch(
                "api.services.multimodal.video_processor.check_ffmpeg",
                return_value=True,
            ),
            patch(
                "api.services.multimodal.video_processor.get_video_metadata",
                return_value=meta,
            ),
            patch(
                "api.services.multimodal.video_processor._load_from_cache",
                return_value=cached_result,
            ),
        ):
            result = process_video("/fake/video.mp4")

        assert result.cached is True
        assert result.transcript_text == "cached transcript"


class TestBuildCombinedSummary:
    def test_combined_summary(self):
        from api.services.multimodal.video_processor import build_combined_summary

        result = build_combined_summary(
            transcript_text="The product has three main features...",
            keyframe_descriptions=[
                {"timestamp_seconds": 10.0, "description": "Product logo on screen"},
                {"timestamp_seconds": 45.0, "description": "Dashboard view"},
                {"timestamp_seconds": 90.0, "description": "Pricing page"},
            ],
            duration_seconds=120.0,
        )

        assert result["transcript_summary"] == "The product has three main features..."
        assert "00:10" in result["visual_summary"]
        assert "Product logo" in result["visual_summary"]
        assert len(result["key_moments"]) == 3
        assert result["duration_formatted"] == "02:00"

    def test_empty_inputs(self):
        from api.services.multimodal.video_processor import build_combined_summary

        result = build_combined_summary("", [], 0)
        assert result["transcript_summary"] == ""
        assert result["key_moments"] == []


class TestCaching:
    def test_save_and_load_cache(self):
        from api.services.multimodal.video_processor import (
            TranscriptSegment,
            VideoProcessingResult,
            _load_from_cache,
            _save_to_cache,
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            result = VideoProcessingResult(
                transcript_text="test transcript",
                transcript_segments=[
                    TranscriptSegment(start_seconds=0, end_seconds=5, text="hello"),
                ],
                transcript_summary="summary here",
            )

            _save_to_cache("test_hash", result, cache_dir)
            loaded = _load_from_cache("test_hash", cache_dir)

            assert loaded is not None
            assert loaded.transcript_text == "test transcript"
            assert len(loaded.transcript_segments) == 1
            assert loaded.transcript_segments[0].text == "hello"

    def test_cache_miss(self):
        from api.services.multimodal.video_processor import _load_from_cache

        with tempfile.TemporaryDirectory() as cache_dir:
            loaded = _load_from_cache("nonexistent_hash", cache_dir)
            assert loaded is None
