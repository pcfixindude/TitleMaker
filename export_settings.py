from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image, ImageFilter

from title_renderer import CANVAS_SIZE, TitleImageOptions, export_filename, render_title_image


BASE_WIDTH, BASE_HEIGHT = CANVAS_SIZE
EXPORT_LAYOUT_MODES = ["Scale to fit", "Fill/crop", "Stretch"]
DEFAULT_EXPORT_TARGET = "Stream 1080p"


@dataclass(frozen=True)
class ExportTarget:
    name: str
    width: int
    height: int
    suffix: str
    aspect_ratio: str
    custom: bool = False


BUILT_IN_EXPORT_TARGETS: dict[str, ExportTarget] = {
    "Stream 1080p": ExportTarget("Stream 1080p", 1920, 1080, "stream_1080p", "16:9"),
    "YouTube Thumbnail": ExportTarget("YouTube Thumbnail", 1280, 720, "youtube_thumb", "16:9"),
    "YouTube 1080p": ExportTarget("YouTube 1080p", 1920, 1080, "youtube_1080p", "16:9"),
    "Facebook Feed Landscape": ExportTarget(
        "Facebook Feed Landscape", 1200, 630, "facebook_landscape", "1.91:1"
    ),
    "Facebook / Instagram Square": ExportTarget(
        "Facebook / Instagram Square", 1080, 1080, "square_1080", "1:1"
    ),
    "Facebook / Instagram Story or Reel": ExportTarget(
        "Facebook / Instagram Story or Reel",
        1080,
        1920,
        "vertical_1080x1920",
        "9:16",
    ),
    "Vimeo/Venmo 1080p": ExportTarget(
        "Vimeo/Venmo 1080p", 1920, 1080, "vimeo_1080p", "16:9"
    ),
}
EXPORT_TARGET_NAMES = [*BUILT_IN_EXPORT_TARGETS.keys(), "Custom"]


def default_export_settings() -> dict:
    return {
        "selected_export_target": DEFAULT_EXPORT_TARGET,
        "custom_export_width": 1920,
        "custom_export_height": 1080,
        "custom_export_suffix": "custom_1920x1080",
        "allow_builtin_export_size_edit": False,
        "export_layout_mode": "Scale to fit",
        "export_multiple_targets": False,
        "multi_target_selection": ["Stream 1080p", "YouTube Thumbnail"],
    }


def migrate_export_settings(raw: dict) -> dict:
    settings = default_export_settings()
    for key in settings:
        if key in raw:
            settings[key] = raw[key]

    if settings["selected_export_target"] not in EXPORT_TARGET_NAMES:
        settings["selected_export_target"] = DEFAULT_EXPORT_TARGET
    if settings["export_layout_mode"] not in EXPORT_LAYOUT_MODES:
        settings["export_layout_mode"] = "Scale to fit"
    settings["custom_export_width"] = max(1, int(settings["custom_export_width"]))
    settings["custom_export_height"] = max(1, int(settings["custom_export_height"]))
    settings["custom_export_suffix"] = sanitize_suffix(settings["custom_export_suffix"])
    settings["multi_target_selection"] = [
        target for target in settings["multi_target_selection"] if target in EXPORT_TARGET_NAMES
    ] or [DEFAULT_EXPORT_TARGET]
    return settings


def resolve_export_target(settings: dict) -> ExportTarget:
    migrated = migrate_export_settings(settings)
    target_name = migrated["selected_export_target"]
    if target_name == "Custom":
        suffix = migrated["custom_export_suffix"] or f"custom_{migrated['custom_export_width']}x{migrated['custom_export_height']}"
        return ExportTarget(
            "Custom",
            migrated["custom_export_width"],
            migrated["custom_export_height"],
            sanitize_suffix(suffix),
            "custom",
            custom=True,
        )

    target = BUILT_IN_EXPORT_TARGETS[target_name]
    if migrated["allow_builtin_export_size_edit"]:
        return ExportTarget(
            target.name,
            migrated["custom_export_width"],
            migrated["custom_export_height"],
            target.suffix,
            target.aspect_ratio,
        )
    return target


def resolve_multi_targets(settings: dict) -> list[ExportTarget]:
    migrated = migrate_export_settings(settings)
    targets = []
    for target_name in migrated["multi_target_selection"]:
        target_settings = {**migrated, "selected_export_target": target_name}
        targets.append(resolve_export_target(target_settings))
    return targets


def sanitize_suffix(value: str) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip()).strip("_").lower()
    return suffix or "custom"


def export_filename_for_target(options: TitleImageOptions, target: ExportTarget) -> str:
    stem = export_filename(options).removesuffix(".png")
    return f"{stem}_{sanitize_suffix(target.suffix)}.png"


def render_for_export(
    options: TitleImageOptions,
    target: ExportTarget,
    layout_mode: str = "Scale to fit",
) -> Image.Image:
    base_image = render_title_image(options)
    return transform_export_image(base_image, target, layout_mode)


def transform_export_image(
    image: Image.Image,
    target: ExportTarget,
    layout_mode: str = "Scale to fit",
) -> Image.Image:
    size = (target.width, target.height)
    if image.size == size:
        return image.copy()
    if layout_mode == "Stretch":
        return image.resize(size, Image.Resampling.LANCZOS)
    if layout_mode == "Fill/crop":
        return _resize_to_cover(image, size)
    return _scale_to_fit(image, size)


def scale_design_box(
    box: dict,
    target_width: int,
    target_height: int,
    layout_mode: str = "Stretch",
) -> dict:
    x_scale = target_width / BASE_WIDTH
    y_scale = target_height / BASE_HEIGHT
    font_scale = min(x_scale, y_scale)
    if layout_mode == "Scale to fit":
        scale = min(x_scale, y_scale)
        x_offset = (target_width - BASE_WIDTH * scale) / 2
        y_offset = (target_height - BASE_HEIGHT * scale) / 2
        x_scale = y_scale = font_scale = scale
    elif layout_mode == "Fill/crop":
        scale = max(x_scale, y_scale)
        x_offset = (target_width - BASE_WIDTH * scale) / 2
        y_offset = (target_height - BASE_HEIGHT * scale) / 2
        x_scale = y_scale = font_scale = scale
    else:
        x_offset = y_offset = 0

    scaled = box.copy()
    scaled["x"] = round(box["x"] * x_scale + x_offset)
    scaled["y"] = round(box["y"] * y_scale + y_offset)
    scaled["width"] = round(box["width"] * x_scale)
    scaled["height"] = round(box["height"] * y_scale)
    scaled["font_size"] = round(box.get("font_size", 1) * font_scale)
    if "max_font_size" in box:
        scaled["max_font_size"] = round(box["max_font_size"] * font_scale)
    return scaled


def _scale_to_fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    scale = min(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    background = _resize_to_cover(image, size).filter(ImageFilter.GaussianBlur(18))
    x = (target_width - resized.width) // 2
    y = (target_height - resized.height) // 2
    background.paste(resized, (x, y))
    return background


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
