import sys
import argparse
import multiprocessing
from pyplayer.player import Player
from pyplayer.exceptions import PyPlayerError
from pyplayer.renderer_factory import RendererFactory, RGBPixel


def main():
    parser = argparse.ArgumentParser(
        description="Play video files in terminal with ASCII art and sound."
    )
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument(
        "--fps",
        "-f",
        type=int,
        help="Frames per second (defaults to video's native FPS)",
    )
    parser.add_argument(
        "--volume", "-v", type=int, default=100, help="Audio volume (0-100)"
    )
    parser.add_argument(
        "--render",
        "-r",
        choices=RendererFactory.get_available_styles(),
        default="default",
        help="ASCII render style",
    )
    parser.add_argument(
        "--skip-threshold",
        "-s",
        type=float,
        default=0.012,
        help="Time threshold to skip frames",
    )
    parser.add_argument(
        "--no-frame-skip", "-nfs", action="store_true", help="Disable frame skipping"
    )
    parser.add_argument(
        "--color", "-c", action="store_true", help="Enable color rendering"
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Enable debug information"
    )
    parser.add_argument(
        "--frame-color", type=str, help="Custom RGB color for frame in the format R,G,B"
    )
    parser.add_argument(
        "--grayscale", "-g", action="store_true", help="Convert video to grayscale"
    )
    parser.add_argument(
        "--color-smoothing",
        "-cs",
        action="store_true",
        help="Apply color smoothing to video",
    )
    parser.add_argument(
        "--pre-render",
        "-pr",
        action="store_true",
        help="Pre-render video frames (uses more RAM)",
    )
    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Number of threads for frame rendering",
    )
    parser.add_argument(
        "--diff-mode",
        "-dm",
        choices=["line", "char", "none"],
        default="none",
        help="Frame difference rendering mode (line-by-line, character-by-character, or none)",
    )
    parser.add_argument(
        "--output-resolution",
        "-or",
        type=str,
        default="native",
        help="Default is 'native'. Use a lower resolution if video processing is slow. This setting affects video-frame processing, not terminal rendering. Format: width,height (e.g., 640,480) or 'native' for original resolution.",
    )

    args = parser.parse_args()

    frame_color: RGBPixel | None = None
    if args.frame_color:
        try:
            r, g, b = map(int, args.frame_color.split(","))
            if not all(0 <= c <= 255 for c in (r, g, b)):
                raise ValueError("RGB values must be between 0 and 255")
            frame_color = (r, g, b)
        except ValueError as e:
            print(f"Error: Invalid frame color format '{args.frame_color}'. {e}")
            print("Expected format: R,G,B (e.g., 255,0,0)")
            sys.exit(1)

    output_resolution_val: tuple[int, int] | None
    if args.output_resolution.lower() == "native":
        output_resolution_val = None
    else:
        try:
            parts = args.output_resolution.split(",")
            if len(parts) != 2:
                raise ValueError("Resolution must contain exactly one comma.")

            width_str, height_str = parts
            # handle potential whitespace like "640, 480"
            width = int(width_str.strip())
            height = int(height_str.strip())

            if width <= 0 or height <= 0:
                raise ValueError(
                    "Resolution width and height must be positive integers."
                )

            output_resolution_val = (width, height)
        except ValueError as e:
            print(
                f"Error: Invalid output resolution format '{args.output_resolution}'. {e}"
            )
            print(
                "Expected format: width,height (e.g., 640,480) or literal 'native' for original resolution"
            )
            sys.exit(1)

    player = None
    try:
        player = Player(
            video_path=args.video_path,
            fps=args.fps,
            volume=args.volume,
            render_style=args.render,
            skip_threshold=args.skip_threshold,
            frame_skip=not args.no_frame_skip,
            color=args.color,
            debug=args.debug,
            frame_color=frame_color,
            grayscale=args.grayscale,
            color_smoothing=args.color_smoothing,
            pre_render=args.pre_render,
            num_threads=args.threads,
            diff_mode=args.diff_mode,
            output_resolution=output_resolution_val,
        )
        player.play()
    except PyPlayerError as e:
        print(f"Error: {e.message}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)
    finally:
        if player:
            player.processor.cleanup()
        # make sure exit(0) happens after cleanup if interrupted
        exc_type, _, _ = sys.exc_info()
        if exc_type is KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
