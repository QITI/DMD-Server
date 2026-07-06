# DMD NDSP Server

An ARTIQ-compatible Network Device Support Protocol (NDSP) server for the Vialux DLP9000XUV Digital Micromirror Device. Designed for the Bloodstone trapped-ion quantum processor at the QITI lab, University of Waterloo.

This server runs on a Windows PC with GPU and USB access to the Vialux ALP 4.3 controller board. It exposes RPC methods for hologram computation, frame memory management, triggered sequence control, aberration calibration, and beam characterization — all accessible from ARTIQ experiments via the standard sipyco protocol.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│   ┌───────────────────────────────────────────────────────────────────────────┐     │
│   │                         ARTIQ Host PC                                     │     │
│   │                                                                           │     │
│   │   ┌────────────────────────────────┐    ┌───────────────────────────┐     │     │
│   │   │       Experiment .py           │    │      device_db.py         │     │     │
│   │   │                                │    │                           │     │     │
│   │   │  def prepare(self):            │    │  device_db["dmd"] = {     │     │     │
│   │   │    self.dmd.prepare_flut_...() │    │    "type":"controller",   │     │     │
│   │   │                                │    │    "host":"192.168.1.X",  │     │     │
│   │   │  @kernel                       │    │    "port": 12345          │     │     │
│   │   │  def run(self):                │    │  }                        │     │     │
│   │   │    self.dmd_advance()          │    │                           │     │     │
│   │   └──────────┬─────────────────────┘    └───────────────────────────┘     │     │
│   │              │                                                            │     │
│   └──────────────┼────────────────────────────────────────────────────────────┘     │
│                  │                                                                  │
│        ┌─────────▼─────────────────────────────────────────────────┐                │
│        │                   Kasli FPGA (Zynq SoC)                   │                │
│        │                                                           │                │
│        │   @kernel dmd_advance():                                  │                │
│        │       self.DMD_TTL.pulse(1*us)  ──────────────────────┐   │                │
│        │       delay(100*us)                                   │   │                │
│        │                                                       │   │                │
│        │   Optional: DMD_SYNCH input ◄────────────────────┐    │   │                │
│        └──────────────────────────────────────────────────┼────┼───┘                │
│                                                           │    │                    │
└───────────────────────────────────────────────────────────┼────┼────────────────────┘
                                                            │    │
                        BNC (Synch OUT)                     │    │  BNC (Trigger IN)
                                                            │    │
┌───────────────────────────────────────────────────────────┼────┼────────────────────┐
│                                                           │    │                    │
│   ┌───────────────────────────────────────────────────────┴────▼──────────────┐     │
│   │                     Vialux ALP 4.3 Board                                  │     │
│   │                                                                           │     │
│   │   Trigger IN ──► FPGA ──► DDR RAM ──► DLPC910 ──► DLP9000XUV              │     │
│   │                   │                                  (DMD chip)           │     │
│   │                   │         16,000+                   2560×1600           │     │
│   │                   │         binary                    micromirrors        │     │
│   │                   │         frames                    7.56 μm pitch       │     │
│   │                   │                                                       │     │
│   │   Synch OUT ◄─────┘   FLUT (reorder table, 4096 entries)                  │     │
│   │                                                                           │     │
│   └────────────────────────────────────────────────┬──────────────────────────┘     │
│                                                    │ USB 3.0                        │
│                                                    │                                │
│   ┌────────────────────────────────────────────────▼──────────────────────────┐     │
│   │                     GPU PC (Windows)                                      │     │
│   │                                                                           │     │
│   │   dmd_server.py                                                           │     │
│   │   ├── sipyco RPC (port 12345)                                             │     │
│   │   ├── pySLM2 (hologram engine)                                            │     │
│   │   ├── ALP4lib (hardware driver)                                           │     │
│   │   ├── TensorFlow GPU (IFTA acceleration)                                  │     │
│   │   └── HologramCache (avoid recomputation)                                 │     │
│   │                                                                           │     │
│   └───────────────────────────────────────────────────────────────────────────┘     │
│                                                                                     │
│   GPU PC also has: TCP/IP network ◄──── sipyco RPC ────► ARTIQ Host                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Capability Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DMD Server Capabilities                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │   ION ADDRESSING    │  │  CALIBRATION        │  │  CROSSTALK SUPPRESSION  │  │
│  │   (Primary)         │  │                     │  │                         │  │
│  │                     │  │  • Aberration maps  │  │  • Secondary grating    │  │
│  │  • IFTA holograms   │  │    (Φ₀, Φ₁, Φ₂)     │  │    (phase/amp scan)     │  │
│  │  • Random method    │  │  • Focal length cal │  │  • Double-pass pupil    │  │
│  │  • Multi-ion        │  │  • HDR imaging      │  │    (IP1 region control) │  │
│  │  • Beam waist ctrl  │  │  • Camera coord     │  │  • Scan sequences       │  │
│  │                     │  │                     │  │                         │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │   SEQUENCE CONTROL  │  │  MEMORY & CACHE     │  │  DIAGNOSTICS            │  │
│  │                     │  │                     │  │                         │  │
│  │  • Upload sequence  │  │  • DDR: 16k frames  │  │  • Board temperature    │  │
│  │  • FLUT reordering  │  │  • Hologram cache   │  │  • Frame counter        │  │
│  │  • Slave mode arm   │  │    (hash-keyed)     │  │  • Memory status        │  │
│  │  • Synch OUT config │  │  • Auto-invalidate  │  │  • Mode reporting       │  │
│  │  • TTL triggering   │  │    on aberr change  │  │  • Device info          │  │
│  │                     │  │                     │  │                         │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Physics and Theory

### Why a DMD? — Fourier Holography for Individual Ion Addressing

A lens performs an optical Fourier transform between its front focal plane (Fourier Plane, FP) and back focal plane (Image Plane, IP). The DMD sits at the FP. The ions live at a plane conjugate to the IP.

```
                        FP (DMD)                        IP (ions)
                   ┌──────────────┐               ┌──────────────┐
  Collimated       │              │   Fourier     │              │
  369 nm beam  ──► │  Binary      │ ──lens────►   │  Focused     │
                   │  hologram    │   (f=250mm)   │  addressing  │
                   │              │               │  beam        |
                   └──────────────┘               └──────────────┘

  Spatial frequency pattern                    Spatial position
  (grating on DMD)                             (beam at ion location)
```

The relationship: each spatial frequency component on the DMD maps to a specific position at the image plane. By creating a carefully designed binary amplitude grating, we engineer the wavefront so the first diffraction order forms a tightly focused Gaussian beam at a chosen ion position.

**Why this matters:** Unlike a simple focused beam, holographic addressing allows aberration correction, beam shaping, and repositioning — all by reprogramming the DMD pattern, with no moving optics.

---

### The Amplitude Grating — Phase and Amplitude from Binary Pixels

A DMD mirror can only be ON (+12°) or OFF (−12°). This is binary amplitude modulation. To achieve full phase AND amplitude control, we use a carrier grating:

```
  Grating function:
                    |F(k)|
  G(k) = η × ────────── × ½ × [ cos(x₀·k + Φ_out(k) − Φ_in(k)) + 1 ]
                   E_in(k)

  Where:
    • x₀ = λf / period      → sets beam position (first-order angle)
    • Φ_out(k)               → target beam phase
    • Φ_in(k)                → aberration correction (cancels in first order!)
    • |F(k)| / E_in(k)       → amplitude shaping
```

The inverse Fourier transform of this grating produces three diffraction orders:
- **m=0 (zeroth):** Undiffracted, carries residual aberration → blocked
- **m=+1 (first):** The target beam profile, **aberration-free** → used
- **m=−1 (negative first):** Complex conjugate, 2× aberration → blocked

**Significance:** This is why the hologram can compensate for arbitrary optical aberrations — the math guarantees the first-order beam is aberration-free as long as Φ_in is measured correctly.

---

### IFTA — Iterative Fourier Transform Algorithm

The continuous grating G(k) has values between 0 and 1, but DMD mirrors are binary. Binarization creates artifacts. IFTA iteratively minimizes these artifacts within a defined signal window:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                      IFTA Loop (N iterations)                   │
  │                                                                 │
  │   Start: unbinarized (ideal) hologram                           │
  │     │                                                           │
  │     ▼                                                           │
  │   BINARIZE at FP                                                │
  │   threshold: t = i/(2N), progressively sharper each iteration   │
  │     │                                                           │
  │     ▼                                                           │
  │   PROPAGATE to IP (FFT)                                         │
  │   Compare beam profile within signal window D                   │
  │     │                                                           │
  │     ▼                                                           │
  │   CORRECT within signal window                                  │
  │   Replace with ideal target (outside: leave as-is)              │
  │     │                                                           │
  │     ▼                                                           │
  │   PROPAGATE back to FP (IFFT) → next iteration                  │
  │                                                                 │
  │   Result: binary hologram with minimized artifacts in window    │
  └─────────────────────────────────────────────────────────────────┘
```

**Performance:**
- Random method (no iteration): IX ~ 10⁻³, computes in ~100 ms
- IFTA (2000 iterations): IX < 10⁻⁴ within signal window, ~6 s on GPU

**Significance:** IFTA is what makes sub-10⁻⁴ intensity crosstalk possible. The `signal_window` parameter defines where beam quality is optimized — outside it, errors are uncontrolled (hence the need for the double-pass pupil for long-range suppression).

---

### Aberration Compensation — In-Situ Phase Map Extraction

Real optics introduce wavefront aberrations that create sidelobes raising crosstalk. The DMD itself is used to measure and correct these:

```
  MEASUREMENT:

  1. Turn on two patches on DMD (reference + scanning)

     DMD (FP):              Camera (IP):
     ┌────────────┐         ┌────────────┐
     │  □      □  │   →     │ ║║║║║║║║║║ │  (interference fringes)
     │ ref   scan │         │ ║║║║║║║║║║ │
     └────────────┘         └────────────┘

  2. Each patch → near-plane-wave at IP → they interfere
     I(x) = A₁² + A₂² + 2A₁A₂ cos((k₁−k₂)·x + φ₁−φ₂)

  3. Extract phase difference from fringe pattern
  4. Scan patch across grid → build 2D phase map

  CORRECTION:

  Maps obtained in stages:
    Φ₀: main aberration (input path) — typically 10–20π peak-to-peak
    Φ₁: first-order path            — typically 4π peak-to-peak
    Φ₂: second-pass (double-pass only)

  Encode: input_profile = exp(1j × (Φ₀ + Φ₁))
  First-order beam emerges aberration-free (math guarantees cancellation).
  After compensation: residual < 0.2λ RMS (~50× improvement).
```

**Significance:** Without this, the beam has severe sidelobes. With it, diffraction-limited quality. Must be re-measured when optics are realigned or temperature drifts.

---

### Secondary Grating — Nearest-Neighbor Crosstalk Suppression

Even after IFTA, the nearest neighbor (at 4w ≈ 4 μm) sees ~10⁻⁴ intensity. A secondary grating creates destructive interference at that location:

```
  E_total at neighbor = Ã₁·e^(iφ₁) + Ã₂·e^(iφ₂)

  I = Ã₁² + Ã₂² + 2Ã₁Ã₂ cos(φ₁ − φ₂)

  When φ₁ − φ₂ = π and Ã₁ ≈ Ã₂:  I_min = (Ã₁ − Ã₂)² → 0

  On DMD: secondary grating in a small window (3×400 pixels)
  Periodicity = cos(π/4) × λ × f / (offset × pixel_size)
  Optimize: scan phase 0→4π, then fine-tune amplitude.

  Result: ~6 dB suppression at nearest neighbor.
```

**Significance:** Approaches the inter-ion scattering limit (~10⁻⁵). Can target any neighbor. Multiple gratings can suppress multiple positions simultaneously.

---

### Double-Pass Pupil — Long-Range Crosstalk Suppression

Beyond ~10w, intensity saturates at ~10⁻⁴. A physical aperture at IP1 clips the tails:

```
  DMD split: FP hologram (cols 0–1960) | IP1 pupil (cols 2060–2560)

  Light path:
    Input → FP (hologram) → retro-reflector → back to DMD at IP1
    → only mirrors inside pupil radius are ON → tails blocked
    → relay to ion plane

  Without pupil: IX ~ 10⁻⁴ everywhere beyond signal window
  With pupil:    IX ~ 10⁻⁶ beyond 14w (camera noise floor)
```

**Significance:** For 30 ions, reduces cumulative error from ~3% to ~0.3%. Essential for multi-round error correction.

---

### HDR Imaging — Measuring Across 6 Orders of Magnitude

Single exposure: ~10³ dynamic range. To verify IX = 10⁻⁶, combine multiple exposures:

```
  120 μs → 1.2 ms → 12 ms → 120 ms → 1.2 s → 12 s
  (peak)   (mid)    (faint)  (tail)   (far)   (floor)

  Background-subtracted and stitched → profile spanning 10⁰ to 10⁻⁶.
```

**Significance:** The primary diagnostic for verifying hologram quality meets targets.

---

### Why It All Matters — MCMR Fidelity Summary

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Method                     │  IX        │  P_AQM     │  Fidelity   │
  ├─────────────────────────────┼────────────┼────────────┼─────────────┤
  │  IFTA alone                 │  < 10⁻⁴    │  < 4×10⁻³  │  99.6%      │
  │  + secondary grating        │  ~ 10⁻⁴·⁹  │  ~ 1×10⁻³  │  99.9%      │
  │  + double-pass pupil        │  < 10⁻⁶    │  < 10⁻⁵    │  >99.99%    │
  │  Fundamental limit          │  ~ 10⁻⁵    │  ~ 2×10⁻⁵  │  99.998%    │
  └─────────────────────────────┴────────────┴────────────┴─────────────┘

  Surface code threshold: P_AQM < 0.57%  ← all methods meet this.
  Bloodstone target:      P_AQM < 0.1%   ← requires secondary grating.
```

---

## Data Flow: Experiment Lifecycle

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         EXPERIMENT LIFECYCLE                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─── STARTUP (once per session) ────────────────────────────────────┐     │
│  │                                                                   │     │
│  │  self.dmd.load_aberration_maps("phi_zeroth.npy","phi_first.npy")  │     │
│  │       │                                                           │     │
│  │       ▼                                                           │     │
│  │  Server loads .npy files, computes aberration hash                │     │
│  │                                                                   │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                             │                                              │
│                             ▼                                              │
│  ┌─── PREPARE (per experiment, host-side Python) ────────────────────┐     │
│  │                                                                   │     │
│  │  self.dmd.prepare_flut_sequence(                                  │     │
│  │      ion_positions_list = [[(5e-6,0)], [(12e-6,0)], [(0,0)]],     │     │
│  │      playback_order = [0, 1, 0, 2, 1, 0, ...],                    │     │
│  │      beam_waist = 1e-6,                                           │     │
│  │      method = "ifta"                                              │     │
│  │  )                                                                │     │
│  │       │                                                           │     │
│  │       ▼                                                           │     │
│  │  ┌──────────────────────────────────────────────────────────┐     │     │
│  │  │  For each unique position:                               │     │     │
│  │  │    Cache hit? → use cached hologram                      │     │     │
│  │  │    Cache miss? → compute_hologram() [GPU, ~6s IFTA]      │     │     │
│  │  │                                                          │     │     │
│  │  │  Upload all unique frames to DDR RAM [USB, ~10ms/frame]  │     │     │
│  │  │  Program FLUT with playback_order [USB, ~1ms]            │     │     │
│  │  │  Arm slave mode [USB, ~1ms]                              │     │     │
│  │  └──────────────────────────────────────────────────────────┘     │     │
│  │                                                                   │     │
│  │  Returns: {n_unique_frames: 3, flut_entries: 6, prep_time: 20s}   │     │
│  │                                                                   │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                             │                                              │
│                             ▼                                              │
│  ┌─── RUN (real-time, @kernel on Kasli FPGA) ────────────────────────┐     │
│  │                                                                   │     │
│  │  ┌─── Per-shot loop (repeats at ~3 ms/shot) ──────────────────┐   │     │
│  │  │                                                            │   │     │
│  │  │  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐    │   │     │
│  │  │  │ Cooling │  │  Prep   │  │   DMD    │  │ Detection  │    │   │     │
│  │  │  │  ~1 ms  │→ │ ~100 μs │→ │  ~100 μs │→ │  ~20 μs    │    │   │     │
│  │  │  └─────────┘  └─────────┘  └────┬─────┘  └────────────┘    │   │     │
│  │  │                                  │                         │   │     │
│  │  │                    DMD_TTL.pulse(1*us)                     │   │     │
│  │  │                    delay(100*us)                           │   │     │
│  │  │                         │                                  │   │     │
│  │  │         ┌───────────────▼──────────────────────┐           │   │     │
│  │  │         │  Vialux hardware (no PC involved):   │           │   │     │
│  │  │         │  1. FPGA reads FLUT[counter]         │           │   │     │
│  │  │         │  2. Fetches frame from DDR (~77 μs)  │           │   │     │
│  │  │         │  3. Mirrors flip (~10-20 μs)         │           │   │     │
│  │  │         │  4. Counter += 1                     │           │   │     │
│  │  │         │  5. Synch OUT pulse (optional)       │           │   │     │
│  │  │         └──────────────────────────────────────┘           │   │     │
│  │  │                                                            │   │     │
│  │  └────────────────────────────────────────────────────────────┘   │     │
│  │                                                                   │     │
│  │  No PC communication during this phase. Fully deterministic.      │     │
│  │                                                                   │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## FLUT Sequencing Model

```
                    UNIQUE FRAMES IN DDR
                    ━━━━━━━━━━━━━━━━━━━━
                    Frame 0: hologram(ion 5)
                    Frame 1: hologram(ion 12)
                    Frame 2: hologram(ion 0)


        FLUT (programmed before experiment)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Entry 0 → Frame 0 (ion 5)      ◄── Trigger 1 displays this
        Entry 1 → Frame 1 (ion 12)     ◄── Trigger 2 displays this
        Entry 2 → Frame 0 (ion 5)      ◄── Trigger 3 displays this
        Entry 3 → Frame 2 (ion 0)      ◄── Trigger 4 displays this
        Entry 4 → Frame 1 (ion 12)     ◄── Trigger 5 displays this
        Entry 5 → Frame 0 (ion 5)      ◄── Trigger 6 displays this
        ...
        (up to 4096 entries, wraps around)


        KERNEL (fires triggers blindly)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Shot 1: dmd_advance() → Trigger 1 → FLUT[0] → Frame 0 → ion 5
        Shot 2: dmd_advance() → Trigger 2 → FLUT[1] → Frame 1 → ion 12
        Shot 3: dmd_advance() → Trigger 3 → FLUT[2] → Frame 0 → ion 5
        Shot 4: dmd_advance() → Trigger 4 → FLUT[3] → Frame 2 → ion 0
        ...

        ┌─────────────────────────────────────────────────────────┐
        │  KEY POINT: The kernel does NOT know which ion it's     │
        │  addressing. It just fires triggers. The FLUT was       │
        │  programmed by prepare() to match the shot order.       │
        └─────────────────────────────────────────────────────────┘
```

---

## Hologram Computation Pipeline

```
    User specifies:                      Server computes:
    ━━━━━━━━━━━━━━━                      ━━━━━━━━━━━━━━━━

    Ion position (x, y)                  Output profile (HermiteGaussian)
         │                                    │
         │                                    ▼
    Beam waist (w)                       Composite profile (sum for multi-ion)
         │                                    │
         │                                    ▼
    Aberration maps ──────────────────►  Input profile = exp(1j * aberration)
    (Φ₀ + Φ₁ from disk)                       │
         │                                    │
         │                                    ▼
    Method: "ifta" or "random"           ┌─────────────────────────────────┐
         │                               │  pySLM2.DLP9000                 │
         │                               │  .calculate_dmd_state(          │
         │                               │      input_profile,             │
         └──────────────────────────────►│      output_profile,            │
                                         │      method, N, signal_window   │
                                         │  )                              │
                                         └──────────────┬──────────────────┘
                                                        │
                                                        ▼
                                         Binary state: bool[1600 × 2560]
                                                        │
                                    ┌───────────────────┼───────────────────┐
                                    │                   │                   │
                                    ▼                   ▼                   ▼
                              Store in cache     Upload to DDR       Return to caller
                              (hash-keyed)       (ALP SeqPut)
```

---

## Crosstalk Suppression Modes

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   MODE 1: IFTA ONLY (baseline)                                               │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                               │
│                                                                              │
│   DMD state: [═══════════════ primary IFTA grating ═══════════════════]      │
│              ◄──────────── 2560 pixels ────────────────────────────────►     │
│                                                                              │
│   Result: IX < 10⁻⁴ within signal window                                     │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MODE 2: IFTA + SECONDARY GRATING (nearest-neighbor suppression)            │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           │
│                                                                              │
│   DMD state: [══════ primary grating ══════[SG]══════════════════════]       │
│                                             ↑                                │
│                                    secondary grating                         │
│                                    (3×400 pixel window)                      │
│                                    phase: 0→4π (scanned)                     │
│                                    amplitude: 0→1                            │
│                                                                              │
│   Result: IX reduced by ~6 dB at nearest neighbor (4w)                       │
│                                                                              │
│   Server methods:                                                            │
│     configure_secondary_grating(phase, amplitude, position_offset)           │
│     scan_secondary_grating(phase_steps=20)                                   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MODE 3: DOUBLE PASS (long-range suppression)                               │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                              │
│                                                                              │
│   DMD regions:                                                               │
│   ◄─── FP (cols 0–1960) ───►◄─ buffer ─►◄── IP1 pupil (cols 2060–2560) ──►   │
│   [══ IFTA hologram ════════]  [░░░░░░]  [○○○ circular pupil ○○○○○○○○○]      │
│                                                     ↑                        │
│                                           center, radius (tunable)           │
│                                                                              │
│   Light path: FP → retro-reflector → IP1 (pupil clips tails) → relay → IP2   │
│                                                                              │
│   Result: IX < 10⁻⁶ beyond 14w (third nearest neighbor)                      │
│                                                                              │
│   Server methods:                                                            │
│     configure_double_pass_pupil(center_row, center_col, radius)              │
│     compute_hologram(..., double_pass=True)                                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Timing Diagram: One Shot Cycle

```
Time ──────────────────────────────────────────────────────────────────────────►

Kasli kernel:
 ┌──────────┐ ┌────────┐ ┌──┐          ┌────────────┐ ┌──────────────┐
 │  Cooling │ │  Pump  │ │  │ (delay)  │ AOM gate   │ │  Detection   │
 │  1 ms    │ │ 10 μs  │ │T │  100 μs  │  1–500 μs  │ │  ~20 μs      │
 └──────────┘ └────────┘ └──┘          └────────────┘ └──────────────┘
                          ↑ TTL pulse
                          │
DMD hardware:            ┌──────────────────┐
                         │ Frame transfer   │
                         │ 77 μs            │
                         │ + mirror settle  │
                         │ 20 μs            │
                         └──────────────────┘
                                            ↑
                                     Beam stable here
                                     AOM gates ON

AOM (addressing laser):
 OFF ────────────────────────────────┌──────┐──────────────── OFF
                                     │  ON  │
                                     └──────┘
                                 (only after mirrors stable)

 ◄────────── ~1.2 ms ──────────────►◄──── ~0.5 ms ────►◄── ~1 ms ──►
              state prep                  addressing         readout
```

---

## Installation

### Prerequisites

- Windows 10/11 (required for Vialux ALP DLL)
- Python 3.9+
- NVIDIA GPU with CUDA (for IFTA acceleration)
- Vialux ALP 4.3 SDK installed (provides `alp4395.dll`)
- USB 3.0 connection to the Vialux V-9001 module

### Install dependencies

```bash
pip install sipyco numpy scipy matplotlib

# pySLM2 (from the QITI repo)
cd /path/to/pySLM2
pip install -e .

# ALP4lib (from the QITI repo)
pip install ALP4lib

# TensorFlow with GPU support (for IFTA)
pip install tensorflow[and-cuda]
```

### ALP4lib bug fix (required for FLUT)

```python
# In ALP4.py ProjControlEx method, change:
self._checkError(self._ALPLib.AlpProjContro(self.ALP_ID, ...))
# To:
self._checkError(self._ALPLib.AlpProjControlEx(self.ALP_ID, ...))
```

---

## Quick Start

```bash
# With hardware:
python dmd_server.py --port 12345

# Development mode (no hardware):
python dmd_server.py --port 12345 --simulation
```

### Verify

```bash
sipyco_rpctool 192.168.1.XXX 12345 list-targets   # → dmd
sipyco_rpctool 192.168.1.XXX 12345 call ping       # → True
sipyco_rpctool 192.168.1.XXX 12345 call get_status
```

---

## ARTIQ Registration

```python
# device_db.py
device_db["dmd"] = {
    "type": "controller",
    "host": "192.168.1.XXX",  # GPU PC IP
    "port": 12345
}
```

```python
# config.py mapping_dict addition
"DMD_TTL": "ttl7",   # TTL output → Vialux Trigger IN (BNC)
"dmd": "dmd",        # NDSP controller
```

---

## RPC API Reference

### Core Ion Addressing

| Method | Description |
|--------|-------------|
| `prepare_flut_sequence(positions_list, playback_order, beam_waist, method)` | Compute + upload + FLUT in one call |
| `prepare_ion_sequence(positions_list, beam_waist, method)` | Compute + upload (linear sequence) |
| `compute_hologram(positions, beam_waist, method, N, r, double_pass)` | Compute single hologram |

### Frame & Sequence Control

| Method | Description |
|--------|-------------|
| `upload_single(dmd_state)` | Upload and display one frame (static) |
| `upload_sequence(dmd_states)` | Upload N frames, arm slave mode |
| `program_flut(frame_order)` | Program FLUT with arbitrary playback order |
| `arm_slave_mode(trigger_edge)` | Arm for TTL triggers |
| `display_static(dmd_state)` | Continuous display (alignment) |
| `halt()` | Stop active sequence |

### Calibration & Aberration

| Method | Description |
|--------|-------------|
| `load_aberration_maps(zeroth_path, first_path, second_path)` | Load .npy phase maps |
| `set_aberration_maps(phi_z, phi_f, phi_s)` | Set from memory arrays |
| `get_aberration_info()` | Query loaded maps |
| `hdr_acquire(dmd_state, exposures, iterations)` | HDR imaging with FLIR camera |

### Crosstalk Suppression

| Method | Description |
|--------|-------------|
| `configure_secondary_grating(phase, amplitude, position_offset, ...)` | Enable secondary beam |
| `scan_secondary_grating(phase_steps, amplitude, position_offset, ...)` | Generate phase-scan sequence |
| `disable_secondary_grating()` | Turn off overlay |
| `configure_double_pass_pupil(center_row, center_col, radius)` | Set IP1 pupil |
| `disable_double_pass_pupil()` | Turn off pupil |

### Diagnostics & Cache

| Method | Description |
|--------|-------------|
| `ping()` | Connectivity check |
| `get_status()` | Mode, frames, FLUT, temperature |
| `get_device_info()` | Resolution, memory, model |
| `get_memory_status()` | DDR capacity/usage |
| `get_frame_counter()` | Triggers since arm |
| `configure_synch_output(pulse_width, polarity)` | Synch OUT BNC config |
| `cache_status()` | Cache entries + memory |
| `clear_cache()` | Invalidate all cached holograms |

---

## Kernel Stubs

```python
@kernel
def dmd_advance(self):
    """Advance to next FLUT entry. ~100 μs total."""
    self.DMD_TTL.pulse(1*us)
    delay(100*us)

@kernel
def dmd_select_frame(self, target_frame, current_frame, n_frames):
    """Jump to specific frame. Costs (steps × 77 μs) + 20 μs."""
    steps = (target_frame - current_frame) % n_frames
    if steps > 0:
        for i in range(steps):
            self.DMD_TTL.pulse(1*us)
            delay(76*us)
        delay(20*us)
```

---

## Experiment Example

```python
class MCMRExperiment(Bloodstone_Experiment):

    def prepare(self):
        self.init()
        result = self.dmd.prepare_flut_sequence(
            ion_positions_list=[[(5e-6, 0)], [(12e-6, 0)], [(0, 0)]],
            playback_order=[0, 1, 0, 2],
            beam_waist=1e-6,
            method="ifta"
        )
        self.n_shots = 4

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        for shot in range(self.n_shots):
            self.doppler_cooling()
            self.pumping()
            self.dmd_advance()
            self.global_pmt_detection()
```

---

## Hardware Wiring

```
┌─────────────────┐              ┌──────────────────┐
│  Kasli FPGA     │              │  Vialux ALP 4.3  │
│                 │    BNC       │                  │
│  ttl7 (OUT) ────┼─────────────►│  Trigger IN      │
│                 │              │                  │
│  ttl28 (IN)  ◄──┼──────────────│  Synch OUT       │
│                 │    BNC       │                  │
└─────────────────┘              └────────┬─────────┘
                                          │ USB 3.0
                                 ┌────────▼─────────┐
                                 │  GPU PC (Windows)│
                                 │  dmd_server.py   │
                                 └──────────────────┘
```

---

## Testing

```bash
# Terminal 1:
python dmd_server.py --port 12345 --simulation

# Terminal 2:
python test_dmd_server.py --host localhost --port 12345
```

---

## Project Structure

```
dmd-server/
├── dmd_server.py         # NDSP server (all capabilities)
├── artiq_stubs.py        # Kernel stubs + example experiment
├── test_dmd_server.py    # Integration test suite
└── README.md             # This file
```

## Related Repositories

- [pySLM2](https://github.com/QITI/pySLM2) — Hologram computation engine
- [ALP4lib](https://github.com/QITI/ALP4lib) — Vialux hardware driver
- [Bloodstone-Control-Artiq](https://github.com/QITI/Bloodstone-Control-Artiq) — Experiment control system
- [Bloodstone_DMD](https://github.com/QITI/Bloodstone_DMD) — Experiment scripts and analysis
