import os
import sys
import time
import pygame
import traceback
from .video_processor import VideoProcessor
from .ascii_renderer import AsciiRenderer

class Player:
    def __init__(self, video_path, fps=30, volume=100, render_style='default',
                 skip_threshold=0.012, frame_skip=True, color=False,
                 debug=False, frame_color=None, grayscale=False, color_smoothing=False):
        self.processor = VideoProcessor(video_path)
        self.frames_dir, self.audio_path, detected_fps = self.processor.process_video(
            grayscale=grayscale,
            color_smoothing=color_smoothing
        )
        
        self.fps = detected_fps or fps
        self.volume = volume
        self.skip_threshold = skip_threshold
        self.frame_skip = frame_skip
        self.debug = debug
        
        self.renderer = AsciiRenderer(
            style=render_style,
            color=color,
            frame_color=frame_color
        )
    
    def play(self):
        """Play the video with audio synchronization"""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(self.audio_path)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            
            self.renderer.hide_cursor()
            sys.stdout.write('\033[2J')
            
            pygame.mixer.music.play(fade_ms=5)
            self._play_frames()
            
        except KeyboardInterrupt:
            sys.stdout.write('\033[2J')
            pygame.mixer.music.stop()
            print("\nPlayback interrupted by user.")
        except Exception as e:
            print(f"\nError: {str(e)}")
            traceback.print_exc()
        finally:
            pygame.mixer.quit()
            self.renderer.show_cursor()
            self.processor.cleanup()
    
    def _play_frames(self):
        """Handle frame playback and timing"""
        term_size = os.get_terminal_size()
        frame_duration = 1.0 / self.fps
        start_time = time.perf_counter()
        next_frame_time = start_time
        current_frame = 0
        skipped_frames = 0
        
        frame_files = sorted(os.path.join(self.frames_dir, f)
                           for f in os.listdir(self.frames_dir)
                           if f.endswith('.png'))
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
                    raise FileNotFoundError(f"Frame {current_frame} missing: {frame_path}")
                
                frame_start = time.perf_counter()
                try:
                    ascii_frame = self.renderer.convert_frame(
                        frame_path,
                        term_size.columns,
                        term_size.lines
                    )
                except Exception as e:
                    raise RuntimeError(f"Frame conversion failed: {str(e)}")
                frame_process_time = time.perf_counter() - frame_start
                
                img_size = os.path.getsize(frame_path)
                ascii_size = len(ascii_frame.encode('utf-8'))
                
                sys.stdout.write('\033[H')
                sys.stdout.write(ascii_frame)
                
                if self.debug:
                    # Calculate data throughput (bytes per second)
                    throughput = ascii_size / frame_process_time if frame_process_time > 0 else 0
                    
                    # Create debug info sections
                    debug_sections = [
                        f"Frame: {current_frame + 1}/{total_frames}",
                        f"FPS: {self.fps:.1f} (real: {(current_frame + 1 - skipped_frames)/(current_time-start_time):.1f})",
                        f"Proc: {frame_process_time*1000:.1f}ms",
                        f"Size: {img_size/1024:.1f}KB→{ascii_size/1024:.1f}KB",
                        f"Throughput: {throughput/1024/1024:.2f}MB/s",
                        f"A/V Sync: {time_difference*1000:+.1f}ms",
                        f"Skipped: {skipped_frames}",
                        f"Term: {term_size.columns}x{term_size.lines}"
                    ]
                    
                    # Calculate available width for debug info
                    max_width = term_size.columns - 4  # Leave some margin
                    
                    # Split debug info into lines that fit the terminal width
                    current_line = ""
                    debug_lines = []
                    
                    for section in debug_sections:
                        if len(current_line) == 0:
                            current_line = "[" + section
                        elif len(current_line) + len(section) + 3 <= max_width:  # +3 for " | " separator
                            current_line += " | " + section
                        else:
                            debug_lines.append(current_line + "]")
                            current_line = "[" + section
                    
                    if current_line:
                        debug_lines.append(current_line + "]")
                    
                    # Write debug lines from bottom of screen
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