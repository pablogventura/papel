"""El modulo por defecto es el fino que el ruido duro todavia lee."""

from papel.codec import page_payload_capacity
from papel.constants import DEFAULT_MODULE_MM, MIN_MODULE_MM, SCAN_DPI
from papel.document import decode_images, encode_pdf
from papel.noise import HARSH, apply_noise
from papel.render import rasterize_pdf


def test_default_module_is_above_the_nyquist_floor_and_survives():
    assert DEFAULT_MODULE_MM + 1e-9 >= MIN_MODULE_MM
    assert page_payload_capacity(DEFAULT_MODULE_MM, "bw") > 20000
    payload = b"densidad" * 100
    pdf = encode_pdf(payload, "d.bin", mode="bw", module_mm=DEFAULT_MODULE_MM)
    scan = apply_noise(rasterize_pdf(pdf, SCAN_DPI)[0], HARSH)
    assert decode_images([scan]) == payload
