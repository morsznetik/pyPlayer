import os
import subprocess

def split_and_sharpen_video(mp4_file, audio_output, frames_output):
    # Create output directories if they don't exist
    os.makedirs(frames_output, exist_ok=True)
    
    # Define the filter to apply edge sharpening
    # The following filter chain applies a sharpening effect using the unsharp filter
    filter_complex = "unsharp=7:7:3:7:7:3,colorlevels=rimin=0.0:gimin=0.0:bimin=0.0:rimax=0.9:gimax=0.9:bimax=0.9"
    
    # Extract audio from the video and save it to the specified output
    audio_command = [
        'ffmpeg',
        '-i', mp4_file,
        '-q:a', '0',   # Best audio quality
        '-map', 'a',
        audio_output
    ]
    subprocess.run(audio_command, check=True)
    
    # Apply the sharpening filter and extract frames
    frames_command = [
        'ffmpeg',
        '-i', mp4_file,
        '-vf', filter_complex,
        os.path.join(frames_output, 'frame_%04d.png')
    ]
    subprocess.run(frames_command, check=True)

if __name__ == "__main__":
    mp4_file_path = "movies/mesmerizer.mp4"
    audio_output_path = "output/audio.wav"
    frames_output_path = "output/frames"

    split_and_sharpen_video(mp4_file_path, audio_output_path, frames_output_path)
