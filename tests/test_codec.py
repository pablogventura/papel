"""La trama cierra sin pasar por una imagen."""

import numpy as np

from papel.codec import pack_header, page_payload_capacity, protect, recover, unpack_header
from papel.codec import PagePayload


def test_header_roundtrip():
    page = PagePayload(
        file_id=7,
        page_index=1,
        page_count=3,
        chunk_offset=100,
        chunk=b"abc",
        file_crc=99,
        original_size=3,
        stored_size=3,
        flags=0,
        name="nota.txt",
        mode="bw",
    )
    restored = unpack_header(pack_header(page) + page.chunk)
    assert restored.chunk == b"abc"
    assert restored.name == "nota.txt"
    assert restored.page_index == 1
    assert restored.mode == "bw"


def test_scatter_roundtrip_keeps_a_byte_together():
    from papel.codec import gather_symbols, scatter_symbols

    symbols = np.arange(320, dtype=np.uint8)
    placed = scatter_symbols(symbols, 1)
    assert np.array_equal(gather_symbols(placed, 1), symbols)
    # Los 8 bits de cada byte siguen juntos en la hoja.
    assert np.all(np.diff(placed.reshape(-1, 8), axis=1) == 1)


def test_reed_solomon_repairs_a_scattered_stain():
    frame = bytes(range(200)) * 10
    capacity = (len(frame) + 222) // 223 * 223
    protected = protect(frame, capacity)
    damaged = bytearray(protected)
    for index in range(0, len(damaged), 17):
        damaged[index] ^= 0xFF
    assert recover(bytes(damaged)).startswith(frame)


def test_page_capacity_grows_with_bits():
    bw = page_payload_capacity(1.0, "bw")
    color = page_payload_capacity(1.0, "cmy")
    assert color > bw * 2.5
