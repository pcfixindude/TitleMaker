from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
DEFAULT_SAMPLE_FALLBACK = "THE QUICK BROWN FOX"
SAMPLE_BY_ROLE = {
    "service": "FRIDAY PM 7-31-26",
    "speaker": "FRIDAY PM 7-31-26",
    "title": "IS GOD REAL?",
}


def sample_text_for_role(role: str) -> str:
    return SAMPLE_BY_ROLE.get(role, DEFAULT_SAMPLE_FALLBACK)


def render_font_sample(
    font_path: Path | str | None,
    sample_text: str,
    *,
    width: int = 520,
    height: int = 72,
    text_color: str = "#FFFFFF",
    background_color: str = "#2A3340",
) -> Image.Image:
    """Render a small preview strip for a font file."""
    image = Image.new("RGB", (max(120, width), max(40, height)), background_color)
    draw = ImageDraw.Draw(image)
    text = (sample_text or DEFAULT_SAMPLE_FALLBACK).strip() or DEFAULT_SAMPLE_FALLBACK
    font = _load_preview_font(font_path, size=_fit_preview_font_size(text, width, height))
    fill = _parse_color(text_color)
    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(12, (image.width - text_w) // 2)
    y = max(4, (image.height - text_h) // 2)
    draw.text((x, y), text, font=font, fill=fill, anchor="lt")
    return image


def safely_render_font_sample(
    font_path: Path | str | None,
    sample_text: str,
    *,
    width: int = 520,
    height: int = 72,
    text_color: str = "#FFFFFF",
    background_color: str = "#2A3340",
    label: str | None = None,
) -> Image.Image:
    """Like render_font_sample, but never raises for bad/missing fonts."""
    try:
        return render_font_sample(
            font_path,
            sample_text,
            width=width,
            height=height,
            text_color=text_color,
            background_color=background_color,
        )
    except Exception:
        image = Image.new("RGB", (max(120, width), max(40, height)), background_color)
        draw = ImageDraw.Draw(image)
        fallback = ImageFont.load_default()
        name = label or (Path(font_path).name if font_path else "Unavailable font")
        draw.text((12, height // 3), name, font=fallback, fill=(220, 220, 220))
        return image


def _fit_preview_font_size(text: str, width: int, height: int) -> int:
    # Leave padding; prefer readable title-card style samples.
    target = min(48, max(18, height - 20))
    # Shrink for very long sample strings.
    if len(text) > 28:
        target = min(target, 28)
    if len(text) > 40:
        target = min(target, 22)
    _ = width
    return target


def _load_preview_font(
    font_path: Path | str | None, size: int
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[Path] = []
    if font_path:
        path = Path(font_path)
        if not path.is_absolute():
            candidates.append((PROJECT_ROOT / path).resolve())
        candidates.append(path)
    candidates.extend(
        [
            FONTS_DIR / "BarlowCondensed-Bold.ttf",
            FONTS_DIR / "BarlowCondensed-BoldItalic.ttf",
        ]
    )
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate)
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        try:
            return ImageFont.truetype(str(resolved), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _parse_color(value: str) -> tuple[int, int, int]:
    text = (value or "#FFFFFF").strip()
    if text.startswith("#") and len(text) == 7:
        return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
    return 255, 255, 255
