# pyright:reportPossiblyUnboundVariable=false
import sys
import argparse
import multiprocessing
import traceback
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from typing import Any, Callable, override
from functools import wraps
from .player import Player
from .exceptions import PyPlayerError, YouTubeError, YouTubeDependencyError
from .renderer_factory import RendererFactory, RGBPixel

_youtube_support = False
try:
    from .youtube import YouTubeDownloader

    _youtube_support = True
except ImportError:
    raise

TypeFunc = Callable[[str], Any]


class BaseArgumentGroup(ABC):
    def __init__(self, parser: "PlayerArgumentParser") -> None:
        """
        Args:
            parser: The main argument parser instance to add arguments to.
        """
        self.parser = parser

    @abstractmethod
    def add_arguments(self) -> None:
        """Add arguments specific to this group to the parser.

        Subclasses must implement this method to define their arguments.
        """
        pass


def type_parser(error_msg_template: str) -> Callable[[TypeFunc], TypeFunc]:
    """Decorator factory for creating robust argparse type-checking functions.

    Wraps a function that parses a string value, providing standardized error
    handling by converting ValueErrors into argparse.ArgumentTypeError.

    Args:
        error_msg_template: The error message prefix to use when parsing fails.
                            The specific ValueError message will be appended.
    Returns:
        A decorator that wraps a type parsing function.
    """

    def decorator(func: TypeFunc) -> TypeFunc:
        @wraps(func)
        def wrapper(value: str) -> Any:
            try:
                return func(value)
            except ValueError as e:
                raise argparse.ArgumentTypeError(f"{error_msg_template}: {e}")

        return wrapper

    return decorator


@type_parser("Invalid RGB color format")
def parse_rgb_color(value: str) -> RGBPixel:
    r, g, b = map(int, value.split(","))
    if not all(0 <= c <= 255 for c in (r, g, b)):
        raise ValueError("RGB values must be between 0 and 255")
    return (r, g, b)


@type_parser("Invalid output resolution format")
def parse_output_resolution(value: str) -> tuple[int, int] | None:
    if value.lower() == "native":
        return None

    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError("Resolution must be in 'width,height' format or 'native'.")

    try:
        width = int(parts[0].strip())
        height = int(parts[1].strip())
    except ValueError:
        raise ValueError("Width and height must be integers.") from None

    if width <= 0 or height <= 0:
        raise ValueError("Resolution width and height must be positive.")

    return (width, height)


@type_parser("Error parsing color smoothing parameters")
def parse_color_smoothing_params(value: str) -> dict[str, float]:
    valid_params = ["luma_spatial", "chroma_spatial", "luma_tmp", "chroma_tmp"]
    result: dict[str, float] = {}

    if not value:
        return result

    for param in value.split(","):
        if "=" not in param:
            raise ValueError(f"Invalid parameter format: '{param}'. Use 'key=value'.")
        key, val_str = param.strip().split("=", 1)
        key = key.strip()
        val_str = val_str.strip()

        if key not in valid_params:
            raise ValueError(
                f"Invalid parameter key: '{key}'. Valid keys: {', '.join(valid_params)}"
            )
        try:
            result[key] = float(val_str)
        except ValueError:
            raise ValueError(
                f"Invalid float value for parameter '{key}': '{val_str}'"
            ) from None
    return result


class PlayerArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._argument_groups: list[BaseArgumentGroup] = []
        self._registered_types: dict[str, TypeFunc] = {
            "rgb_color": parse_rgb_color,
            "output_resolution": parse_output_resolution,
            "color_smoothing_params": parse_color_smoothing_params,
        }

    def register_type(self, name: str, type_func: TypeFunc) -> None:
        self._registered_types[name] = type_func

    def get_type(self, name: str) -> TypeFunc:
        if name not in self._registered_types:
            raise KeyError(f"No type parser registered with name '{name}'")
        return self._registered_types[name]

    def register_argument_group[T: BaseArgumentGroup](
        self, group_class: type[T], *args: Any, **kwargs: Any
    ) -> T:
        group: T = group_class(self, *args, **kwargs)
        self._argument_groups.append(group)
        group.add_arguments()
        return group

    @classmethod
    def create_with_defaults(cls) -> "PlayerArgumentParser":
        parser = cls(
            description="Play video files in the terminal with ASCII art and sound.",
            formatter_class=argparse.RawTextHelpFormatter,
        )

        parser.register_argument_group(CoreArgumentGroup)
        parser.register_argument_group(RenderingArgumentGroup)
        parser.register_argument_group(VideoArgumentGroup)
        parser.register_argument_group(PerformanceArgumentGroup)

        return parser


class CoreArgumentGroup(BaseArgumentGroup):
    @override
    def add_arguments(self) -> None:
        if _youtube_support:
            self.parser.add_argument(
                "video_path_or_url",
                help="Path to the video file to play or youtube url.",
            )
        else:
            self.parser.add_argument(
                "video_path",
                help="Path to the video file to play.",
                name="video_path_or_url",
            )

        self.parser.add_argument(
            "--fps",
            "-f",
            type=int,
            default=None,
            help="Force playback at specific frames per second.\n"
            + "(Default: uses video's native FPS)",
        )
        self.parser.add_argument(
            "--volume",
            "-v",
            type=int,
            default=100,
            choices=range(0, 101),
            metavar="[0-100]",
            help="Set audio volume percentage (0-100).\n(Default: 100)",
        )
        self.parser.add_argument(
            "--debug",
            "-d",
            action="store_true",
            help="Enable detailed debug logging during playback.",
        )


class RenderingArgumentGroup(BaseArgumentGroup):
    @override
    def add_arguments(self) -> None:
        rendering_group = self.parser.add_argument_group("Rendering Options")
        rendering_group.add_argument(
            "--frame-color",
            type=self.parser.get_type("rgb_color"),
            default=None,
            metavar="R,G,B",
            help="Set the color of the frame border (RGB values).\n"
            + "Example: --frame-color 255,0,0 (red)",
        )
        rendering_group.add_argument(
            "--render",
            "-r",
            choices=RendererFactory.get_available_styles(),
            default="default",
            help="Select the ASCII rendering style.\n"
            + f"(Available: {', '.join(RendererFactory.get_available_styles())})\n"
            + "(Default: default)",
        )
        rendering_group.add_argument(
            "--diff-mode",
            "-dm",
            choices=["line", "char", "none"],
            default="none",
            help="Optimize rendering by only updating changed parts:\n"
            + "- line: Redraw only changed lines.\n"
            + "- char: Redraw only changed characters (may be slower).\n"
            + "- none: Redraw the full frame every time.\n"
            + "(Default: none)",
        )
        rendering_group.add_argument(
            "--output-resolution",
            "-or",
            type=self.parser.get_type("output_resolution"),
            default="native",
            metavar="W,H|native",
            help="Internal processing resolution for video frames.\n"
            + "Use 'width,height' (e.g., 160,90) or 'native'.\n"
            + "Lower resolutions can improve performance but reduce detail.\n"
            + "This does not directly set terminal character dimensions.\n"
            + "(Default: native)",
        )
        rendering_group.add_argument(
            "--no-transparent",
            "-ntr",
            action="store_false",
            dest="transparent",
            help="Disable transparent background for low brightness pixels.\n"
            + "This makes dark areas of the video appear solid instead of transparent.\n"
            + "(Default: enabled)",
        )


class VideoArgumentGroup(BaseArgumentGroup):
    @override
    def add_arguments(self) -> None:
        color_group = self.parser.add_argument_group("Color Options")
        color_group.add_argument(
            "--color",
            "-c",
            action="store_true",
            help="Enable color rendering (if supported by terminal/style).",
        )
        color_group.add_argument(
            "--grayscale",
            "-g",
            action="store_true",
            help="Convert video to grayscale before rendering.",
        )

        smoothing_group = self.parser.add_argument_group(
            "Color Smoothing (Experimental)"
        )
        smoothing_group.add_argument(
            "--color-smoothing",
            "-cs",
            action="store_true",
            help="Apply video noise reduction (smoothing) filter.\n"
            + "Can reduce flickering/blockiness but increases CPU load.",
        )
        smoothing_group.add_argument(
            "--color-smoothing-params",
            "-csp",
            type=self.parser.get_type("color_smoothing_params"),
            metavar="'key=val,...'",
            default=None,
            help="Fine-tune color smoothing filter parameters.\n"
            + "Format: 'param1=value1,param2=value2'.\n"
            + "Supported parameters (float values):\n"
            + " - luma_spatial: Spatial luma strength (brightness smoothing across space, default: 4.0)\n"
            + " - chroma_spatial: Spatial chroma strength (color smoothing across space, default: 3.0)\n"
            + " - luma_tmp: Temporal luma strength (brightness smoothing between frames, default: 6.0)\n"
            + " - chroma_tmp: Temporal chroma strength (color smoothing between frames, default: 4.5)",
        )


class PerformanceArgumentGroup(BaseArgumentGroup):
    @override
    def add_arguments(self) -> None:
        perf_group = self.parser.add_argument_group("Performance Tuning")
        perf_group.add_argument(
            "--skip-threshold",
            "-s",
            type=float,
            default=0.012,
            metavar="SECONDS",
            help="Time threshold (in seconds) for frame skipping.\n"
            + "If audio/video sync deviates more than this, frames are skipped.\n"
            + "(Default: 0.012)",
        )
        perf_group.add_argument(
            "--no-frame-skip",
            "-nfs",
            action="store_true",
            help="Disable frame skipping entirely (may cause sync issues on slow systems).",
        )
        perf_group.add_argument(
            "--pre-render",
            "-pr",
            action="store_true",
            help="Attempt to pre-render video frames ahead of time.\n"
            + "Uses more RAM but might smooth out playback.",
        )
        perf_group.add_argument(
            "--threads",
            "-t",
            type=int,
            default=multiprocessing.cpu_count(),
            metavar="N",
            help="Number of threads used for parallel frame processing.\n"
            + f"(Default: system CPU count = {multiprocessing.cpu_count()})",
        )


def parse_cli_args() -> argparse.Namespace:
    """Parses command-line arguments using the PlayerArgumentParser."""
    parser = PlayerArgumentParser.create_with_defaults()
    return parser.parse_args()


def main() -> None:
    """Main application entry point."""

    def is_youtube_url(url: str) -> bool:
        return urlparse(url).netloc in [
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "m.youtube.com",
            "music.youtube.com",
        ]

    args = parse_cli_args()
    video_path_or_url = args.video_path_or_url

    player = None
    youtube_downloader = None
    try:
        if _youtube_support:
            if is_youtube_url(video_path_or_url):
                print("Detected YouTube URL. Downloading video...")
                try:
                    youtube_downloader = YouTubeDownloader()
                    video_path_or_url = youtube_downloader.download_video(
                        video_path_or_url
                    )
                except YouTubeError as e:
                    raise YouTubeError(f"Error downloading YouTube video: {e}") from e
        elif not _youtube_support and is_youtube_url(video_path_or_url):
            raise YouTubeDependencyError

        player = Player(
            video_path=video_path_or_url,
            fps=args.fps,
            volume=args.volume,
            render_style=args.render,
            skip_threshold=args.skip_threshold,
            frame_skip=not args.no_frame_skip,
            color=args.color,
            debug=args.debug,
            frame_color=args.frame_color,
            grayscale=args.grayscale,
            color_smoothing=args.color_smoothing,
            color_smoothing_params=args.color_smoothing_params,
            pre_render=args.pre_render,
            num_threads=args.threads,
            diff_mode=args.diff_mode,
            output_resolution=args.output_resolution,
            transparent=args.transparent,
        ).play()

    except PyPlayerError as e:
        print(f"Player Error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Video file not found at '{args.video_path}'", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
    except Exception as e:
        print(
            f"\nAn unexpected error occurred: {type(e).__name__}: {e}", file=sys.stderr
        )
        if args.debug:
            traceback.print_exc()
        sys.exit(1)
    finally:
        if youtube_downloader:
            youtube_downloader.cleanup()
        if player:
            player.processor.cleanup()
        if sys.exc_info()[0] is KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
