from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
FONTS_DIR = PROJECT_ROOT / "fonts"
SAFE_EXTENSIONS = {".ttf", ".otf"}  # .ttc excluded — Pillow support is unreliable

BARLOW_BOLD_NAME = "BarlowCondensed-Bold.ttf"
BARLOW_BOLD_ITALIC_NAME = "BarlowCondensed-BoldItalic.ttf"


@dataclass(frozen=True)
class FontChoice:
    """A selectable font with a stable id and display label."""

    font_id: str
    label: str
    path: Path
    source: str  # "project" | "system"


def discover_fonts(
    project_fonts_dir: Path | None = None,
    include_system: bool = True,
) -> list[FontChoice]:
    """Discover project and system fonts without crashing on missing folders."""
    fonts_dir = project_fonts_dir or FONTS_DIR
    found: list[FontChoice] = []
    seen_paths: set[Path] = set()

    if fonts_dir.exists():
        for path in sorted(fonts_dir.iterdir()):
            choice = _choice_from_path(path, source="project", project_root=PROJECT_ROOT)
            if choice is None or choice.path in seen_paths:
                continue
            seen_paths.add(choice.path)
            found.append(choice)

    if include_system:
        for folder in system_font_dirs():
            if not folder.exists() or not folder.is_dir():
                continue
            try:
                entries = sorted(folder.iterdir())
            except OSError:
                continue
            for path in entries:
                choice = _choice_from_path(path, source="system", project_root=PROJECT_ROOT)
                if choice is None or choice.path in seen_paths:
                    continue
                seen_paths.add(choice.path)
                found.append(choice)

    return _dedupe_labels(found)


def system_font_dirs() -> list[Path]:
    dirs: list[Path] = []
    home = Path.home()
    # macOS
    dirs.extend(
        [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ]
    )
    # Windows
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windir:
        dirs.append(Path(windir) / "Fonts")
    # Linux
    dirs.extend(
        [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            home / ".local" / "share" / "fonts",
            home / ".fonts",
        ]
    )
    return dirs


def default_font_id_for_role(role: str) -> str:
    name = BARLOW_BOLD_ITALIC_NAME if role == "title" else BARLOW_BOLD_NAME
    project_path = FONTS_DIR / name
    if project_path.exists():
        return stable_font_id(project_path, PROJECT_ROOT)
    return name


def resolve_selected_font(
    font_id: str | None,
    *,
    role: str,
    catalog: list[FontChoice] | None = None,
) -> Path | None:
    """Resolve a selected font id to an existing path, with safe defaults."""
    choices = catalog if catalog is not None else discover_fonts()
    by_id = {choice.font_id: choice for choice in choices}

    if font_id and font_id in by_id and by_id[font_id].path.exists():
        return by_id[font_id].path

    # Direct path / filename fallbacks.
    if font_id:
        candidate = Path(font_id)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        if candidate.exists() and candidate.suffix.lower() in SAFE_EXTENSIONS:
            return candidate
        by_name = {choice.path.name: choice for choice in choices}
        if Path(font_id).name in by_name:
            return by_name[Path(font_id).name].path

    # Role defaults.
    default_name = BARLOW_BOLD_ITALIC_NAME if role == "title" else BARLOW_BOLD_NAME
    fallback_names = (
        (default_name, BARLOW_BOLD_NAME, BARLOW_BOLD_ITALIC_NAME)
        if role == "title"
        else (default_name, BARLOW_BOLD_ITALIC_NAME)
    )
    by_name = {choice.path.name: choice for choice in choices}
    for name in fallback_names:
        if name in by_name and by_name[name].path.exists():
            return by_name[name].path
        project_path = FONTS_DIR / name
        if project_path.exists():
            return project_path
    return choices[0].path if choices else None


def stable_font_id(path: Path, project_root: Path | None = None) -> str:
    root = project_root or PROJECT_ROOT
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
        return str(relative).replace("\\", "/")
    except ValueError:
        return str(resolved)


def _choice_from_path(
    path: Path,
    *,
    source: str,
    project_root: Path,
) -> FontChoice | None:
    if not path.is_file():
        return None
    if path.suffix.lower() not in SAFE_EXTENSIONS:
        return None
    font_id = stable_font_id(path, project_root)
    label = path.name
    if source == "system":
        label = f"{path.name} ({path.parent.name})"
    return FontChoice(font_id=font_id, label=label, path=path.resolve(), source=source)


def _dedupe_labels(choices: list[FontChoice]) -> list[FontChoice]:
    counts: dict[str, int] = {}
    for choice in choices:
        counts[choice.label] = counts.get(choice.label, 0) + 1
    if all(count == 1 for count in counts.values()):
        return choices

    result: list[FontChoice] = []
    for choice in choices:
        if counts[choice.label] == 1:
            result.append(choice)
            continue
        # Disambiguate duplicates with parent folder.
        label = f"{choice.path.name} · {choice.path.parent.name}"
        result.append(
            FontChoice(
                font_id=choice.font_id,
                label=label,
                path=choice.path,
                source=choice.source,
            )
        )
    return result
