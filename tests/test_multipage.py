"""Varias hojas, en cualquier orden, y error si falta una."""

import numpy as np

from papel.constants import SCAN_DPI
from papel.document import decode_images, encode_pdf
from papel.errors import IncompleteBackup
from papel.noise import HARSH, apply_noise
from papel.render import rasterize_pdf

# Aleatorio: no comprime, y no entra en una sola hoja de 1 mm.
PAYLOAD = np.random.default_rng(1).integers(0, 256, size=12000, dtype=np.uint8).tobytes()


def _pages(module_mm: float) -> list[np.ndarray]:
    pdf = encode_pdf(PAYLOAD, "datos.bin", mode="bw", module_mm=module_mm)
    return [apply_noise(image, HARSH) for image in rasterize_pdf(pdf, SCAN_DPI)]


def test_pages_out_of_order():
    pages = _pages(1.0)
    assert len(pages) >= 2
    shuffled = list(reversed(pages))
    assert decode_images(shuffled) == PAYLOAD


def test_missing_page_does_not_return_a_partial_file():
    pages = _pages(1.0)
    try:
        decode_images(pages[:-1])
    except IncompleteBackup as exc:
        assert exc.missing
        return
    raise AssertionError("a missing page still produced a file")
