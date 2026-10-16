"""Trama de una pagina: cabecera, zlib, CRC-32 y Reed-Solomon intercalado."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

import numpy as np
from reedsolo import RSCodec, ReedSolomonError

from papel.constants import (
    BITS_PER_MODULE,
    FLAG_ZLIB,
    HEADER_SIZE,
    MAGIC,
    MODE_BY_NAME,
    NAME_BY_MODE,
    RS_BLOCK,
    RS_DATA,
    RS_NSYM,
    VERSION,
)
from papel.errors import DecodeError, PapelError
from papel.grid import data_coordinates, grid_shape

_HEADER = struct.Struct("<4sBBIHHIIIIIBx64s")
_CODEC = RSCodec(RS_NSYM)


@dataclass(frozen=True)
class PagePayload:
    file_id: int
    page_index: int
    page_count: int
    chunk_offset: int
    chunk: bytes
    file_crc: int
    original_size: int
    stored_size: int
    flags: int
    name: str
    mode: str


def fit_name(name: str) -> bytes:
    raw = name.encode("utf-8")
    while len(raw) > 64:
        raw = raw[:-1]
        while raw and (raw[-1] & 0xC0) == 0x80:
            raw = raw[:-1]
    return raw.ljust(64, b"\x00")


def store_bytes(data: bytes) -> tuple[bytes, int]:
    compressed = zlib.compress(data, 9)
    if len(compressed) < len(data):
        return compressed, FLAG_ZLIB
    return data, 0


def frame_capacity(data_modules: int, mode: str) -> int:
    """Bytes de trama (con cabecera) que entran en la grilla."""
    bits = BITS_PER_MODULE[mode]
    symbol_bytes = (data_modules * bits) // 8
    blocks = symbol_bytes // RS_BLOCK
    return blocks * RS_DATA


def page_payload_capacity(module_mm: float, mode: str) -> int:
    rows, cols = grid_shape(module_mm)
    modules = int(data_coordinates(rows, cols)[0].size)
    capacity = frame_capacity(modules, mode) - HEADER_SIZE
    if capacity < 1:
        raise PapelError("page has no room for a payload")
    return capacity


def pack_header(page: PagePayload) -> bytes:
    blob = _HEADER.pack(
        MAGIC,
        VERSION,
        MODE_BY_NAME[page.mode],
        page.file_id & 0xFFFFFFFF,
        page.page_index,
        page.page_count,
        page.chunk_offset,
        len(page.chunk),
        page.file_crc & 0xFFFFFFFF,
        page.original_size,
        page.stored_size,
        page.flags,
        fit_name(page.name),
    )
    if len(blob) != HEADER_SIZE:
        raise PapelError("header size drifted")
    return blob


def unpack_header(frame: bytes) -> PagePayload:
    if len(frame) < HEADER_SIZE or frame[:4] != MAGIC:
        raise DecodeError("missing page magic")
    (
        _magic,
        version,
        mode_id,
        file_id,
        page_index,
        page_count,
        chunk_offset,
        chunk_length,
        file_crc,
        original_size,
        stored_size,
        flags,
        raw_name,
    ) = _HEADER.unpack(frame[:HEADER_SIZE])
    if version != VERSION or mode_id not in NAME_BY_MODE:
        raise DecodeError("unsupported page version")
    if page_count < 1 or page_index >= page_count:
        raise DecodeError("invalid page index")
    end = HEADER_SIZE + chunk_length
    if chunk_length < 0 or end > len(frame):
        raise DecodeError("chunk does not fit in the frame")
    name = raw_name.split(b"\x00", 1)[0].decode("utf-8", "replace")
    return PagePayload(
        file_id=file_id,
        page_index=page_index,
        page_count=page_count,
        chunk_offset=chunk_offset,
        chunk=frame[HEADER_SIZE:end],
        file_crc=file_crc,
        original_size=original_size,
        stored_size=stored_size,
        flags=flags,
        name=name,
        mode=NAME_BY_MODE[mode_id],
    )


def protect(frame: bytes, capacity: int) -> bytes:
    """Devuelve los bytes intercalados, listos para pintar."""
    if len(frame) > capacity:
        raise PapelError("frame exceeds page capacity")
    padded = frame + bytes(capacity - len(frame))
    if len(padded) % RS_DATA != 0:
        raise PapelError("frame capacity is not a whole Reed-Solomon block")
    blocks = len(padded) // RS_DATA
    words = [
        bytes(_CODEC.encode(padded[index * RS_DATA : (index + 1) * RS_DATA]))
        for index in range(blocks)
    ]
    interleaved = bytearray(blocks * RS_BLOCK)
    for block_index, word in enumerate(words):
        for symbol_index, symbol in enumerate(word):
            interleaved[symbol_index * blocks + block_index] = symbol
    return bytes(interleaved)


def recover(symbol_bytes: bytes) -> bytes:
    if len(symbol_bytes) < RS_BLOCK:
        raise DecodeError("not enough symbols")
    blocks = len(symbol_bytes) // RS_BLOCK
    trimmed = symbol_bytes[: blocks * RS_BLOCK]
    parts: list[bytes] = []
    for block_index in range(blocks):
        word = bytearray(RS_BLOCK)
        for symbol_index in range(RS_BLOCK):
            word[symbol_index] = trimmed[symbol_index * blocks + block_index]
        try:
            data, _full, _errors = _CODEC.decode(bytes(word))
        except ReedSolomonError as exc:
            raise DecodeError("reed-solomon could not repair the page") from exc
        parts.append(bytes(data))
    return b"".join(parts)


def symbols_per_group(bits: int) -> int:
    """Simbolos que completan bytes enteros. Un grupo viaja junto."""
    count = 1
    while (count * bits) % 8 != 0:
        count += 1
    return count


def _group_placement(count: int) -> np.ndarray:
    """Permutacion fija: una mancha local no cae en los mismos bloques."""
    return np.random.default_rng(0).permutation(count)


def scatter_symbols(symbols: np.ndarray, bits: int) -> np.ndarray:
    group = symbols_per_group(bits)
    if symbols.size % group != 0:
        raise PapelError("symbol stream is not a whole number of bytes")
    groups = symbols.reshape(-1, group)
    placed = np.empty_like(groups)
    placed[_group_placement(groups.shape[0])] = groups
    return placed.reshape(-1)


def gather_symbols(placed: np.ndarray, bits: int) -> np.ndarray:
    group = symbols_per_group(bits)
    groups = placed.reshape(-1, group)
    logical = groups[_group_placement(groups.shape[0])]
    return logical.reshape(-1)


def bytes_to_symbols(payload: bytes, bits: int) -> np.ndarray:
    if bits not in (1, 2, 3):
        raise PapelError("unsupported bits per module")
    symbols = np.zeros((len(payload) * 8) // bits, dtype=np.uint8)
    accumulator = 0
    held = 0
    cursor = 0
    mask = (1 << bits) - 1
    for byte in payload:
        accumulator = (accumulator << 8) | byte
        held += 8
        while held >= bits:
            held -= bits
            symbols[cursor] = (accumulator >> held) & mask
            cursor += 1
    return symbols


def symbols_to_bytes(symbols: np.ndarray, bits: int, nbytes: int) -> bytes:
    mask = (1 << bits) - 1
    accumulator = 0
    held = 0
    out = bytearray()
    for symbol in symbols:
        accumulator = (accumulator << bits) | (int(symbol) & mask)
        held += bits
        while held >= 8 and len(out) < nbytes:
            held -= 8
            out.append((accumulator >> held) & 0xFF)
    if len(out) < nbytes:
        raise DecodeError("symbol stream ended early")
    return bytes(out)


def file_crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF
