from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
DEFAULT_SERVICE_FONT_PATH = "fonts/BarlowCondensed-Bold.ttf"
DEFAULT_TITLE_FONT_PATH = "fonts/BarlowCondensed-BoldItalic.ttf"
DEFAULT_SPEAKER_FONT_PATH = "fonts/BarlowCondensed-Bold.ttf"
TEXT_COLOR_WHITE = "#FFFFFF"
SHADOW_COLOR_DEFAULT = "#000000"
OUTLINE_COLOR_DEFAULT = "#000000"


@dataclass
class FontConfig:
    """Per-section font file + optional fancy effects."""

    font_path: str = DEFAULT_SERVICE_FONT_PATH
    text_color: str = TEXT_COLOR_WHITE
    use_font_file_default_style_only: bool = True
    artificial_bold: bool = False
    artificial_italic: bool = False
    skew_angle: float = 0.0
    underline: bool = False
    shadow_enabled: bool = False
    shadow_offset_x: int = 4
    shadow_offset_y: int = 4
    shadow_color: str = SHADOW_COLOR_DEFAULT
    outline_enabled: bool = False
    outline_width: int = 0
    outline_color: str = OUTLINE_COLOR_DEFAULT
    letter_spacing: float = 0.0

    def effective(self) -> "FontConfig":
        """Return a copy with fancy effects cleared when default-style-only is on."""
        cfg = deepcopy(self)
        if cfg.use_font_file_default_style_only:
            cfg.artificial_bold = False
            cfg.artificial_italic = False
            cfg.skew_angle = 0.0
            cfg.underline = False
            cfg.shadow_enabled = False
            cfg.outline_enabled = False
            cfg.outline_width = 0
            cfg.letter_spacing = 0.0
        if cfg.artificial_italic and abs(cfg.skew_angle) < 0.01:
            cfg.skew_angle = 12.0
        if not cfg.outline_enabled:
            cfg.outline_width = 0
        return cfg

    def resolved_font_path(self) -> Path:
        path = Path(self.font_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def effects_summary(self) -> str:
        if self.use_font_file_default_style_only:
            return "default style only"
        enabled: list[str] = []
        if self.artificial_bold:
            enabled.append("fake bold")
        if self.artificial_italic or abs(self.skew_angle) > 0.01:
            enabled.append(f"skew {self.skew_angle:g}°")
        if self.underline:
            enabled.append("underline")
        if self.shadow_enabled:
            enabled.append("shadow")
        if self.outline_enabled and self.outline_width > 0:
            enabled.append(f"outline {self.outline_width}")
        if abs(self.letter_spacing) > 0.01:
            enabled.append(f"spacing {self.letter_spacing:g}")
        return ", ".join(enabled) if enabled else "custom (no effects)"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_service_font_config() -> FontConfig:
    return FontConfig(font_path=DEFAULT_SERVICE_FONT_PATH)


def default_title_font_config() -> FontConfig:
    return FontConfig(font_path=DEFAULT_TITLE_FONT_PATH)


def default_speaker_font_config() -> FontConfig:
    return FontConfig(font_path=DEFAULT_SPEAKER_FONT_PATH)


def default_font_config_for_role(role: str) -> FontConfig:
    if role == "title":
        return default_title_font_config()
    if role == "speaker":
        return default_speaker_font_config()
    return default_service_font_config()


def font_config_from_dict(raw: Any, *, role: str = "service") -> FontConfig:
    """Migrate old font-path strings / partial dicts into a FontConfig."""
    base = default_font_config_for_role(role)
    if raw is None:
        return base
    if isinstance(raw, FontConfig):
        return deepcopy(raw)
    if isinstance(raw, str):
        base.font_path = _normalize_font_path_str(raw, role=role)
        return base
    if not isinstance(raw, dict):
        return base

    data = base.to_dict()
    for field in fields(FontConfig):
        if field.name in raw and raw[field.name] is not None:
            data[field.name] = raw[field.name]
    # Legacy single-path fields.
    if "font_path" not in raw:
        for key in ("path", "selected_font", "font"):
            if raw.get(key):
                data["font_path"] = raw[key]
                break
    data["font_path"] = _normalize_font_path_str(str(data["font_path"]), role=role)
    data["skew_angle"] = float(data.get("skew_angle") or 0)
    data["letter_spacing"] = float(data.get("letter_spacing") or 0)
    data["outline_width"] = max(0, int(data.get("outline_width") or 0))
    data["shadow_offset_x"] = int(data.get("shadow_offset_x") or 0)
    data["shadow_offset_y"] = int(data.get("shadow_offset_y") or 0)
    for flag in (
        "use_font_file_default_style_only",
        "artificial_bold",
        "artificial_italic",
        "underline",
        "shadow_enabled",
        "outline_enabled",
    ):
        data[flag] = bool(data.get(flag))
    return FontConfig(**data)


def _normalize_font_path_str(value: str, *, role: str) -> str:
    text = value.strip().replace("\\", "/")
    if not text:
        return default_font_config_for_role(role).font_path
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
        except ValueError:
            return str(path)
    if text.startswith("fonts/"):
        return text
    if "/" not in text and text.lower().endswith((".ttf", ".otf")):
        return f"fonts/{text}"
    return text
