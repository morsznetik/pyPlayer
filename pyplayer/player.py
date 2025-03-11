import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

import sys
import time
import pygame
import traceback
import statistics
import numpy as np
from typing import Callable, cast
from .video_processor import VideoProcessor
from .ascii_renderer import AsciiRenderer


class Player:
    def __init__(
        self,
        video_path: str,
        fps: int = 30,
        volume: int = 100,
        render_style: str = "default",
        skip_threshold: float = 0.012,
        frame_skip: bool = True,
        color: bool = False,
        debug: bool = False,
        frame_color: tuple[int, int, int] | None = None,
        grayscale: bool = False,
        color_smoothing: bool = False,
        pre_render: bool = False,
        num_threads: int = 0,
    ) -> None:
        self.processor = VideoProcessor(video_path)
        self.frames_dir, self.audio_path, detected_fps = self.processor.process_video(
            grayscale=grayscale, color_smoothing=color_smoothing
        )

        self.fps = detected_fps or fps
        self.volume = volume
        self.skip_threshold = skip_threshold
        self.frame_skip = frame_skip
        self.debug = debug
        self.pre_render = pre_render
        self.num_threads = num_threads

        self.renderer = AsciiRenderer(
            style=render_style, color=color, frame_color=frame_color
        )

        self.pre_rendered_frames = {}
        if self.pre_render:
            frame_files = sorted(
                os.path.join(self.frames_dir, f)
                for f in os.listdir(self.frames_dir)
                if f.endswith(".png")
            )
            term_size = os.get_terminal_size()
            self.pre_rendered_frames = self.renderer.pre_render_frames(
                frame_files, term_size.columns, term_size.lines, self.num_threads
            )

    def play(self) -> None:
        """Play the video with audio synchronization"""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(self.audio_path)
            pygame.mixer.music.set_volume(self.volume / 100.0)

            self.renderer.hide_cursor()
            sys.stdout.write("\033[2J")

            pygame.mixer.music.play(fade_ms=5)
            self._play_frames()

        except KeyboardInterrupt:
            sys.stdout.write("\033[2J")
            pygame.mixer.music.stop()
            print("\nPlayback interrupted by user.")
        except Exception as e:
            print(f"\nError: {str(e)}")
            traceback.print_exc()
        finally:
            pygame.mixer.quit()
            self.renderer.show_cursor()
            self.processor.cleanup()

    def _play_frames(self) -> None:
        """Handle frame playback and timing"""
        term_size = os.get_terminal_size()
        frame_duration = 1.0 / self.fps
        start_time = time.perf_counter()
        next_frame_time = start_time
        current_frame = 0
        skipped_frames = 0

        # performance metrics
        frame_times: list[float] = []
        processing_times: list[float] = []
        sync_offsets: list[float] = []
        throughput_rates: list[float] = []

        frame_files: list[str] = sorted(
            os.path.join(self.frames_dir, f)
            for f in os.listdir(self.frames_dir)
            if f.endswith(".png")
        )
        total_frames = len(frame_files)

        while current_frame < total_frames:
            current_time = time.perf_counter()
            time_difference = current_time - next_frame_time

            if time_difference >= 0:
                if time_difference > self.skip_threshold and self.frame_skip:
                    skipped_frames += 1
                    next_frame_time = start_time + (current_frame + 1) * frame_duration
                    current_frame += 1
                    continue

                term_size = os.get_terminal_size()

                frame_path = frame_files[current_frame]
                if not os.path.exists(frame_path):
                    raise FileNotFoundError(
                        f"Frame {current_frame} missing: {frame_path}"
                    )

                frame_start = time.perf_counter()
                try:
                    # Use pre-rendered frame if available, otherwise render on-the-fly
                    if self.pre_render and frame_path in self.pre_rendered_frames:
                        ascii_frame = self.pre_rendered_frames[frame_path]
                    else:
                        ascii_frame = self.renderer.convert_frame(
                            frame_path,
                            term_size.columns,
                            term_size.lines,
                            self.num_threads,
                        )
                except Exception as e:
                    raise RuntimeError(f"Frame conversion failed: {str(e)}")
                frame_process_time = time.perf_counter() - frame_start

                img_size = os.path.getsize(frame_path)
                ascii_size = len(ascii_frame.encode("utf-8"))

                throughput = (
                    ascii_size / frame_process_time if frame_process_time > 0 else 0
                )

                if current_frame > 0:  # skip first frame
                    frame_time = current_time - (
                        start_time + (current_frame - 1) * frame_duration
                    )
                    frame_times.append(frame_time)
                    processing_times.append(frame_process_time)
                    sync_offsets.append(time_difference)
                    throughput_rates.append(throughput)

                sys.stdout.write("\033[H")
                sys.stdout.write(ascii_frame)

                if self.debug:
                    window_size = min(10, current_frame)
                    if window_size > 0:
                        recent_frame_time = (
                            sum(frame_times[-window_size:]) / window_size
                        )
                        real_fps = (
                            1.0 / recent_frame_time if recent_frame_time > 0 else 0
                        )
                    else:
                        real_fps = 0

                    debug_sections = [
                        f"Frame: {current_frame + 1}/{total_frames}",
                        f"FPS: {self.fps:.1f} (real: {real_fps:.1f})",
                        f"Proc: {frame_process_time * 1000:.1f}ms",
                        f"Size: {img_size / 1024:.1f}KB→{ascii_size / 1024:.1f}KB",
                        f"Throughput: {throughput / 1024 / 1024:.2f}MB/s",
                        f"A/V Sync: {time_difference * 1000:+.1f}ms",
                        f"Skipped: {skipped_frames}",
                        f"Term: {term_size.columns}x{term_size.lines}",
                    ]

                    max_width = term_size.columns - 4  # margin

                    current_line = ""
                    debug_lines = []

                    for section in debug_sections:
                        if len(current_line) == 0:
                            current_line = "[" + section
                        elif (
                            len(current_line) + len(section) + 3 <= max_width
                        ):  # +3 for | separator
                            current_line += " | " + section
                        else:
                            debug_lines.append(current_line + "]")
                            current_line = "[" + section

                    if current_line:
                        debug_lines.append(current_line + "]")

                    base_line = term_size.lines
                    for i, line in enumerate(reversed(debug_lines)):
                        sys.stdout.write(f"\033[{base_line - i};0H{line}")

                sys.stdout.flush()
                current_frame += 1
                next_frame_time = start_time + current_frame * frame_duration
            else:
                time.sleep(-time_difference)

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        if self.debug and frame_times:
            term_size = os.get_terminal_size()

            # statistics
            frames_played = total_frames - skipped_frames
            drop_rate: float | None = (
                (skipped_frames / total_frames) * 100 if total_frames > 0 else None
            )

            def __calc[T, R: (int | float)](
                vars: T, func: Callable[[T], R], factor: float
            ) -> float | None:
                return func(vars) * factor if vars else None

            stats: dict[str, dict[str, float | None]] = {
                "FPS": {
                    "target": self.fps,
                    "avg": __calc(frame_times, lambda v: 1.0 / statistics.mean(v), 1.0),
                    "min": __calc(frame_times, lambda v: 1.0 / max(v), 1.0),
                    "max": __calc(frame_times, lambda v: 1.0 / min(v), 1.0),
                },
                "Frame Time": {
                    "avg": __calc(frame_times, statistics.mean, 1000),
                    "min": __calc(frame_times, min, 1000),
                    "max": __calc(frame_times, max, 1000),
                },
                "Processing": {
                    "avg": __calc(processing_times, statistics.mean, 1000),
                    "min": __calc(processing_times, min, 1000),
                    "max": __calc(processing_times, max, 1000),
                },
                "A/V Sync": {
                    "avg": __calc(sync_offsets, statistics.mean, 1000),
                    "min": __calc(sync_offsets, min, 1000),
                    "max": __calc(sync_offsets, max, 1000),
                },
                "Throughput": {
                    "avg": __calc(throughput_rates, statistics.mean, 1 / (1024 * 1024)),
                    "min": __calc(throughput_rates, min, 1 / (1024 * 1024)),
                    "max": __calc(throughput_rates, max, 1 / (1024 * 1024)),
                },
            }

            percentiles: dict[int, float | None] = (
                {
                    p: __calc(
                        frame_times,
                        cast(
                            Callable[[list[float]], float],
                            lambda v: np.percentile(v, p),
                        ),
                        1000,
                    )
                    for p in [90, 95, 99]
                }
                if frame_times
                else {}
            )

            # clear screen and cursor at top
            sys.stdout.write("\033[2J\033[H")

            width = min(term_size.columns - 6, 76)  # max width with margin
            h_margin = (
                term_size.columns - width
            ) // 2  # horizontal margin for centering

            box = {
                "tl": "╭",
                "tr": "╮",
                "bl": "╰",
                "br": "╯",  # corners
                "h": "─",
                "v": "│",  # edges
                "lt": "├",
                "rt": "┤",
                "tt": "┬",
                "bt": "┴",  # t-junctions
                "cross": "┼",  # cross
            }

            def draw_box(title: str, content: list[str]) -> list[str]:
                title_len = len(title) + 2  # +2 for spaces around title
                left_pad = (width - title_len) // 2
                right_pad = width - title_len - left_pad

                lines = [
                    f"{box['tl']}{box['h'] * left_pad} {title} {box['h'] * right_pad}{box['tr']}"
                ]
                for line in content:
                    if not line:
                        lines.append(f"{box['v']}{' ' * width}{box['v']}")
                    elif line.startswith("•"):  # points
                        lines.append(f"{box['v']} {line:<{width - 2}} {box['v']}")
                    elif ":" in line and not line.startswith(" "):  # headers
                        lines.append(f"{box['v']} {line:^{width - 2}} {box['v']}")
                    else:  # content
                        lines.append(f"{box['v']} {line:<{width - 2}} {box['v']}")

                lines.append(f"{box['bl']}{box['h'] * width}{box['br']}")
                return lines

            summary_content = [
                "",
                f"• Frames: {frames_played}/{total_frames}",
                f"• Dropped: {skipped_frames} ({drop_rate and f'{drop_rate:.1f}%' or 'N/A'})"
                f"• Target FPS: {self.fps:.1f}",
                "",
            ]

            perf_content: list[str] = [""]
            for metric, values in stats.items():
                unit = (
                    "ms"
                    if metric in ["Frame Time", "Processing", "A/V Sync"]
                    else "MB/s"
                    if metric == "Throughput"
                    else ""
                )

                perf_content.append(f"{metric}{f' ({unit})' if unit else ''}:")

                if metric == "FPS":
                    perf_content.append(
                        f"  Target: {values['target']:.1f}  |  Actual: {values['avg']:.1f}"
                    )

                vals: list[str] = [
                    f"{k.capitalize()}: {'N/A' if v is None else f'{float(v):.1f}{unit}'}"
                    for k, v in values.items()
                    if k != "target"
                ]
                perf_content.append(f"  {' | '.join(vals)}")
                perf_content.append("")

            latency_content: list[str] = [""]
            if percentiles:
                percentile_vals: list[str] = [
                    f"{p}th: {'N/A' if v is None else f'{float(v):.1f}ms'}"
                    for p, v in sorted(percentiles.items())
                ]
                latency_content.append("Frame Time Percentiles:")
                latency_content.append(f"  {' | '.join(percentile_vals)}")
                latency_content.append("")

            summary_box = draw_box("PLAYBACK SUMMARY", summary_content)
            performance_box = draw_box("PERFORMANCE METRICS", perf_content)
            latency_box = (
                draw_box("LATENCY ANALYSIS", latency_content) if percentiles else []
            )

            all_lines: list[str] = []
            for line in (
                summary_box
                + [""]
                + performance_box
                + ([""] + latency_box if latency_box else [])
            ):
                all_lines.append(f"{' ' * h_margin}{line}")

            # Center the output vertically
            v_margin = max(1, (term_size.lines - len(all_lines)) // 2)
            for i, line in enumerate(all_lines):
                sys.stdout.write(f"\033[{v_margin + i};0H{line}")

            sys.stdout.flush()
