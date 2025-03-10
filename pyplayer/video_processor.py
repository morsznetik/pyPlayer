import os
import multiprocessing
import tempfile
import shutil
import ffmpeg
import re


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
        except ffmpeg.Error as e:
            raise RuntimeError(
                f"Error processing video: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}"
            )

    def _extract_audio(self):
        """Extract audio from video file"""
        num_threads = multiprocessing.cpu_count()
        try:
            (
                ffmpeg.input(self.video_path)
                .output(self.audio_path, q="0", map="a", threads=num_threads)
                .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
            )
        except ffmpeg.Error as e:
            raise RuntimeError(
                f"Error extracting audio: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}"
            )

    def _extract_frames(self, grayscale=False, color_smoothing=False):
        """Extract and process frames from video file"""
        num_threads = multiprocessing.cpu_count()

        # Start with the base video input
        stream = ffmpeg.input(self.video_path)

        # Apply unsharp filter
        # stream = ffmpeg.filter(
        #     stream,
        #     "unsharp",
        #     luma_msize_x=7,
        #     luma_msize_y=7,
        #     luma_amount=3,
        #     chroma_msize_x=3,
        #     chroma_msize_y=3,
        #     chroma_amount=0,
        # )
        # Apply grayscale filter if requested
        if grayscale:
            # Apply the complex lutrgb filter
            lut_expr = "if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))"
            stream = stream.filter("lutrgb", r=lut_expr, g=lut_expr, b=lut_expr)
            # Apply hue filter to remove saturation
            stream = stream.filter("hue", s=0)

        if color_smoothing:
            stream = stream.filter("hqdn3d")

        output_path = os.path.join(self.frames_dir, "frame_%05d.png")
        try:
            (
                stream.output(output_path, threads=num_threads).run(
                    capture_stdout=True, capture_stderr=True, overwrite_output=True
                )
            )
        except ffmpeg.Error as e:
            raise RuntimeError(
                f"Error extracting frames: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}"
            )

    def _get_video_fps(self):
        """Get video frame rate using FFprobe"""
        try:
            probe = ffmpeg.probe(self.video_path)
            video_stream = next(
                (
                    stream
                    for stream in probe["streams"]
                    if stream["codec_type"] == "video"
                ),
                None,
            )
            if video_stream is None:
                return None

            # Extract frame rate which might be in the format '24/1'
            frame_rate = video_stream.get("r_frame_rate")
            if frame_rate:
                match = re.match(r"(\d+)/(\d+)", frame_rate)
                if match:
                    num, den = map(int, match.groups())
                    return num / den
            return None
        except (ffmpeg.Error, KeyError, StopIteration, ValueError):
            return None

    def cleanup(self):
        """Remove temporary files and directories"""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup temporary files: {e}")
