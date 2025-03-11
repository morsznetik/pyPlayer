# pyPlayer

A powerful and performant terminal-based video player that renders videos as ASCII art with audio.

## Features

### Multiple ASCII Rendering Styles
- **default**: Detailed ASCII character set
  - Medium quality, fast rendering
  - Fastest terminal performance
  - Decent color support (*will look blurry but is arguably the best*)
- **legacy**: Simple ASCII character set
  - Low quality, fastest rendering
  - Fastest terminal performance
  - Bad color support (*it works, but doesn't look great*)
- **block**: Block-based rendering
  - Very low quality, decently fast rendering
  - Slow terminal performance
  - Best-ish color support (*will be reworked with a smarter brightness algorithm, see TODO*)
- **braille**: Unicode 2x4 braille pattern rendering
  - Best quality, slow rendering
  - Slow terminal performance
  - Very good color support (*recommended for high-complexity videos, bad with videos with low dynamic range*)

### Color Support
- Truecolor (Full RGB) rendering
- Custom frame color options
- Grayscale conversion

### Performance Optimizations
- Adaptive frame skipping
- Multi-threaded rendering
- Pre-rendering capability (*Uses more RAM but enables smoother playback*)
- Performance metrics and debugging information

### Video Processing
- Automatic frame extraction
- Audio synchronization
- Color smoothing
- Grayscale conversion

## Installation

### Requirements
- Python 3.13+
- FFmpeg

### Windows Standalone
Pre-built executables available on the [releases page](https://github.com/morsznetik/pyPlayer/releases) or if you're feeling fancy you can also download it from the artifacts! (if you don't know what that is, you shouldn't worry about it:D).

**Windows users: don't forget to (download FFmpeg)[https://ffmpeg.org/download.html] and add it to your PATH**

*Note: Windows Defender might flag it due to PyInstaller packaging - this is a false positive. Also due to it not being signed, SmartScreen is complain*

### From Source

```zsh
git clone https://github.com/morsznetik/pyPlayer
cd pyPlayer
uv pip install -e .
```

## Usage

```zsh
# Basic usage
pyplayer path/to/your/video.mp4

# With custom rendering style and color
pyplayer path/to/your/video.mp4 --render braille --color
```

### Command Line Options

```zsh
pyplayer video_path [options]
```

#### Required Arguments
- **video_path**: Path to the video file

#### Optional Arguments
- `--fps`, `-f`: Frames per second (default: 30) - will overwrite the video's fps
- `--volume`, `-v`: Audio volume from 0-100 (default: 100)
- `--render`, `-r`: ASCII render style (choices: default, legacy, blockNoColor, block, blockv2, braille)
- `--skip-threshold`, `-s`: Time threshold to skip frames (default: 0.012)
  *Found it best to work at 12ms, but it's not a magic number, it's just what worked for me.*
- `--no-frame-skip`, `-nfs`: Disable frame skipping
  *Not recommended, it will cause sync issues with the audio.*
- `--color`, `-c`: Enable color rendering
- `--debug`, `-d`: Enable debug information
- `--frame-color`: Custom RGB color for frame in the format R,G,B
  *Nice option when you want a grayscale video to have some color.*
- `--grayscale`, `-g`: Convert video to grayscale
  *This will force the conversion of a video to grayscale, can eliminate some brightness issues when rendering without color.*
- `--color-smoothing`, `-cs`: Apply color smoothing to video
  *Generally not recommended, can cause some blockiness and ghosting, but feel free to play around with it*
- `--pre-render`, `-pr`: Pre-render video frames (uses more RAM)
  *Not recommended, it will use a lot of RAM, but useful if you want to play a video at a large resolution or make the video play smoother if you do not have a powerful enough CPU. For a 3 minute long 853x226, colored, braille-rendered video I found it to use around 9GB of RAM, but it's still not a bad option if you want to play a video at a large resolution. (Currently bugged with debug's mode on-screen performance statistics.)*
- `--threads`, `-t`: Number of threads for frame rendering (default: number of CPU cores)

## Development

### Setup Development Environment

```zsh
# Clone the repository
git clone https://github.com/morsznetik/pyPlayer.git
cd pyPlayer

# Create and activate a virtual environment
uv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
uv pip install -e .
```

### Code Style

This project uses:
- **Ruff** for linting and formatting
- **Pre-commit hooks** for code quality checks

Install pre-commit hooks:

```zsh
uv pip install pre-commit
pre-commit install
```

## TODO
- [ ] Make a character space fill-to-color algorithm to theoretically allow up to 90 times more colors
- [ ] Fix pre-render mode issues when debug is enabled
- [ ] Improve color smoothing algorithm
- [ ] Improve CI/CD pipeline
- [ ] Support for playing Youtube videos straight from the URL
- [ ] Transparency toggle

## Known Issues
- [ ] Pre-render mode is bugged with debug's mode on-screen performance statistics
- [x] Some Windows environments using the executable will have issues trying to find the video path


#### Goals for 1.0.0
- [ ] Complete all TODO's
- [ ] Fix all known issues
- [ ] Support for user-defined FFMPEG video filters
