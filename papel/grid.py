"""Geometria de la grilla: finders y pista de conteo.

La pista de conteo va solo en el borde de arriba y en el de la izquierda.
Eso fija la orientacion de la hoja: las otras rotaciones no tienen una
pista que alterne con paso constante.
"""

from __future__ import annotations

import numpy as np

from papel.constants import (
    CORNER_SPAN,
    FINDER_MODULES,
    GRID_HEIGHT_MM,
    GRID_WIDTH_MM,
    MIN_MODULE_MM,
    TIMING_INDEX,
)
from papel.errors import PapelError

# Finder de QR: anillo exterior y cuadrado interior de 3x3.
_FINDER = np.zeros((FINDER_MODULES, FINDER_MODULES), dtype=bool)
_FINDER[0, :] = True
_FINDER[-1, :] = True
_FINDER[:, 0] = True
_FINDER[:, -1] = True
_FINDER[2:5, 2:5] = True

# Del centro del finder (3.5) al borde donde arranca la pista.
TIMING_INSET_NEAR = 4.5
# Del centro del finder opuesto al borde donde termina la pista.
TIMING_INSET_FAR = 5.5
# Del centro del finder hacia adentro, hasta el centro de la pista.
TIMING_INSET_INWARD = 5.0


def grid_shape(module_mm: float) -> tuple[int, int]:
    """Filas y columnas que entran en el area util."""
    if module_mm < MIN_MODULE_MM - 1e-9:
        raise PapelError(
            f"module {module_mm:.3f} mm is below the 3 px scan limit "
            f"({MIN_MODULE_MM:.3f} mm)"
        )
    rows = int(GRID_HEIGHT_MM / module_mm)
    cols = int(GRID_WIDTH_MM / module_mm)
    if rows < CORNER_SPAN * 2 + 8 or cols < CORNER_SPAN * 2 + 8:
        raise PapelError("module is too large for an A4 grid")
    return rows, cols


def finder_origins(rows: int, cols: int) -> list[tuple[int, int]]:
    last_row = rows - FINDER_MODULES
    last_col = cols - FINDER_MODULES
    return [(0, 0), (0, last_col), (last_row, 0), (last_row, last_col)]


def timing_bounds(length: int) -> tuple[int, int]:
    """Inicio inclusivo y fin exclusivo de la pista sobre un lado."""
    return TIMING_INDEX, length - CORNER_SPAN


def grid_size_from_timing_runs(run_count: int) -> int:
    """Pasa de la cantidad de tramos de la pista al lado de la grilla."""
    return run_count + TIMING_INDEX + CORNER_SPAN


def reserved_mask(rows: int, cols: int) -> np.ndarray:
    """True en modulos que no llevan datos."""
    mask = np.zeros((rows, cols), dtype=bool)
    boxes = (
        (slice(0, CORNER_SPAN), slice(0, CORNER_SPAN)),
        (slice(0, CORNER_SPAN), slice(cols - CORNER_SPAN, cols)),
        (slice(rows - CORNER_SPAN, rows), slice(0, CORNER_SPAN)),
        (slice(rows - CORNER_SPAN, rows), slice(cols - CORNER_SPAN, cols)),
    )
    for row_slice, col_slice in boxes:
        mask[row_slice, col_slice] = True
    col_start, col_stop = timing_bounds(cols)
    row_start, row_stop = timing_bounds(rows)
    mask[TIMING_INDEX, col_start:col_stop] = True
    mask[row_start:row_stop, TIMING_INDEX] = True
    return mask


def data_coordinates(rows: int, cols: int) -> tuple[np.ndarray, np.ndarray]:
    """Coordenadas de datos en orden de fila."""
    free = ~reserved_mask(rows, cols)
    return np.nonzero(free)


def geometry_black(rows: int, cols: int) -> np.ndarray:
    """Modulos de geometria que van en negro solido."""
    black = np.zeros((rows, cols), dtype=bool)
    for row0, col0 in finder_origins(rows, cols):
        black[row0 : row0 + FINDER_MODULES, col0 : col0 + FINDER_MODULES] = _FINDER
    col_start, col_stop = timing_bounds(cols)
    row_start, row_stop = timing_bounds(rows)
    columns = np.arange(col_start, col_stop)
    rows_idx = np.arange(row_start, row_stop)
    black[TIMING_INDEX, col_start:col_stop] = columns % 2 == 0
    black[row_start:row_stop, TIMING_INDEX] = rows_idx % 2 == 0
    return black
