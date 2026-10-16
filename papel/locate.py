"""Encuentra la grilla en un escaneo: finders, orientacion y muestreo."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from papel.constants import CORNER_SPAN, FINDER_MODULES, TIMING_INDEX
from papel.errors import DecodeError
from papel.grid import (
    TIMING_INSET_FAR,
    TIMING_INSET_INWARD,
    TIMING_INSET_NEAR,
    grid_size_from_timing_runs,
)

_RATIO = (1.0, 1.0, 3.0, 1.0, 1.0)
_RATIO_TOLERANCE = 0.65


@dataclass(frozen=True)
class GridPose:
    rows: int
    cols: int
    module_px: float
    # Coeficientes 3x2: [col, row, 1] -> [x, y] en pixeles.
    affine: np.ndarray


def as_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        gray = image
        return np.stack((gray, gray, gray), axis=-1)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image


def luminance(rgb: np.ndarray) -> np.ndarray:
    red = rgb[:, :, 0].astype(np.float32)
    green = rgb[:, :, 1].astype(np.float32)
    blue = rgb[:, :, 2].astype(np.float32)
    return 0.299 * red + 0.587 * green + 0.114 * blue


def locate_grid(rgb: np.ndarray) -> GridPose:
    gray = luminance(rgb)
    # <= para que un bitmap puro (0 y 255) no deje el negro fuera del umbral.
    mask = gray <= _otsu_threshold(gray)
    centers = _finder_centers(mask)
    if len(centers) < 4:
        raise DecodeError("could not find the four corner marks")
    corners = _extreme_corners(centers)
    pose = _best_pose(gray, corners)
    if pose is None:
        raise DecodeError("timing track is not readable")
    return pose


def sample_modules(rgb: np.ndarray, pose: GridPose, radius: int = 0) -> np.ndarray:
    """Color del centro de cada modulo. `radius` 0 es un solo pixel."""
    rows, cols = pose.rows, pose.cols
    col_index, row_index = np.meshgrid(
        np.arange(cols, dtype=np.float32) + 0.5,
        np.arange(rows, dtype=np.float32) + 0.5,
    )
    design = np.stack(
        (col_index, row_index, np.ones_like(col_index)),
        axis=-1,
    )
    pixels = design @ pose.affine.astype(np.float32)
    return _window_mean(rgb, pixels, radius)


def _otsu_threshold(gray: np.ndarray) -> float:
    hist, _edges = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    total = gray.size
    sum_total = np.dot(np.arange(256), hist)
    sum_background = 0.0
    weight_background = 0.0
    best_variance = -1.0
    threshold = 128.0
    for level, count in enumerate(hist):
        weight_background += count
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += level * count
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        variance = (
            weight_background
            * weight_foreground
            * (mean_background - mean_foreground) ** 2
        )
        if variance > best_variance:
            best_variance = variance
            threshold = float(level)
    return threshold


def _finder_centers(mask: np.ndarray) -> list[tuple[float, float, float]]:
    height, width = mask.shape
    found: list[tuple[float, float, float]] = []
    step = 2 if height > 800 else 1
    for row in range(0, height, step):
        starts, ends = _run_bounds(mask[row])
        lengths = ends - starts
        if lengths.size < 5:
            continue
        black = mask[row, starts]
        for index in range(lengths.size - 4):
            if not black[index]:
                continue
            run = lengths[index : index + 5]
            if not _ratio_ok(run):
                continue
            total = int(run.sum())
            module = total / 7.0
            if module < 1.6 or total > width * 0.5:
                continue
            center_x = float(starts[index] + run[0] + run[1] + run[2] / 2.0)
            center = _confirm_vertical(mask, center_x, row, module)
            if center is not None:
                found.append(center)
    if not found:
        return []
    return _cluster_centers(found)


def _run_bounds(bits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    changes = np.flatnonzero(bits[1:] != bits[:-1]) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [bits.size]))
    return starts, ends


def _ratio_ok(lengths: np.ndarray) -> bool:
    total = float(lengths.sum())
    module = total / 7.0
    if module <= 0:
        return False
    for length, target in zip(lengths, _RATIO, strict=True):
        if abs(float(length) / module - target) > _RATIO_TOLERANCE:
            return False
    return True


def _confirm_vertical(
    mask: np.ndarray,
    center_x: float,
    row: int,
    module: float,
) -> tuple[float, float, float] | None:
    height, width = mask.shape
    x = int(round(center_x))
    if x < 0 or x >= width:
        return None
    half = int(module * 5)
    y0 = max(0, row - half)
    y1 = min(height, row + half)
    column = mask[y0:y1, x]
    if column.size < 7:
        return None
    starts, ends = _run_bounds(column)
    lengths = ends - starts
    black = column[starts]
    for index in range(lengths.size - 4):
        if not black[index]:
            continue
        run = lengths[index : index + 5]
        if not _ratio_ok(run):
            continue
        center_y = y0 + float(starts[index] + run[0] + run[1] + run[2] / 2.0)
        if abs(center_y - row) > module * 2:
            continue
        refined = float(run.sum()) / 7.0
        return center_x, center_y, refined
    return None


def _cluster_centers(
    points: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    clusters: list[list[tuple[float, float, float]]] = []
    for point in points:
        placed = False
        for cluster in clusters:
            anchor = cluster[0]
            limit = max(anchor[2], point[2]) * 4
            if abs(point[0] - anchor[0]) <= limit and abs(point[1] - anchor[1]) <= limit:
                cluster.append(point)
                placed = True
                break
        if not placed:
            clusters.append([point])
    centers: list[tuple[float, float, float]] = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        stacked = np.array(cluster, dtype=np.float64)
        centers.append(tuple(np.median(stacked, axis=0)))
    return centers


def _extreme_corners(
    centers: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    points = np.array(centers, dtype=np.float64)
    sums = points[:, 0] + points[:, 1]
    diffs = points[:, 0] - points[:, 1]
    indexes = [
        int(np.argmin(sums)),
        int(np.argmax(diffs)),
        int(np.argmax(sums)),
        int(np.argmin(diffs)),
    ]
    if len(set(indexes)) < 4:
        raise DecodeError("corner marks collapsed into each other")
    return [tuple(points[index]) for index in indexes]


def _best_pose(
    gray: np.ndarray,
    corners: list[tuple[float, float, float]],
) -> GridPose | None:
    # corners: imagen TL, TR, BR, BL. Se prueban las 4 rotaciones y el espejo.
    ring = [(item[0], item[1]) for item in corners]
    module_hint = float(np.median([item[2] for item in corners]))
    best: tuple[float, GridPose] | None = None
    for winding in (ring, list(reversed(ring))):
        for shift in range(4):
            ordered = winding[shift:] + winding[:shift]
            pose, score = _pose_from_order(gray, ordered, module_hint)
            if pose is None:
                continue
            if best is None or score > best[0]:
                best = (score, pose)
    if best is None or best[0] < 8:
        return None
    return best[1]


def _pose_from_order(
    gray: np.ndarray,
    ordered: list[tuple[float, float]],
    module_hint: float,
) -> tuple[GridPose | None, float]:
    top_left, top_right, bottom_right, bottom_left = (np.array(point) for point in ordered)
    horizontal = top_right - top_left
    vertical = bottom_left - top_left
    span_x = float(np.linalg.norm(horizontal))
    span_y = float(np.linalg.norm(vertical))
    if span_x < module_hint * 12 or span_y < module_hint * 12:
        return None, 0.0
    dir_x = horizontal / span_x
    dir_y = vertical / span_y
    # Si el orden no es consistente, los ejes quedan cruzados.
    cross = float(dir_x[0] * dir_y[1] - dir_x[1] * dir_y[0])
    if abs(cross) < 0.3:
        return None, 0.0
    cols, score_x, module_x = _measure_timing(
        gray,
        top_left,
        top_right,
        dir_x,
        dir_y,
        module_hint,
    )
    rows, score_y, module_y = _measure_timing(
        gray,
        top_left,
        bottom_left,
        dir_y,
        dir_x,
        module_hint,
    )
    if cols < CORNER_SPAN * 2 + 8 or rows < CORNER_SPAN * 2 + 8:
        return None, 0.0
    module_px = float(np.median([module_x, module_y]))
    source = np.array(
        [
            [3.5, 3.5, 1.0],
            [cols - 3.5, 3.5, 1.0],
            [cols - 3.5, rows - 3.5, 1.0],
            [3.5, rows - 3.5, 1.0],
        ],
        dtype=np.float64,
    )
    target = np.vstack((top_left, top_right, bottom_right, bottom_left))
    affine, _residuals, _rank, _singular = np.linalg.lstsq(source, target, rcond=None)
    pose = GridPose(rows=rows, cols=cols, module_px=module_px, affine=affine)
    return pose, score_x + score_y


def _measure_timing(
    gray: np.ndarray,
    origin: np.ndarray,
    far: np.ndarray,
    along: np.ndarray,
    inward: np.ndarray,
    module_hint: float,
) -> tuple[int, float, float]:
    start = (
        origin
        + along * (TIMING_INSET_NEAR * module_hint)
        + inward * (TIMING_INSET_INWARD * module_hint)
    )
    end = (
        far
        - along * (TIMING_INSET_FAR * module_hint)
        + inward * (TIMING_INSET_INWARD * module_hint)
    )
    length = float(np.linalg.norm(end - start))
    samples = max(8, int(length))
    line = _sample_line(gray, start, end, samples)
    if line.size < 8:
        return 0, 0.0, module_hint
    low = float(line.min())
    high = float(line.max())
    # La mediana falla cuando hay un negro de mas: queda del lado negro
    # y no marca ningun tramo. El punto medio separa los dos tonos.
    if high - low < 16:
        return 0, 0.0, module_hint
    bits = line <= (low + high) / 2
    starts, ends = _run_bounds(bits)
    lengths = ends - starts
    # Une solo astillas: un punto fino por el desenfoque sigue siendo un tramo.
    min_run = max(1.0, module_hint * 0.30)
    merged: list[tuple[bool, float]] = []
    for is_black, run_length, start_index in zip(bits[starts], lengths, starts, strict=True):
        if merged and (run_length < min_run or merged[-1][0] == bool(is_black)):
            merged[-1] = (merged[-1][0], merged[-1][1] + float(run_length))
        else:
            merged.append((bool(is_black), float(run_length)))
    if len(merged) < 8:
        return 0, 0.0, module_hint
    median_guess = float(np.median([item[1] for item in merged]))
    # Solo se descarta un borde si es menos de medio modulo: un modulo
    # real adelgazado por el desenfoque sigue por encima de eso.
    while len(merged) > 8 and merged[0][1] < median_guess * 0.5:
        merged.pop(0)
    while len(merged) > 8 and merged[-1][1] < median_guess * 0.5:
        merged.pop()
    run_lengths = np.array([item[1] for item in merged], dtype=np.float64)
    median = float(np.median(run_lengths))
    if median <= 0:
        return 0, 0.0, module_hint
    deviation = float(np.std(run_lengths) / median)
    # La pista arranca en negro (indice par).
    starts_black = 1.0 if merged[0][0] else 0.4
    score = starts_black * len(merged) / (deviation + 0.08)
    return grid_size_from_timing_runs(len(merged)), score, median


def _sample_line(
    gray: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    count: int,
) -> np.ndarray:
    height, width = gray.shape
    positions = np.linspace(0.0, 1.0, count)
    xs = np.clip(np.rint(start[0] + (end[0] - start[0]) * positions).astype(int), 0, width - 1)
    ys = np.clip(np.rint(start[1] + (end[1] - start[1]) * positions).astype(int), 0, height - 1)
    return gray[ys, xs]


def _window_mean(rgb: np.ndarray, pixels: np.ndarray, radius: int) -> np.ndarray:
    height, width = rgb.shape[:2]
    # Ventana par, centrada, para que un tramado 2x2 promedie justo.
    offsets = range(-radius, radius) if radius else range(1)
    if radius == 0:
        offsets = (0,)
    accumulator = np.zeros(pixels.shape[:2] + (3,), dtype=np.float32)
    taps = 0
    for dy in offsets:
        for dx in offsets:
            xs = np.clip(np.rint(pixels[:, :, 0] + dx).astype(int), 0, width - 1)
            ys = np.clip(np.rint(pixels[:, :, 1] + dy).astype(int), 0, height - 1)
            accumulator += rgb[ys, xs]
            taps += 1
    return accumulator / max(taps, 1)


def reference_levels(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Negro del finder y blanco de la quiet zone, en RGB."""
    rows, cols = samples.shape[:2]
    black_points = []
    white_points = []
    origins = (
        (0, 0),
        (0, cols - FINDER_MODULES),
        (rows - FINDER_MODULES, 0),
        (rows - FINDER_MODULES, cols - FINDER_MODULES),
    )
    for row0, col0 in origins:
        black_points.append(samples[row0 + 3, col0 + 3])
        if row0 == 0:
            white_row = TIMING_INDEX - 1
        else:
            white_row = row0 - 1
        if col0 == 0:
            white_col = 3
        else:
            white_col = col0 + 3
        white_points.append(samples[white_row, white_col])
    black = np.median(np.stack(black_points), axis=0)
    white = np.median(np.stack(white_points), axis=0)
    return black, white
