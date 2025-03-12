# pyPlayer

[![Test, build, deploy](https://github.com/morsznetik/pyPlayer/actions/workflows/ci.yml/badge.svg)](https://github.com/morsznetik/pyPlayer/actions/workflows/ci.yml)

A powerful and performant terminal-based video player that renders videos as ASCII art with audio.

## Contributing

Contributions are very much welcome! Please open an issue or submit a pull request.

## Features

### Multiple ASCII Rendering Styles

- **default**: Detailed ASCII character set
  - Medium quality, fast rendering
  - Fastest terminal performance
  - Decent color support (*will look blurry but is arguably the best with high-complexity videos*)
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
- others **(these are very much unsupported and are deprecated!)**:
  - **blockNoColor**: hacky way to have transparency with block rendering, as the name suggests best way to use it is without color
  - **blockv2**: hacky way to only have pixel-based rendering with only the full block being used

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
uv pip install -e .

# or alternatively:
uv pip install git+https://github.com/morsznetik/pyPlayer.git
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

### Using as a Package

PyPlayer can be used as a Python package in your own projects. Although created to mainly be used as a CLI, you can still import it into your projects and interact with someone of its various API's. Each part is created as a separate classes that handle different parts, so you can import them individually. Stuff you need is mostly in the base package, but some more internal stuff that still could be useful can be accessed throught importing different modules. You can check the source code for now.

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

> **Note**:
> If you want to contribute, please use the provided pre-commit hooks to ensure code quality.

This project uses:

- **Ruff** for linting and formatting
- **Pre-commit hooks** for code quality checks

Install pre-commit hooks:

```zsh
pre-commit install
```

That's it! Ruff will automatically run as well, you can also add PyRight, but I didn't feel like enforcing type checking on everything, especially when this is not even fully typed yet. But it does run in the CI to non-restrictively check already typed code

## TODO

- in order of personal importance:

- [ ] Fully type define the project[^1]
- [ ] Fix pre-render mode issues when debug is enabled
- [ ] Improve color smoothing algorithm
- [ ] Transparency toggle[^2]
- [ ] Improve CI/CD pipeline
- [ ] True[^3] multi-threaded parallelism[^4]
- [ ] Support for playing Youtube videos straight from the URL - potentially something for 1.0, haven't decided yet

## Known Issues

- [ ] Pre-render mode is bugged with debug's mode on-screen performance statistics
- [ ] Left-side transparency can cause glitchy rendering
- [x] Some Windows environments using the executable will have issues trying to find the video path

### Goals for 1.0.0

- [ ] Complete all TODO's
- [ ] Fix all known issues
- [ ] Support for user-defined FFMPEG video filters
- [ ] Make a character space fill-to-color algorithm to theoretically allow up to 90 times more colors

[^1]: Coming in 0.2.0-beta*, from that point pyright will be required and set on strict.

[^2]: This is in theory possible, but would require a significant re-write of how the text rendering pipeline handles low brightness pixels. Maybe just setting the background to a pure black would work?

[^3]: Possible only due to the fact you can disable the GIL in 3.13.

[^4] Haven't decided if doing it in chunks on singular images or process a couple images ahead of time. Doing it in chunks would be more beneficial as a package, but it would lead to dramatically less friendly DX. Pipelining would have more latency with dynamic settings like the terminal size because they are rendered slightly ahead of time, and use more ram, I guess we could always throw out the rendered frames when the size changes. The buffer size could also be dynamic which would benefit lower-end devices. Batching is obvously the better option in terms of actual performance and latency per frame, but I'm not sure if it would benefit the CLI as a whole. As a comparison - Cinebench R23 uses batching while Cinebench R24 switched to pipelining, which is interesing.
