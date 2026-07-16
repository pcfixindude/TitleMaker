from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CANVAS_SIZE = (1920, 1080)
CANVAS_WIDTH, CANVAS_HEIGHT = CANVAS_SIZE
PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
EXPORTS_DIR = PROJECT_ROOT / "exports"
PRESETS_DIR = PROJECT_ROOT / "presets"

BARLOW_BOLD_ITALIC = FONTS_DIR / "BarlowCondensed-BoldItalic.ttf"
BEBAS_FONT = FONTS_DIR / "BebasNeue-Regular.ttf"
FONT_EXTENSIONS = {".ttf", ".otf"}

MAX_TITLE_FONT_SIZE = 400
MIN_TITLE_FONT_SIZE = 40
SERVICE_FONT_SIZE = 86
SPEAKER_FONT_SIZE = 80
TITLE_SIDE_PADDING = 120
TITLE_VERTICAL_GAP = 35
MIN_TITLE_HEIGHT = 80

SERVICE_BOX = {"x": 120, "y": 130, "width": 1680, "height": 110}
SPEAKER_BOX = {"x": 120, "y": 740, "width": 1680, "height": 120}

# Compatibility aliases for unused legacy modules (not used by the simplified app).
DEFAULT_TOP_POSITION = (960, SERVICE_BOX["y"])
DEFAULT_TITLE_POSITION = (960, 470)
DEFAULT_BOTTOM_POSITION = (960, SPEAKER_BOX["y"])


@dataclass(frozen=True)
class TextBox:
    x: int
    y: int
    width: int
    height: int
    alignment: str = "center"
    auto_size: bool = True
    font_size: int = 86
    max_font_size: int = MAX_TITLE_FONT_SIZE
    line_spacing: float = 0.9
    skew_angle: float = 0.0


@dataclass(frozen=True)
class TitleImageOptions:
    """Simplified render options for the live title maker."""

    day: str
    service: str
    service_date: date
    sermon_title: str
    speaker_name: str
    text_color: str = "#FFFFFF"
    background_path: Path | None = None
    show_bounding_boxes: bool = False
    title_vertical_offset: int = 0
    # Kept for older call sites / tests; ignored by the simplified renderer.
    font_path: Path | None = None
    service_font_path: Path | None = None
    title_font_path: Path | None = None
    speaker_font_path: Path | None = None
    auto_size: bool = True
    title_font_size: int = MAX_TITLE_FONT_SIZE
    shadow_enabled: bool = True
    show_service_line: bool = True
    skew_enabled: bool = False
    show_layout_guides: bool = False
    selected_layout_area: str | None = None
    service_line_box: TextBox | None = None
    title_box: TextBox | None = None
    speaker_box: TextBox | None = None
    top_line_position: tuple[int, int] = (960, 130)
    title_position: tuple[int, int] = (960, 470)
    bottom_line_position: tuple[int, int] = (960, 740)
    text_alignment: str = "center"


def ensure_project_dirs() -> None:
    for folder in (FONTS_DIR, TEMPLATES_DIR, EXPORTS_DIR, PRESETS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def format_short_date(value: date) -> str:
    return f"{value.month}-{value.day}-{value.strftime('%y')}"


def format_service_line(day: str, service: str, service_date: date) -> str:
    return f"{day.upper()} {service_code(service)} {format_short_date(service_date)}"


def format_top_line(options: TitleImageOptions) -> str:
    return format_service_line(options.day, options.service, options.service_date)


def service_code(service: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", service.lower())
    service_codes = {
        "morning": "AM",
        "am": "AM",
        "afternoon": "AFT",
        "aft": "AFT",
        "evening": "PM",
        "pm": "PM",
    }
    return service_codes.get(normalized, service.upper())


def format_title(value: str) -> str:
    lines = [" ".join(line.strip().upper().split()) for line in value.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned


def format_speaker(value: str) -> str:
    return " ".join(value.strip().upper().split())


def export_filename(options: TitleImageOptions) -> str:
    date_part = options.service_date.isoformat()
    service_part = f"{options.day}_{service_code(options.service)}".upper()
    title_part = _slug(format_title(options.sermon_title))
    return f"{date_part}_{service_part}_{title_part}.png"


def default_font_path(fonts: list[Path] | None = None) -> Path | None:
    if BARLOW_BOLD_ITALIC.exists():
        return BARLOW_BOLD_ITALIC
    available = list_custom_fonts() if fonts is None else fonts
    if BEBAS_FONT in available:
        return BEBAS_FONT
    return available[0] if available else None


def list_custom_fonts() -> list[Path]:
    ensure_project_dirs()
    return sorted(
        path for path in FONTS_DIR.iterdir() if path.suffix.lower() in FONT_EXTENSIONS
    )


def list_template_backgrounds() -> list[Path]:
    ensure_project_dirs()
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        path for path in TEMPLATES_DIR.iterdir() if path.suffix.lower() in extensions
    )


def compute_title_box(title_vertical_offset: int = 0) -> dict[str, int]:
    service_bottom = SERVICE_BOX["y"] + SERVICE_BOX["height"]
    speaker_top = SPEAKER_BOX["y"]
    available = speaker_top - service_bottom
    height = max(MIN_TITLE_HEIGHT, available - (2 * TITLE_VERTICAL_GAP))
    y = service_bottom + TITLE_VERTICAL_GAP + int(title_vertical_offset)
    # Keep the title box inside the service/speaker gap as much as practical.
    min_y = service_bottom + 10
    max_y = speaker_top - height - 10
    if max_y < min_y:
        y = service_bottom + max(0, (available - height) // 2)
    else:
        y = max(min_y, min(max_y, y))
    return {
        "x": TITLE_SIDE_PADDING,
        "y": y,
        "width": CANVAS_WIDTH - (2 * TITLE_SIDE_PADDING),
        "height": height,
    }


def render_title_image(options: TitleImageOptions) -> Image.Image:
    ensure_project_dirs()
    image = _load_background(options.background_path)
    draw = ImageDraw.Draw(image)
    font_path = default_font_path()

    service_box = TextBox(**SERVICE_BOX, alignment="center", auto_size=True, font_size=SERVICE_FONT_SIZE)
    speaker_box = TextBox(**SPEAKER_BOX, alignment="center", auto_size=True, font_size=SPEAKER_FONT_SIZE)
    title_metrics = compute_title_box(options.title_vertical_offset)
    title_box = TextBox(
        x=title_metrics["x"],
        y=title_metrics["y"],
        width=title_metrics["width"],
        height=title_metrics["height"],
        alignment="center",
        auto_size=True,
        font_size=MAX_TITLE_FONT_SIZE,
        max_font_size=MAX_TITLE_FONT_SIZE,
        line_spacing=0.9,
    )

    top_line = format_top_line(options)
    title = format_title(options.sermon_title)
    speaker = format_speaker(options.speaker_name)

    if options.show_service_line:
        _draw_fixed_text(
            draw,
            top_line,
            font_path,
            options.text_color,
            service_box,
            options.shadow_enabled,
            preferred_size=SERVICE_FONT_SIZE,
        )

    _draw_main_title(
        draw,
        title,
        options.text_color,
        font_path,
        title_box,
        options.shadow_enabled,
    )

    _draw_fixed_text(
        draw,
        speaker,
        font_path,
        options.text_color,
        speaker_box,
        options.shadow_enabled,
        preferred_size=SPEAKER_FONT_SIZE,
    )

    show_boxes = options.show_bounding_boxes or options.show_layout_guides
    if show_boxes:
        _draw_bounding_boxes(draw, service_box, title_box, speaker_box)

    return image


def save_title_image(options: TitleImageOptions) -> Path:
    ensure_project_dirs()
    image = render_title_image(options)
    output_path = EXPORTS_DIR / export_filename(options)
    image.save(output_path, "PNG")
    return output_path


def fit_title_two_lines(
    title: str,
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = MAX_TITLE_FONT_SIZE,
    min_font_size: int = MIN_TITLE_FONT_SIZE,
    line_spacing: float = 0.9,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    """Fit title to at most 2 lines, preferring 1 line when possible."""
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    cleaned = format_title(title)
    if not cleaned:
        font = _load_font(max_font_size, font_path)
        return font, [], max(1, round(max_font_size * line_spacing)), 0, 0

    start = max(min_font_size, min(int(max_font_size), MAX_TITLE_FONT_SIZE))
    for size in range(start, min_font_size - 1, -2):
        font = _load_font(size, font_path)
        line_height = max(1, round(size * line_spacing))
        lines = _choose_title_lines(cleaned, font, max_width, probe)
        if len(lines) > 2:
            continue
        block_width = max((_text_width(probe, line, font) for line in lines), default=0)
        block_height = line_height * len(lines)
        if block_width <= max_width and block_height <= max_height:
            return font, lines, line_height, block_width, block_height

    font = _load_font(min_font_size, font_path)
    lines = _choose_title_lines(cleaned, font, max_width, probe)[:2]
    line_height = max(1, round(min_font_size * line_spacing))
    block_width = max((_text_width(probe, line, font) for line in lines), default=0)
    block_height = line_height * len(lines)
    return font, lines, line_height, block_width, block_height


def fit_title_metrics_for_test(
    title: str,
    max_width: int = 1680,
    max_height: int = 440,
    font_size: int = MAX_TITLE_FONT_SIZE,
    auto_size: bool = True,
    line_spacing: float = 0.9,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    if not auto_size:
        font = _load_font(font_size, default_font_path())
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        lines = _choose_title_lines(format_title(title), font, max_width, probe)
        line_height = max(1, round(font_size * line_spacing))
        block_width = max((_text_width(probe, line, font) for line in lines), default=0)
        return font, lines, line_height, block_width, line_height * len(lines)
    return fit_title_two_lines(
        title,
        max_width=max_width,
        max_height=max_height,
        font_path=default_font_path(),
        max_font_size=font_size,
        line_spacing=line_spacing,
    )


def fit_title_lines_for_test(
    title: str,
    max_width: int = 1680,
    font_size: int = 218,
    font_path: Path | None = None,
) -> list[str]:
    font = _load_font(font_size, font_path or default_font_path())
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    return _choose_title_lines(format_title(title), font, max_width, draw)


def fit_title_font_size_for_test(
    title: str,
    max_width: int = 1680,
    max_height: int = 440,
    font_size: int = MAX_TITLE_FONT_SIZE,
) -> int:
    font, _, _, _, _ = fit_title_metrics_for_test(
        title, max_width=max_width, max_height=max_height, font_size=font_size
    )
    return int(getattr(font, "size", font_size))


def _choose_title_lines(
    title: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    manual = [line for line in title.splitlines() if line.strip()]
    if len(manual) >= 2:
        # Preserve up to two manual lines; merge extras into line 2.
        first = manual[0]
        second = " ".join(manual[1:])
        return [first, second] if second else [first]

    text = manual[0] if manual else title
    if _text_width(draw, text, font) <= max_width:
        return [text]
    return _best_two_line_wrap(text, font, max_width, draw)


def _best_two_line_wrap(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    words = text.split()
    if len(words) <= 1:
        return [text]

    best: list[str] | None = None
    best_score: tuple[float, float, float] | None = None
    for split in range(1, len(words)):
        line1 = " ".join(words[:split])
        line2 = " ".join(words[split:])
        w1 = _text_width(draw, line1, font)
        w2 = _text_width(draw, line2, font)
        if w1 > max_width or w2 > max_width:
            continue
        # Prefer balanced widths; penalize a one-word second line when avoidable.
        balance = abs(w1 - w2)
        orphan = 2.0 if len(words[split:]) == 1 and len(words) > 2 else 0.0
        score = (-max(w1, w2), -orphan, -balance)
        if best_score is None or score > best_score:
            best = [line1, line2]
            best_score = score

    if best:
        return best

    # Fallback greedy wrap capped at 2 lines.
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == 1:
            # Remaining words go on line 2.
            rest = [current] + words[words.index(word) + 1 :]
            lines.append(" ".join(rest))
            return lines
    if current:
        lines.append(current)
    return lines[:2]


def _draw_main_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    fill: str,
    font_path: Path | None,
    box: TextBox,
    shadow_enabled: bool,
) -> None:
    if not title:
        return
    font, lines, line_height, _, block_height = fit_title_two_lines(
        title,
        max_width=box.width,
        max_height=box.height,
        font_path=font_path,
        max_font_size=box.max_font_size,
        line_spacing=box.line_spacing,
    )
    y = box.y + (box.height - block_height) // 2
    for line in lines:
        line_width = _text_width(draw, line, font)
        x = box.x + (box.width - line_width) // 2
        if shadow_enabled:
            _draw_text_shadow(draw, (x, y), line, font)
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _draw_fixed_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path | None,
    fill: str,
    box: TextBox,
    shadow_enabled: bool,
    preferred_size: int,
) -> None:
    if not text:
        return
    size = preferred_size
    font = _load_font(size, font_path)
    while size > 28 and _text_width(draw, text, font) > box.width:
        size -= 2
        font = _load_font(size, font_path)
    line_height = max(1, round(size * 1.0))
    x = box.x + (box.width - _text_width(draw, text, font)) // 2
    y = box.y + (box.height - line_height) // 2
    if shadow_enabled:
        _draw_text_shadow(draw, (x, y), text, font)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_bounding_boxes(
    draw: ImageDraw.ImageDraw,
    service_box: TextBox,
    title_box: TextBox,
    speaker_box: TextBox,
) -> None:
    for box, color in (
        (service_box, (255, 255, 255, 140)),
        (title_box, (255, 220, 80, 180)),
        (speaker_box, (255, 255, 255, 140)),
    ):
        draw.rectangle(
            (box.x, box.y, box.x + box.width, box.y + box.height),
            outline=color,
            width=4,
        )


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    return slug or "SERMON_TITLE"


def _load_background(background_path: Path | None) -> Image.Image:
    if background_path and background_path.exists():
        with Image.open(background_path) as source:
            return _resize_to_cover(source.convert("RGB"), CANVAS_SIZE)
    return _generated_background()


def _generated_background() -> Image.Image:
    width, height = CANVAS_SIZE
    top_color = (173, 193, 210)
    bottom_color = (55, 72, 92)
    gradient = Image.new("RGB", (1, height))
    pixels = gradient.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        pixels[0, y] = tuple(
            int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3)
        )
    image = gradient.resize(CANVAS_SIZE)
    rays = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    ray_draw = ImageDraw.Draw(rays)
    origin = (width // 2, -130)
    for index, x in enumerate(range(-360, width + 360, 320)):
        alpha = 24 if index % 2 == 0 else 14
        ray_draw.polygon(
            [origin, (x, height), (x + 170, height)],
            fill=(255, 255, 255, alpha),
        )
    rays = rays.filter(ImageFilter.GaussianBlur(20))
    image = Image.alpha_composite(image.convert("RGBA"), rays)
    vignette_mask = Image.new("L", CANVAS_SIZE, 175)
    vignette_draw = ImageDraw.Draw(vignette_mask)
    vignette_draw.ellipse((-260, -210, width + 260, height + 250), fill=0)
    vignette_mask = vignette_mask.filter(ImageFilter.GaussianBlur(115))
    vignette = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 150))
    image = Image.composite(vignette, image, vignette_mask)
    return image.convert("RGB")


def _resize_to_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2
    return resized.crop((left, top, left + target_width, top + target_height))


def _load_font(
    size: int,
    preferred_font: Path | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        preferred_font,
        BARLOW_BOLD_ITALIC,
        BEBAS_FONT,
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    seen: set[Path] = set()
    for font_path in candidates:
        if font_path and font_path.exists() and font_path not in seen:
            seen.add(font_path)
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _draw_text_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    radius: int = 3,
    offset: tuple[int, int] = (5, 5),
) -> None:
    x, y = xy
    for dx in range(-radius, radius + 1, radius):
        for dy in range(-radius, radius + 1, radius):
            draw.text(
                (x + offset[0] + dx, y + offset[1] + dy),
                text,
                font=font,
                fill=(0, 0, 0, 105),
            )
