import os
import tempfile
from typing import Any
from .exceptions import YouTubeError
from yt_dlp import YoutubeDL  # should already be checked if exists in cli

try:
    from yt_dlp import YDLOpts
except ImportError:
    pass


class YouTubeDownloader:
    """Class to handle downloading YouTube videos."""

    def __init__(self) -> None:
        """Initialize the YouTube downloader.

        Raises:
            YouTubeDependencyError: If yt-dlp is not installed
        """

        self.temp_dir = tempfile.mkdtemp(prefix="pyplayer_youtube_")
        self._cleanup_done = False

    def download_video(self, url: str) -> str:
        """Download a YouTube video and return the path to the downloaded file.

        Args:
            url: The YouTube URL to download

        Returns:
            Path to the downloaded video file

        Raises:
            YouTubeError: If there's an error downloading the video
        """
        output_path = os.path.join(self.temp_dir, "video.%(ext)s")

        ydl_opts: YDLOpts = {  # pyright: ignore[reportPossiblyUnboundVariable]  # just for typing
            "format": "best[ext=mp4]/best",  # prefer mp4
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:  # pyright: ignore[reportPossiblyUnboundVariable]  # just for typing
                info: dict[str, Any] | None = ydl.extract_info(url)
                if info is None:
                    raise YouTubeError("Failed to extract video information")

                filename = str(ydl.prepare_filename(info))  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownArgumentType]  # ignores for bad types

                if not os.path.exists(filename):
                    base, _ = os.path.splitext(filename)
                    for ext in [".mp4", ".webm", ".mkv"]:
                        test_path = base + ext
                        if os.path.exists(test_path):
                            filename = test_path
                            break

                if not os.path.exists(filename):
                    raise YouTubeError(f"Downloaded file not found at {filename}")

                return filename
        except Exception as e:
            raise YouTubeError(f"Error downloading YouTube video: {str(e)}") from e

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if not self._cleanup_done and os.path.exists(self.temp_dir):
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self._cleanup_done = True

    def __del__(self) -> None:
        self.cleanup()
