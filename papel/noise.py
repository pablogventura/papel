"""Ruido de impresora y escaner sobre el raster de la hoja."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from papel.constants import SCAN_DPI


@dataclass(frozen=True)
class NoiseProfile:
    name: str
    blur_px: float = 0.0
    noise_sigma: float = 0.0
    brightness: int = 0
    rotation_deg: float = 0.0
    shift_px: tuple[int, int] = (0, 0)
    stain_fraction: float = 0.0
    misregister_mm: float = 0.0
    crosstalk: float = 0.0
    seed: int = 0


CLEAN = NoiseProfile("clean")
MILD = NoiseProfile(
    "mild",
    blur_px=0.8,
    noise_sigma=4.0,
    brightness=8,
    rotation_deg=1.0,
    shift_px=(6, -4),
    stain_fraction=0.0,
    seed=1,
)
HARSH = NoiseProfile(
    "harsh",
    blur_px=1.2,
    noise_sigma=6.0,
    brightness=12,
    rotation_deg=3.0,
    shift_px=(14, -9),
    stain_fraction=0.012,
    misregister_mm=0.1,
    crosstalk=0.12,
    seed=2,
)
# A proposito por encima de lo que el Reed-Solomon puede reconstruir.
FATAL = NoiseProfile(
    "fatal",
    blur_px=1.0,
    noise_sigma=8.0,
    rotation_deg=2.0,
    stain_fraction=0.55,
    seed=3,
)


def apply_noise(image: np.ndarray, profile: NoiseProfile, dpi: int = SCAN_DPI) -> np.ndarray:
    working = image
    if profile.misregister_mm or profile.crosstalk:
        shift = profile.misregister_mm / 25.4 * dpi
        working = _shift_plates(working, shift, profile.crosstalk)
    pil = Image.fromarray(working, "RGB")
    if profile.blur_px > 0:
        pil = pil.filter(ImageFilter.GaussianBlur(radius=profile.blur_px))
    if profile.rotation_deg:
        pil = pil.rotate(
            profile.rotation_deg,
            expand=True,
            fillcolor=(255, 255, 255),
            resample=Image.Resampling.BICUBIC,
        )
    array = np.asarray(pil).astype(np.int16)
    if profile.noise_sigma or profile.brightness:
        generator = np.random.default_rng(profile.seed)
        if profile.noise_sigma:
            array = array + generator.normal(0.0, profile.noise_sigma, array.shape)
        array = array + profile.brightness
        array = np.clip(array, 0, 255)
    array = array.astype(np.uint8)
    if profile.shift_px != (0, 0):
        array = _translate(array, profile.shift_px[0], profile.shift_px[1])
    if profile.stain_fraction > 0:
        array = _stain(array, profile.stain_fraction, profile.seed)
    return array


def _shift_plates(image: np.ndarray, shift_px: float, crosstalk: float) -> np.ndarray:
    """Separa C, M, Y, los desplaza y los vuelve a mezclar.

    Un desregistro de este orden es lo que desalinea las tintas de una inkjet.
    """
    pixels = int(round(shift_px))
    red = image[:, :, 0].astype(np.float32) / 255.0
    green = image[:, :, 1].astype(np.float32) / 255.0
    blue = image[:, :, 2].astype(np.float32) / 255.0
    cyan = _shift_channel(1.0 - red, pixels, 0)
    magenta = _shift_channel(1.0 - green, 0, pixels)
    yellow = _shift_channel(1.0 - blue, -pixels, pixels // 2)
    if crosstalk:
        mixed_c = np.clip(cyan + crosstalk * magenta, 0.0, 1.0)
        mixed_m = np.clip(magenta + crosstalk * yellow, 0.0, 1.0)
        mixed_y = np.clip(yellow + crosstalk * cyan, 0.0, 1.0)
        cyan, magenta, yellow = mixed_c, mixed_m, mixed_y
    out = np.empty_like(image)
    out[:, :, 0] = np.clip((1.0 - cyan) * 255.0, 0, 255).astype(np.uint8)
    out[:, :, 1] = np.clip((1.0 - magenta) * 255.0, 0, 255).astype(np.uint8)
    out[:, :, 2] = np.clip((1.0 - yellow) * 255.0, 0, 255).astype(np.uint8)
    return out


def _shift_channel(channel: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(channel)
    height, width = channel.shape
    if abs(dx) >= width or abs(dy) >= height:
        return out
    src_x0 = max(0, -dx)
    src_y0 = max(0, -dy)
    dst_x0 = max(0, dx)
    dst_y0 = max(0, dy)
    copy_w = width - abs(dx)
    copy_h = height - abs(dy)
    out[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = channel[
        src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w
    ]
    return out


def _translate(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.full_like(image, 255)
    height, width = image.shape[:2]
    src_x0 = max(0, -dx)
    src_y0 = max(0, -dy)
    dst_x0 = max(0, dx)
    dst_y0 = max(0, dy)
    copy_w = width - abs(dx)
    copy_h = height - abs(dy)
    out[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = image[
        src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w
    ]
    return out


def _stain(image: np.ndarray, fraction: float, seed: int) -> np.ndarray:
    """Mancha gris en el centro de la hoja, lejos de las cuatro esquinas."""
    height, width = image.shape[:2]
    radius_y = max(4, int(height * (fraction ** 0.5) * 0.55))
    radius_x = max(4, int(width * (fraction ** 0.5) * 0.55))
    canvas = Image.fromarray(image, "RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    generator = np.random.default_rng(seed)
    center_x = int(width * 0.48 + generator.integers(-width // 20, width // 20))
    center_y = int(height * 0.46 + generator.integers(-height // 20, height // 20))
    draw.ellipse(
        (
            center_x - radius_x,
            center_y - radius_y,
            center_x + radius_x,
            center_y + radius_y,
        ),
        fill=(170, 170, 170, 210),
    )
    return np.asarray(canvas.convert("RGB"))
