from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Final, Mapping

from art import ThroneArt, build_art_data_url

ROOT: Final[Path] = Path(__file__).parent
CSS_LIMIT: Final[int] = 50_000
EXPECTED_COLOR_ROLES: Final[int] = 61

DOOMSDAY_COLORS: Final[Mapping[str, str]] = {
    "canvas": "#0b0e0d",
    "chrome": "#070909",
    "toolbar": "#0b0e0d",
    "toolbarForeground": "#e1e7e4",
    "toolbarBorder": "#1d2623",
    "toolbarControl": "#141918",
    "toolbarControlForeground": "#e1e7e4",
    "toolbarControlHover": "#1b2421",
    "surface": "#111615",
    "surfaceRaised": "#141918",
    "surfaceOverlay": "#171e1c",
    "text": "#e1e7e4",
    "textMuted": "#8d9c96",
    "border": "#222c29",
    "input": "#283430",
    "focus": "#10b981",
    "accent": "#10b981",
    "accentForeground": "#03120c",
    "secondary": "#141918",
    "secondaryForeground": "#e1e7e4",
    "muted": "#101514",
    "mutedForeground": "#8d9c96",
    "placeholder": "#84938d",
    "secondaryLabel": "#8d9c96",
    "iconMuted": "#8d9c96",
    "error": "#e05252",
    "errorForeground": "#f87171",
    "errorSurface": "#291011",
    "warning": "#d4af37",
    "warningForeground": "#f0cb54",
    "warningSurface": "#231b08",
    "update": "#10b981",
    "updateForeground": "#5eead4",
    "updateSurface": "#0f2920",
    "accentSurface": "#172e25",
    "accentSurfaceForeground": "#f0f5f3",
    "messageSurface": "#14261f",
    "messageForeground": "#e1e7e4",
    "messageAction": "#d4af37",
    "messageActionForeground": "#070909",
    "messageActionHover": "#e4c24d",
    "codeBackground": "#080b0a",
    "codeForeground": "#e1e7e4",
    "searchMatchBackground": "#6b541c",
    "searchMatchForeground": "#f4f7f5",
    "searchMatchActiveBackground": "#d4af37",
    "searchMatchActiveForeground": "#070909",
    "sidebar": "#070909",
    "sidebarForeground": "#e1e7e4",
    "sidebarMutedForeground": "#94a49e",
    "sidebarControlSurface": "#101514",
    "sidebarRowHover": "#121a17",
    "sidebarRowActive": "#162620",
    "sidebarRowSelected": "#172e25",
    "sidebarBorder": "#1d2623",
    "terminalBackground": "#060908",
    "terminalForeground": "#e1e7e4",
    "terminalCursor": "#10b981",
    "terminalSelection": "#172e25",
    "terminalScrollbar": "#62736d",
    "terminalScrollbarHover": "#10b981",
}

SHORT_VARIABLES: Final[Mapping[str, str]] = {
    "--dm-jewel-gold-hover": "--jh",
    "--dm-jewel-crimson": "--jc",
    "--dm-jewel-gold": "--jg",
    "--dm-rim-crimson": "--rc",
    "--dm-rim-soft": "--rs",
    "--dm-rim": "--r",
}

RESERVED_THEME_VARIABLES: Final[frozenset[str]] = frozenset({
    "--g",
    "--w",
    "--d",
    "--gx",
    "--gp",
    "--hl",
    "--s",
    "--gl",
    "--gm",
    "--a",
    "--f",
    "--e",
    "--m",
    "--pe",
    "--pi",
    "--n",
    "--c",
    "--k",
})

PROTECTED_APP_VARIABLES: Final[frozenset[str]] = frozenset({
    "--glass-opacity",
    "--glass-blur",
    "--glass-saturation",
    "--sidebar-width",
    "--sidebar-content-inset",
    "--sidebar-row-content-inset",
    "--sidebar-muted-foreground",
    "--sidebar-row-hover",
    "--sidebar-row-active",
    "--sidebar-row-selected",
    "--font-sans",
    "--ring",
    "--primary",
    "--primary-foreground",
    "--accent",
    "--accent-foreground",
    "--foreground",
    "--muted-foreground",
    "--radius",
    "--control-radius",
    "--contrast-secondary-label",
    "--contrast-icon-muted",
    "--chat-composer-glass-surface",
    "--chat-composer-outline",
    "--chat-composer-attached-surface",
    "--chat-composer-attached-outline",
    "--chat-composer-attached-tint",
    "--app-scrollbar-thumb",
    "--app-scrollbar-thumb-hover",
})


@dataclass(frozen=True)
class ThemeVariant:
    id: str
    name: str
    sources: tuple[str, ...]
    art: ThroneArt
    plus_pressed: str


@dataclass(frozen=True)
class BuiltTheme:
    id: str
    name: str
    colors: Mapping[str, str]
    css: str

    def to_payload(self) -> dict:
        return {
            "version": 1,
            "name": self.name,
            "appearance": "dark",
            "colors": dict(self.colors),
            "css": self.css,
        }


VARIANTS: Final[tuple[ThemeVariant, ...]] = (
    ThemeVariant(
        id="avengers-doomsday",
        name="Avengers: Doomsday",
        sources=("theme.css",),
        art=ThroneArt(Path("assets/throne.png")),
        plus_pressed="",
    ),
    ThemeVariant(
        id="avengers-doomsday-plus",
        name="Avengers: Doomsday Plus",
        sources=("theme.css", "plus.css"),
        art=ThroneArt(Path("assets/throne.png")),
        plus_pressed=",.dark [data-model-picker-sidebar] [aria-pressed=true]",
    ),
)

HEX_PATTERN = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)


def validate_build_invariants(
    colors: Mapping[str, str], short_vars: Mapping[str, str]
) -> None:
    if len(colors) != EXPECTED_COLOR_ROLES:
        raise ValueError(
            f"Expected {EXPECTED_COLOR_ROLES} color roles, got {len(colors)}"
        )

    for role, color_val in colors.items():
        if not HEX_PATTERN.match(color_val):
            raise ValueError(f"Invalid hex color '{color_val}' for role '{role}'")

    if len(short_vars) != len(set(short_vars.values())):
        raise ValueError("Duplicate target aliases in SHORT_VARIABLES")

    for long_var, short_var in short_vars.items():
        if short_var in RESERVED_THEME_VARIABLES:
            raise ValueError(
                f"Short variable '{short_var}' collides with reserved theme variables"
            )
        if short_var in PROTECTED_APP_VARIABLES:
            raise ValueError(
                f"Short variable '{short_var}' collides with protected app variables"
            )
        if long_var in PROTECTED_APP_VARIABLES:
            raise ValueError(
                f"Long variable '{long_var}' collides with protected app variables"
            )


def minify_css(css: str, short_vars: Mapping[str, str]) -> str:
    strings: list[str] = []

    def stash(match: re.Match[str]) -> str:
        strings.append(match.group(0))
        return f"\x00{len(strings) - 1}\x00"

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r'="([A-Za-z_][\w-]*)"\]', r"=\1]", css)
    css = re.sub(r'"[^"]*"|\'[^\']*\'|url\([^)]*\)', stash, css)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    css = re.sub(r":\s+", ":", css)
    css = re.sub(r"\s*!important", "!important", css)
    css = re.sub(r" ([*/]) ", r"\1", css)
    css = css.replace(";}", "}")
    css = re.sub(r"\btransparent\b", "#0000", css)
    css = re.sub(
        r"#([0-9a-fA-F])\1([0-9a-fA-F])\2([0-9a-fA-F])\3(([0-9a-fA-F])\5)?\b",
        lambda m: "#" + m.group(1) + m.group(2) + m.group(3) + (m.group(5) or ""),
        css,
    )
    css = re.sub(r"\s*([<>])\s*", r"\1", css)
    css = re.sub(r"(?<![\w.])0\.(\d)", r".\1", css)
    for long_name in sorted(short_vars, key=len, reverse=True):
        css = css.replace(long_name, short_vars[long_name])
    css = re.sub(r"(?<=[{};,])&(?: |(?=>))", "", css)
    css = re.sub(r"\x00(\d+)\x00", lambda m: strings[int(m.group(1))], css)
    return css.strip()


def build_theme(
    variant: ThemeVariant, root: Path, colors: Mapping[str, str]
) -> BuiltTheme:
    validate_build_invariants(colors, SHORT_VARIABLES)
    raw_css = "\n".join(
        (root / source).read_text(encoding="utf-8") for source in variant.sources
    )
    art = (
        variant.art
        if variant.art.asset_path.is_absolute()
        else ThroneArt(
            root / variant.art.asset_path,
            variant.art.width,
            variant.art.height,
            variant.art.palette_hex,
        )
    )
    minified = minify_css(raw_css, SHORT_VARIABLES)
    final_css = (
        minified.replace("__PLUS_PRESSED__", variant.plus_pressed)
        .replace("__ART_WIDTH__", str(art.width))
        .replace("__ART__", build_art_data_url(art))
    )

    if len(final_css) > CSS_LIMIT:
        raise ValueError(
            f"{variant.id} css length {len(final_css)} exceeds limit {CSS_LIMIT}"
        )

    return BuiltTheme(
        id=variant.id,
        name=variant.name,
        colors=colors,
        css=final_css,
    )


if __name__ == "__main__":
    for theme_variant in VARIANTS:
        built = build_theme(theme_variant, ROOT, DOOMSDAY_COLORS)
        out_file = ROOT / f"{theme_variant.id}.json"
        out_file.write_text(
            json.dumps(built.to_payload(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"{out_file.name}: {len(built.css)} css characters")
