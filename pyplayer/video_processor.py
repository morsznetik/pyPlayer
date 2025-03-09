import os
import subprocess
import multiprocessing
import tempfile
import shutil


class VideoProcessor:
    def __init__(self, video_path):
        self.video_path = video_path
        self.temp_dir = tempfile.mkdtemp(prefix="pyplayer_")
        self.frames_dir = os.path.join(self.temp_dir, "frames")
        self.audio_path = os.path.join(self.temp_dir, "audio.wav")
        os.makedirs(self.frames_dir, exist_ok=True)

    def process_video(self, grayscale=False, color_smoothing=False):
        """Process video file by extracting frames and audio"""
        try:
            fps = self._get_video_fps()
            self._extract_audio()
            self._extract_frames(grayscale, color_smoothing)
            return self.frames_dir, self.audio_path, fps
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error processing video: {e}")

    def _extract_audio(self):
        """Extract audio from video file"""
        num_threads = multiprocessing.cpu_count()
        audio_command = [
            "ffmpeg",
            "-i",
            self.video_path,
            "-q:a",
            "0",
            "-map",
            "a",
            "-threads",
            str(num_threads),
            self.audio_path,
        ]
        subprocess.run(audio_command, check=True, capture_output=True)

    def _extract_frames(self, grayscale=False, color_smoothing=False):
        """Extract and process frames from video file"""
        num_threads = multiprocessing.cpu_count()
        filter_complex = "unsharp=7:7:3:7:7:3"

        if grayscale:
            filter_complex += ",lutrgb=r='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))':g='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))':b='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))',hue=s=0"

        if color_smoothing:
            filter_complex += ",hqdn3d"

        frames_command = [
            "ffmpeg",
            "-i",
            self.video_path,
            "-vf",
            filter_complex,
            "-threads",
            str(num_threads),
            os.path.join(self.frames_dir, "frame_%05d.png"),
        ]
        subprocess.run(frames_command, check=True, capture_output=True)

    def _get_video_fps(self):
        """Get video frame rate using FFprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                self.video_path,
            ]
            output = subprocess.check_output(cmd).decode().strip()
            num, den = map(int, output.split("/"))
            return num / den
        except (subprocess.CalledProcessError, ValueError):
            return None

    def cleanup(self):
        """Remove temporary files and directories"""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup temporary files: {e}")
