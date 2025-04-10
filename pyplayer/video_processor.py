import os
import tempfile
import shutil
import ffmpeg
import re
import subprocess
from shutil import which
from ffmpeg import exceptions as ffmpeg_e
from .exceptions import (
    VideoNotFoundError,
    FFmpegNotFoundError,
    AudioExtractionError,
    FrameExtractionError,
)


def check_ffmpeg_available() -> bool:  # TODO: make this return the version as well
    """Check if FFmpeg is available on the system"""
    # try using shutil.which first (checks if it's in PATH)
    if which("ffmpeg") is not None:
        return True

    # if not found in PATH, try running ffmpeg command directly
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


class VideoProcessor:
    def __init__(self, video_path: str) -> None:
        self.video_path = (
            os.path.isabs(video_path) and video_path or os.path.abspath(video_path)
        )
        if not os.path.exists(self.video_path):
            raise VideoNotFoundError(self.video_path)
        self.temp_dir = tempfile.mkdtemp(prefix="pyplayer_")
        self.frames_dir = os.path.join(self.temp_dir, "frames")
        self.audio_path = os.path.join(self.temp_dir, "audio.wav")
        self._cleanup_done = False
        os.makedirs(self.frames_dir, exist_ok=True)

    def process_video(
        self,
        grayscale: bool = False,
        color_smoothing: bool = False,
        output_resolution: tuple[int, int] | None = (640, 480),
    ) -> tuple[str, str, float | None]:
        """Process video file by extracting frames and audio"""
        if not check_ffmpeg_available():
            raise FFmpegNotFoundError()

        try:
            print(f"Processing video: {self.video_path} (This might take a bit...)")
            fps = self._get_video_fps()
            self._extract_audio()
            self._extract_frames(grayscale, color_smoothing, output_resolution)
            return self.frames_dir, self.audio_path, fps
        except ffmpeg_e.FFMpegError as e:
            stderr = getattr(e, "stderr", None)
            error_msg = stderr.decode() if stderr else str(e)
            raise FrameExtractionError(error_msg)

    def _extract_audio(self) -> None:
        """Extract audio from video file"""
        try:
            input_stream = ffmpeg.input(filename=self.video_path)
            output_stream = input_stream.output(
                filename=self.audio_path, q="0", map="a"
            )
            output_stream.run(
                capture_stdout=True, capture_stderr=True, overwrite_output=True
            )
        except ffmpeg_e.FFMpegError as e:
            stderr = getattr(e, "stderr", None)
            error_msg = stderr.decode() if stderr else str(e)
            raise AudioExtractionError(error_msg)

    def _extract_frames(
        self,
        grayscale: bool = False,
        color_smoothing: bool = False,
        output_resolution: tuple[int, int] | None = (640, 480),
    ) -> None:
        """Extract and process frames from video file"""
        stream = ffmpeg.input(filename=self.video_path)

        # Apply grayscale filter if requested
        if grayscale:
            # Apply the complex lutrgb filter
            lut_expr = "if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))"
            stream = stream.lutrgb(r=lut_expr, g=lut_expr, b=lut_expr)
            # Apply hue filter to remove saturation
            stream = stream.hue(s=0)

        if color_smoothing:
            stream = stream.hqdn3d()

        if output_resolution is not None:
            stream = stream.scale(w=output_resolution[0], h=output_resolution[1])

        output_path = os.path.join(self.frames_dir, "frame_%05d.png")
        try:
            output_stream = ffmpeg.output(stream, filename=output_path)
            output_stream.run(
                capture_stdout=True, capture_stderr=True, overwrite_output=True
            )
        except ffmpeg_e.FFMpegError as e:
            stderr = getattr(e, "stderr", None)
            error_msg = stderr.decode() if stderr else str(e)
            raise FrameExtractionError(error_msg)

    def _get_video_fps(self) -> float | None:
        """Get video frame rate using FFprobe"""
        try:
            probe = ffmpeg.probe(
                filename=self.video_path, cmd="ffprobe", timeout=5, loglevel="quiet"
            )
            video_stream = next(
                (
                    stream
                    for stream in probe["streams"]
                    if stream["codec_type"] == "video"
                ),
                None,
            )
            if video_stream is None:
                return None

            # Extract frame rate which might be in the format '24/1'
            frame_rate = video_stream.get("r_frame_rate")
            if frame_rate:
                match = re.match(r"(\d+)/(\d+)", frame_rate)
                if match:
                    num, den = map(int, match.groups())
                    return num / den
            return None
        except (ffmpeg_e.FFMpegError, KeyError, StopIteration, ValueError):
            return None

    def cleanup(self) -> None:
        """Remove temporary files and directories"""
        if self._cleanup_done:
            return

        if hasattr(self, "temp_dir") and os.path.exists(
            self.temp_dir
        ):  # just in case its in a weird quasi-initialized state
            try:
                shutil.rmtree(self.temp_dir)
                self._cleanup_done = True
            except (OSError, IOError) as e:
                print(f"Warning: Failed to cleanup temporary files: {e}")
