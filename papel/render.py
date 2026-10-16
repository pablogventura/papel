"""Arma el PDF A4 listo para imprimir."""

from __future__ import annotations

import io

import numpy as np
import pymupdf
from PIL import Image

from papel.codec import bytes_to_symbols, protect, scatter_symbols
from papel.constants import (
    BITS_PER_MODULE,
    GRID_ORIGIN_X_MM,
    GRID_ORIGIN_Y_MM,
    PAGE_HEIGHT_MM,
    PAGE_WIDTH_MM,
    RS_BLOCK,
)
from papel.grid import data_coordinates, grid_shape
from papel.paint import render_modules, symbols_image


def mm_to_pt(millimetres: float) -> float:
    return millimetres * 72.0 / 25.4


def embed_pixels_per_module(module_mm: float) -> int:
    """Pixeles del bitmap embebido, cerca de la resolucion del escaneo."""
    return max(3, int(round(module_mm / 25.4 * 300)))


def paint_frame(frame: bytes, module_mm: float, mode: str) -> np.ndarray:
    rows, cols = grid_shape(module_mm)
    modules = int(data_coordinates(rows, cols)[0].size)
    bits = BITS_PER_MODULE[mode]
    symbol_bytes = (modules * bits) // 8
    blocks = symbol_bytes // RS_BLOCK
    capacity = blocks * (RS_BLOCK - 32)
    protected = protect(frame, capacity)
    values = scatter_symbols(bytes_to_symbols(protected, bits), bits)
    symbols = symbols_image(rows, cols, mode, values)
    return render_modules(symbols, mode, embed_pixels_per_module(module_mm))


def page_pdf(
    frame: bytes,
    module_mm: float,
    mode: str,
    caption: str,
    footer: str,
) -> bytes:
    rows, cols = grid_shape(module_mm)
    image = paint_frame(frame, module_mm, mode)
    buffer = io.BytesIO()
    Image.fromarray(image, "RGB").save(buffer, format="PNG")
    document = pymupdf.open()
    page = document.new_page(width=mm_to_pt(PAGE_WIDTH_MM), height=mm_to_pt(PAGE_HEIGHT_MM))
    rect = pymupdf.Rect(
        mm_to_pt(GRID_ORIGIN_X_MM),
        mm_to_pt(GRID_ORIGIN_Y_MM),
        mm_to_pt(GRID_ORIGIN_X_MM + cols * module_mm),
        mm_to_pt(GRID_ORIGIN_Y_MM + rows * module_mm),
    )
    page.insert_image(rect, stream=buffer.getvalue())
    page.insert_text(
        (mm_to_pt(GRID_ORIGIN_X_MM), mm_to_pt(11)),
        caption,
        fontsize=10,
        fontname="helv",
    )
    page.insert_text(
        (mm_to_pt(GRID_ORIGIN_X_MM), mm_to_pt(PAGE_HEIGHT_MM - 8)),
        footer,
        fontsize=9,
        fontname="helv",
    )
    payload = document.tobytes()
    document.close()
    return payload


def rasterize_pdf(pdf: bytes, dpi: int) -> list[np.ndarray]:
    document = pymupdf.open(stream=pdf, filetype="pdf")
    images: list[np.ndarray] = []
    for page in document:
        pixmap = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        images.append(image.copy())
    document.close()
    return images
