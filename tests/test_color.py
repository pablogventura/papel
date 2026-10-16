"""El color se queda solo si, con el ruido duro, mete bastante mas que el negro."""

from papel.codec import page_payload_capacity
from papel.constants import COLOR_MODE, DEFAULT_MODULE_MM, LASER_MODE, SCAN_DPI
from papel.document import decode_images, encode_pdf
from papel.noise import HARSH, apply_noise
from papel.render import rasterize_pdf


def _survives(mode: str) -> int:
    capacity = page_payload_capacity(DEFAULT_MODULE_MM, mode)
    payload = bytes([index % 256 for index in range(1200)])
    pdf = encode_pdf(payload, "muestra.bin", mode=mode, module_mm=DEFAULT_MODULE_MM)
    scan = apply_noise(rasterize_pdf(pdf, SCAN_DPI)[0], HARSH)
    assert decode_images([scan]) == payload
    return capacity


def test_cmy_is_worth_enabling():
    black = _survives("bw")
    color = _survives("cmy")
    assert color >= black * 1.5
    assert LASER_MODE == "bw"
    assert COLOR_MODE == "cmy"
