import os
import sys
import argparse
from pyplayer.player import Player

def main():
    parser = argparse.ArgumentParser(description="Play video files in terminal with ASCII art and sound.")
    parser.add_argument('video_path', help='Path to the video file')
    parser.add_argument('--fps', '-f', type=int, default=30, help='Frames per second')
    parser.add_argument('--volume', '-v', type=int, default=100, help='Audio volume (0-100)')
    parser.add_argument('--render', '-r', choices=['default', 'legacy', 'blockNoColor', 'block', 'blockv2', 'braille'],
                        default='default', help='ASCII render style')
    parser.add_argument('--skip-threshold', '-s', type=float, default=0.012,
                        help='Time threshold to skip frames')
    parser.add_argument('--no-frame-skip', '-nfs', action='store_true',
                        help='Disable frame skipping')
    parser.add_argument('--color', '-c', action='store_true',
                        help='Enable color rendering')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug information')
    parser.add_argument('--frame-color', type=str,
                        help='Custom RGB color for frame in the format R,G,B')
    parser.add_argument('--grayscale', '-g', action='store_true',
                        help='Convert video to grayscale')
    parser.add_argument('--color-smoothing', '-cs', action='store_true',
                        help='Apply color smoothing to video')

    args = parser.parse_args()

    # Validate video file exists
    if not os.path.isfile(args.video_path):
        print(f"Error: Video file '{args.video_path}' not found.")
        sys.exit(1)

    # Parse frame color if provided
    frame_color = None
    if args.frame_color:
        try:
            frame_color = tuple(map(int, args.frame_color.split(',')))
            if len(frame_color) != 3 or any(c < 0 or c > 255 for c in frame_color):
                raise ValueError
        except ValueError:
            print("Error: Frame color must be in the format R,G,B with values between 0 and 255.")
            sys.exit(1)

    try:
        # Create and start the player
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
            color_smoothing=args.color_smoothing
        )
        player.play()
    except Exception as e:
        print(f"\nError while creating Player: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()