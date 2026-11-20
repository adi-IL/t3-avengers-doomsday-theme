from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Final

import numpy as np
from PIL import Image

ART_WIDTH: Final[int] = 480
ART_HEIGHT: Final[int] = 270

LATVERIA_PALETTE_HEX: Final[tuple[str, ...]] = (
    "#000000",
    "#060908",
    "#082219",
    "#0b0e0d",
    "#0e3b2b",
    "#10b981",
    "#131917",
    "#202925",
    "#34d399",
    "#35403b",
    "#505d57",
    "#6b541b",
    "#c9a227",
)

BAYER_8: Final[np.ndarray] = (
    np.array(
        [
            [0, 32, 8, 40, 2, 34, 10, 42],
            [48, 16, 56, 24, 50, 18, 58, 26],
            [12, 44, 4, 36, 14, 46, 6, 38],
            [60, 28, 52, 20, 62, 30, 54, 22],
            [3, 35, 11, 43, 1, 33, 9, 41],
            [51, 19, 59, 27, 49, 17, 57, 25],
            [15, 47, 7, 39, 13, 45, 5, 37],
            [63, 31, 55, 23, 61, 29, 53, 21],
        ],
        dtype=float,
    )
    / 64.0
    - 0.5
)


@dataclass(frozen=True)
class ThroneArt:
    asset_path: Path
    width: int = ART_WIDTH
    height: int = ART_HEIGHT
    palette_hex: tuple[str, ...] = LATVERIA_PALETTE_HEX


def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    normalized = hex_code.lstrip("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def quantize_bayer(source_image: Path, art: ThroneArt) -> np.ndarray:
    image = Image.open(source_image).convert("RGB")
    resized = image.resize((art.width, art.height), resample=Image.Resampling.LANCZOS)
    img_array = np.asarray(resized, dtype=float)
    palette_rgb = np.array([hex_to_rgb(h) for h in art.palette_hex], dtype=float)

    tile_y = art.height // 8 + 1
    tile_x = art.width // 8 + 1
    threshold = np.tile(BAYER_8, (tile_y, tile_x))[: art.height, : art.width]

    jittered = np.clip(img_array + threshold[..., None] * 32.0, 0.0, 255.0)
    diffs = jittered[:, :, None, :] - palette_rgb[None, None, :, :]
    return (diffs**2).sum(axis=-1).argmin(axis=-1).astype(np.uint8)


def encode_webp(art: ThroneArt) -> bytes:
    image = Image.open(art.asset_path).convert("RGB")
    if image.size != (art.width, art.height):
        raise ValueError(
            f"Asset dimensions {image.size} do not match expected {(art.width, art.height)}"
        )

    allowed_colors = {hex_to_rgb(hex_code) for hex_code in art.palette_hex}
    unique_pixels = {
        tuple(int(v) for v in rgb)
        for rgb in np.unique(np.asarray(image).reshape(-1, 3), axis=0)
    }
    bad_colors = unique_pixels - allowed_colors
    if bad_colors:
        r, g, b = next(iter(sorted(bad_colors)))
        raise ValueError(
            f"Pixel color #{r:02x}{g:02x}{b:02x} not in allowed palette {art.palette_hex}"
        )

    buffer = io.BytesIO()
    image.save(buffer, "WEBP", lossless=True, quality=100, method=6, exact=True)
    return buffer.getvalue()


def build_art_data_url(art: ThroneArt) -> str:
    return "data:image/webp;base64," + base64.b64encode(encode_webp(art)).decode("ascii")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python art.py <source_image> <output_png>")
        sys.exit(1)

    src_file = Path(sys.argv[1])
    dst_file = Path(sys.argv[2])
    target_art = ThroneArt(dst_file)

    indices = quantize_bayer(src_file, target_art)
    indexed_image = Image.fromarray(indices, mode="P")

    palette_bytes = bytearray()
    for hex_entry in target_art.palette_hex:
        palette_bytes.extend(hex_to_rgb(hex_entry))
    palette_bytes.extend([0] * (768 - len(palette_bytes)))

    indexed_image.putpalette(palette_bytes)
    indexed_image.save(dst_file, format="PNG", optimize=True)
    print(
        f"Quantized {src_file} -> {dst_file} ({target_art.width}x{target_art.height}, {len(target_art.palette_hex)} colors)"
    )
