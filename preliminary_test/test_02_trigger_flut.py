"""
Preliminary Test 2 — Trigger + FLUT with arbitrary, reprogrammable order
========================================================================

Purpose
-------
Verify the PC <-> DMD connection AND the FLUT (Frame Look-Up Table) + external
trigger path. The numbered patterns (0, 1, 2, ... max) are uploaded to DDR
memory ONCE. After that you can type ANY playback order (e.g. 3,4,1,2,5,4,6,4,2),
program it into the FLUT, and re-arm — WITHOUT re-uploading the frames. You can
change the order and reprogram as many times as you like to confirm the FLUT is
really doing the reordering.

Flow
----
    1. Determine the max number  -> upload frames 0..max to DDR (once).
    2. Type an order             -> program the FLUT, arm SLAVE mode.
    3. Send TTL triggers         -> each rising edge advances one FLUT entry.
    4. Type a new order          -> reprogram the FLUT (NO re-upload), re-arm.
    5. Repeat 3-4, or quit.

How the advance works
---------------------
The ALP has an internal counter that increments by +1 per trigger. With FLUT
order = [3,4,1,2,5,4,6,4,2]:
    trigger 1 -> FLUT[0]=3 -> number 3
    trigger 2 -> FLUT[1]=4 -> number 4
    trigger 3 -> FLUT[2]=1 -> number 1
    ...
    trigger 9 -> FLUT[8]=2 -> number 2, then wraps to FLUT[0]=3.
Frames 0..max stay in DDR the whole time; only the FLUT (the order) changes.

Wiring
------
    PC ── USB 3.0 ──────────► Vialux V-module
    Trigger source ── BNC ──► Vialux "Trigger IN"
Trigger source = ARTIQ Kasli TTL (DMD_TTL, e.g. ttl7) or any pulse/function
generator giving a clean rising edge (~3.3 V). One pulse = one advance.

Usage
-----
    python test_02_trigger_flut.py                 # prompts for max, then orders
    python test_02_trigger_flut.py --max 6         # upload frames 0..6
    python test_02_trigger_flut.py --order 3,4,1,2,5,4,6,4,2   # skip first prompt
    python test_02_trigger_flut.py --simulation    # no hardware; exercise the flow

Note
----
Programming the FLUT calls ProjControlEx. Some ALP4lib versions have a typo
(AlpProjContro instead of AlpProjControlEx) — patch it if you hit an error there
(see ../README.md "ALP4lib bug fix").
"""

import argparse
import ctypes as ct
import sys
import time

import numpy as np

from digit_patterns import render_numbers

try:
    from ALP4 import (
        ALP4,
        ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED,
        ALP_PROJ_MODE, ALP_SLAVE,
        ALP_TRIGGER_EDGE, ALP_EDGE_RISING,
        ALP_MIN_PICTURE_TIME,
        ALP_FLUT_MODE, ALP_FLUT_9BIT, ALP_FLUT_ENTRIES9,
        ALP_FLUT_WRITE_9BIT, tFlutWrite,
        ALP_DEV_DISPLAY_WIDTH, ALP_DEV_DISPLAY_HEIGHT,
        ALP_AVAIL_MEMORY,
    )
    ALP_AVAILABLE = True
except ImportError:
    ALP_AVAILABLE = False

MAX_FLUT_ENTRIES = 4096


# ----------------------------------------------------------------------
# Input helpers
# ----------------------------------------------------------------------

def parse_order(raw, max_index):
    """Parse '3,4,1 2' -> [3,4,1,2] and validate against loaded frames."""
    parts = raw.replace(",", " ").split()
    if not parts:
        raise ValueError("empty order")
    order = []
    for p in parts:
        try:
            idx = int(p)
        except ValueError:
            raise ValueError(f"'{p}' is not an integer")
        if idx < 0 or idx > max_index:
            raise ValueError(f"index {idx} out of range 0..{max_index}")
        order.append(idx)
    if len(order) > MAX_FLUT_ENTRIES:
        raise ValueError(f"{len(order)} entries exceeds FLUT limit {MAX_FLUT_ENTRIES}")
    return order


def prompt_max(default_max):
    """Ask for the highest number to upload; Enter keeps the default."""
    while True:
        raw = input(f"Highest number to upload (frames 0..N) [default {default_max}]: ").strip()
        if raw == "":
            return default_max
        try:
            m = int(raw)
            if m < 0:
                print("  Must be >= 0.")
                continue
            return m
        except ValueError:
            print("  Please enter an integer.")


def prompt_order(max_index, preset=None):
    """
    Ask for a FLUT order. Returns a list of ints, or None to quit.
    `preset` (from --order) is used once on the first call.
    """
    if preset is not None:
        try:
            return parse_order(preset, max_index)
        except ValueError as e:
            print(f"  --order invalid ({e}); ignoring it.")
    while True:
        raw = input(
            f"\nEnter FLUT order over frames 0..{max_index} "
            f"(e.g. 3,4,1,2,5,4,6,4,2), or 'q' to quit: "
        ).strip().lower()
        if raw in {"q", "quit", "exit"}:
            return None
        try:
            return parse_order(raw, max_index)
        except ValueError as e:
            print(f"  Invalid order: {e}. Try again.")


# ----------------------------------------------------------------------
# Simulation mode (no hardware) — exercises the same interactive flow
# ----------------------------------------------------------------------

def run_simulation(default_max, preset_order):
    print("SIMULATION mode — no DMD. Frames are not really uploaded.\n")
    max_index = prompt_max(default_max)
    n_frames = max_index + 1
    t0 = time.perf_counter()
    render_numbers(range(n_frames), Nx=2560, Ny=1600)   # measure render cost
    t_render = time.perf_counter() - t0
    print(f"  Would upload frames 0..{max_index} to DDR once (numbers 0..{max_index}).")
    print(f"  [timing] rendered {n_frames} frames: {_ms(t_render)} "
          f"({_ms(t_render / n_frames)}/frame). "
          f"(Upload/reprogram timings appear only in hardware mode.)")
    preset = preset_order
    while True:
        order = prompt_order(max_index, preset)
        preset = None
        if order is None:
            break
        print(f"  Would program FLUT (9-bit), {len(order)} entries: {order}")
        print("  Would arm SLAVE mode (rising edge). Frames stay in DDR; only FLUT changed.")
        print("  Trigger sequence would show numbers: "
              + " -> ".join(str(v) for v in order) + " -> (wrap)")
    print("Simulation complete.")


# ----------------------------------------------------------------------
# Hardware mode
# ----------------------------------------------------------------------

def _ms(t):
    """Format a duration in seconds as milliseconds."""
    return f"{t * 1e3:.1f} ms"


def program_flut(dmd, order, min_pt, first_time):
    """
    Program the FLUT with `order` and arm slave mode. Does NOT touch the uploaded
    frame sequence, so frames stay in DDR across reprogramming.

    Returns a dict of sub-step timings (seconds).
    """
    t = {}
    t0 = time.perf_counter()

    th = time.perf_counter()
    if not first_time:
        dmd.Halt()  # must halt before reprogramming the FLUT
    t["halt"] = time.perf_counter() - th

    tw = time.perf_counter()
    dmd.SeqControl(ALP_FLUT_MODE, ALP_FLUT_9BIT)
    dmd.SeqControl(ALP_FLUT_ENTRIES9, len(order))
    flut = tFlutWrite()
    flut.nOffset = 0
    flut.nSize = len(order)
    for i, frame_idx in enumerate(order):
        flut.FrameNumbers[i] = frame_idx
    try:
        dmd.ProjControlEx(ALP_FLUT_WRITE_9BIT, ct.byref(flut))
    except AttributeError as e:
        raise RuntimeError(
            "ProjControlEx failed — likely the ALP4lib 'AlpProjContro' typo. "
            "See ../README.md 'ALP4lib bug fix'."
        ) from e
    t["write_flut"] = time.perf_counter() - tw

    ta = time.perf_counter()
    dmd.ProjControl(ALP_PROJ_MODE, ALP_SLAVE)
    dmd.DevControl(ALP_TRIGGER_EDGE, ALP_EDGE_RISING)
    dmd.SetTiming(pictureTime=min_pt)
    dmd.Run()
    t["arm"] = time.perf_counter() - ta

    t["total"] = time.perf_counter() - t0
    return t


def run_hardware(default_max, preset_order):
    reprogram_times = []  # total time to change the order, per reprogram

    t_init0 = time.perf_counter()
    dmd = ALP4(version="4.3",libDir="C:\Program Files\ALP-4.3\ALP-4.3 API")
    dmd.Initialize()
    t_init = time.perf_counter() - t_init0
    try:
        Nx = dmd.DevInquire(ALP_DEV_DISPLAY_WIDTH)
        Ny = dmd.DevInquire(ALP_DEV_DISPLAY_HEIGHT)
        avail = dmd.DevInquire(ALP_AVAIL_MEMORY)
        print(f"ALP board initialized. DMD resolution: {Nx} x {Ny}, {avail} frames free")
        print(f"  [timing] ALP init: {_ms(t_init)}")

        # 1) Determine the max number and upload frames 0..max ONCE.
        max_index = prompt_max(default_max)
        n_frames = max_index + 1
        if n_frames > avail:
            raise RuntimeError(f"Need {n_frames} frames but only {avail} available.")

        t_render0 = time.perf_counter()
        patterns = render_numbers(range(n_frames), Nx=Nx, Ny=Ny)
        t_render = time.perf_counter() - t_render0

        t_alloc0 = time.perf_counter()
        dmd.SeqAlloc(nbImg=n_frames, bitDepth=1)
        dmd.SeqControl(ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED)
        t_alloc = time.perf_counter() - t_alloc0

        t_concat0 = time.perf_counter()
        concat = np.concatenate([(p.astype(np.uint8) * 255) for p in patterns])
        t_concat = time.perf_counter() - t_concat0

        t_put0 = time.perf_counter()
        dmd.SeqPut(imgData=concat)                      # <-- the one-time USB upload
        t_put = time.perf_counter() - t_put0

        min_pt = dmd.SeqInquire(ALP_MIN_PICTURE_TIME)
        print(f"  Uploaded frames 0..{max_index} to DDR (numbers 0..{max_index}). "
              f"Min picture time: {min_pt} us")
        print(f"  [timing] render {n_frames} frames: {_ms(t_render)} | "
              f"alloc: {_ms(t_alloc)} | concat: {_ms(t_concat)} | "
              f"upload (SeqPut): {_ms(t_put)} "
              f"({_ms(t_put / n_frames)}/frame)")
        print("  Frames now stay in DDR — only the FLUT order changes below.\n")

        # 2-5) Interactive: type order -> program FLUT -> send triggers -> repeat.
        first_time = True
        preset = preset_order
        while True:
            order = prompt_order(max_index, preset)
            preset = None
            if order is None:
                break

            t = program_flut(dmd, order, min_pt, first_time)
            if not first_time:
                reprogram_times.append(t["total"])
            first_time = False

            print(f"  FLUT programmed with {len(order)} entries: {order}")
            print(f"  [timing] change order: total {_ms(t['total'])} "
                  f"(halt {_ms(t['halt'])} | write FLUT {_ms(t['write_flut'])} | "
                  f"arm {_ms(t['arm'])})")
            print("  Armed in SLAVE mode (rising edge). Send TTL pulses to 'Trigger IN' now.")
            print("  Expected number sequence per trigger: "
                  + " -> ".join(str(v) for v in order) + " -> (wraps to start)")
            print("  (Type a new order to reprogram — frames are NOT re-uploaded.)")

        print("\nTest 2 complete.")
        _print_timing_summary(t_init, t_render, t_put, n_frames, reprogram_times)

    finally:
        try:
            dmd.Halt()
            if dmd._lastDDRseq is not None:
                dmd.FreeSeq()
            dmd.Free()
        except Exception as e:
            print(f"Cleanup warning: {e}")
        print("DMD released.")


def _print_timing_summary(t_init, t_render, t_put, n_frames, reprogram_times):
    """Print aggregate timing statistics for the run."""
    print("\n" + "-" * 60)
    print("  TIMING SUMMARY")
    print("-" * 60)
    print(f"  ALP init:                    {_ms(t_init)}")
    print(f"  Render {n_frames:>2} frames:            {_ms(t_render)}")
    print(f"  One-time upload (SeqPut):    {_ms(t_put)} ({_ms(t_put / n_frames)}/frame)")
    if reprogram_times:
        arr = np.array(reprogram_times)
        print(f"  Change order (reprogram):    "
              f"min {_ms(arr.min())} | mean {_ms(arr.mean())} | max {_ms(arr.max())} "
              f"(n={len(reprogram_times)})")
    else:
        print("  Change order (reprogram):    (only one order programmed; no reprogram timed)")
    print("-" * 60)
    print("  Key comparison: the one-time upload is the expensive step; changing the")
    print("  FLUT order is far cheaper and needs NO re-upload — that is the point of the FLUT.")
    print("-" * 60)


def main():
    ap = argparse.ArgumentParser(
        description="DMD Preliminary Test 2: trigger + reprogrammable FLUT order")
    ap.add_argument("--max", type=int, default=10,
                    help="default highest number to upload (frames 0..max); you can also enter it interactively")
    ap.add_argument("--order", type=str, default=None,
                    help="optional initial FLUT order, e.g. '3,4,1,2,5,4,6,4,2'")
    ap.add_argument("--simulation", action="store_true", help="no hardware; exercise the flow")
    args = ap.parse_args()

    print("=" * 64)
    print("  DMD Preliminary Test 2 — Trigger + reprogrammable FLUT order")
    print("=" * 64)

    if args.simulation or not ALP_AVAILABLE:
        if not ALP_AVAILABLE and not args.simulation:
            print("ALP4lib not found — falling back to SIMULATION mode.\n")
        run_simulation(args.max, args.order)
        return 0

    run_hardware(args.max, args.order)
    return 0


if __name__ == "__main__":
    sys.exit(main())
