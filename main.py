import os
import subprocess
import multiprocessing

def split_and_sharpen_video(mp4_file, audio_output, frames_output, grayscale=False, color_smoothing=False):
    # Create output directories if they don't exist
    os.makedirs(frames_output, exist_ok=True)
    
    # Get the number of available CPU threads
    num_threads = multiprocessing.cpu_count()
    
    # Initialize the filter chain with sharpening
    filter_complex = "unsharp=7:7:3:7:7:3"
    
    if grayscale:
        filter_complex += ",lutrgb=r='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))':g='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))':b='if(gte(val,0), if(gte(val,224), 255, if(gte(val,128), 192, if(gte(val,64), 128, 0))))',hue=s=0"
    
    # Add color smoothing filter (hqdn3d) if the color_smoothing flag is True
    if color_smoothing:
        filter_complex += ",hqdn3d"
    
    # Extract audio from the video and save it to the specified output
    audio_command = [
        'ffmpeg',
        '-i', mp4_file,
        '-q:a', '0',   # Best audio quality
        '-map', 'a',
        '-threads', str(num_threads),  # Use all available threads
        audio_output
    ]
    subprocess.run(audio_command, check=True)
    
    # Apply the sharpening (and any additional filters) and extract frames
    frames_command = [
        'ffmpeg',
        '-i', mp4_file,
        '-vf', filter_complex,
        '-threads', str(num_threads),  # Use all available threads
        os.path.join(frames_output, 'frame_%05d.png')
    ]
    subprocess.run(frames_command, check=True)

if __name__ == "__main__":
    mp4_file_path = "movies/mayo96.mp4"
    audio_output_path = "output/audio.wav"
    frames_output_path = "output/frames"
    
    # Example usage: grayscale=True, color_smoothing=True
    split_and_sharpen_video(mp4_file_path, audio_output_path, frames_output_path, grayscale=False, color_smoothing=False)
