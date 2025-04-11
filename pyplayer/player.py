import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

import sys
import time
import pygame
import traceback
import statistics
import re
import numpy as np
from typing import Callable
from .video_processor import VideoProcessor
from .renderer_factory import RendererManager
from .renderer_factory import RGBPixel
from .exceptions import (
    PyPlayerError,
    FrameNotFoundError,
    FrameRenderingError,
    AudioPlaybackError,
    VideoProcessingError,
)


class Player:
    def __init__(
        self,
        video_path: str,
        fps: float | None = None,
        volume: int = 100,
        render_style: str = "default",
        skip_threshold: float = 0.012,
        frame_skip: bool = True,
        color: bool = False,
        debug: bool = False,
        frame_color: RGBPixel | None = None,
        grayscale: bool = False,
        color_smoothing: bool = False,
        color_smoothing_params: dict | None = None,
        pre_render: bool = False,
        num_threads: int = 0,
        diff_mode: str = "none",
        output_resolution: tuple[int, int] | None = (640, 480),
    ) -> None:
        self.processor = VideoProcessor(video_path)
        self.frames_dir, self.audio_path, detected_fps = self.processor.process_video(
            grayscale=grayscale,
            color_smoothing=color_smoothing,
            color_smoothing_params=color_smoothing_params,
            output_resolution=output_resolution,
        )

        if fps is not None:
            self.fps = fps
        elif detected_fps is not None:
            self.fps = detected_fps
        else:
            raise VideoProcessingError("Unable to detect FPS in video file.")

        self.volume = volume
        self.skip_threshold = skip_threshold
        self.frame_skip = frame_skip
        self.debug = debug
        self.pre_render = pre_render
        self.num_threads = num_threads
        self.diff_mode = diff_mode
        self.previous_frame = None
        self.diff_render_time = 0.0

        self.renderer = RendererManager(
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
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(self.audio_path)
                pygame.mixer.music.set_volume(self.volume / 100.0)
            except pygame.error as e:
                raise AudioPlaybackError(str(e))

            self.renderer.hide_cursor()
            sys.stdout.write("\033[2J")

            pygame.mixer.music.play(fade_ms=5)
            self._play_frames()

        except KeyboardInterrupt:
            sys.stdout.write("\033[2J")
            pygame.mixer.music.stop()
            print("\nPlayback interrupted by user.")
        except PyPlayerError as e:
            print(f"\nError: {e.message}")
        except Exception as e:
            print(f"\nUnexpected error: {str(e)}")
            traceback.print_exc()
        finally:
            pygame.mixer.quit()
            self.renderer.show_cursor()
            self.processor.cleanup()

    def _render_frame_diff(self, current_frame: str) -> None:
        diff_start_time = time.perf_counter()

        if self.previous_frame is None:
            sys.stdout.write("\033[H")
            sys.stdout.write(current_frame)
            self.diff_render_time = time.perf_counter() - diff_start_time
            return

        prev_lines = self.previous_frame.split("\n")
        curr_lines = current_frame.split("\n")

        def strip_ansi(text: str) -> str:
            ansi_escape = re.compile(r"\033(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            return ansi_escape.sub("", text)

        if self.diff_mode == "line":
            for i, (prev_line, curr_line) in enumerate(zip(prev_lines, curr_lines)):
                if strip_ansi(prev_line) != strip_ansi(curr_line):
                    sys.stdout.write(f"\033[{i + 1};0H")
                    sys.stdout.write(curr_line)

            if len(curr_lines) > len(prev_lines):
                for i in range(len(prev_lines), len(curr_lines)):
                    sys.stdout.write(f"\033[{i + 1};0H")
                    sys.stdout.write(curr_lines[i])

        elif self.diff_mode == "char":
            for row_idx, (prev_line, curr_line) in enumerate(
                zip(prev_lines, curr_lines)
            ):
                stripped_prev = strip_ansi(prev_line)
                stripped_curr = strip_ansi(curr_line)

                max_len = min(len(stripped_prev), len(stripped_curr))
                for col_idx in range(max_len):
                    if stripped_prev[col_idx] != stripped_curr[col_idx]:
                        sys.stdout.write(f"\033[{row_idx + 1};{col_idx + 1}H")
                        sys.stdout.write(curr_line[col_idx])

                # Handle any extra characters in the current line
                if len(stripped_curr) > len(stripped_prev):
                    for col_idx in range(len(stripped_prev), len(stripped_curr)):
                        sys.stdout.write(f"\033[{row_idx + 1};{col_idx + 1}H")
                        sys.stdout.write(curr_line[col_idx])

            # Handle extra lines if current frame is longer
            if len(curr_lines) > len(prev_lines):
                for row_idx in range(len(prev_lines), len(curr_lines)):
                    sys.stdout.write(f"\033[{row_idx + 1};1H")
                    sys.stdout.write(curr_lines[row_idx])

        self.diff_render_time = time.perf_counter() - diff_start_time

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
        diff_render_times: list[float] = []  # Track diff render times

        frame_files = sorted(
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
                    raise FrameNotFoundError(current_frame, frame_path)

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
                        )
                except FrameRenderingError as e:
                    raise e
                except Exception as e:
                    raise FrameRenderingError(frame_path, str(e))

                frame_process_time = time.perf_counter() - frame_start

                img_size = os.path.getsize(frame_path)
                ascii_size = len(ascii_frame.encode("utf-8"))

                # Calculate memory usage of pre-rendered frames
                pre_rendered_memory = sum(
                    len(frame.encode("utf-8"))
                    for frame in self.pre_rendered_frames.values()
                )

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
                    diff_render_times.append(
                        self.diff_render_time
                    )  # Add diff render time to the list

                # Apply diff rendering based on the selected mode
                if self.diff_mode == "none" or self.previous_frame is None:
                    # Full frame rendering (no diff)
                    sys.stdout.write("\033[H")
                    sys.stdout.write(ascii_frame)
                else:
                    # Diff-based rendering
                    self._render_frame_diff(ascii_frame)

                # Store current frame for next comparison
                self.previous_frame = ascii_frame

                if self.pre_render and frame_path in self.pre_rendered_frames:
                    del self.pre_rendered_frames[frame_path]

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

                    memory_usage = pre_rendered_memory / (1024 * 1024)  # convert to MB

                    debug_sections = [
                        f"Frame: {current_frame + 1}/{total_frames}{' [pre]' if self.pre_render else '[on-the-fly]'}",
                        f"FPS: {self.fps:.1f} (real: {real_fps:.1f})",
                        f"{f'Mem: {memory_usage:.2f}MB' if self.pre_render else f'Proc: {frame_process_time * 1000:.1f}ms'}",
                        f"Size: {img_size / 1024:.1f}KB→{ascii_size / 1024:.1f}KB",
                    ]

                    # only add throughput for non-pre-rendered frames
                    if not self.pre_render:
                        debug_sections.append(
                            f"Throughput: {throughput / 1024 / 1024:.2f}MB/s"
                        )
                        # Add diff render timing information
                        debug_sections.append(
                            f"Diff Render: {self.diff_render_time * 1000:.1f}ms"
                        )

                    # the rest
                    debug_sections.extend(
                        [
                            f"A/V Sync: {time_difference * 1000:+.1f}ms",
                            f"Skipped: {skipped_frames}",
                            f"Term: {term_size.columns}x{term_size.lines}",
                        ]
                    )

                    max_width = term_size.columns - 4  # margin

                    current_line = ""
                    debug_lines = [""]

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
            drop_rate = (
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
                "Diff Rendering": {
                    "avg": __calc(diff_render_times, statistics.mean, 1000),
                    "min": __calc(diff_render_times, min, 1000),
                    "max": __calc(diff_render_times, max, 1000),
                },
            }

            if not self.pre_render:
                stats["Throughput"] = {
                    "avg": __calc(throughput_rates, statistics.mean, 1 / (1024 * 1024)),
                    "min": __calc(throughput_rates, min, 1 / (1024 * 1024)),
                    "max": __calc(throughput_rates, max, 1 / (1024 * 1024)),
                }

            percentiles = (
                {
                    p: __calc(
                        frame_times,
                        lambda v: float(np.percentile(v, p)),
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
                + f"• Target FPS: {self.fps:.1f}",
                "",
            ]

            perf_content = [""]
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

            latency_content = [""]
            if percentiles:
                percentile_vals = [
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

            all_lines = [""]
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
