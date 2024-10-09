import glob
import sys
import time
import os
import argparse
from PIL import Image
from tqdm import tqdm
import subprocess

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

ASCII_RENDER_STYLES = {
    'default': "      `.-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@",
    'legacy': "     .:-=+*#%@",
    'block': "▒▓█",
    "blockv2": "█████████",
    'braille': '⠀⠀⠀⠀⠀⠠⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿'
}


def clear_screen():
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)


def convert_to_ascii(image_path, width, height, ascii_chars, color=False):
    img = Image.open(image_path).resize((width, height))
    intensity_range = 255 / (len(ascii_chars) - 1)

    if color:
        return convert_to_ascii_color(img, ascii_chars, intensity_range)
    return convert_to_ascii_grayscale(img, ascii_chars, intensity_range)


def convert_to_ascii_color(img, ascii_chars, intensity_range):
    img = img.convert('RGB')
    ascii_image = []

    for pixel in img.getdata():
        r, g, b = pixel
        if r == 0 and g == 0 and b == 0:
            ascii_image.append(' ')  # Black pixels are represented by a space
        else:
            color_code = f"\033[38;2;{r};{g};{b}m"
            ascii_char = ascii_chars[int((r + g + b) / 3 / intensity_range)]
            ascii_image.append(color_code + ascii_char)

    ascii_image.append("\033[0m")
    return ''.join(ascii_image)


def convert_to_ascii_grayscale(img, ascii_chars, intensity_range):
    img = img.convert('L')  # Convert to grayscale
    return ''.join([ascii_chars[int(pixel_value / intensity_range)] for pixel_value in img.getdata()])


def preload_frames(frame_folder, width, height, ascii_chars, color=False):
    frame_files = sorted(glob.glob(os.path.join(frame_folder, '*.png')))
    frames = []
    with tqdm(total=len(frame_files), desc="Processing frames", unit='frame', ncols=100) as pbar:
        for frame in frame_files:
            frame_data = convert_to_ascii(frame, width, height, ascii_chars, color)
            frames.append(frame_data)
            pbar.update(1)
    return frames


def play_video_with_sound(frame_folder, audio_path, fps, volume, skip_threshold, frame_skip, color, debug):
    pygame.mixer.init()
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.set_volume(volume / 100.0)

    frame_files = sorted(glob.glob(os.path.join(frame_folder, '*.png')))
    total_frames = len(frame_files)
    frame_duration = 1.0 / fps

    pygame.mixer.music.play(fade_ms=5)

    term_size = os.get_terminal_size()

    start_time = time.perf_counter()
    next_frame_time = start_time
    current_frame = 0
    skipped_frames = 0

    while current_frame < total_frames:
        current_time = time.perf_counter()

        time_difference = current_time - next_frame_time

        if time_difference >= 0:
            if time_difference > skip_threshold and frame_skip:
                skipped_frames += 1
                next_frame_time = start_time + (current_frame + 1) * frame_duration
                current_frame += 1
                continue

            if current_frame % fps == 0:
                term_size = os.get_terminal_size()
            ascii_frame = convert_to_ascii(frame_files[current_frame], *term_size, ascii_chars, color)

            sys.stdout.write("\033[H")
            sys.stdout.write(ascii_frame)

            if debug:
                debug_info = (f"[Frame: {current_frame + 1}/{total_frames}, "
                              f"A/V Off sync: {time_difference:.6f}s, "
                              f"Skipped: {skipped_frames}]")

                sys.stdout.write(f"\033[{term_size.lines};0H{debug_info}")

            sys.stdout.flush()

            current_frame += 1
            next_frame_time = start_time + current_frame * frame_duration

            if current_frame >= total_frames:
                break
        else:
            time.sleep(-time_difference)

    while pygame.mixer.music.get_busy():
        time.sleep(0.1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a video with colored ASCII art and sound.")
    parser.add_argument('frame_folder', type=str, help='Path to the folder containing video frames')
    parser.add_argument('audio_path', type=str, help='Path to the audio file')
    parser.add_argument('--fps', '-f', type=int, default=30, help='Frames per second')
    parser.add_argument('--volume', '-v', type=int, default=100, help='Audio volume')
    parser.add_argument('--render', '-r', choices=ASCII_RENDER_STYLES.keys(), default='default',
                        help='ASCII render style')
    parser.add_argument('--skip-threshold', '-s', type=float, default=0.012, help='Time threshold to skip frames')
    parser.add_argument('--no-frame-skip', '-nfs', action='store_false', dest='frame_skip',
                        help='Disable frame skipping')
    parser.add_argument('--generate', '-g', action='store_true', help='Generate ASCII frames ahead of time')
    parser.add_argument('--noaudio', '-na', action='store_true', help='Disable sound')
    parser.add_argument('--color', '-c', action='store_true', help='Enable color rendering')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug information')
    args = parser.parse_args()

    ascii_chars = ASCII_RENDER_STYLES.get(args.render, ASCII_RENDER_STYLES['default'])
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    if args.generate:
        term_size = os.get_terminal_size()
        frames = preload_frames(args.frame_folder, *term_size, ascii_chars, args.color)
    else:
        frames = None

    try:
        clear_screen()
        play_video_with_sound(args.frame_folder, args.audio_path, args.fps, args.volume, args.skip_threshold,
                              args.frame_skip, args.color, args.debug)
    except KeyboardInterrupt:
        clear_screen()
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        clear_screen()
        sys.exit(0)
