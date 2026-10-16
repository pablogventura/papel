"""Pinta la grilla en RGB."""

from __future__ import annotations

import numpy as np

from papel.grid import data_coordinates, geometry_black, reserved_mask


def symbols_image(rows: int, cols: int, mode: str, values: np.ndarray) -> np.ndarray:
    """Grilla de simbolos. La geometria queda en un canal aparte."""
    symbols = np.zeros((rows, cols), dtype=np.uint8)
    data_rows, data_cols = data_coordinates(rows, cols)
    if values.size > data_rows.size:
        raise ValueError("too many symbols for the grid")
    symbols[data_rows[: values.size], data_cols[: values.size]] = values
    return symbols


def render_modules(symbols: np.ndarray, mode: str, pixels_per_module: int) -> np.ndarray:
    """Imagen RGB nitida, un modulo ocupa `pixels_per_module` pixeles."""
    small = _colorize(symbols, mode)
    if pixels_per_module == 1:
        image = small
    else:
        image = np.repeat(np.repeat(small, pixels_per_module, axis=0), pixels_per_module, axis=1)
    return np.ascontiguousarray(image)


def _colorize(symbols: np.ndarray, mode: str) -> np.ndarray:
    rows, cols = symbols.shape
    rgb = np.full((rows, cols, 3), 255, dtype=np.uint8)
    if mode == "bw":
        rgb[symbols > 0] = (0, 0, 0)
    elif mode == "cmy":
        # bit 0 cian (apaga R), bit 1 magenta (apaga G), bit 2 amarillo (apaga B).
        rgb[:, :, 0] = np.where(symbols & 1, 0, 255)
        rgb[:, :, 1] = np.where(symbols & 2, 0, 255)
        rgb[:, :, 2] = np.where(symbols & 4, 0, 255)
    else:
        raise ValueError(mode)
    black = geometry_black(rows, cols)
    rgb[black] = (0, 0, 0)
    reserved = reserved_mask(rows, cols)
    rgb[reserved & ~black] = (255, 255, 255)
    return rgb
