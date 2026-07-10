"""
digit_patterns.py — render integer "numbers drawn by the mirrors" for the
DMD preliminary connection tests.

Produces binary (0/1) DMD patterns of shape (Ny, Nx) = (1600, 2560) for the
Vialux DLP9000XUV, where each number (0, 1, 2, ... 10) is drawn as large blocky
digits made of ON mirrors on a background of OFF mirrors.

This module has NO hardware or GPU dependencies (only numpy), because it is used
purely to make simple, visually recognizable test frames — the goal of the
preliminary tests is to verify the PC <-> DMD connection, nothing more.
"""

import numpy as np

# 3-wide x 5-tall bitmap font for digits 0-9. '1' = ON mirror.
_FONT = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}

_GLYPH_ROWS = 5
_GLYPH_COLS = 3
_CHAR_SPACING_CELLS = 1  # blank font-cells between digits


def _glyph_grid(text):
    """Assemble a small bitmap grid (list of strings) for a multi-char string."""
    rows = [""] * _GLYPH_ROWS
    for k, ch in enumerate(text):
        if ch not in _FONT:
            raise ValueError(f"Unsupported character {ch!r}; only digits 0-9.")
        glyph = _FONT[ch]
        for r in range(_GLYPH_ROWS):
            if k > 0:
                rows[r] += "0" * _CHAR_SPACING_CELLS
            rows[r] += glyph[r]
    return rows


def render_number(n, Nx=2560, Ny=1600, fill_fraction=0.6, invert=False):
    """
    Render integer ``n`` as a centered blocky pattern.

    Parameters
    ----------
    n : int
        Number to draw (0..10 for the preliminary tests, but any non-negative
        integer works).
    Nx, Ny : int
        DMD width (columns) and height (rows). Output shape is (Ny, Nx).
    fill_fraction : float
        Target fraction of the DMD short axis the digits should occupy.
    invert : bool
        If True, digits are OFF on an ON background (default: ON digits on OFF).

    Returns
    -------
    np.ndarray of shape (Ny, Nx), dtype=uint8, values in {0, 1}.
    """
    text = str(int(n))
    grid = _glyph_grid(text)
    grid_rows = _GLYPH_ROWS
    grid_cols = len(grid[0])

    # Choose a per-cell block size so the glyph fits within fill_fraction of the
    # short axis (height) and never overflows the width.
    block_h = int((fill_fraction * Ny) / grid_rows)
    block_w = int((fill_fraction * Nx) / grid_cols)
    block = max(1, min(block_h, block_w))

    glyph_h = grid_rows * block
    glyph_w = grid_cols * block
    row0 = (Ny - glyph_h) // 2
    col0 = (Nx - glyph_w) // 2

    canvas = np.zeros((Ny, Nx), dtype=np.uint8)
    for r in range(grid_rows):
        for c in range(grid_cols):
            if grid[r][c] == "1":
                y = row0 + r * block
                x = col0 + c * block
                canvas[y:y + block, x:x + block] = 1

    if invert:
        canvas = 1 - canvas
    return canvas


def render_numbers(values, Nx=2560, Ny=1600, **kwargs):
    """Render a list of integers; returns a list of (Ny, Nx) uint8 patterns."""
    return [render_number(v, Nx=Nx, Ny=Ny, **kwargs) for v in values]


def save_preview(pattern, path):
    """Save a pattern as a PNG (0/1 -> 0/255). Requires imageio; no-op if absent."""
    try:
        from imageio import imwrite
    except ImportError:
        print(f"  (imageio not installed; skipping preview {path})")
        return False
    imwrite(path, (pattern * 255).astype(np.uint8))
    return True


if __name__ == "__main__":
    # Quick self-test: render 0..10 and save previews next to this file.
    import os
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
    os.makedirs(out_dir, exist_ok=True)
    for v in range(11):
        p = render_number(v)
        ok = save_preview(p, os.path.join(out_dir, f"number_{v:02d}.png"))
        print(f"number {v}: shape={p.shape} on_pixels={int(p.sum())}"
              + ("" if ok else "  (no preview saved)"))
    print(f"Previews (if saved) are in: {out_dir}")
