"""Escalera de una pagina en blanco y negro, de la memoria al papel ruidoso."""

import subprocess
import sys

import numpy as np

from papel.constants import SCAN_DPI
from papel.document import decode_images, encode_pdf
from papel.errors import DecodeError
from papel.noise import CLEAN, FATAL, HARSH, MILD, apply_noise
from papel.render import paint_frame, rasterize_pdf

PAYLOAD = b"papel backup " * 40


def _scan_pdf(pdf: bytes, profile) -> np.ndarray:
    image = rasterize_pdf(pdf, SCAN_DPI)[0]
    return apply_noise(image, profile)


def test_pdf_clean_roundtrip():
    pdf = encode_pdf(PAYLOAD, "nota.txt", mode="bw", module_mm=1.0)
    assert decode_images([_scan_pdf(pdf, CLEAN)]) == PAYLOAD


def test_image_grid_without_pdf():
    from papel.codec import PagePayload, file_crc, pack_header, store_bytes

    stored, flags = store_bytes(PAYLOAD)
    page = PagePayload(
        file_id=file_crc(b"nota.txt" + PAYLOAD),
        page_index=0,
        page_count=1,
        chunk_offset=0,
        chunk=stored,
        file_crc=file_crc(PAYLOAD),
        original_size=len(PAYLOAD),
        stored_size=len(stored),
        flags=flags,
        name="nota.txt",
        mode="bw",
    )
    grid = paint_frame(pack_header(page) + stored, 1.0, "bw")
    border = 48
    canvas = np.full((grid.shape[0] + 2 * border, grid.shape[1] + 2 * border, 3), 255, np.uint8)
    canvas[border : border + grid.shape[0], border : border + grid.shape[1]] = grid
    assert decode_images([canvas]) == PAYLOAD


def test_mild_noise():
    pdf = encode_pdf(PAYLOAD, "nota.txt", mode="bw", module_mm=1.0)
    assert decode_images([_scan_pdf(pdf, MILD)]) == PAYLOAD


def test_harsh_noise():
    pdf = encode_pdf(PAYLOAD, "nota.txt", mode="bw", module_mm=1.0)
    assert decode_images([_scan_pdf(pdf, HARSH)]) == PAYLOAD


def test_cli_roundtrip(tmp_path):
    source = tmp_path / "hola.txt"
    source.write_bytes(b"hola desde la hoja")
    pdf = tmp_path / "backup.pdf"
    restored = tmp_path / "vuelta.txt"
    python = sys.executable
    subprocess.run(
        [python, "-m", "papel", "encode", str(source), "-o", str(pdf), "--module-mm", "1"],
        check=True,
    )
    subprocess.run(
        [python, "-m", "papel", "decode", str(pdf), "-o", str(restored)],
        check=True,
    )
    assert restored.read_bytes() == source.read_bytes()


def test_excessive_damage_fails_cleanly():
    pdf = encode_pdf(PAYLOAD, "nota.txt", mode="bw", module_mm=1.0)
    try:
        decode_images([_scan_pdf(pdf, FATAL)])
    except DecodeError:
        return
    raise AssertionError("excessive damage returned a file")
