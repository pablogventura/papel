"""Lee los simbolos de una hoja ya localizada y reconstruye la trama."""

from __future__ import annotations

import numpy as np

from papel.codec import (
    PagePayload,
    gather_symbols,
    recover,
    symbols_to_bytes,
    unpack_header,
)
from papel.constants import BITS_PER_MODULE, RS_BLOCK
from papel.errors import DecodeError
from papel.grid import data_coordinates
from papel.locate import reference_levels, sample_modules


def read_page(rgb: np.ndarray, pose) -> PagePayload:
    rows, cols = pose.rows, pose.cols
    samples = sample_modules(rgb, pose, radius=0)
    black, white = reference_levels(samples)
    data_rows, data_cols = data_coordinates(rows, cols)
    observed = samples[data_rows, data_cols]
    last_error: Exception | None = None
    for mode in ("bw", "cmy"):
        try:
            return _read_mode(observed, mode, black, white)
        except DecodeError as exc:
            last_error = exc
    raise DecodeError("page is not readable") from last_error


def _read_mode(
    observed: np.ndarray,
    mode: str,
    black: np.ndarray,
    white: np.ndarray,
) -> PagePayload:
    symbols = _classify(observed, mode, black, white)
    bits = BITS_PER_MODULE[mode]
    symbol_bytes = (symbols.size * bits) // 8
    blocks = symbol_bytes // RS_BLOCK
    if blocks < 1:
        raise DecodeError("page is too small")
    used = blocks * RS_BLOCK * 8 // bits
    payload = symbols_to_bytes(gather_symbols(symbols[:used], bits), bits, blocks * RS_BLOCK)
    frame = recover(payload)
    page = unpack_header(frame)
    if page.mode != mode:
        raise DecodeError("mode does not match the header")
    return page


def _classify(
    observed: np.ndarray,
    mode: str,
    black: np.ndarray,
    white: np.ndarray,
) -> np.ndarray:
    scale = np.maximum(white - black, 1.0)
    normal = np.clip((observed - black) / scale, 0.0, 1.0)
    if mode == "bw":
        luma = normal @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        return (luma < 0.5).astype(np.uint8)
    if mode == "cmy":
        # Tinta presente cuando el canal complementario esta por debajo del medio.
        cyan = normal[:, 0] < 0.5
        magenta = normal[:, 1] < 0.5
        yellow = normal[:, 2] < 0.5
        return (cyan.astype(np.uint8) | (magenta.astype(np.uint8) << 1) | (yellow.astype(np.uint8) << 2))
    raise DecodeError(mode)

