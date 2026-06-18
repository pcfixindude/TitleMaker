from __future__ import annotations

import re
from math import radians, tan
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from layout_controls import MAX_TITLE_FONT_SIZE


CANVAS_SIZE = (1920, 1080)
PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
EXPORTS_DIR = PROJECT_ROOT / "exports"
PRESETS_DIR = PROJECT_ROOT / "presets"
BEBAS_FONT = FONTS_DIR / "BebasNeue-Regular.ttf"
FONT_EXTENSIONS = {".ttf", ".otf"}
DEFAULT_TOP_POSITION = (960, 112)
DEFAULT_TITLE_POSITION = (960, 540)
DEFAULT_BOTTOM_POSITION = (960, 902)


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
    line_spacing: float = 1.0
    skew_angle: float = 0.0


@dataclass(frozen=True)
class TitleImageOptions:
    day: str
    service: str
    service_date: date
    sermon_title: str
    speaker_name: str
    text_color: str = "#FFFFFF"
    background_path: Path | None = None
    font_path: Path | None = None
    service_font_path: Path | None = None
    title_font_path: Path | None = None
    speaker_font_path: Path | None = None
    auto_size: bool = True
    title_font_size: int = 218
    top_line_position: tuple[int, int] = DEFAULT_TOP_POSITION
    title_position: tuple[int, int] = DEFAULT_TITLE_POSITION
    bottom_line_position: tuple[int, int] = DEFAULT_BOTTOM_POSITION
    text_alignment: str = "center"
    shadow_enabled: bool = True
    show_service_line: bool = True
    service_line_box: TextBox | None = None
    title_box: TextBox | None = None
    speaker_box: TextBox | None = None
    skew_enabled: bool = True
    show_layout_guides: bool = False
    selected_layout_area: str | None = None


def ensure_project_dirs() -> None:
    for folder in (FONTS_DIR, TEMPLATES_DIR, EXPORTS_DIR, PRESETS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def format_short_date(value: date) -> str:
    return f"{value.month}-{value.day}-{value.strftime('%y')}"


def format_top_line(options: TitleImageOptions) -> str:
    return format_service_line(options.day, options.service, options.service_date)


def format_service_line(day: str, service: str, service_date: date) -> str:
    return f"{day.upper()} {service_code(service)} {format_short_date(service_date)}"


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
    cleaned = " ".join(value.strip().upper().split())
    return cleaned


def export_filename(options: TitleImageOptions) -> str:
    date_part = options.service_date.isoformat()
    service_part = f"{options.day}_{service_code(options.service)}".upper()
    title_part = _slug(format_title(options.sermon_title))
    return f"{date_part}_{service_part}_{title_part}.png"


def render_title_image(options: TitleImageOptions) -> Image.Image:
    ensure_project_dirs()

    image = _load_background(options.background_path)
    draw = ImageDraw.Draw(image)
    text_color = options.text_color

    service_box = _service_box(options)
    title_box = _title_box(options)
    speaker_box = _speaker_box(options)

    top_line = format_top_line(options)
    title = format_title(options.sermon_title)
    speaker = format_speaker(options.speaker_name)

    if options.show_service_line:
        _draw_text_box(
            draw,
            top_line,
            options.service_font_path or options.font_path,
            text_color,
            service_box,
            options.shadow_enabled,
        )
    _draw_main_title(
        image,
        title,
        text_color,
        options.title_font_path or options.font_path,
        title_box,
        options.shadow_enabled,
        options.skew_enabled,
    )
    _draw_text_box(
        draw,
        speaker,
        options.speaker_font_path or options.font_path,
        text_color,
        speaker_box,
        options.shadow_enabled,
    )

    if options.show_layout_guides:
        _draw_layout_guides(
            draw,
            service_box,
            title_box,
            speaker_box,
            options.selected_layout_area,
        )

    return image


def save_title_image(options: TitleImageOptions) -> Path:
    ensure_project_dirs()
    image = render_title_image(options)
    output_path = EXPORTS_DIR / export_filename(options)
    image.save(output_path, "PNG")
    return output_path


def list_template_backgrounds() -> list[Path]:
    ensure_project_dirs()
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        path for path in TEMPLATES_DIR.iterdir() if path.suffix.lower() in extensions
    )


def list_custom_fonts() -> list[Path]:
    ensure_project_dirs()
    return sorted(
        path for path in FONTS_DIR.iterdir() if path.suffix.lower() in FONT_EXTENSIONS
    )


def default_font_path(fonts: list[Path] | None = None) -> Path | None:
    available_fonts = list_custom_fonts() if fonts is None else fonts
    if not available_fonts:
        return None

    for font_path in available_fonts:
        if _is_barlow_condensed_extrabold_italic(font_path):
            return font_path

    if BEBAS_FONT in available_fonts:
        return BEBAS_FONT

    return available_fonts[0]


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
    gradient_pixels = gradient.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        gradient_pixels[0, y] = tuple(
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


def _is_barlow_condensed_extrabold_italic(font_path: Path) -> bool:
    normalized_name = re.sub(r"[^a-z0-9]+", "", font_path.stem.lower())
    return all(
        part in normalized_name
        for part in ("barlow", "condensed", "extrabold", "italic")
    )


def _load_font(
    size: int,
    preferred_font: Path | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        preferred_font,
        BEBAS_FONT,
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Impact.ttf"),
        Path("/System/Library/Fonts/Supplemental/Helvetica.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]

    seen: set[Path] = set()
    for font_path in font_candidates:
        if font_path and font_path.exists() and font_path not in seen:
            seen.add(font_path)
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue

    return ImageFont.load_default()


def _draw_text_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path | None,
    fill: str,
    box: TextBox,
    shadow_enabled: bool,
) -> None:
    if not text:
        return

    font, lines, line_height, _, block_height = _fit_box_text(
        text,
        box,
        font_path,
        min_size=28,
    )
    y = box.y + (box.height - block_height) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = box.x + _aligned_line_offset(box.width, line_width, box.alignment)
        if shadow_enabled:
            _draw_text_shadow(draw, (x, y), line, font)
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _draw_main_title(
    image: Image.Image,
    title: str,
    fill: str,
    font_path: Path | None,
    box: TextBox,
    shadow_enabled: bool,
    skew_enabled: bool,
) -> None:
    font, lines, line_height, block_width, block_height = _fit_title(
        title,
        max_width=box.width,
        max_height=box.height,
        font_path=font_path,
        auto_size=box.auto_size,
        title_font_size=box.max_font_size if box.auto_size else box.font_size,
        line_spacing=box.line_spacing,
    )

    layer_width = box.width + 260
    layer_height = box.height + 130
    title_layer = Image.new("RGBA", (layer_width, layer_height), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(title_layer)

    y = (layer_height - block_height) // 2
    for line in lines:
        bbox = layer_draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (layer_width - box.width) // 2 + _aligned_line_offset(
            box.width, line_width, box.alignment
        )
        if shadow_enabled:
            _draw_text_shadow(layer_draw, (x, y), line, font, radius=5, offset=(8, 9))
        layer_draw.text((x, y), line, font=font, fill=fill)
        y += line_height

    if not skew_enabled:
        paste_x = box.x - 130
        paste_y = box.y - 65
        image.paste(title_layer, (paste_x, paste_y), title_layer)
        return

    skew = tan(radians(box.skew_angle))
    if abs(skew) < 0.0001:
        paste_x = box.x - 130
        paste_y = box.y - 65
        image.paste(title_layer, (paste_x, paste_y), title_layer)
        return

    x_shift = int(abs(skew) * layer_height)
    skewed = title_layer.transform(
        (layer_width + x_shift, layer_height),
        Image.Transform.AFFINE,
        (1, -skew, x_shift if skew > 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )

    paste_x = box.x - 130
    paste_y = box.y - 65 + 8
    image.paste(skewed, (paste_x, paste_y), skewed)


def _fit_title(
    title: str,
    max_width: int,
    max_height: int,
    font_path: Path | None,
    auto_size: bool,
    title_font_size: int,
    line_spacing: float,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    start_size = max(48, min(title_font_size, MAX_TITLE_FONT_SIZE))

    for size in range(start_size, 87, -4):
        font = _load_font(size, font_path)
        line_height = max(1, round(size * _effective_line_spacing(font_path, line_spacing)))
        lines = _wrap_title(title, font, max_width, probe)
        block_width = max((_text_width(probe, line, font) for line in lines), default=0)
        block_height = line_height * len(lines)

        if not auto_size or (block_width <= max_width and block_height <= max_height):
            return font, lines, line_height, block_width, block_height

    fallback_font = _load_font(88, font_path)
    fallback_lines = _wrap_title(title, fallback_font, max_width, probe)
    line_height = max(1, round(88 * _effective_line_spacing(font_path, line_spacing)))
    block_width = max(
        (_text_width(probe, line, fallback_font) for line in fallback_lines), default=0
    )
    block_height = line_height * len(fallback_lines)
    return fallback_font, fallback_lines, line_height, block_width, block_height


def _line_spacing(font_path: Path | None) -> float:
    if font_path:
        return 0.9
    if BEBAS_FONT.exists():
        return 0.86
    return 1.03


def _effective_line_spacing(font_path: Path | None, requested: float) -> float:
    return requested if requested > 0 else _line_spacing(font_path)


def _wrap_title(
    title: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    if not title.strip():
        return []

    lines: list[str] = []
    for manual_line in title.splitlines():
        words = manual_line.split()
        if not words:
            continue

        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or _text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue

            lines.append(current)
            current = word

        if current:
            lines.append(current)

    return lines


def fit_title_metrics_for_test(
    title: str,
    max_width: int = 1360,
    max_height: int = 430,
    font_size: int = MAX_TITLE_FONT_SIZE,
    auto_size: bool = True,
    line_spacing: float = 0.9,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    return _fit_title(
        format_title(title),
        max_width=max_width,
        max_height=max_height,
        font_path=None,
        auto_size=auto_size,
        title_font_size=font_size,
        line_spacing=line_spacing,
    )


def fit_title_lines_for_test(
    title: str,
    max_width: int = 1360,
    font_size: int = 218,
    font_path: Path | None = None,
) -> list[str]:
    font = _load_font(font_size, font_path)
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    return _wrap_title(format_title(title), font, max_width, draw)


def _fit_box_text(
    text: str,
    box: TextBox,
    font_path: Path | None,
    min_size: int,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    start_size = max(min_size, min(box.font_size, 260))
    sizes = range(start_size, min_size - 1, -2) if box.auto_size else [start_size]
    for size in sizes:
        font = _load_font(size, font_path)
        line_height = max(1, round(size * box.line_spacing))
        lines = _wrap_title(text, font, box.width, probe)
        block_width = max((_text_width(probe, line, font) for line in lines), default=0)
        block_height = line_height * len(lines)
        if not box.auto_size or (block_width <= box.width and block_height <= box.height):
            return font, lines, line_height, block_width, block_height

    font = _load_font(min_size, font_path)
    lines = _wrap_title(text, font, box.width, probe)
    line_height = max(1, round(min_size * box.line_spacing))
    block_width = max((_text_width(probe, line, font) for line in lines), default=0)
    block_height = line_height * len(lines)
    return font, lines, line_height, block_width, block_height


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


def _aligned_x(anchor_x: int, width: int, alignment: str) -> int:
    if alignment == "left":
        return anchor_x
    if alignment == "right":
        return anchor_x - width
    return anchor_x - (width // 2)


def _aligned_line_offset(block_width: int, line_width: int, alignment: str) -> int:
    if alignment == "left":
        return 0
    if alignment == "right":
        return block_width - line_width
    return (block_width - line_width) // 2


def _service_box(options: TitleImageOptions) -> TextBox:
    if options.service_line_box:
        return options.service_line_box
    return TextBox(
        x=280,
        y=options.top_line_position[1],
        width=1360,
        height=110,
        alignment=options.text_alignment,
        auto_size=True,
        font_size=86,
        max_font_size=260,
        line_spacing=1.0,
    )


def _title_box(options: TitleImageOptions) -> TextBox:
    if options.title_box:
        return options.title_box
    return TextBox(
        x=280,
        y=options.title_position[1] - 215,
        width=1360,
        height=430,
        alignment=options.text_alignment,
        auto_size=options.auto_size,
        font_size=options.title_font_size,
        max_font_size=MAX_TITLE_FONT_SIZE,
        line_spacing=0,
        skew_angle=-7.0,
    )


def _speaker_box(options: TitleImageOptions) -> TextBox:
    if options.speaker_box:
        return options.speaker_box
    return TextBox(
        x=280,
        y=options.bottom_line_position[1],
        width=1360,
        height=110,
        alignment=options.text_alignment,
        auto_size=True,
        font_size=80,
        max_font_size=260,
        line_spacing=1.0,
    )


def _draw_layout_guides(
    draw: ImageDraw.ImageDraw,
    service_box: TextBox,
    title_box: TextBox,
    speaker_box: TextBox,
    selected_layout_area: str | None,
) -> None:
    guide_color = (255, 255, 255, 115)
    boxes = {
        "Service Line": service_box,
        "Sermon Title": title_box,
        "Speaker": speaker_box,
    }
    for area_name, box in boxes.items():
        width = 6 if area_name == selected_layout_area else 3
        color = (255, 230, 80, 180) if area_name == selected_layout_area else guide_color
        draw.rectangle(
            (box.x, box.y, box.x + box.width, box.y + box.height),
            outline=color,
            width=width,
        )
