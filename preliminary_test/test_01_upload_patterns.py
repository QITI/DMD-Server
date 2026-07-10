"""
Preliminary Test 1 — Upload patterns to the DMD (PC <-> DMD connection test)
============================================================================

Purpose
-------
Verify the USB connection between the PC and the Vialux ALP 4.3 / DLP9000XUV by
UPLOADING a series of test patterns and DISPLAYING each one for 5 seconds. The
patterns are simple numbers drawn by the mirrors: 0, 1, 2, ... up to 10.

This exercises the "master mode" software-driven path:
    upload pattern  ->  display  ->  wait 5 s  ->  upload next pattern

Nothing more is tested here: no holograms, no GPU, no ARTIQ trigger. If the
numbers appear (on a camera at the image plane, or by eye on the DMD face) and
change every 5 seconds, the PC->DMD link works.

Usage
-----
    python test_01_upload_patterns.py                 # real hardware
    python test_01_upload_patterns.py --dwell 3       # 3 s per number
    python test_01_upload_patterns.py --max 5         # only 0..5
    python test_01_upload_patterns.py --simulation    # no hardware; save PNG previews

Wiring: just the USB 3.0 cable from the PC to the Vialux V-module.
"""

import argparse
import os
import sys
import time

import numpy as np

from digit_patterns import render_numbers, save_preview

try:
    from ALP4 import (
        ALP4,
        ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED,
        ALP_PROJ_MODE, ALP_MASTER,
        ALP_DEV_DISPLAY_WIDTH, ALP_DEV_DISPLAY_HEIGHT,
    )
    ALP_AVAILABLE = True
except ImportError:
    ALP_AVAILABLE = False


def run_simulation(values, Nx, Ny):
    """No hardware: render the patterns and save PNG previews so you can verify them."""
    print("SIMULATION mode — no DMD. Rendering previews instead of uploading.")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.perf_counter()
    patterns = render_numbers(values, Nx=Nx, Ny=Ny)
    t_render = time.perf_counter() - t0
    print(f"  [timing] rendered {len(patterns)} patterns: {_ms(t_render)} "
          f"({_ms(t_render / len(patterns))}/pattern)")

    for v, p in zip(values, patterns):
        path = os.path.join(out_dir, f"test1_number_{v:02d}.png")
        saved = save_preview(p, path)
        print(f"  number {v:>2}: on_pixels={int(p.sum()):>8}"
              + (f"  -> {path}" if saved else ""))
    print("Simulation complete. (Upload/arm timings appear only in hardware mode.)")


def _ms(t):
    """Format a duration in seconds as milliseconds."""
    return f"{t * 1e3:.1f} ms"


def run_hardware(values, dwell):
    """Upload each numbered pattern and display it for `dwell` seconds."""
    timings = {"upload_per_frame": []}  # collected per-frame upload+display-arm times

    t_init0 = time.perf_counter()
    dmd = ALP4(version="4.3")
    dmd.Initialize()
    timings["init"] = time.perf_counter() - t_init0
    try:
        Nx = dmd.DevInquire(ALP_DEV_DISPLAY_WIDTH)
        Ny = dmd.DevInquire(ALP_DEV_DISPLAY_HEIGHT)
        print(f"ALP board initialized. DMD resolution: {Nx} x {Ny}")
        print(f"  [timing] ALP init: {_ms(timings['init'])}")

        t_render0 = time.perf_counter()
        patterns = render_numbers(values, Nx=Nx, Ny=Ny)
        timings["render_all"] = time.perf_counter() - t_render0
        print(f"  [timing] rendered {len(patterns)} patterns: {_ms(timings['render_all'])} "
              f"({_ms(timings['render_all'] / len(patterns))}/pattern)")
        print()

        for v, pattern in zip(values, patterns):
            t_frame0 = time.perf_counter()

            # Free any previous sequence before uploading the next one.
            t_free0 = time.perf_counter()
            if dmd._lastDDRseq is not None:
                dmd.Halt()
                dmd.FreeSeq()
            t_free = time.perf_counter() - t_free0

            # Upload this single frame and display it continuously (master mode).
            img = pattern.astype(np.uint8) * 255

            t_alloc0 = time.perf_counter()
            dmd.SeqAlloc(nbImg=1, bitDepth=1)
            dmd.SeqControl(ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED)
            t_alloc = time.perf_counter() - t_alloc0

            t_put0 = time.perf_counter()
            dmd.SeqPut(imgData=img)                 # <-- the actual USB upload
            t_put = time.perf_counter() - t_put0

            t_arm0 = time.perf_counter()
            dmd.ProjControl(ALP_PROJ_MODE, ALP_MASTER)
            dmd.SetTiming()                         # default (fast) internal timing
            dmd.Run(loop=True)
            t_arm = time.perf_counter() - t_arm0

            t_total = time.perf_counter() - t_frame0
            timings["upload_per_frame"].append(t_total)

            print(f"  number {v:>2} (on mirrors: {int(pattern.sum()):>8})  "
                  f"[free {_ms(t_free)} | alloc {_ms(t_alloc)} | "
                  f"upload {_ms(t_put)} | arm {_ms(t_arm)} | total {_ms(t_total)}]  "
                  f"— holding {dwell} s")
            time.sleep(dwell)

        print("\nAll numbers displayed. Test 1 complete.")
        _print_timing_summary(timings)

    finally:
        try:
            dmd.Halt()
            if dmd._lastDDRseq is not None:
                dmd.FreeSeq()
            dmd.Free()
        except Exception as e:
            print(f"Cleanup warning: {e}")
        print("DMD released.")


def _print_timing_summary(timings):
    """Print aggregate timing statistics for the run."""
    per = timings.get("upload_per_frame", [])
    print("\n" + "-" * 60)
    print("  TIMING SUMMARY")
    print("-" * 60)
    print(f"  ALP init:                 {_ms(timings.get('init', 0))}")
    print(f"  Render all patterns:      {_ms(timings.get('render_all', 0))}")
    if per:
        arr = np.array(per)
        print(f"  Per-frame upload+arm:     "
              f"min {_ms(arr.min())} | mean {_ms(arr.mean())} | max {_ms(arr.max())} "
              f"(n={len(per)})")
        print(f"  Total upload+arm (all):   {_ms(arr.sum())}")
    print("  (Note: excludes the {}-second display dwell between frames.)"
          .format("N/A" if not per else "chosen"))
    print("-" * 60)


def main():
    ap = argparse.ArgumentParser(description="DMD Preliminary Test 1: upload + display numbers")
    ap.add_argument("--dwell", type=float, default=5.0, help="seconds per number (default 5)")
    ap.add_argument("--max", type=int, default=10, help="highest number to show (default 10)")
    ap.add_argument("--simulation", action="store_true", help="no hardware; save PNG previews")
    args = ap.parse_args()

    values = list(range(0, args.max + 1))

    print("=" * 60)
    print("  DMD Preliminary Test 1 — Upload Patterns (0..%d)" % args.max)
    print("=" * 60)

    if args.simulation or not ALP_AVAILABLE:
        if not ALP_AVAILABLE and not args.simulation:
            print("ALP4lib not found — falling back to SIMULATION mode.\n")
        run_simulation(values, Nx=2560, Ny=1600)
        return 0

    run_hardware(values, dwell=args.dwell)
    return 0


if __name__ == "__main__":
    sys.exit(main())
