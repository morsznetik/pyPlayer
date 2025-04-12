import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from tqdm import tqdm
from typing import override
from .exceptions import InvalidRenderStyleError, FrameRenderingError

type RGBPixel = tuple[int, int, int]
type GrayscalePixel = int
type RGBPixelSequence = Sequence[RGBPixel]
type GrayscalePixelSequence = Sequence[GrayscalePixel]
type ColorTextSegment = tuple[str | None, str]


class ColorManager:
    @staticmethod
    def rgb_to_ansi(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def reset_color() -> str:
        return "\033[0m"

    @staticmethod
    def calculate_average_color(
        colors: RGBPixelSequence,
    ) -> RGBPixel:
        if not colors:
            return (0, 0, 0)
        avg_r = sum(c[0] for c in colors) // len(colors)
        avg_g = sum(c[1] for c in colors) // len(colors)
        avg_b = sum(c[2] for c in colors) // len(colors)
        return (avg_r, avg_g, avg_b)

    @staticmethod
    def compress_frame(text: str) -> str:
        """Compress a frame by optimizing ANSI color codes.

        This method reduces the amount of ANSI escape sequences by combining
        consecutive characters with the same color code.

        Args:
            text: The text to compress

        Returns:
            The compressed text with optimized ANSI color codes
        """
        if not text:
            return text

        lines = text.split("\n")
        compressed_lines: list[str] = []

        for line in lines:
            if not line or "\033[" not in line:
                compressed_lines.append(line)
                continue

            tokens: list[tuple[str, str]] = []
            i: int = 0
            while i < len(line):
                if line.startswith("\033[", i):
                    end: int = line.find("m", i)
                    if end != -1:
                        tokens.append(
                            ("ansi", line[i : end + 1])
                        )  # capture ANSI escape
                        i = end + 1
                    else:
                        tokens.append(("text", line[i]))  # capture non-ANSI text
                        i += 1
                else:
                    tokens.append(("text", line[i]))  # capture non-ANSI text
                    i += 1

            optimized: list[tuple[str | None, str]] = []
            current_color: str | None = None
            current_text = ""
            reset_code = "\033[0m"

            for token_type, token_value in tokens:
                if token_type == "ansi":
                    if token_value.startswith(
                        "\033[38;2;"
                    ):  # checks for true color escape
                        if current_color != token_value and current_text:
                            optimized.append(
                                (current_color, current_text)
                            )  # append accumulated text with color
                            current_text = ""
                        current_color = token_value
                    elif token_value == reset_code:  # reset to default color
                        if current_text:
                            optimized.append((current_color, current_text))
                            current_text = ""
                        optimized.append((reset_code, ""))  # append reset code
                        current_color = None
                    else:
                        if current_text:
                            optimized.append((current_color, current_text))
                            current_text = ""
                        optimized.append(
                            (token_value, "")
                        )  # append other ANSI codes as-is
                else:
                    current_text += token_value  # add non-ANSI text

            if current_text:
                optimized.append((current_color, current_text))  # add remaining text

            compressed_line = ""
            for color, segment_text in optimized:
                if color is None:
                    compressed_line += segment_text
                elif color == reset_code:
                    compressed_line += reset_code  # add reset sequence
                else:
                    compressed_line += color + segment_text  # add color with text

            if any(color is not None and color != reset_code for color, _ in optimized):
                if not compressed_line.endswith(reset_code):
                    compressed_line += (
                        reset_code  # ensure reset at the end of colored text
                    )

            compressed_lines.append(compressed_line)

        return "\n".join(compressed_lines)


class BaseRenderer(ABC):
    """Base class for all renderers.

    All custom renderers should inherit from this class and implement the render method.
    """

    def __init__(
        self,
        style: str,
        color: bool = False,
        frame_color: RGBPixel | None = None,
        transparent: bool = True,
    ):
        self.style = style
        self.color = color
        self.frame_color = frame_color
        self.transparent = transparent

    @abstractmethod
    def render(self, img: Image.Image, width: int, height: int) -> str:
        """Render an image as string.

        Args:
            img: The PIL Image to render
            width: The target width in characters
            height: The target height in characters

        Returns:
            A string containing the string representation of the image
        """
        pass

    def apply_frame_color(
        self, text: str
    ) -> str:  # might find a better way to do this, idk yet
        """Apply frame color to the rendered text if specified."""
        if self.frame_color:
            r, g, b = self.frame_color
            return (
                f"{ColorManager.rgb_to_ansi(r, g, b)}{text}{ColorManager.reset_color()}"
            )
        return text

    def calculate_otsu_threshold(self, gray_img: Image.Image) -> int:
        """Calculate optimal threshold using Otsu's method.

        This method finds the optimal brightness threshold that maximizes
        the between-class variance (or minimizes within-class variance)
        between foreground and background pixels.

        Args:
            gray_img: A grayscale PIL Image

        Returns:
            The optimal threshold value (0-255)
        """
        hist = [0] * 256
        pixels: GrayscalePixelSequence = list(gray_img.getdata())
        for pixel in pixels:
            hist[pixel] += 1

        total = sum(hist)
        sum_total = sum(i * hist[i] for i in range(256))
        max_variance = 0.0
        threshold = 128

        sum_b = 0
        w_b = 0
        for i in range(256):
            w_b += hist[i]
            if w_b == 0:
                continue
            w_f = total - w_b
            if w_f == 0:
                break

            sum_b += i * hist[i]
            m_b = sum_b / w_b
            m_f = (sum_total - sum_b) / w_f
            variance = w_b * w_f * (m_b - m_f) ** 2

            if variance > max_variance:
                max_variance = variance
                threshold = i

        return threshold


class TextRenderer(BaseRenderer):
    """Renderer that converts images to ASCII text characters."""

    styles = {
        "default": ".-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@",
        "legacy": ".:-=+*#%@",
        "blockNoColor": " ▒▓█",
        "block": "▒▓█",
        "blockv2": "█████████",
    }

    def __init__(
        self,
        style: str,
        color: bool = False,
        frame_color: RGBPixel | None = None,
        transparent: bool = False,
    ):
        super().__init__(
            style=style, color=color, frame_color=frame_color, transparent=transparent
        )
        self.ascii_chars = self.styles[style]

    @override
    def render(self, img: Image.Image, width: int, height: int) -> str:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        intensity_range = 255 / (len(self.ascii_chars) - 1)
        result = (
            self._render_color(img, intensity_range)
            if self.color
            else self._render_grayscale(img, intensity_range)
        )
        return ColorManager.compress_frame(result)

    def _render_color(self, img: Image.Image, intensity_range: float) -> str:
        img = img.convert("RGB")
        ascii_image: list[str] = []

        threshold = 0
        if self.transparent:
            gray_img = img.convert("L")
            threshold = self.calculate_otsu_threshold(gray_img)
            threshold = max(10, int(threshold * 0.4))

        pixels: RGBPixelSequence = list(img.getdata())
        for pixel in pixels:
            r, g, b = pixel
            brightness = (r + g + b) / 3

            if self.transparent and brightness < threshold:
                ascii_image.append(" ")
            elif r == g == b == 0:
                ascii_image.append(" ")
            else:
                color_code = ColorManager.rgb_to_ansi(r, g, b)
                ascii_char = self.ascii_chars[int(brightness / intensity_range)]
                ascii_image.append(color_code + ascii_char)

        ascii_image.append(ColorManager.reset_color())
        return "".join(ascii_image)

    def _render_grayscale(self, img: Image.Image, intensity_range: float) -> str:
        img = img.convert("L")

        pixel_values: GrayscalePixelSequence = list(img.getdata())

        if self.transparent:
            threshold = self.calculate_otsu_threshold(img)
            threshold = max(10, int(threshold * 0.2))

            ascii_chars = []
            for pixel_value in pixel_values:
                if pixel_value < threshold:
                    ascii_chars.append(" ")
                else:
                    ascii_chars.append(
                        self.ascii_chars[int(pixel_value / intensity_range)]
                    )
            ascii_image = "".join(ascii_chars)
        else:
            ascii_image = "".join(
                [
                    self.ascii_chars[int(pixel_value / intensity_range)]
                    for pixel_value in pixel_values
                ]
            )

        return self.apply_frame_color(ascii_image)


class BrailleRenderer(BaseRenderer):
    """Renderer that converts images to braille patterns."""

    BRAILLE_PATTERN_BASE = 0x2800
    DOT_MAPPING = {
        (0, 0): 0x01,  # top-left 1/1
        (1, 0): 0x08,  # top-right 1/2
        (0, 1): 0x02,  # middle-left 2/1
        (1, 1): 0x10,  # middle-right 2/2
        (0, 2): 0x04,  # bottom-left 3/1
        (1, 2): 0x20,  # bottom-right 3/2
        (0, 3): 0x40,  # lower-left 4/1
        (1, 3): 0x80,  # lower-right 4/2
    }

    @override
    def render(self, img: Image.Image, width: int, height: int) -> str:
        target_width = width * 2
        target_height = height * 4
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        gray_img = img.convert("L")
        threshold = self.calculate_otsu_threshold(gray_img)
        result = self._convert_to_braille(img, gray_img, threshold)
        return ColorManager.compress_frame(result)

    def _convert_to_braille(
        self, color_img: Image.Image, gray_img: Image.Image, threshold: int
    ) -> str:
        width, height = gray_img.size
        gray_pixels: GrayscalePixelSequence = list(gray_img.getdata())
        color_pixels: RGBPixelSequence = list(color_img.convert("RGB").getdata())
        braille_text: list[str] = []

        cols = max(1, width // 2)
        rows = max(1, height // 4)

        for y in range(rows):
            row: list[str] = []
            for x in range(cols):
                code = self.BRAILLE_PATTERN_BASE
                active_dots: RGBPixelSequence = []

                for dy in range(4):
                    for dx in range(2):
                        px = x * 2 + dx
                        py = y * 4 + dy

                        if px >= width or py >= height:
                            continue

                        idx: int = py * width + px
                        if idx < len(gray_pixels):
                            pixel_threshold = threshold * 0.8
                            if self.transparent:
                                pixel_threshold = threshold * 1.2

                            if gray_pixels[idx] > pixel_threshold:
                                code |= self.DOT_MAPPING[(dx, dy)]
                                active_dots.append(color_pixels[idx])

                if active_dots:
                    if self.color:
                        avg_color = ColorManager.calculate_average_color(active_dots)
                        row.append(
                            f"{ColorManager.rgb_to_ansi(*avg_color)}{chr(code)}{ColorManager.reset_color()}"
                        )
                    else:
                        row.append(chr(code))
                else:
                    row.append(" ")

            braille_text.append("".join(row))

        return self.apply_frame_color("\n".join(braille_text))


class RendererFactory:
    """Factory class for creating renderers.

    This class manages the creation of renderers and allows for registration of custom renderers.
    Each renderer is responsible for handling its own styles internally.
    """

    # registry for all renderers
    _renderers: dict[str, type[BaseRenderer]] = {}

    @classmethod
    def _normalize_names(cls, name: str | tuple[str, ...]) -> tuple[str, ...]:
        """Ensure the name is always a tuple for consistent iteration."""
        return (name,) if isinstance(name, str) else name

    @classmethod
    def register_renderer(
        cls, name: str | tuple[str, ...], renderer_class: type[BaseRenderer]
    ) -> None:
        """Register a renderer by name. Will override any existing renderer with the same name.

        Args:
            name: The name or tuple of names to register the renderer under
            renderer_class: The renderer class to register
        """

        for style_name in cls._normalize_names(name):
            cls._renderers[style_name] = renderer_class

    @classmethod
    def unregister_renderer(cls, name: str | tuple[str, ...]) -> None:
        """Unregister a renderer by name.

        Args:
            name: The name or tuple of names to unregister
        """

        for style_name in cls._normalize_names(name):
            cls._renderers.pop(style_name, None)

    @classmethod
    def get_available_styles(cls) -> list[str]:
        """Get a list of all available rendering styles.

        Returns:
            A list of style names that can be used with create_renderer
        """
        return list(cls._renderers.keys())

    @classmethod
    def has_renderer(cls, style: str) -> bool:
        """Check if a renderer style is registered.

        Args:
            style: The style name to check

        Returns:
            bool: True if the style is registered, False otherwise
        """
        return style in cls._renderers

    @classmethod
    def get_renderer_class(cls, style: str) -> type[BaseRenderer] | None:
        """Get the renderer class for a given style.

        Args:
            style: The style name to get the renderer class for

        Returns:
            The renderer class if found, None otherwise
        """
        return cls._renderers.get(style)

    @classmethod
    def create_renderer(
        cls,
        style: str,
        color: bool = False,
        frame_color: RGBPixel | None = None,
        transparent: bool = False,
    ) -> BaseRenderer:
        """Create a renderer instance based on the specified style.

        Args:
            style: The rendering style to use
            color: Whether to enable color rendering
            frame_color: Optional frame color as RGB tuple
            transparent: Whether to enable transparent background for low brightness pixels

        Raises:
            InvalidRenderStyleError: If the specified style is not registered
        """
        if not cls.has_renderer(style):
            raise InvalidRenderStyleError(style)

        return cls._renderers[style](
            style=style, color=color, frame_color=frame_color, transparent=transparent
        )


# built-in renderers
RendererFactory.register_renderer(tuple(TextRenderer.styles.keys()), TextRenderer)
RendererFactory.register_renderer("braille", BrailleRenderer)


class RendererManager:
    """Manager class for handling rendering operations.

    This class provides a high-level interface for rendering operations and handles
    common functionality like cursor management and frame pre-rendering.
    """

    def __init__(
        self,
        style: str = "default",
        color: bool = False,
        frame_color: RGBPixel | None = None,
        transparent: bool = True,
    ) -> None:
        self.renderer = RendererFactory.create_renderer(
            style=style, color=color, frame_color=frame_color, transparent=transparent
        )

    def hide_cursor(self) -> None:
        """Hide the terminal cursor"""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def show_cursor(self) -> None:
        """Show the terminal cursor"""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def convert_frame(self, image_path: str, width: int, height: int) -> str:
        try:
            with Image.open(image_path) as img:
                return self.renderer.render(img, width, height)
        except Exception as e:
            raise FrameRenderingError(image_path, str(e))

    def pre_render_frames(
        self, frame_paths: list[str], width: int, height: int, num_threads: int = 1
    ) -> dict[str, str]:
        if not frame_paths:
            return {}

        num_threads = max(1, min(num_threads, len(frame_paths)))
        pre_rendered_frames: dict[str, str] = {}

        def render_frame(frame_path: str) -> tuple[str, str]:
            try:
                with Image.open(frame_path) as img:
                    return frame_path, self.renderer.render(img, width, height)
            except Exception as e:
                raise FrameRenderingError(frame_path, str(e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(render_frame, path) for path in frame_paths]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Pre-rendering frames ({num_threads} threads)",
                unit="frame",
            ):
                try:
                    path, rendered = future.result()
                    if rendered:
                        pre_rendered_frames[path] = rendered
                except Exception as e:
                    print(f"Exception during frame rendering: {str(e)}")

        return pre_rendered_frames
