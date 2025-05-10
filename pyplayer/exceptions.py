class PyPlayerError(Exception):
    """Base exception class for all pyPlayer errors.

    All custom exceptions in the application should inherit from this class
    to allow for easy catching of all application-specific errors.
    """

    def __init__(self, message: str = "An error occurred in pyPlayer") -> None:
        self.message = message
        super().__init__(self.message)


class YouTubeError(PyPlayerError):
    """Exception raised for YouTube-related errors"""

    pass


class YouTubeDependencyError(YouTubeError):
    """Exception raised when YouTube dependencies are missing"""

    def __init__(self) -> None:
        super().__init__(
            "yt-dlp is required for YouTube support. " + "For more info see README.md"
        )


# Video Processing Errors
class VideoProcessingError(PyPlayerError):
    """Base class for errors related to video processing."""

    def __init__(self, message: str = "Error processing video") -> None:
        super().__init__(message)


class VideoNotFoundError(VideoProcessingError):
    """Raised when the specified video file cannot be found."""

    def __init__(self, video_path: str) -> None:
        super().__init__(f"Video file not found: {video_path}")
        self.video_path = video_path


class FFmpegNotFoundError(VideoProcessingError):
    """Raised when FFmpeg is not installed or not found in PATH."""

    def __init__(self) -> None:
        super().__init__(
            "FFmpeg is not installed or not found in your PATH. "
            + "Please install FFmpeg (https://ffmpeg.org/download.html) "
            + "and make sure it's added to your PATH. For more info see README.md"
        )


class AudioExtractionError(VideoProcessingError):
    """Raised when there's an error extracting audio from the video."""

    def __init__(self, error_details: str = "") -> None:
        message = "Error extracting audio from video"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)


class FrameExtractionError(VideoProcessingError):
    """Raised when there's an error extracting frames from the video."""

    def __init__(self, error_details: str = "") -> None:
        message = "Error extracting frames from video"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)


# Rendering Errors
class RenderingError(PyPlayerError):
    """Base class for errors related to ASCII rendering."""

    def __init__(self, message: str = "Error rendering video frame") -> None:
        super().__init__(message)


class InvalidRenderStyleError(RenderingError):
    """Raised when an invalid rendering style is specified."""

    def __init__(self, style: str) -> None:
        super().__init__(f"Invalid render style: {style}")
        self.style = style


class FrameRenderingError(RenderingError):
    """Raised when there's an error rendering a specific frame."""

    def __init__(self, frame_path: str, error_details: str = "") -> None:
        message = f"Error rendering frame: {frame_path}"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)
        self.frame_path = frame_path


class FrameNotFoundError(RenderingError):
    """Raised when a frame file cannot be found during playback."""

    def __init__(self, frame_number: int, frame_path: str) -> None:
        super().__init__(f"Frame {frame_number} missing: {frame_path}")
        self.frame_number = frame_number
        self.frame_path = frame_path


# Playback Errors
class PlaybackError(PyPlayerError):
    """Base class for errors related to video playback."""

    def __init__(self, message: str = "Error during video playback") -> None:
        super().__init__(message)


class AudioPlaybackError(PlaybackError):
    """Raised when there's an error playing the audio."""

    def __init__(self, error_details: str = "") -> None:
        message = "Error playing audio"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)


# Pre-rendering Errors
class PreRenderingError(PyPlayerError):
    """Base class for errors related to pre-rendering frames."""

    def __init__(self, message: str = "Error pre-rendering frames") -> None:
        super().__init__(message)


class ThreadingError(PreRenderingError):
    """Raised when there's an error with multi-threading during pre-rendering."""

    def __init__(self, error_details: str = "") -> None:
        message = "Error in multi-threading during pre-rendering"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)
