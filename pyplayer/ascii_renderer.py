import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from abc import ABC, abstractmethod
from tqdm import tqdm

type RGBPixel = tuple[int, int, int]


class ColorManager:
    @staticmethod
    def rgb_to_ansi(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def reset_color() -> str:
        return "\033[0m"

    @staticmethod
    def calculate_average_color(
        colors: list[RGBPixel],
    ) -> RGBPixel:
        if not colors:
            return (0, 0, 0)
        avg_r = sum(c[0] for c in colors) // len(colors)
        avg_g = sum(c[1] for c in colors) // len(colors)
        avg_b = sum(c[2] for c in colors) // len(colors)
        return (avg_r, avg_g, avg_b)


class BaseRenderer(ABC):
    def __init__(self, color: bool = False, frame_color: RGBPixel | None = None):
        self.color = color
        self.frame_color = frame_color

    @abstractmethod
    def render(self, img: Image.Image, width: int, height: int) -> str:
        pass

    def apply_frame_color(self, text: str) -> str:
        if self.frame_color:
            r, g, b = self.frame_color
            return (
                f"{ColorManager.rgb_to_ansi(r, g, b)}{text}{ColorManager.reset_color()}"
            )
        return text


class TextRenderer(BaseRenderer):
    def __init__(
        self,
        ascii_chars: str,
        color: bool = False,
        frame_color: RGBPixel | None = None,
    ):
        super().__init__(color, frame_color)
        self.ascii_chars = ascii_chars

    def render(self, img: Image.Image, width: int, height: int) -> str:
        img = img.resize((width, height), Image.LANCZOS)  # type: ignore
        intensity_range = 255 / (len(self.ascii_chars) - 1)
        return (
            self._render_color(img, intensity_range)
            if self.color
            else self._render_grayscale(img, intensity_range)
        )

    def _render_color(self, img: Image.Image, intensity_range: float) -> str:
        img = img.convert("RGB")
        ascii_image: list[str] = []

        pixel: RGBPixel
        pixels: list[RGBPixel] = list(img.getdata())  # type: ignore
        for pixel in pixels:
            r, g, b = pixel
            if r == g == b == 0:
                ascii_image.append(" ")
            else:
                color_code = ColorManager.rgb_to_ansi(r, g, b)
                ascii_char = self.ascii_chars[int((r + g + b) / 3 / intensity_range)]
                ascii_image.append(color_code + ascii_char)

        ascii_image.append(ColorManager.reset_color())
        return "".join(ascii_image)

    def _render_grayscale(self, img: Image.Image, intensity_range: float) -> str:
        img = img.convert("L")

        pixel_values: list[int] = list(img.getdata())  # type: ignore
        ascii_image = "".join(
            [
                self.ascii_chars[int(pixel_value / intensity_range)]
                for pixel_value in pixel_values
            ]
        )
        return self.apply_frame_color(ascii_image)


class BrailleRenderer(BaseRenderer):
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

    def render(self, img: Image.Image, width: int, height: int) -> str:
        target_width = width * 2
        target_height = height * 4
        img = img.resize((target_width, target_height), Image.LANCZOS)  # type: ignore
        gray_img = img.convert("L")
        threshold = self._calculate_otsu_threshold(gray_img)
        return self._convert_to_braille(img, gray_img, threshold)

    def _calculate_otsu_threshold(self, gray_img: Image.Image) -> int:
        hist = [0] * 256
        pixels: list[int] = list(gray_img.getdata())  # type: ignore
        for pixel in pixels:
            hist[pixel] += 1

        total: int = sum(hist)
        sum_total: int = sum(i * hist[i] for i in range(256))
        max_variance: float = 0.0
        threshold: int = 128

        sum_b: int = 0
        w_b: int = 0
        for i in range(256):
            w_b += hist[i]
            if w_b == 0:
                continue
            w_f: int = total - w_b
            if w_f == 0:
                break

            sum_b += i * hist[i]
            m_b: float = sum_b / w_b
            m_f: float = (sum_total - sum_b) / w_f
            variance: float = w_b * w_f * (m_b - m_f) ** 2

            if variance > max_variance:
                max_variance = variance
                threshold = i

        return threshold

    def _convert_to_braille(
        self, color_img: Image.Image, gray_img: Image.Image, threshold: int
    ) -> str:
        width, height = gray_img.size
        gray_pixels: list[int] = list(gray_img.getdata())  # type: ignore
        color_pixels: list[RGBPixel] = list(color_img.convert("RGB").getdata())  # type: ignore
        braille_text: list[str] = []

        cols: int = max(1, width // 2)
        rows: int = max(1, height // 4)

        for y in range(rows):
            row: list[str] = []
            for x in range(cols):
                code: int = self.BRAILLE_PATTERN_BASE
                active_dots: list[RGBPixel] = []

                for dy in range(4):
                    for dx in range(2):
                        px: int = x * 2 + dx
                        py: int = y * 4 + dy

                        if px >= width or py >= height:
                            continue

                        idx: int = py * width + px
                        if (
                            idx < len(gray_pixels)
                            and gray_pixels[idx] > threshold * 0.8
                        ):
                            code |= self.DOT_MAPPING[(dx, dy)]
                            active_dots.append(color_pixels[idx])

                if active_dots:
                    if self.color:
                        avg_color: RGBPixel = ColorManager.calculate_average_color(
                            active_dots
                        )
                        row.append(
                            f"{ColorManager.rgb_to_ansi(*avg_color)}{chr(code)}{ColorManager.reset_color()}"
                        )
                    else:
                        row.append(chr(code))
                else:
                    row.append(" ")

            braille_text.append("".join(row))

        return self.apply_frame_color("\n".join(braille_text))


class AsciiRenderer:
    ASCII_STYLES = {
        "default": "      .-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@",
        "legacy": "     .:-=+*#%@",
        "blockNoColor": " ▒▓█",
        "block": "▒▓█",
        "blockv2": "█████████",
    }

    def __init__(
        self,
        style: str = "default",
        color: bool = False,
        frame_color: RGBPixel | None = None,
    ) -> None:
        if style == "braille":
            self.renderer = BrailleRenderer(color=color, frame_color=frame_color)
        else:
            ascii_chars = self.ASCII_STYLES.get(style, self.ASCII_STYLES["default"])
            self.renderer = TextRenderer(
                ascii_chars, color=color, frame_color=frame_color
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
        with Image.open(image_path) as img:
            return self.renderer.render(img, width, height)

    def pre_render_frames(
        self, frame_paths: list[str], width: int, height: int, num_threads: int = 4
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
                print(f"Error rendering frame {frame_path}: {str(e)}")
                return frame_path, ""

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
