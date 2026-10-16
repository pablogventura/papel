"""Tamaños de hoja, modos y parametros medidos.

DEFAULT_MODULE_MM, LASER_MODE y COLOR_MODE se fijan despues de la
comparacion de ruido. Los tests de regresion vuelven a medirlos.
"""

SCAN_DPI = 300
MIN_PIXELS_PER_MODULE = 3

PAGE_WIDTH_MM = 210.0
PAGE_HEIGHT_MM = 297.0
GRID_ORIGIN_X_MM = 12.0
GRID_ORIGIN_Y_MM = 18.0
GRID_WIDTH_MM = 186.0
GRID_HEIGHT_MM = 260.0

# 3 px a 300 dpi. Por debajo, el Nyquist del escaneo ya no alcanza.
MIN_MODULE_MM = MIN_PIXELS_PER_MODULE / SCAN_DPI * 25.4

FINDER_MODULES = 7
QUIET_MODULES = 1
TIMING_INDEX = FINDER_MODULES + QUIET_MODULES  # fila y columna 8
CORNER_SPAN = TIMING_INDEX + 1  # 9: finder + quiet + timing

RS_NSYM = 32
RS_BLOCK = 255
RS_DATA = RS_BLOCK - RS_NSYM  # 223

HEADER_SIZE = 100
MAGIC = b"PAPL"
VERSION = 1

MODE_BW = 0
MODE_CMY = 1

MODE_BY_NAME = {
    "bw": MODE_BW,
    "cmy": MODE_CMY,
}
NAME_BY_MODE = {value: name for name, value in MODE_BY_NAME.items()}
BITS_PER_MODULE = {
    "bw": 1,
    "cmy": 3,
}

FLAG_ZLIB = 0x01

# Medido con el perfil harsh (desenfoque, ruido, 3 grados, mancha y 0,1 mm
# de desregistro) a 300 dpi. 0,40 mm ya no recupera. 0,45 mm si: el blanco y
# negro entra unos 25 KB y el cian/magenta/amarillo unos 77 KB, el triple.
DEFAULT_MODULE_MM = 0.45
LASER_MODE = "bw"
COLOR_MODE: str | None = "cmy"
