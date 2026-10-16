"""Codifica un archivo en un PDF de una o varias hojas y lo recupera."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

from papel.codec import (
    PagePayload,
    file_crc,
    pack_header,
    page_payload_capacity,
    store_bytes,
)
from papel.constants import (
    COLOR_MODE,
    DEFAULT_MODULE_MM,
    FLAG_ZLIB,
    LASER_MODE,
    SCAN_DPI,
)
from papel.decode_page import read_page
from papel.errors import DecodeError, IncompleteBackup
from papel.locate import as_rgb, locate_grid
from papel.render import page_pdf, rasterize_pdf


def encode_pdf(
    data: bytes,
    name: str,
    mode: str = LASER_MODE,
    module_mm: float = DEFAULT_MODULE_MM,
) -> bytes:
    stored, flags = store_bytes(data)
    capacity = page_payload_capacity(module_mm, mode)
    chunks = _split(stored, capacity)
    identity = file_crc(name.encode("utf-8") + data)
    checksum = file_crc(data)
    document = pymupdf.open()
    total = len(chunks)
    offset = 0
    for index, chunk in enumerate(chunks):
        payload = PagePayload(
            file_id=identity,
            page_index=index,
            page_count=total,
            chunk_offset=offset,
            chunk=chunk,
            file_crc=checksum,
            original_size=len(data),
            stored_size=len(stored),
            flags=flags,
            name=name,
            mode=mode,
        )
        caption = f"{name} [{len(data)} bytes] - página {index + 1} de {total}"
        if mode == "cmy":
            footer = "Escanear en color, 300 dpi"
        else:
            footer = "Escanear en escala de grises, 300 dpi"
        blob = page_pdf(pack_header(payload) + chunk, module_mm, mode, caption, footer)
        source = pymupdf.open(stream=blob, filetype="pdf")
        document.insert_pdf(source)
        source.close()
        offset += len(chunk)
    encoded = document.tobytes()
    document.close()
    return encoded


def decode_images(images: list[np.ndarray]) -> bytes:
    if not images:
        raise DecodeError("no scans")
    pages = [decode_page_image(image) for image in images]
    return assemble(pages)


def decode_page_image(image: np.ndarray) -> PagePayload:
    rgb = as_rgb(np.asarray(image))
    pose = locate_grid(rgb)
    return read_page(rgb, pose)


def decode_paths(paths: list[str | Path]) -> bytes:
    images: list[np.ndarray] = []
    for path in paths:
        images.extend(load_scans(Path(path)))
    return decode_images(images)


def load_scans(path: Path) -> list[np.ndarray]:
    if path.suffix.lower() == ".pdf":
        return rasterize_pdf(path.read_bytes(), SCAN_DPI)
    with Image.open(path) as handle:
        rgb = handle.convert("RGB")
        return [np.asarray(rgb).copy()]


def assemble(pages: list[PagePayload]) -> bytes:
    if not pages:
        raise DecodeError("no pages")
    file_id = pages[0].file_id
    if any(page.file_id != file_id for page in pages):
        raise DecodeError("scans belong to different files")
    page_count = pages[0].page_count
    if any(page.page_count != page_count for page in pages):
        raise DecodeError("scans disagree on the page count")
    by_index: dict[int, PagePayload] = {}
    for page in pages:
        previous = by_index.get(page.page_index)
        if previous is not None and previous.chunk != page.chunk:
            raise DecodeError("two scans of the same page disagree")
        by_index[page.page_index] = page
    missing = [index for index in range(page_count) if index not in by_index]
    if missing:
        raise IncompleteBackup(missing)
    ordered = [by_index[index] for index in range(page_count)]
    offset = 0
    parts: list[bytes] = []
    for page in ordered:
        if page.chunk_offset != offset:
            raise DecodeError("gap between page chunks")
        parts.append(page.chunk)
        offset += len(page.chunk)
    stored = b"".join(parts)
    if len(stored) != ordered[0].stored_size:
        raise DecodeError("stored size does not match")
    if ordered[0].flags & FLAG_ZLIB:
        import zlib

        raw = zlib.decompress(stored)
    else:
        raw = stored
    if file_crc(raw) != ordered[0].file_crc or len(raw) != ordered[0].original_size:
        raise DecodeError("file crc does not match")
    return raw


def available_modes() -> tuple[str, ...]:
    modes = [LASER_MODE]
    if COLOR_MODE and COLOR_MODE not in modes:
        modes.append(COLOR_MODE)
    return tuple(modes)


def _split(stored: bytes, capacity: int) -> list[bytes]:
    if capacity < 1:
        raise DecodeError("page capacity is empty")
    if not stored:
        return [b""]
    return [stored[index : index + capacity] for index in range(0, len(stored), capacity)]
