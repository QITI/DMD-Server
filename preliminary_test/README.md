# Preliminary Tests — DMD ↔ PC Connection

Two minimal tests to confirm the Vialux ALP 4.3 / DLP9000XUV is connected and
controllable from the PC. **They test the connection only** — no holograms, no
GPU, no aberration maps. The patterns are just numbers (0, 1, 2, … 10) drawn by
the mirrors so you can see, by eye or on a camera at the image plane, that the
DMD is receiving and switching frames.

```
preliminary_test/
├── digit_patterns.py            # renders numbers 0..10 as binary DMD frames (numpy only)
├── test_01_upload_patterns.py   # Test 1: upload + display each number, 5 s apart
├── test_02_trigger_flut.py      # Test 2: upload all + FLUT + advance via external TTL trigger
└── README.md                    # this file
```

## Requirements

- Windows PC with the Vialux ALP 4.3 SDK and `ALP4lib` installed.
- USB 3.0 cable PC → Vialux V-module.
- `numpy` (required). `imageio` (optional, only for saving PNG previews in
  simulation mode).

No GPU / pySLM2 needed — these are pure connection checks.

## Test 1 — Upload patterns (`test_01_upload_patterns.py`)

Uploads a numbered pattern, displays it in master mode, waits 5 seconds, then
uploads the next one — cycling 0 → 1 → 2 → … → 10.

```bash
python test_01_upload_patterns.py            # 5 s per number, 0..10
python test_01_upload_patterns.py --dwell 3  # 3 s per number
python test_01_upload_patterns.py --max 5    # only 0..5
python test_01_upload_patterns.py --simulation   # no hardware; saves PNG previews to ./preview/
```

**Pass criterion:** the numbers appear on the DMD/camera and change every 5 s.
That confirms the PC → DMD upload+display path over USB.

**Wiring:** just the USB cable.

## Test 2 — Trigger + reprogrammable FLUT (`test_02_trigger_flut.py`)

Uploads the numbered frames to DDR **once**, then lets you type **any playback
order** (e.g. `3,4,1,2,5,4,6,4,2`), programs it into the **FLUT**, and arms the
board in **slave mode** (rising-edge trigger). Each external TTL pulse advances
one FLUT entry in hardware. You can then type a **new order and reprogram the
FLUT without re-uploading the frames** — that is the whole point of the FLUT and
the thing this test verifies.

Interactive flow:

```
1. Determine the max number   -> upload frames 0..max to DDR (once)
2. Type an order              -> program FLUT, arm slave mode
3. Send TTL triggers          -> each rising edge advances one FLUT entry
4. Type a new order           -> reprogram FLUT (NO re-upload), re-arm
5. Repeat 3-4, or 'q' to quit
```

With order `[3,4,1,2,5,4,6,4,2]`:

```
trigger 1 → FLUT[0]=3 → number 3
trigger 2 → FLUT[1]=4 → number 4
trigger 3 → FLUT[2]=1 → number 1
...
trigger 9 → FLUT[8]=2 → number 2  → wraps to FLUT[0]=3
```

Frames 0..max stay in DDR the entire time; only the order changes.

```bash
python test_02_trigger_flut.py                          # prompts for max, then orders
python test_02_trigger_flut.py --max 6                  # default upload frames 0..6
python test_02_trigger_flut.py --order 3,4,1,2,5,4,6,4,2  # use this order first
python test_02_trigger_flut.py --simulation             # no hardware; exercise the flow
```

**Pass criterion:** for a given order, each TTL rising edge on the Vialux
**Trigger IN** advances the displayed number to the next entry of that order; and
typing a different order changes the sequence **without** re-uploading frames.
That confirms the USB upload path, the FLUT reordering, and the real-time trigger
path used by the experiment.

Reprogramming briefly `Halt()`s and re-`Run()`s the sequence (so triggering
pauses for the ~ms it takes to rewrite the FLUT), but it never frees or re-uploads
the frames.

> **Trigger → display latency & jitter.** The number does not change the instant you
> send the pulse. Per the ALP-4.3 API, the frame transition happens **between
> `1×PictureTime` and `2×PictureTime` after the trigger edge** (`PictureTime` floor
> ≈ 77 µs), because the trigger is asynchronous to the DMD's internal frame clock.
> So expect the displayed number to update **~77–154 µs** after each pulse, with up
> to ~77 µs of shot-to-shot jitter — normal, not a fault. In a real experiment the
> kernel must wait this worst case (~180 µs) before gating the addressing laser; see
> "Trigger Latency & Jitter" in [`../README.md`](../README.md).

**Wiring:**

```
PC ── USB 3.0 ──────────► Vialux V-module
Trigger source ── BNC ──► Vialux "Trigger IN"
```

The trigger source is normally the ARTIQ Kasli TTL (`DMD_TTL`, e.g. `ttl7`), but
any pulse generator / function generator producing a clean rising edge (~3.3 V)
works for a bench check. Send one pulse per advance. Because the FLUT counter only
increments by +1 per trigger, this is exactly the mechanism described in
[`../../discussion.md`](../../discussion.md) (Part IV/VI) and
[`../README.md`](../README.md).

## Timing analysis

Both scripts use `time.perf_counter()` to time every step and print millisecond
figures live plus a summary at the end. This tells you exactly where time goes —
in particular that the **USB upload** dominates while **changing the FLUT order**
is cheap.

**Test 1** reports, per number: `free` (release previous seq) · `alloc`
(`SeqAlloc`+`SeqControl`) · `upload` (`SeqPut`, the USB transfer) · `arm`
(`ProjControl`+`SetTiming`+`Run`) · `total`. The end summary gives ALP init,
render time, and min/mean/max per-frame upload+arm (the 5 s display dwell is
excluded).

**Test 2** reports:
- one-time setup: ALP init, render, `SeqAlloc`, `concat`, and `SeqPut`
  (upload) with a per-frame figure;
- for every order you enter: `change order: total …(halt … | write FLUT … | arm …)`;
- an end summary comparing the one-time upload against min/mean/max reprogram
  time, making the FLUT's advantage explicit (reorder without re-upload).

Example (numbers illustrative; real values depend on the PC/USB/board):

```
  [timing] ALP init: 420.0 ms
  [timing] render 11 frames: 22.0 ms | alloc: 3.1 ms | concat: 9.0 ms | upload (SeqPut): 180.0 ms (16.4 ms/frame)
  ...
  [timing] change order: total 6.2 ms (halt 1.1 ms | write FLUT 3.0 ms | arm 2.1 ms)
  ------------------------------------------------------------
    TIMING SUMMARY
    One-time upload (SeqPut):    180.0 ms (16.4 ms/frame)
    Change order (reprogram):    min 5.9 ms | mean 6.4 ms | max 7.1 ms (n=3)
```

The two hardware-timed quantities you asked about are labelled directly:
**"upload (SeqPut)"** = time to upload the frames, **"change order: total"** =
time to reprogram the FLUT order. In simulation mode only the render timing is
shown (there is no hardware to upload to).

## Notes

- **ALP4lib FLUT bug:** programming the FLUT calls `ProjControlEx`. Some ALP4lib
  versions ship a typo (`AlpProjContro` instead of `AlpProjControlEx`). If Test 2
  raises an `AttributeError`/error there, apply the one-line patch described in
  [`../README.md`](../README.md) ("ALP4lib bug fix").
- **Simulation mode** (`--simulation`, or automatically if `ALP4lib` is missing)
  runs the logic without hardware: Test 1 saves PNG previews of each number to
  `./preview/`, and Test 2 prints the upload + FLUT plan. Use it to sanity-check
  the patterns before going to the bench.
- These scripts use `ALP4` directly (not the NDSP server) because the point is to
  validate the raw hardware link. Once both pass, bring up the full
  [`../dmd_server.py`](../dmd_server.py).
```
