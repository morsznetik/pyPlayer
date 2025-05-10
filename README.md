# pyPlayer

[![Test, build, deploy](https://github.com/morsznetik/pyPlayer/actions/workflows/ci.yml/badge.svg)](https://github.com/morsznetik/pyPlayer/actions/workflows/ci.yml)

A powerful and performant terminal-based video player that renders videos as ASCII art with audio.

## Contributing

Contributions are very much welcome! Please open an issue or submit a pull request.

## Features

### YouTube Support

- Play videos directly from YouTube URLs
- Automatic video downloading and cleanup
- Optional dependency

### Multiple ASCII Rendering Styles

- **default**: Detailed ASCII character set
  - Medium quality, fast rendering
  - Fastest terminal performance
  - Excellent color support (*will look blurry but is arguably the best with high-complexity videos*)
- **halfblock**: Unicode Lower half block (▄) rendering (1:1 pixel ratio); recommended for most
  - High quality, slow-ish rendering
  - Meh terminal performance
  - Excellent color support (*achieves double vertical resolution by using foreground/background colors but same drawbacks as the default, it'll look blurry if it's small*)
- **legacy**: Simple ASCII character set
  - Low quality, fastest rendering
  - Fastest terminal performance
  - Poor color support (*it works, but doesn't look great*)
- **braille**: Unicode 2x4 braille pattern rendering
  - Best* quality, slow rendering
  - Slow terminal performance
  - Decent color support (*recommended for high-complexity videos, bad with videos with low dynamic range*)

#### Deprecated Rendering Styles

The following styles are deprecated and will be removed in a future version; they are still useable and show up in the help menu.

Superseded by halfblock:

- **block**: Block-based rendering
- **blockNoColor**: Hacky way to have transparency with block rendering
- **blockv2**: Pixel-based rendering with only full blocks

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

> **Note**:
> This is just how I build it, just suggestions.

### Requirements

- Python 3.13+
- FFmpeg

### Windows Standalone

Pre-built executables available on the [releases page](https://github.com/morsznetik/pyPlayer/releases) or if you're feeling fancy you can also download it from the artifacts! (if you don't know what that is, you shouldn't worry about it:D).

**Windows users: don't forget to [download FFmpeg](https://ffmpeg.org/download.html) and add it to your PATH**

> **Note**:
> Windows Defender *may* flag it due to PyInstaller packaging - this is a false positive. Also since the binary is unsigned, SmartScreen will complain.

### From Source

```zsh
git clone https://github.com/morsznetik/pyPlayer
cd pyPlayer

# Basic installation
uv pip install -e .

# With YouTube support
uv pip install -e .[youtube]

# or alternatively:
uv pip install git+https://github.com/morsznetik/pyPlayer.git
```

## Usage

```zsh
# Basic usage
pyplayer path/to/your/video.mp4

# With custom rendering style and color
pyplayer path/to/your/video.mp4 --render braille --color

# Play directly from YouTube URL
pyplayer https://www.youtube.com/watch?v=dQw4w9WgXcQ --render braille --color
```

### Command Line Options

```zsh
pyplayer video_path [options]
```

#### Required Arguments

- **video_path**: Path to the video file to play.

#### Optional Arguments

- **Core Options**:
  - `--fps`, `-f`: Force playback at specific frames per second (default: video's native FPS).
  - `--volume`, `-v`: Set audio volume percentage (0-100) (default: 100).
  - `--debug`, `-d`: Enable detailed debug logging during playback.

- **Rendering Options**:
  - `--frame-color`: Set the color of the frame border (RGB values). Example: --frame-color 255,0,0 (red).
  - `--render`, `-r`: Select the ASCII rendering style (choices: default, legacy, blockNoColor, block, blockv2, braille, halfblock) (default: default).
  - `--diff-mode`, `-dm`: Optimize rendering by only updating changed parts (choices: line, char, none) (default: none).
  - `--output-resolution`, `-or`: Internal processing resolution for video frames (format: W,H|native) (default: native).
  - `--no-transparent`, `-ntr`: Disable transparent background for low brightness pixels (default: enabled).

- **Color Options**:
  - `--color`, `-c`: Enable color rendering (if supported by terminal/style).
  - `--grayscale`, `-g`: Convert video to grayscale before rendering.

- **Color Smoothing (Experimental)**:
  - `--color-smoothing`, `-cs`: Apply video noise reduction (smoothing) filter.
  - `--color-smoothing-params`, `-csp`: Fine-tune color smoothing filter parameters (format: 'param1=value1,param2=value2').

- **Performance Tuning**:
  - `--skip-threshold`, `-s`: Time threshold (in seconds) for frame skipping (default: 0.012).
  - `--no-frame-skip`, `-nfs`: Disable frame skipping entirely.
  - `--pre-render`, `-pr`: Attempt to pre-render video frames ahead of time.
  - `--threads`, `-t`: Number of threads used for parallel frame processing (default: system CPU count).
- `--diff-mode`, `-dm`: Frame difference rendering mode (choices: line, char, none, default: none)
  *The current implementations may not improve performance and could potentially reduce it. Try it, depends on your hardware*
- `--output-resolution`, `-or`: Custom resolution for video processing (default: native)
  *Format: width,height (e.g., 640,480). Use a lower resolution if video processing is slow. This affects video-frame processing, not terminal rendering.*

### Using as a Package

PyPlayer can be used as a Python package in your own projects. Although created to mainly be used as a CLI, you can still import it into your projects and interact with some of its various API's. Each part is created as a separate classes that handle different parts, so you can import them individually. You can check the source code for now.

Creating a custom renderer is easy, and uses a factory approach, so you can create your own renderer by inheriting from the base Renderer class and implementing the render method. Then you use the provided RendererFactory class to register it via register_renderer using a string key or a tuple of strings that will point to that renderer. Then to use it, you can use the get_renderer method to get an instance of your renderer.

For optimal performance, it's strongly recommended to pass the output of render through ColorManager.compress_frame to reduce the amount of data being passed through to the terminal. This compression helps maintain smooth playback by minimizing terminal I/O overhead.

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
uv pip install -r pyproject.toml --all-extras --reinstall -e .
```

### Code Style

> **Note**:
> If you want to contribute, please use the provided pre-commit hooks to ensure code quality.

This project uses:

- **Ruff** for linting and formatting
- **Pre-commit hooks** for code quality checks
- **basedpyright** for type checking, ci-only for now[^1]
- **Typos** for spelling and grammar checks

Install pre-commit hooks:

```zsh
pre-commit install
```

That's it! Ruff and Typos will automatically run as well.

## TODO

- in order of personal importance:

- [x] Fully type define the project
- [x] Custom error handling
- [x] Fix pre-render mode issues when debug is enabled
- [x] More extensible text-rendering styles[^2]
- [x] Compressing color video frames by grouping the same color in the same line
- [x] Diff algorithm for printing frames, only updating what is needed
- [x] Improve color smoothing algorithm
- [x] Create a custom parser and validator for CLI args
- [x] Transparency toggle[^3]
- [x] Improve CI/CD pipeline
- [ ] True[^4] multi-threaded parallelism[^5]
- [x] Support for playing Youtube videos straight from the URL

## Known Issues

- [x] Pre-render mode is bugged with debug's mode on-screen performance statistics
- [ ] While pre-rendering is running, you cannot exit early via keyboard interrupt[^6]
- [ ] Left-side transparency can cause glitchy rendering
- [x] Some Windows environments using the executable will have issues trying to find the video path

### Goals for 1.0.0

- [ ] Complete all TODO's
- [ ] Fix all known issues
- [ ] Support for user-defined FFMPEG video filters
- [ ] Make a character space fill-to-color algorithm to theoretically allow up to 90 times more colors
- [ ] Add video playback control with on-screen timestamps

[^1]: I've had a lot of trouble between PyRight running locally and in the CI, basedpyright seems to be a little better at it, but it's not perfect hence the a bunch of the reporting rules are turned off. I'm not sure if this is a direct effect of my workflow setup or not.

[^2]: Right now, it's limited to predefined styles for TextRenderer - but for the long run, I think it would be a good idea to have a better way of doing them, as well as detecting the user intent of which renderer they would want to use.

[^3]: This is in theory possible, but would require a significant re-write of how the text rendering pipeline handles low brightness pixels. Maybe just setting the background to a pure black would work?

[^4]: Possible only due to the fact you can disable the GIL in 3.13.

[^5]: Haven't decided if doing it in chunks on singular images or process a couple images ahead of time. Doing it in chunks would be more beneficial as a package, but it would lead to dramatically less friendly DX. Pipelining would have more latency with dynamic settings like the terminal size because they are rendered slightly ahead of time, and use more ram, I guess we could always throw out the rendered frames when the size changes. The buffer size could also be dynamic which would benefit lower-end devices. Batching is obvously the better option in terms of actual performance and latency per frame, but I'm not sure if it would benefit the CLI as a whole. As a comparison - Cinebench R23 uses batching while Cinebench R24 switched to pipelining, which is interesting.

[^6]: It hangs the progress bar, but the calculation are still running in the background then when they complete it will throw KeyboardInterrupt.
