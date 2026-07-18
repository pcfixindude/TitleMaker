from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from font_config import (
    FontConfig,
    default_service_font_config,
    default_title_font_config,
    font_config_from_dict,
)


CANVAS_SIZE = (1920, 1080)
CANVAS_WIDTH, CANVAS_HEIGHT = CANVAS_SIZE
PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
EXPORTS_DIR = PROJECT_ROOT / "exports"
PRESETS_DIR = PROJECT_ROOT / "presets"
YOUTUBE_PLAYLIST_URL = (
    "https://studio.youtube.com/playlist/PLC0_dngm_51A/videos"
)
WHATSAPP_WEB_URL = "https://web.whatsapp.com/"


def get_default_downloads_dir() -> Path:
    """Prefer the user's Downloads folder; fall back to app exports/."""
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORTS_DIR


def resolve_export_dir(preference: str = "Downloads folder") -> Path:
    """Resolve export directory from a UI preference label."""
    if preference == "App exports folder":
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        return EXPORTS_DIR
    return get_default_downloads_dir()

BARLOW_BOLD = FONTS_DIR / "BarlowCondensed-Bold.ttf"
BARLOW_BOLD_ITALIC = FONTS_DIR / "BarlowCondensed-BoldItalic.ttf"
BEBAS_FONT = FONTS_DIR / "BebasNeue-Regular.ttf"
FONT_EXTENSIONS = {".ttf", ".otf"}

# Backwards-compatible aliases (older names / app imports).
BARLOW_BOLDITALIC = BARLOW_BOLD_ITALIC
BARLOW_FONT = BARLOW_BOLD_ITALIC
DEFAULT_FONT = BARLOW_BOLD_ITALIC
FONT_PATH = BARLOW_BOLD_ITALIC
DEFAULT_SERVICE_FONT = BARLOW_BOLD
DEFAULT_TITLE_FONT = BARLOW_BOLD_ITALIC
DEFAULT_SPEAKER_FONT = BARLOW_BOLD

MAX_TITLE_FONT_SIZE = 520
# Barlow glyph height is often shorter than the em-size; allow searching above the
# box height so short titles can truly fill the title area.
TITLE_FONT_SEARCH_SCALE = 2.2
MIN_TITLE_FONT_SIZE = 28
MIN_SINGLE_LINE_FONT_SIZE = 28
TITLE_LINE_SPACING = 0.95
DEFAULT_TITLE_LINE_SPACING_PX = 0
MIN_TITLE_LINE_GAP_RATIO = 0.4
TITLE_LINE_SPACING_PX_MIN = -80
TITLE_LINE_SPACING_PX_MAX = 120
TEXT_COLOR_WHITE = "#FFFFFF"
LAYOUT_DEFAULTS_VERSION = 6

# Default boxes tuned for the open-Bible template (1920x1080).
DEFAULT_SERVICE_BOX = {"x": 280, "y": 95, "width": 1360, "height": 90}
DEFAULT_TITLE_BOX = {"x": 30, "y": 195, "width": 1860, "height": 460}
DEFAULT_SPEAKER_BOX = {"x": 280, "y": 665, "width": 1360, "height": 90}

# Compatibility aliases for unused legacy modules.
SERVICE_BOX = dict(DEFAULT_SERVICE_BOX)
SPEAKER_BOX = dict(DEFAULT_SPEAKER_BOX)
TITLE_SIDE_PADDING = DEFAULT_TITLE_BOX["x"]
TITLE_VERTICAL_GAP = 35
MIN_TITLE_HEIGHT = 80
DEFAULT_TOP_POSITION = (960, DEFAULT_SERVICE_BOX["y"])
DEFAULT_TITLE_POSITION = (960, 440)
DEFAULT_BOTTOM_POSITION = (960, DEFAULT_SPEAKER_BOX["y"])


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
    line_spacing: float = TITLE_LINE_SPACING
    line_gap_adjust: int = 0
    skew_angle: float = 0.0


@dataclass(frozen=True)
class TitleImageOptions:
    """Simplified render options for the live title maker."""

    day: str
    service: str
    service_date: date
    sermon_title: str
    speaker_name: str
    text_color: str = TEXT_COLOR_WHITE
    background_path: Path | None = None
    show_bounding_boxes: bool = False
    title_vertical_offset: int = 0  # unused; kept for older call sites
    font_path: Path | None = None
    service_font_path: Path | None = None
    title_font_path: Path | None = None
    speaker_font_path: Path | None = None
    service_font_config: FontConfig | None = None
    title_font_config: FontConfig | None = None
    speaker_font_config: FontConfig | None = None
    auto_size: bool = True
    title_font_size: int = MAX_TITLE_FONT_SIZE
    title_line_spacing: int = DEFAULT_TITLE_LINE_SPACING_PX
    shadow_enabled: bool = False
    show_service_line: bool = True
    skew_enabled: bool = False
    show_layout_guides: bool = False
    selected_layout_area: str | None = None
    service_line_box: TextBox | None = None
    title_box: TextBox | None = None
    speaker_box: TextBox | None = None
    top_line_position: tuple[int, int] = (960, 95)
    title_position: tuple[int, int] = (960, 425)
    bottom_line_position: tuple[int, int] = (960, 665)
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


def normalize_service_code(value: str) -> str:
    """Map Morning/AM, Afternoon/AFT, Evening/PM to AM/AFT/PM."""
    normalized = re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
    service_codes = {
        "morning": "AM",
        "am": "AM",
        "afternoon": "AFT",
        "aft": "AFT",
        "evening": "PM",
        "pm": "PM",
    }
    return service_codes.get(normalized, str(value or "").upper())


def service_code(service: str) -> str:
    """Alias for normalize_service_code (kept for existing call sites)."""
    return normalize_service_code(service)


def format_title(value: str) -> str:
    lines = [" ".join(line.strip().upper().split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def format_speaker(value: str) -> str:
    return " ".join(value.strip().upper().split())


def format_youtube_title(service_line: str, title: str, speaker: str) -> str:
    """Full YouTube title: SERVICE LINE | SERMON TITLE | SPEAKER."""
    line = " ".join(str(service_line or "").strip().upper().split())
    sermon = format_title(title).replace("\n", " ").strip()
    minister = format_speaker(speaker)
    return " | ".join(part for part in (line, sermon, minister) if part)


def format_short_youtube_title(day: str, title: str, speaker: str) -> str:
    """Short YouTube title: WEEKDAY | SERMON TITLE | SPEAKER."""
    weekday = " ".join(str(day or "").strip().upper().split())
    sermon = format_title(title).replace("\n", " ").strip()
    minister = format_speaker(speaker)
    return " | ".join(part for part in (weekday, sermon, minister) if part)


def export_filename(options: TitleImageOptions) -> str:
    date_part = options.service_date.isoformat()
    service_part = f"{options.day}_{service_code(options.service)}".upper()
    title_part = _slug(format_title(options.sermon_title))
    return f"{date_part}_{service_part}_{title_part}.png"


def default_font_path(fonts: list[Path] | None = None) -> Path | None:
    """Title / default display font (Bold Italic preferred)."""
    return resolve_title_font_path(fonts=fonts)


def resolve_service_font_path(
    preferred: Path | None = None,
    fonts: list[Path] | None = None,
) -> Path | None:
    """Service line font: preferred, then Bold, then Bold Italic, then fallbacks."""
    chain = tuple(path for path in (preferred, BARLOW_BOLD, BARLOW_BOLD_ITALIC) if path)
    return _resolve_font_path(preferred=chain, fonts=fonts)


def resolve_speaker_font_path(
    preferred: Path | None = None,
    fonts: list[Path] | None = None,
) -> Path | None:
    """Speaker font: preferred, then Bold, then Bold Italic, then fallbacks."""
    return resolve_service_font_path(preferred=preferred, fonts=fonts)


def resolve_title_font_path(
    preferred: Path | None = None,
    fonts: list[Path] | None = None,
) -> Path | None:
    """Sermon title font: preferred, then Bold Italic, then Bold, then fallbacks."""
    chain = tuple(path for path in (preferred, BARLOW_BOLD_ITALIC, BARLOW_BOLD) if path)
    return _resolve_font_path(preferred=chain, fonts=fonts)


def _resolve_font_path(
    *,
    preferred: tuple[Path, ...],
    fonts: list[Path] | None = None,
) -> Path | None:
    for path in preferred:
        candidate = Path(path)
        if candidate.exists():
            return candidate
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


def default_service_box() -> TextBox:
    return TextBox(**DEFAULT_SERVICE_BOX)


def default_title_box() -> TextBox:
    return TextBox(
        **DEFAULT_TITLE_BOX,
        max_font_size=MAX_TITLE_FONT_SIZE,
        line_spacing=TITLE_LINE_SPACING,
    )


def default_speaker_box() -> TextBox:
    return TextBox(**DEFAULT_SPEAKER_BOX)


def box_dict(box: TextBox) -> dict[str, int]:
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def clamp_title_line_spacing(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_TITLE_LINE_SPACING_PX
    return max(TITLE_LINE_SPACING_PX_MIN, min(TITLE_LINE_SPACING_PX_MAX, parsed))


def text_box_from_dict(
    values: dict[str, Any],
    *,
    max_font_size: int = MAX_TITLE_FONT_SIZE,
    font_size: int | None = None,
    auto_size: bool | None = None,
    line_gap_adjust: int | None = None,
) -> TextBox:
    resolved_font = int(values["font_size"]) if values.get("font_size") is not None else font_size
    if resolved_font is None:
        resolved_font = 86
    resolved_auto = (
        bool(values["auto_size"])
        if values.get("auto_size") is not None
        else (True if auto_size is None else bool(auto_size))
    )
    resolved_max = int(values.get("max_font_size") or max_font_size)
    if not resolved_auto:
        resolved_max = max(resolved_max, resolved_font)
    if line_gap_adjust is None:
        if values.get("line_gap_adjust") is not None:
            gap = int(values["line_gap_adjust"])
        elif values.get("title_line_spacing") is not None:
            gap = clamp_title_line_spacing(values["title_line_spacing"])
        else:
            gap = DEFAULT_TITLE_LINE_SPACING_PX
    else:
        gap = clamp_title_line_spacing(line_gap_adjust)
    return TextBox(
        x=int(values["x"]),
        y=int(values["y"]),
        width=max(1, int(values["width"])),
        height=max(1, int(values["height"])),
        font_size=resolved_font,
        max_font_size=resolved_max,
        auto_size=resolved_auto,
        line_spacing=TITLE_LINE_SPACING,
        line_gap_adjust=gap,
    )


def resolve_layout_boxes(options: TitleImageOptions) -> tuple[TextBox, TextBox, TextBox]:
    from dataclasses import replace

    service_box = options.service_line_box or default_service_box()
    title_box = options.title_box or default_title_box()
    speaker_box = options.speaker_box or default_speaker_box()
    spacing = clamp_title_line_spacing(options.title_line_spacing)
    title_box = replace(title_box, line_gap_adjust=spacing)
    return service_box, title_box, speaker_box


def compute_title_box(title_vertical_offset: int = 0) -> dict[str, int]:
    """Legacy helper kept for older tests; returns the default title box with optional y nudge."""
    box = dict(DEFAULT_TITLE_BOX)
    box["y"] = max(0, box["y"] + int(title_vertical_offset))
    return box


def resolve_section_font_config(
    config: FontConfig | dict[str, Any] | None,
    preferred_path: Path | None,
    *,
    role: str,
) -> FontConfig:
    """Build an effective FontConfig from explicit config and/or legacy path fields."""
    if isinstance(config, FontConfig):
        cfg = font_config_from_dict(config.to_dict(), role=role)
    elif isinstance(config, dict):
        cfg = font_config_from_dict(config, role=role)
    else:
        cfg = font_config_from_dict(None, role=role)
        if preferred_path is not None:
            try:
                rel = Path(preferred_path).resolve().relative_to(PROJECT_ROOT)
                cfg.font_path = str(rel).replace("\\", "/")
            except Exception:
                cfg.font_path = str(preferred_path)
    resolver = {
        "service": resolve_service_font_path,
        "title": resolve_title_font_path,
        "speaker": resolve_speaker_font_path,
    }.get(role, resolve_service_font_path)
    resolved = resolver(preferred=cfg.resolved_font_path())
    if resolved is not None:
        try:
            cfg.font_path = str(resolved.resolve().relative_to(PROJECT_ROOT)).replace(
                "\\", "/"
            )
        except ValueError:
            cfg.font_path = str(resolved)
    return cfg


def render_title_image(options: TitleImageOptions) -> Image.Image:
    ensure_project_dirs()
    # RGBA so each text layer can be clipped to its box tile.
    image = _load_background(options.background_path).convert("RGBA")
    service_cfg = resolve_section_font_config(
        options.service_font_config, options.service_font_path, role="service"
    )
    title_cfg = resolve_section_font_config(
        options.title_font_config, options.title_font_path, role="title"
    )
    speaker_cfg = resolve_section_font_config(
        options.speaker_font_config, options.speaker_font_path, role="speaker"
    )
    service_box, title_box, speaker_box = resolve_layout_boxes(options)

    if options.show_service_line:
        render_text_in_box(
            image,
            format_top_line(options),
            service_box,
            mode="single",
            font_config=service_cfg,
        )

    render_text_in_box(
        image,
        format_title(options.sermon_title),
        title_box,
        mode="title",
        font_config=title_cfg,
    )

    render_text_in_box(
        image,
        format_speaker(options.speaker_name),
        speaker_box,
        mode="single",
        font_config=speaker_cfg,
    )

    # Guides only when explicitly requested — never because a text area is selected.
    if options.show_bounding_boxes or options.show_layout_guides:
        draw_preview_guides(
            ImageDraw.Draw(image),
            service_box,
            title_box,
            speaker_box,
            selected=normalize_selected_area(options.selected_layout_area),
        )

    return image.convert("RGB")


def save_title_image(options: TitleImageOptions) -> Path:
    ensure_project_dirs()
    image = render_title_image(options)
    output_path = EXPORTS_DIR / export_filename(options)
    image.save(output_path, "PNG")
    return output_path


def render_text_in_box(
    image: Image.Image,
    text: str,
    box: TextBox,
    *,
    mode: str,
    font_config: FontConfig | None = None,
    font_path: Path | None = None,
    fill: str | None = None,
    shadow_enabled: bool | None = None,
) -> Image.Image:
    """Draw text centered in ``box``, clipped so ink cannot escape the rectangle."""
    if not text:
        return image
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    if font_config is None:
        role = "title" if mode == "title" else "service"
        base = (
            default_title_font_config()
            if role == "title"
            else default_service_font_config()
        )
        if font_path is not None:
            try:
                base.font_path = str(
                    Path(font_path).resolve().relative_to(PROJECT_ROOT)
                ).replace("\\", "/")
            except Exception:
                base.font_path = str(font_path)
        if fill:
            base.text_color = fill
        if shadow_enabled:
            base.use_font_file_default_style_only = False
            base.shadow_enabled = True
        font_config = base

    cfg = font_config.effective()
    resolved_font = cfg.resolved_font_path()
    if not resolved_font.exists():
        resolved_font = resolve_title_font_path() if mode == "title" else resolve_service_font_path()

    # Inset + effect padding so stroke/skew/spacing stay inside the box.
    pad_x, pad_y = _effect_fit_padding(cfg)
    fit_width = max(1, box.width - 4 - pad_x)
    fit_height = max(1, box.height - 4 - pad_y)
    if mode == "title":
        ceiling = (
            max(box.font_size, 40)
            if not box.auto_size
            else max(box.max_font_size, MAX_TITLE_FONT_SIZE)
        )
        font, lines, line_height, _, block_height = fit_title_max_2_lines(
            text,
            max_width=fit_width,
            max_height=fit_height,
            font_path=resolved_font,
            max_font_size=ceiling,
            line_spacing=box.line_spacing,
            line_gap_adjust=box.line_gap_adjust,
            letter_spacing=cfg.letter_spacing,
            skew_angle=cfg.skew_angle,
            outline_width=cfg.outline_width if cfg.outline_enabled else 0,
            artificial_bold=cfg.artificial_bold,
            underline=cfg.underline,
        )
    else:
        ceiling = (
            max(box.font_size, 20)
            if not box.auto_size
            else max(120, min(fit_height, 200))
        )
        font, lines, line_height, _, block_height = fit_single_line_text(
            text,
            max_width=fit_width,
            max_height=fit_height,
            font_path=resolved_font,
            max_font_size=ceiling,
            letter_spacing=cfg.letter_spacing,
            skew_angle=cfg.skew_angle,
            outline_width=cfg.outline_width if cfg.outline_enabled else 0,
            artificial_bold=cfg.artificial_bold,
            underline=cfg.underline,
        )

    content = _render_text_layer(
        lines,
        font,
        line_height,
        block_height,
        cfg,
    )
    # Clip content into the box tile (text stays inside; shadow may be clipped).
    tile = Image.new("RGBA", (max(1, box.width), max(1, box.height)), (0, 0, 0, 0))
    if content.width > 0 and content.height > 0:
        paste_x = max(0, (box.width - content.width) // 2)
        paste_y = max(0, (box.height - content.height) // 2)
        tile.alpha_composite(content, dest=(paste_x, paste_y))

    image.alpha_composite(tile, dest=(max(0, box.x), max(0, box.y)))
    return image


def _effect_fit_padding(cfg: FontConfig) -> tuple[int, int]:
    pad_x = 0
    pad_y = 0
    if cfg.outline_enabled and cfg.outline_width > 0:
        pad_x += 2 * int(cfg.outline_width)
        pad_y += 2 * int(cfg.outline_width)
    if cfg.artificial_bold:
        pad_x += 4
        pad_y += 4
    if cfg.underline:
        pad_y += 8
    # Shadow does not shrink the text fit box (text stays in box; shadow may clip).
    return pad_x, pad_y


def _skew_extra_width(height: int, angle: float) -> int:
    if abs(angle) < 0.01:
        return 0
    return int(abs(math.tan(math.radians(angle))) * max(1, height)) + 2


def _letter_spacing_extra(text: str, letter_spacing: float) -> float:
    if abs(letter_spacing) < 0.01 or len(text) < 2:
        return 0.0
    return float(letter_spacing) * (len(text) - 1)


def _render_text_layer(
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    line_height: int,
    block_height: int,
    cfg: FontConfig,
) -> Image.Image:
    """Rasterize styled text; may be larger than the final box before clipping."""
    if not lines:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))
    widths = [
        _styled_text_width(probe, line, font, cfg.letter_spacing, cfg.artificial_bold)
        for line in lines
    ]
    max_width = max(widths) if widths else 1
    underline_extra = 10 if cfg.underline else 0
    outline = int(cfg.outline_width) if cfg.outline_enabled else 0
    pad = outline + (2 if cfg.artificial_bold else 0) + 4
    shadow_pad_x = abs(int(cfg.shadow_offset_x)) if cfg.shadow_enabled else 0
    shadow_pad_y = abs(int(cfg.shadow_offset_y)) if cfg.shadow_enabled else 0
    canvas_w = max_width + 2 * pad + 2 * shadow_pad_x + _skew_extra_width(
        block_height + underline_extra, cfg.skew_angle
    )
    canvas_h = block_height + underline_extra + 2 * pad + 2 * shadow_pad_y
    layer = Image.new("RGBA", (max(1, canvas_w), max(1, canvas_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    origin_x = pad + shadow_pad_x
    origin_y = pad + shadow_pad_y
    y = origin_y
    fill = _fill_to_rgba(cfg.text_color)
    for line, line_width in zip(lines, widths):
        x = origin_x + max(0, (max_width - line_width) // 2)
        _draw_styled_line(draw, (x, y), line, font, fill, cfg)
        y += line_height

    if abs(cfg.skew_angle) > 0.01:
        layer = _apply_skew(layer, cfg.skew_angle)

    return _trim_alpha(layer)


def _draw_styled_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    cfg: FontConfig,
) -> None:
    x, y = xy
    stroke_width = int(cfg.outline_width) if cfg.outline_enabled else 0
    stroke_fill = _fill_to_rgba(cfg.outline_color) if stroke_width else None
    offsets = [(0, 0)]
    if cfg.artificial_bold:
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0), (-1, -1), (1, 1)]

    if cfg.shadow_enabled:
        shadow = _fill_to_rgba(cfg.shadow_color)
        sx = x + int(cfg.shadow_offset_x)
        sy = y + int(cfg.shadow_offset_y)
        for dx, dy in offsets:
            _draw_text_with_spacing(
                draw,
                (sx + dx, sy + dy),
                text,
                font,
                shadow,
                cfg.letter_spacing,
                stroke_width=0,
                stroke_fill=None,
            )

    for dx, dy in offsets:
        _draw_text_with_spacing(
            draw,
            (x + dx, y + dy),
            text,
            font,
            fill,
            cfg.letter_spacing,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    if cfg.underline:
        bbox = _styled_text_bbox(draw, text, font, cfg.letter_spacing, cfg.artificial_bold)
        underline_y = y + max(bbox[3] - bbox[1] + 2, int(getattr(font, "size", 20) * 0.12))
        draw.line(
            (x + bbox[0], underline_y, x + bbox[2], underline_y),
            fill=fill,
            width=max(2, int(getattr(font, "size", 20) * 0.04)),
        )


def _draw_text_with_spacing(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    letter_spacing: float,
    *,
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | None = None,
) -> None:
    x, y = xy
    if abs(letter_spacing) < 0.01:
        kwargs: dict[str, Any] = {"font": font, "fill": fill, "anchor": "lt"}
        if stroke_width > 0 and stroke_fill is not None:
            kwargs["stroke_width"] = stroke_width
            kwargs["stroke_fill"] = stroke_fill
        draw.text((x, y), text, **kwargs)
        return
    cursor = float(x)
    for index, char in enumerate(text):
        kwargs = {"font": font, "fill": fill, "anchor": "lt"}
        if stroke_width > 0 and stroke_fill is not None:
            kwargs["stroke_width"] = stroke_width
            kwargs["stroke_fill"] = stroke_fill
        draw.text((int(round(cursor)), y), char, **kwargs)
        cursor += _text_width(draw, char, font)
        if index < len(text) - 1:
            cursor += letter_spacing


def _styled_text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    letter_spacing: float,
    artificial_bold: bool,
) -> int:
    width = _text_width(draw, text, font) + int(_letter_spacing_extra(text, letter_spacing))
    if artificial_bold:
        width += 2
    return max(1, width)


def _styled_text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    letter_spacing: float,
    artificial_bold: bool,
) -> tuple[int, int, int, int]:
    width = _styled_text_width(draw, text, font, letter_spacing, artificial_bold)
    height = _text_height(draw, text, font)
    return 0, 0, width, height


def _apply_skew(image: Image.Image, angle: float) -> Image.Image:
    """Shear horizontally; positive angle slants right."""
    if abs(angle) < 0.01:
        return image
    shear = math.tan(math.radians(angle))
    extra = int(abs(shear) * image.height) + 2
    wide = Image.new("RGBA", (image.width + extra, image.height), (0, 0, 0, 0))
    # Shift so negative shear stays on canvas.
    offset = extra if shear < 0 else 0
    wide.paste(image, (offset, 0))
    # AFFINE: x' = x + shear*y
    return wide.transform(
        wide.size,
        Image.Transform.AFFINE,
        (1, shear, -offset * (1 if shear >= 0 else 0), 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )


def _trim_alpha(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image
    alpha = image.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return image.crop(bbox)


def center_text_block_in_box(box: TextBox, block_height: int) -> tuple[int, int]:
    """Return top-left origin so the text block is centered in the box."""
    x = box.x
    y = box.y + max(0, (box.height - min(block_height, box.height)) // 2)
    return x, y


def _fill_to_rgba(fill: str) -> tuple[int, int, int, int]:
    value = (fill or TEXT_COLOR_WHITE).strip()
    if value.startswith("#") and len(value) == 7:
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 255
    return 255, 255, 255, 255


def effective_line_stride(
    max_glyph: int,
    font_size: int,
    *,
    line_spacing: float = TITLE_LINE_SPACING,
    line_gap_adjust: int = 0,
    line_count: int = 1,
) -> int:
    """Baseline stride used for fitting and drawing (must stay in sync)."""
    base = max(1, max_glyph, round(int(font_size) * float(line_spacing)))
    if line_count < 2:
        return base
    # Allow tightening, but keep a floor so lines rarely fully overlap.
    min_stride = max(1, int(max_glyph * MIN_TITLE_LINE_GAP_RATIO))
    return max(min_stride, base + int(line_gap_adjust))


def measure_text_block(
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    *,
    line_spacing: float = TITLE_LINE_SPACING,
    line_gap_adjust: int = 0,
    draw: ImageDraw.ImageDraw | None = None,
    letter_spacing: float = 0.0,
    artificial_bold: bool = False,
    underline: bool = False,
    skew_angle: float = 0.0,
    outline_width: int = 0,
) -> tuple[int, int, int]:
    """Return (block_width, line_stride, block_height) for a line layout."""
    probe = draw or ImageDraw.Draw(Image.new("RGB", (10, 10)))
    if not lines:
        size = int(getattr(font, "size", 1) or 1)
        return 0, size, 0

    size = int(getattr(font, "size", 1) or 1)
    widths = [
        _styled_text_width(probe, line, font, letter_spacing, artificial_bold)
        for line in lines
    ]
    glyph_heights = [_text_height(probe, line, font) for line in lines]
    max_glyph = max(glyph_heights)
    if artificial_bold:
        max_glyph += 2
    if outline_width > 0:
        max_glyph += 2 * int(outline_width)
        widths = [w + 2 * int(outline_width) for w in widths]
    line_stride = effective_line_stride(
        max_glyph,
        size,
        line_spacing=line_spacing,
        line_gap_adjust=line_gap_adjust,
        line_count=len(lines),
    )
    if len(lines) == 1:
        block_height = max_glyph
    else:
        block_height = line_stride * (len(lines) - 1) + max_glyph
    if underline:
        block_height += max(4, int(size * 0.08))
    block_width = max(widths)
    block_width += _skew_extra_width(block_height, skew_angle)
    return block_width, line_stride, block_height


def find_largest_fitting_font_size(
    lines: list[str],
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = MAX_TITLE_FONT_SIZE,
    min_font_size: int = MIN_TITLE_FONT_SIZE,
    line_spacing: float = TITLE_LINE_SPACING,
    line_gap_adjust: int = 0,
    letter_spacing: float = 0.0,
    skew_angle: float = 0.0,
    outline_width: int = 0,
    artificial_bold: bool = False,
    underline: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int, int, int]:
    """Binary-search the largest font size where the fixed line layout fits."""
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    hi = max(
        min_font_size,
        int(max_font_size),
        MAX_TITLE_FONT_SIZE,
        int(max_height * TITLE_FONT_SEARCH_SCALE),
    )
    lo = min_font_size
    best_font = _load_font(lo, font_path)
    best_stride = lo
    best_width = 0
    best_height = 0
    best_size = lo

    while lo <= hi:
        mid = (lo + hi) // 2
        font = _load_font(mid, font_path)
        block_width, stride, block_height = measure_text_block(
            lines,
            font,
            line_spacing=line_spacing,
            line_gap_adjust=line_gap_adjust,
            draw=probe,
            letter_spacing=letter_spacing,
            artificial_bold=artificial_bold,
            underline=underline,
            skew_angle=skew_angle,
            outline_width=outline_width,
        )
        if block_width <= max_width and block_height <= max_height:
            best_font = font
            best_stride = stride
            best_width = block_width
            best_height = block_height
            best_size = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best_font, best_size, best_stride, best_width, best_height


def fit_single_line_text(
    text: str,
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = 120,
    min_font_size: int = MIN_SINGLE_LINE_FONT_SIZE,
    letter_spacing: float = 0.0,
    skew_angle: float = 0.0,
    outline_width: int = 0,
    artificial_bold: bool = False,
    underline: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    return fit_service_text_one_line(
        text,
        max_width=max_width,
        max_height=max_height,
        font_path=font_path,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        letter_spacing=letter_spacing,
        skew_angle=skew_angle,
        outline_width=outline_width,
        artificial_bold=artificial_bold,
        underline=underline,
    )


def fit_service_text_one_line(
    text: str,
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = 120,
    min_font_size: int = MIN_SINGLE_LINE_FONT_SIZE,
    letter_spacing: float = 0.0,
    skew_angle: float = 0.0,
    outline_width: int = 0,
    artificial_bold: bool = False,
    underline: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    cleaned = " ".join(text.strip().upper().split())
    if not cleaned:
        font = _load_font(max_font_size, font_path)
        return font, [], max(1, max_font_size), 0, 0
    font, _, stride, width, height = find_largest_fitting_font_size(
        [cleaned],
        max_width=max_width,
        max_height=max_height,
        font_path=font_path,
        max_font_size=min(max_font_size, max(1, max_height)),
        min_font_size=min_font_size,
        line_spacing=1.0,
        letter_spacing=letter_spacing,
        skew_angle=skew_angle,
        outline_width=outline_width,
        artificial_bold=artificial_bold,
        underline=underline,
    )
    return font, [cleaned], stride, width, height


def fit_speaker_text_one_line(
    text: str,
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = 120,
    min_font_size: int = MIN_SINGLE_LINE_FONT_SIZE,
    letter_spacing: float = 0.0,
    skew_angle: float = 0.0,
    outline_width: int = 0,
    artificial_bold: bool = False,
    underline: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    return fit_service_text_one_line(
        text,
        max_width=max_width,
        max_height=max_height,
        font_path=font_path,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        letter_spacing=letter_spacing,
        skew_angle=skew_angle,
        outline_width=outline_width,
        artificial_bold=artificial_bold,
        underline=underline,
    )


def fit_title_max_2_lines(
    title: str,
    max_width: int,
    max_height: int,
    font_path: Path | None = None,
    max_font_size: int = MAX_TITLE_FONT_SIZE,
    min_font_size: int = MIN_TITLE_FONT_SIZE,
    line_spacing: float = TITLE_LINE_SPACING,
    line_gap_adjust: int = 0,
    letter_spacing: float = 0.0,
    skew_angle: float = 0.0,
    outline_width: int = 0,
    artificial_bold: bool = False,
    underline: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    """Maximize font size for a 1- or 2-line title that fits the title box."""
    cleaned = format_title(title)
    ceiling = max(
        int(max_font_size),
        MAX_TITLE_FONT_SIZE,
        int(max_height * TITLE_FONT_SEARCH_SCALE),
    )
    if not cleaned:
        font = _load_font(min(ceiling, MAX_TITLE_FONT_SIZE), font_path)
        return font, [], max(1, round(MAX_TITLE_FONT_SIZE * line_spacing)), 0, 0

    candidates = _title_layout_candidates(cleaned)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    best: tuple[
        ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int
    ] | None = None
    best_score: tuple[int, int, int] | None = None
    gap = clamp_title_line_spacing(line_gap_adjust)

    for lines in candidates:
        font, size, stride, width, height = find_largest_fitting_font_size(
            lines,
            max_width=max_width,
            max_height=max_height,
            font_path=font_path,
            max_font_size=ceiling,
            min_font_size=min_font_size,
            line_spacing=line_spacing,
            line_gap_adjust=gap,
            letter_spacing=letter_spacing,
            skew_angle=skew_angle,
            outline_width=outline_width,
            artificial_bold=artificial_bold,
            underline=underline,
        )
        if size < min_font_size or width > max_width or height > max_height:
            # find_largest always returns something; reject if it still overflows.
            if width > max_width or height > max_height:
                continue
        balance = 0
        if len(lines) == 2:
            balance = abs(
                _styled_text_width(probe, lines[0], font, letter_spacing, artificial_bold)
                - _styled_text_width(probe, lines[1], font, letter_spacing, artificial_bold)
            )
        # Prefer larger fonts; near ties prefer one line, then balanced wraps.
        score = (size, -len(lines), -balance)
        if best_score is None or score > best_score:
            best = (font, lines, stride, width, height)
            best_score = score

    if best is None:
        font = _load_font(min_font_size, font_path)
        lines = candidates[0][:2]
        width, stride, height = measure_text_block(
            lines,
            font,
            line_spacing=line_spacing,
            line_gap_adjust=gap,
            letter_spacing=letter_spacing,
            artificial_bold=artificial_bold,
            underline=underline,
            skew_angle=skew_angle,
            outline_width=outline_width,
        )
        return font, lines, stride, width, height

    return best


# Backward-compatible aliases used by older tests / call sites.
fit_title_one_or_two_lines = fit_title_max_2_lines
fit_title_two_lines = fit_title_max_2_lines


def _title_layout_candidates(cleaned: str) -> list[list[str]]:
    manual = [line for line in cleaned.splitlines() if line.strip()]
    if len(manual) >= 2:
        return [[manual[0], " ".join(manual[1:])]]
    text = manual[0] if manual else cleaned
    candidates: list[list[str]] = [[text]]
    words = text.split()
    if len(words) >= 2:
        for split in range(1, len(words)):
            candidates.append([" ".join(words[:split]), " ".join(words[split:])])
    return candidates


def choose_best_two_line_wrap(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw | None = None,
) -> list[str]:
    probe = draw or ImageDraw.Draw(Image.new("RGB", (10, 10)))
    return _best_two_line_wrap(text, font, max_width, probe)


def normalize_selected_area(value: str | None) -> str | None:
    """Map UI labels / aliases to internal keys: service, title, speaker."""
    if value is None:
        return None
    normalized = " ".join(str(value).strip().lower().replace("_", " ").split())
    aliases = {
        "service": "service",
        "service line": "service",
        "service_line": "service",
        "title": "title",
        "sermon title": "title",
        "sermon_title": "title",
        "speaker": "speaker",
        "minister": "speaker",
        "speaker / minister": "speaker",
        "speaker/minister": "speaker",
        "speaker minister": "speaker",
    }
    return aliases.get(normalized)


def draw_preview_guides(
    draw: ImageDraw.ImageDraw,
    service_box: TextBox,
    title_box: TextBox,
    speaker_box: TextBox,
    selected: str | None = None,
) -> None:
    """Draw layout guides. ``selected`` may be a label or key; unknown values are ignored."""
    selected_key = normalize_selected_area(selected)
    areas = (
        ("service", service_box, (255, 255, 255, 160)),
        ("title", title_box, (255, 220, 80, 190)),
        ("speaker", speaker_box, (255, 255, 255, 160)),
    )
    for name, box, color in areas:
        is_selected = selected_key == name
        outline = (80, 220, 255, 255) if is_selected else color
        draw.rectangle(
            (box.x, box.y, box.x + box.width, box.y + box.height),
            outline=outline,
            width=7 if is_selected else 4,
        )


def fit_title_metrics_for_test(
    title: str,
    max_width: int = DEFAULT_TITLE_BOX["width"],
    max_height: int = DEFAULT_TITLE_BOX["height"],
    font_size: int = MAX_TITLE_FONT_SIZE,
    auto_size: bool = True,
    line_spacing: float = TITLE_LINE_SPACING,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int, int]:
    if not auto_size:
        font = _load_font(font_size, default_font_path())
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        lines = _choose_title_lines(format_title(title), font, max_width, probe)
        width, stride, height = measure_text_block(
            lines, font, line_spacing=line_spacing, draw=probe
        )
        return font, lines, stride, width, height
    return fit_title_max_2_lines(
        title,
        max_width=max_width,
        max_height=max_height,
        font_path=default_font_path(),
        max_font_size=font_size,
        line_spacing=line_spacing,
    )


def fit_title_lines_for_test(
    title: str,
    max_width: int = DEFAULT_TITLE_BOX["width"],
    font_size: int = 218,
    font_path: Path | None = None,
) -> list[str]:
    # Use the maximized layout so tests see the same wrap choices as the renderer.
    _, lines, _, _, _ = fit_title_max_2_lines(
        title,
        max_width=max_width,
        max_height=DEFAULT_TITLE_BOX["height"],
        font_path=font_path or default_font_path(),
        max_font_size=max(font_size, MAX_TITLE_FONT_SIZE),
    )
    return lines


def fit_title_font_size_for_test(
    title: str,
    max_width: int = DEFAULT_TITLE_BOX["width"],
    max_height: int = DEFAULT_TITLE_BOX["height"],
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
        first = manual[0]
        second = " ".join(manual[1:])
        return [first, second] if second else [first]

    text = manual[0] if manual else title
    if _text_width(draw, text, font) <= max_width:
        return [text]
    return choose_best_two_line_wrap(text, font, max_width, draw)


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
        balance = abs(w1 - w2)
        orphan = 2.0 if len(words[split:]) == 1 and len(words) > 2 else 0.0
        # Prefer fills that use more width, then avoid orphans, then balance.
        score = (min(w1, w2), -orphan, -balance)
        if best_score is None or score > best_score:
            best = [line1, line2]
            best_score = score

    if best:
        return best

    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        candidate = f"{current} {word}".strip()
        if not current or _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        rest = words[index:]
        lines.append(" ".join(rest))
        return lines[:2]
    if current:
        lines.append(current)
    return lines[:2]


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
        BARLOW_BOLD,
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
    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    return bbox[2] - bbox[0]


def _text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    return max(1, bbox[3] - bbox[1])


def _draw_text_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    radius: int = 3,
    offset: tuple[int, int] = (5, 5),
    anchor: str = "lt",
) -> None:
    # Kept only for optional/debug use; simplified app never enables shadow.
    x, y = xy
    for dx in range(-radius, radius + 1, radius):
        for dy in range(-radius, radius + 1, radius):
            draw.text(
                (x + offset[0] + dx, y + offset[1] + dy),
                text,
                font=font,
                fill=(0, 0, 0, 105),
                anchor=anchor,
            )
