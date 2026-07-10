# Optical Theory of DMD-Based Holographic Beam Shaping

This document provides the complete optical and mathematical background for every capability implemented in the DMD server. It is intended as a self-contained reference for anyone working on or extending the system.

> **Primary reference.** The double-pass and Fourier-plane-multiplexing results described
> here are published in: S. Mahato and R. Islam, *"Achieving $10^{-5}$ level relative
> intensity crosstalk in optical holographic qubit addressing via a double-pass digital
> micromirror device,"* arXiv:2512.13882v1 (2025). Numerical values (crosstalk levels,
> effective aperture, window sizes, optimized parameters) in this document are taken from
> that paper. The paper characterizes the optical system up to the second image plane
> (IP2); relaying to actual ions is future work.
>
> **Foundational reference.** The core method on which this system is built —
> the DMD Fourier-holography addressing scheme, the specific high-precision IFTA, and
> *in-situ* aberration characterization using the trapped ions themselves as the
> wavefront sensor — was established in: C.-Y. Shih *et al.*, *"Reprogrammable and
> high-precision holographic optical addressing of trapped ions for scalable quantum
> control,"* npj Quantum Information **7**, 57 (2021) (and the earlier MSc thesis,
> Shih 2019). That work introduced an IFTA giving **>1 order of magnitude** accuracy
> improvement over prior hologram algorithms, demonstrated a baseline relative intensity
> crosstalk of $\sim 10^{-4}$ ($-40$ dB), and introduced a DMD+AOM scheme for
> multi-frequency addressing. The Mahato & Islam paper extends this baseline downward with
> secondary-grating multiplexing and double-pass pupil filtering.

### Headline results (from the paper)

- Baseline crosstalk from the IFTA primary beam alone: $I_X \approx -42.6$ dB ($\approx 10^{-4.3}$).
- A single secondary hologram reduces $I_X$ to $\approx -48$ dB (about **5 dB** improvement;
  up to **10 dB** suppression is possible under ideal amplitude matching).
- **Multiplexing** several secondary holograms holds $I_X \lesssim -50$ dB ($10^{-5}$) at all
  targeted sites ($\pm4w$, $\pm8w$, $\pm12w$) across the full field of view.
- **Double-pass image-plane filtering** drives $I_X$ below $-50$ dB beyond $\sim14w'$ and
  toward $-60$ dB ($10^{-6}$) beyond $\sim30w'$, approaching the detector noise floor.

---

## Table of Contents

1. [Fourier Optics Fundamentals](#1-fourier-optics-fundamentals)
2. [The Digital Micromirror Device](#2-the-digital-micromirror-device)
3. [Amplitude Grating and Diffraction Orders](#3-amplitude-grating-and-diffraction-orders)
4. [Hologram Generation Algorithms](#4-hologram-generation-algorithms)
5. [Aberration Theory and Compensation](#5-aberration-theory-and-compensation)
6. [Secondary Grating for Crosstalk Suppression](#6-secondary-grating-for-crosstalk-suppression)
7. [Double-Pass Pupil Filtering](#7-double-pass-pupil-filtering)
8. [Intensity Crosstalk and Measurement Error](#8-intensity-crosstalk-and-measurement-error)
9. [High Dynamic Range Imaging](#9-high-dynamic-range-imaging)

---

## 1. Fourier Optics Fundamentals

### 1.1 The Lens as a Fourier Transformer

```
     FOURIER PLANE (FP)              LENS (f)               IMAGE PLANE (IP)
     ┌──────────────────┐         │         │         ┌──────────────────┐
     │                  │         │         │         │                  │
     │  E_FP(ξ, η)      │         │    f    │    f    │  E_IP(x, y)      │
     │  (grating)       │ ◄──────►│─────────│◄───────►│  (focused beam)  │
     │                  │         │         │         │                  │
     │  spatial freq    │         │ Fourier │         │  spatial position│
     │  domain          │         │transform│         │  domain          │
     └──────────────────┘         │         │         └──────────────────┘
           ◄── f ──►                                        ◄── f ──►

     Periodic pattern here    ─────────────►    Discrete spots here
     Small patch here         ─────────────►    Plane wave here
     Complex pattern here     ─────────────►    Shaped beam here
```

A thin lens of focal length *f* performs an optical Fourier transform between its front focal plane (the Fourier Plane, FP) and its back focal plane (the Image Plane, IP). For a monochromatic field E_FP(ξ, η) at the FP, the field at the IP is:

```
                    1
E_IP(x, y) = ────────── ∬ E_FP(ξ, η) · exp[-i 2π/(λf) · (xξ + yη)] dξ dη
              i λ f
```

This is exactly a 2D Fourier transform with the spatial frequency variable mapped to position:

```
k_x = 2π ξ / (λf)    →    x = λf · k_x / (2π)
k_y = 2π η / (λf)    →    y = λf · k_y / (2π)
```

**Physical interpretation:** Each point (ξ, η) on the FP contributes a plane wave traveling at angle θ ≈ ξ/f to the optical axis. The lens focuses all plane waves with the same angle to a single point at the IP. A small patch at the FP produces a nearly uniform plane wave at the IP; a periodic structure at the FP produces discrete diffraction spots at the IP.

### 1.2 Scaling Factor

```
     FP coordinate ξ                          IP coordinate x
     ─────────────────                        ────────────────
     
     ξ (meters on DMD)  ──── × λf / (2π) ────►  x (meters at ions)
     
     Example:
     Grating period p = 30.24 μm    →    Beam position x₁ = λf/p = 3.05 mm
     (4 pixels × 7.56 μm)                (distance from zeroth order at IP1)
```

The conversion between FP coordinates and IP coordinates is governed by the scaling factor:

```
Λ = λ · f
```

For our system: λ = 369 nm, f = 250 mm → Λ = 92.25 μm·mm = 9.225 × 10⁻⁸ m².

A grating with period *p* at the FP produces first-order diffraction spots at:

```
x₁ = ± Λ / p = ± λf / p
```

For a 4-pixel-period grating (p = 4 × 7.56 μm = 30.24 μm):

```
x₁ = (369 × 10⁻⁹ × 250 × 10⁻³) / (30.24 × 10⁻⁶) = 3.05 mm
```

This is the distance between zeroth and first order at IP1 before demagnification.

### 1.3 The Discrete Fourier Transform on a Pixelated Device

The DMD has N_x × N_y pixels with pitch Δ (pixel size). The discrete version of the Fourier relationship is:

```
E_IP[m, n] = Σ_j Σ_k  E_FP[j, k] · exp[-i 2π (jm/N_x + kn/N_y)]
```

The IP grid spacing is:

```
Δx_IP = λf / (N_x · Δ)
```

For DLP9000XUV: N_x = 2560, Δ = 7.56 μm → Δx_IP = 369e-9 × 0.25 / (2560 × 7.56e-6) = 4.77 μm

This sets the resolution at the image plane.

### 1.4 The Paraxial Approximation

All of the above assumes the paraxial approximation: sin θ ≈ θ. For our system, the maximum diffraction angle is:

```
θ_max = λ / (2Δ) = 369e-9 / (2 × 7.56e-6) = 0.0244 rad ≈ 1.4°
```

Well within the paraxial regime. The approximation is excellent.

---

## 2. The Digital Micromirror Device

```
     TOP VIEW OF DLP9000XUV                    SIDE VIEW (single mirror)
     ━━━━━━━━━━━━━━━━━━━━━━                    ━━━━━━━━━━━━━━━━━━━━━━━━
     
     ◄────────── 2560 pixels ──────────►                    incident
     ┌───────────────────────────────────┐                   light
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ ▲                    \
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │                     \  +12°
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │             ─────────\────── ON
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ 1600              flat  │
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ pixels      ─────────/────── OFF
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │                   /  -12°
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │                  /
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ ▼              reflected
     └───────────────────────────────────┘              (to beam dump)
     
     Each ░ = one 7.56 μm mirror
     Tilt axis = along diagonal (hence 45° mount)
     Total: 4,096,000 individually addressable mirrors
```

### 2.1 Physical Structure

The DLP9000XUV consists of a 2D array of aluminum micromirrors:

| Parameter | Value |
|-----------|-------|
| Array size | 2560 × 1600 pixels |
| Mirror pitch | 7.56 μm |
| Mirror tilt angle | ±12° from flat |
| Tilt axis | Along mirror diagonal |
| Switching time | ~10–20 μs |
| Fill factor | ~92% |
| Reflectivity (369 nm) | ~88% |

### 2.2 Binary Amplitude Modulation

Each mirror has two states:
- **ON (+12°):** Reflects light toward the optical system
- **OFF (−12°):** Reflects light away (into a beam dump)

The reflected field from the entire DMD is:

```
E_reflected(ξ, η) = E_incident(ξ, η) × M(ξ, η)
```

where M(ξ, η) ∈ {0, 1} is the binary mirror state.

### 2.3 The 45° Mounting Angle

The mirror tilt axis lies along the diagonal of the pixel array. To keep the diffracted beam in the plane of the optical table, the DMD is mounted rotated by 45°. This means the grating angle parameter θ in the software is set to ±π/4.

The coordinate transformation between the DMD pixel grid (i, j) and the physical coordinates (x, y) at the FP is:

```
x = (j - N_x/2) × Δ
y = (N_y/2 - i) × Δ
```

### 2.4 Blazing Condition

The tilt angle of the mirrors determines which diffraction order receives the most power. The blazing condition is satisfied when the incident angle θ_i and the diffraction angle θ_d are symmetric about the mirror tilt:

```
θ_tilt = (θ_i + θ_d) / 2
```

For our geometry (θ_tilt = 12°, grating directing light at angle θ_d), the incident angle should be chosen to maximize power in the desired order. The negative first order is typically used because it satisfies the blazing condition better for the chosen geometry.

---

## 3. Amplitude Grating and Diffraction Orders

```
     DMD GRATING PATTERN (FP)                    IMAGE PLANE (IP)
     ━━━━━━━━━━━━━━━━━━━━━━━━                    ━━━━━━━━━━━━━━━━━━
     
     ┌────────────────────────┐         ┌──────────────────────────┐
     │ █░█░█░█░█░█░█░█░█░█░█░ │         │                          │
     │ ░█░█░█░█░█░█░█░█░█░█░█ │         │    m=-1        m=0       │
     │ █░█░█░█░█░█░█░█░█░█░█░ │  ──►    │ (aberr-free!) (residual) │
     │ ░█░█░█░█░█░█░█░█░█░█░█ │  lens   │     ●          ●         │
     │ █░█░█░█░█░█░█░█░█░█░█░ │         │  ← USED              ●   │
     │ ░█░█░█░█░█░█░█░█░█░█░█ │         │                   m=+1   │
     │ █░█░█░█░█░█░█░█░█░█░█░ │         │                (2×aberr) │
     └────────────────────────┘         └──────────────────────────┘
     
     period = 4 pixels
     (ON/OFF alternating                  Three orders separated by
      with phase modulation)              x₁ = λf/p = 3.05 mm
     
     NOTE: Bloodstone uses negative_order=True, so the grating phase
     sign is flipped: cos(x₀·k − Φ_out + Φ_in). This makes m=−1
     the aberration-free order. Blazing also favors this order.
```

### 3.1 The Grayscale Grating Function

For a target electric field f(x) at the image plane, its Fourier transform is:

```
F(k) = F{f(x)}
```

where k represents spatial frequency coordinates at the FP.

The ideal grayscale grating that would produce f(x) in the first diffraction order is:

```
G(k) = |F(k)| / (2 · E_in(k)) × [cos(x₀·k + Φ_out(k) − Φ_in(k)) + 1]
```

where:
- E_in(k): amplitude of the illuminating beam at the FP
- Φ_in(k) = arg(E_in(k)): phase of the illumination (includes aberrations)
- Φ_out(k) = arg(F(k)): phase of the target field
- x₀: determines grating periodicity → position of first-order beam
- The "+1" ensures G(k) ≥ 0 (mirrors can't produce negative amplitude)

A normalization factor η ensures 0 ≤ G(k) ≤ 1:

```
η = max(E_in(k) / |F(k)|)
```

### 3.2 Diffraction Orders from the Grating

Taking the inverse Fourier transform of E_in(k) × G(k), we obtain three terms:

```
g(x) = F⁻¹{E_in(k) · G(k)}

     = (η/4) · f(x + x₀)                           ← first order (m=+1)
     + (η/4) · f*(−x + x₀) * F⁻¹{e^(2iΦ_in)}     ← negative first (m=−1)
     + (η/2) · F⁻¹{|F(k)| · e^(iΦ_in)}            ← zeroth order (m=0)
```

**Critical observation:** The first-order term is simply f(x + x₀) — the target field, shifted to position x₀, with NO aberration phase. The aberration cancels because Φ_in appears with opposite signs in the grating argument and the field phase.

The negative first order carries **twice** the aberration. The zeroth order carries residual aberration. Both are spatially separated from the first order and are blocked by a spatial filter.

> **Convention note:** This derivation uses the *default* convention (`negative_order=False`), where the **positive** first order (m=+1) is aberration-free. Bloodstone uses `negative_order=True`, which flips the phase sign (see Section 3.4) so that the **negative** first order (m=−1) is aberration-free instead. This is why the diagram at the top of this section labels m=−1 as the used order. The physics is identical — only which order carries the clean beam changes.

### 3.3 Periodicity and Beam Position

The parameter x₀ in the grating function determines the period:

```
period (pixels) = 2π / |x₀| × (pixel_size) / (2π) ... 

More precisely: |x₀| = λf / (period × pixel_size)
```

In the software, `periodicity = 4` means the grating repeats every 4 pixels. The first-order beam appears at:

```
x_first_order = cos(θ) × λf / (periodicity × pixel_size)
y_first_order = sin(θ) × λf / (periodicity × pixel_size)
```

For θ = −π/4 (45° grating), periodicity = 4, pixel_size = 7.56 μm:

```
x₀ = cos(-π/4) × 369e-9 × 0.25 / (4 × 7.56e-6) = 2.16 mm
y₀ = sin(-π/4) × 369e-9 × 0.25 / (4 × 7.56e-6) = −2.16 mm

|origin| = √(x₀² + y₀²) = 3.05 mm from zeroth order
```

### 3.4 Negative Order Convention

When `negative_order=True`, the sign of the phase term flips:

```
G(k) = |F(k)|/(2·E_in) × [cos(x₀·k − Φ_out(k) + Φ_in(k)) + 1]
```

Now the **negative** first order (m = −1) is aberration-free, and the positive first order carries 2× aberration. This is chosen based on which order has better diffraction efficiency (blazing).

---

## 4. Hologram Generation Algorithms

```
     THE BINARIZATION CHALLENGE
     ━━━━━━━━━━━━━━━━━━━━━━━━━━

     Ideal (grayscale):        Binarized (threshold):     Binarized (IFTA):
     ┌───────────────────┐     ┌─────────────────────┐      ┌───────────────────┐
     │ ▓▓▒▒░░▒▒▓▓▓▓▒▒░░  │     │ █░░░░░░█████░░░░    │      │ █░█░░█░████░█░░░  │
     │ smooth gradients  │ →   │ hard edges →        │  vs  │ randomized →      │
     │ continuous 0–1    │     │ structured artifacts│      │ diffuse noise     │
     └───────────────────┘     └─────────────────────┘      └───────────────────┘
     
     Result at IP:             Result at IP:               Result at IP:
     ┌───────────────────┐     ┌───────────────────┐      ┌───────────────────┐
     │      ╭─╮          │     │   ╭─╮  ↑↑  ↑↑     │      │      ╭─╮          │
     │     ╱   ╲         │     │  ╱   ╲ artifacts  │      │     ╱   ╲ ~noise  │
     │ ───╱─────╲─── │   │     │ ╱─────╲──↓↓──↓↓   │      │ ───╱─────╲──···   │
     │   perfect beam    │     │ IX ~ 10⁻²         │      │ IX ~ 10⁻³ (random)│
     └───────────────────┘     └───────────────────┘      │ IX < 10⁻⁴ (IFTA)  │
                                                          └───────────────────┘
```

### 4.1 The Binarization Problem

The ideal grating G(k) is continuous (values in [0, 1]). The DMD is binary (0 or 1). We need a binarization operator U:

```
G_binary(k) = U[G(k)] ∈ {0, 1}
```

The challenge: binarization is nonlinear. It introduces frequency components not present in the original grating, creating spurious diffraction (artifacts) at the image plane.

### 4.2 Simple Threshold Binarization

```
G_binary(k) = { 1  if G(k) > 0.5
              { 0  otherwise
```

This produces severe structured artifacts because the threshold creates sharp edges that diffract coherently. Typical result: IX ~ 10⁻² (unusable for ion addressing).

### 4.3 Random Binarization

Instead of a fixed threshold, use a stochastic threshold:

```
G_binary(k) = { 1  with probability P(G(k))
              { 0  with probability 1 − P(G(k))
```

where P is a sigmoid function controlled by steepness parameter r:

```
P(g) = 1 / (1 + exp(−r(2g − 1)))
```

For r → ∞: approaches hard threshold. For r ~ 10: smooth transition.

**Why it works:** The randomness converts structured binarization artifacts into spatially incoherent noise that spreads uniformly across the IP, rather than concentrating at specific locations. Result: IX ~ 10⁻³.

**Computation time:** Single pass, no iteration. ~100 ms on GPU.

### 4.4 IFTA (Iterative Fourier Transform Algorithm)

> **Origin.** The specific IFTA used here was developed by Shih *et al.* (npj QI 7, 57,
> 2021), building on the Lee/Wyrowski amplitude-hologram tradition and the Gerchberg–Saxton
> family. Shih's version demonstrated **more than an order of magnitude** improvement in
> addressing accuracy over previously proposed algorithms, and is what first brought the
> DMD baseline crosstalk down to $\sim 10^{-4}$ ($-40$ dB) for trapped-ion addressing.

IFTA iteratively refines the binarization to minimize errors within a signal window D:

**Algorithm:**

For iteration i = 1, 2, ..., N:

1. **Binarize** with dynamic threshold t = i/(2N):
   ```
   G_b^(i)(k) = { 0           if Re[G^(i)(k)] < t
                { 1           if Re[G^(i)(k)] > (1−t)
                { Re[G^(i)(k)] otherwise (soft region)
   ```

2. **Propagate** to image plane:
   ```
   g^(i)(x) = F⁻¹{E_in(k) · G_b^(i)(k)}
   ```

3. **Correct** within signal window:
   ```
   g_c^(i)(x) = { g_ideal(x)  if x ∈ D
                { g^(i)(x)    otherwise
   ```
   where g_ideal(x) = F⁻¹{E_in(k) · G(k)} is from the unbinarized hologram.

4. **Propagate back** to Fourier plane:
   ```
   G^(i+1)(k) = F{g_c^(i)(x)} / E_in(k)
   ```

As i increases, t goes from 0 (no binarization) to 0.5 (full binarization). The correction step forces the beam within D to match the ideal, while allowing errors to redistribute outside D.

**Key parameters:**
- N (iterations): More = better quality, diminishing returns beyond ~2000
- D (signal window): Region where IX is minimized. Defined as a rectangle centered on the first-order origin.
- s (scaling): Multiplies the ideal hologram before binarization to trade diffraction efficiency vs. artifact level.

**Result:** IX < 10⁻⁴ within D. Outside D, artifacts are uncontrolled (can be worse than random method).

**Computation time:** ~6 s for 2000 iterations on GPU (vs. ~200 s on CPU).

### 4.5 Comparison

| Method | IX within window | IX outside window | Computation | Use case |
|--------|-----------------|-------------------|-------------|----------|
| Simple threshold | ~10⁻² | ~10⁻² | Instant | Never (testing only) |
| Random (r=10) | ~10⁻³ | ~10⁻³ | ~100 ms | Calibration, quick tests |
| IFTA (N=2000) | < 10⁻⁴ | ~10⁻³ | ~6 s (GPU) | Production holograms |

### 4.6 Multi-Frequency Addressing via DMD Zones + AOM

A single static DMD hologram produces one addressing beam pattern at one optical frequency.
Multi-qubit entangling gates (e.g. Mølmer–Sørensen) require **multiple frequency tones**
delivered to selected ions simultaneously. Shih *et al.* (npj QI 7, 57, 2021) introduced a
scheme that pairs the DMD with an **acousto-optic modulator (AOM)** to achieve this without
any additional spatial light modulators:

```
     AOM splits input into angularly separated, frequency-shifted copies
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                          ┌─────── f₀+δ₁ ──►  DMD ZONE A  ─┐
        input   ┌─────┐   │                   (hologram A) │
        beam ──►│ AOM │───┼─────── f₀+δ₂ ──►  DMD ZONE B  ─┤──► lens ──► ions
                └─────┘   │                   (hologram B) │            ● ● ● ●
                (multi-   └─────── f₀+δ₃ ──►  DMD ZONE C  ─┘             ↑ ↑
                 tone RF)                                              each tone
                                                                       lands on its
     Each AOM tone illuminates a DIFFERENT spatial zone of the DMD.    targeted ion(s)
     Each zone carries an INDEPENDENT hologram (own target ion set).
     A given ion can therefore receive several frequency tones at once.
```

**Principle:** driving the AOM with several RF tones produces several first-order beams at
slightly different angles and different optical frequencies. By arranging the geometry so
each angularly-separated copy lands on a **distinct region (zone) of the DMD**, and by
writing an independent hologram in each zone, each optical frequency becomes an independent
addressing channel. The lens then superimposes the zone outputs at the ion plane, so a
single ion can be illuminated by a programmable set of frequency tones — the requirement for
spin-dependent forces and arbitrary spin–spin coupling graphs.

**Significance:** this turns the DMD from a single-frequency amplitude shaper into a
reconfigurable *multi-frequency* addressing system, enabling parallel single-qubit rotations
and multi-qubit entangling operations with arbitrary connectivity, all reprogrammable in
software.

---

## 5. Aberration Theory and Compensation

```
     WITHOUT ABERRATION CORRECTION              WITH ABERRATION CORRECTION
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━              ━━━━━━━━━━━━━━━━━━━━━━━━━━

     Beam at IP:                                Beam at IP:
     ┌────────────────────────┐                 ┌────────────────────────┐
     │    ↑   ╭─╮   ↑         │                 │        ╭──╮            │
     │   ╱╲  ╱   ╲  ╱╲        │                 │       ╱    ╲           │
     │  ╱  ╲╱     ╲╱  ╲       │                 │      ╱      ╲          │
     │ ╱ sidelobes from ╲     │                 │  ───╱────────╲───      │
     │╱  aberrations      ╲   │                 │  clean Gaussian        │
     │ IX ~ 10⁻² (unusable)   │                 │  IX ~ 10⁻⁴             │
     └────────────────────────┘                 └────────────────────────┘
     
     
     MEASUREMENT PROCEDURE:
     ━━━━━━━━━━━━━━━━━━━━━━
     
     Step 1: Two patches ON          Step 2: Observe fringes at IP
     
     DMD (FP):                        Camera (IP):
     ┌────────────────────┐           ┌────────────────────┐
     │                    │           │ ║  ║  ║  ║  ║  ║   │
     │  ┌──┐      ┌──┐    │    →      │ ║  ║  ║  ║  ║  ║   │
     │  │R │      │S │    │           │ ║  ║  ║  ║  ║  ║   │
     │  │ef│      │ca│    │           │ ║  ║  ║  ║  ║  ║   │
     │  └──┘      │n │    │           │  fringe spacing =  │
     │            └──┘    │           │  λf / patch_sep    │
     └────────────────────┘           └────────────────────┘
     
     Step 3: Extract phase from       Step 4: Scan across grid
     fringe position (correlation)    → build 2D phase map Φ(ξ,η)
     
     ┌──────────────────────────────────────────────────────────┐
     │                                                          │
     │  Φ_total = Φ₀ + Φ₁ (+ Φ₂ for double pass)                │
     │                                                          │
     │  Φ₀: ~10λ peak-to-peak (dominant: lens + DMD flatness)   │
     │  Φ₁: ~2λ peak-to-peak (diffraction path difference)      │
     │  Φ₂: ~1λ peak-to-peak (retro-reflector path)             │
     │                                                          │
     │  After correction: residual < 0.2λ RMS (50× better)      │
     │                                                          │
     └──────────────────────────────────────────────────────────┘
```

### 5.1 Sources of Aberration

The optical system introduces phase errors from:
- Lens surface errors and design residuals
- DMD surface non-flatness (curvature of the MEMS substrate)
- Mirror alignment errors
- Beam propagation through non-ideal media

These aberrations are modeled as a phase map Φ_ab(k) at the FP:

```
E_in(k) = A_in(k) · exp(iΦ_ab(k))
```

where A_in(k) is the (real) amplitude profile of the illumination. It is nominally Gaussian,
but it is also **measured**, not just assumed: during the zeroth-order scan each scan patch is
additionally imaged *alone*, and its total (background-subtracted) camera counts give the
local reflected intensity. Interpolating these across the DMD and taking the square root
(intensity → field) yields the amplitude map A_in used in the 1/E_in(k) term of the grating
equation (Section 3.1). This corrects the hologram for the real, non-uniform illumination
across the DMD.

### 5.2 Effect on the Beam

Without correction, the image plane field picks up the aberration:

```
E_IP(x) = F{A_in(k) · exp(iΦ_ab(k)) · G(k)}
```

For a simple patch (uniform G = 1 in a small region), the IP field is:

```
E_IP(x) ≈ exp(iΦ_ab) × [ideal Airy pattern]
```

The intensity |E_IP|² develops sidelobes and distortions proportional to the aberration magnitude. For Φ_ab ~ 10λ peak-to-peak (typical), this destroys the Gaussian shape entirely.

### 5.3 Correction via the Grating Function

The key insight: by including Φ_in(k) = Φ_ab(k) in the grating equation:

```
G(k) = |F|/(2·A_in) × [cos(x₀·k + Φ_out − Φ_ab) + 1]
```

The first-order field becomes:

```
E_first_order(x) = (η/4) · f(x + x₀)
```

The aberration phase Φ_ab cancels exactly in the first-order term. This is guaranteed by the mathematics of Fourier holography — it's not an approximation.

### 5.4 Two-Patch Interference for Phase Extraction

To measure Φ_ab, we exploit the DMD itself:

**Setup:** Two small square patches turned ON at positions (ξ₁, η₁) and (ξ₂, η₂) on the DMD.

**At the IP:** Each patch produces a nearly plane wave. They interfere:

```
I(x) = |E₁|² + |E₂|² + 2|E₁||E₂| · cos[(k₁ − k₂)·x + (φ₁ − φ₂)]
```

where:
- k₁ − k₂ = 2π(ξ₁ − ξ₂)/(λf) is the fringe spatial frequency
- φ₁ − φ₂ is the phase difference we want to extract

**Extraction:** Correlate the measured fringe pattern with a reference sinusoid:

```
C = ∫ f(x) · exp[i(k₁−k₂)·x] dx

Phase difference = arg(C)
```

**Building the full map:** Fix one patch (reference, at center of DMD). Scan the second patch across a grid of positions. At each position, extract φ_scan − φ_ref. This builds a 2D relative phase map.

**How this is actually implemented (calibration code).** The bench procedure that produces
the maps (see `experiment_scans/exp_scan.md`) refines the idealized integral above in four
ways that matter for accuracy:

1. **Background subtraction.** Each fringe frame is corrected as
   `fringe = img − img_ref + bg` (a global DMD-OFF background `bg` and a reference frame
   `img_ref`) to remove static illumination and DC offset before correlation.
2. **Globally-fitted fringe frequency.** Rather than trusting a noisy per-frame FFT peak, the
   fringe frequency is first estimated per frame (`freq_estimate`: FFT peak + optional
   least-squares) and then fit to a *linear* model across the whole scan grid,
   `f(i,j) = a·(i − i_ref) + b·(j − j_ref)`, because the fringe frequency is proportional to
   patch separation. Outliers (fit residual > 10⁻²) are rejected and the model is refit. The
   correlation phase at each point then uses this *fitted* frequency, which keeps the
   reference consistent across the grid. The fitted slope (a, b) also encodes the λf scaling
   (Sections 1.2, 3.3), so this step doubles as a focal-length/geometry check.
3. **2-D phase unwrapping.** The scattered `arg(C)` values are reshaped onto the scan grid and
   unwrapped (2-D `unwrap_phase`) to remove 2π discontinuities, then interpolated (bicubic) to
   the full DMD grid.
4. **Detrending.** A best-fit plane (piston + tip/tilt) is subtracted from the map
   (`derend2D`). Piston and linear tilt carry *no beam-quality information* — a global tilt
   only translates the beam at the image plane — so the stored map is a **detrended relative
   phase**, not an absolute one. The first-order scan additionally averages several repeats
   and median-filters to suppress noise.

The map is therefore defined only up to an overall piston and tilt (which are physically
irrelevant), and its transverse resolution is set by the scan grid, not the pixel pitch
(Section 5.7).

### 5.5 Multi-Stage Aberration Characterization

The total aberration is measured in stages:

**Φ₀ (zeroth-order map):** Measures aberrations from the input source through the lens to the camera. Both patches are **flat ON squares** with *no grating* (in the code: small 8×8-pixel squares on a 20-pixel grid). The fringe encodes path-length differences of the undiffracted light.

**Φ₁ (first-order map):** The patches now display **grating patterns that produce first-order beams** (in the code: larger circular grating patches), so the fringe carries the aberration of the diffraction path itself (e.g., the non-flat DMD surface affects the diffracted order differently). Crucially, these grating patches are generated **with Φ₀ already applied**, so the fringe phase isolates the *incremental* first-order aberration rather than re-measuring Φ₀. The two maps then add: the correction encodes Φ₀ + Φ₁. Because the first-order signal is weaker, this scan uses larger patches, a coarser grid, and several repeats that are averaged.

**Φ₂ (second-pass map, double-pass only):** Same process but after the retro-reflected beam returns to the DMD. Captures additional aberrations from the retro-reflector optics.

> The patches are scanned only over the Fourier-plane hologram region (DMD columns ~0–1960, with the reference patch at the region centre), matching the FP1/IP1 split used for double-pass (Section 7.4). Detrending (Section 5.4) means each stage is a relative map; adding Φ₀ + Φ₁ is valid because both are referenced to the same central patch.

**Combined correction:**
- Single pass: input_profile = exp(1j × (Φ₀ + Φ₁))
- Double pass: input_profile = exp(1j × (−Φ₀ − Φ₁ + Φ₂))

The sign flip in double-pass is because the light traverses the system in reverse on the second pass.

### 5.5a In-Situ Characterization Using the Ions Themselves

The camera-based two-patch interferometry above measures aberrations *up to the imaging
camera*. The residual wavefront error at the *ion plane* — the plane that actually matters —
can differ, because the relay optics and vacuum viewport between the camera-conjugate plane
and the ions add their own aberrations that no camera in the addressing path can see.

Shih *et al.* (npj QI 7, 57, 2021) resolved this by using **the trapped ions as the
wavefront probe**. Instead of (or in addition to) a camera, the figure of merit is measured
directly on the ions:

```
     CAMERA-BASED (up to imaging plane)      ION-BASED (all the way to the ion)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

     DMD ─► optics ─► [camera]               DMD ─► optics ─► viewport ─► [ion]
                        │                                                  │
              fringe phase map                          AC Stark shift  /
              Φ(ξ,η) to camera                          fluorescence  /  Rabi rate
                                                        at neighbor site

     Blind to viewport +                     Sees the complete wavefront
     relay aberrations                       error, including everything
     downstream of the camera                between DMD and ion
```

**How the ion reports crosstalk / aberration.** A beam aimed at a *target* ion leaks a
small field onto its *neighbor*. That leakage is measured on the neighbor by any
intensity-sensitive observable — the light shift (AC Stark shift) it induces, the
depumping/scattering rate, or the residual Rabi rate. Minimizing this observable while
scanning the encoded aberration terms (or the secondary-grating parameters, Section 6)
tunes the correction against the *true* end-to-end optical system. Shih *et al.* reported
that this in-situ, ion-referenced procedure reached relative intensity crosstalk at the
$\sim 10^{-4}$ level — the baseline that the multiplexing and double-pass techniques of this
document then push further.

**Practical consequence for this server.** The `Φ₀/Φ₁/Φ₂` maps loaded at startup are the
camera-derived starting point. A final in-situ refinement loop (scan → measure on the ion →
update) is the intended production calibration path once the beam reaches ions; it is the
reason the aberration maps and secondary-grating parameters are exposed as reloadable
server state rather than baked into a fixed hologram.

### 5.6 Zernike Decomposition

The phase maps can be decomposed into Zernike polynomials Z_n^m(ρ, φ) for analysis:

```
Φ(ρ, φ) = Σ_{n,m} a_n^m · Z_n^m(ρ, φ)
```

Common terms:
- Z₂⁰: Defocus (parabolic phase)
- Z₂²: Astigmatism
- Z₃¹: Coma
- Z₄⁰: Spherical aberration

Typically dominant in our system: astigmatism and defocus. The residual after compensation is < 0.2λ RMS, with primary residuals being higher-order terms that the grating sampling cannot resolve.

### 5.7 Spatial Resolution of Aberration Correction

The transverse resolution of the aberration map is set by the **scan grid spacing**, not the
DMD pixel pitch — between grid points the phase is interpolated (bicubic). The two scans use
different sampling:

```
Zeroth-order (Φ₀): patch 8×8 px,  grid spacing 20 px → 20 × 7.56 μm ≈ 151 μm
First-order  (Φ₁): larger circular patches, grid spacing 25 px → ≈ 189 μm
```

(The analysis code uses a 7.6 μm pitch; 7.56 μm is the datasheet value — the difference is
negligible here.) The sampling is chosen as a trade-off: finer grids resolve higher-order
aberration but need more images and give weaker per-patch signal. Even the coarser first-order
grid is comparable to or finer than a Shack–Hartmann sensor (micro-lens diameter > 150 μm).
As noted in Section 5.4, the stored map is a **detrended relative phase** (piston and tilt
removed), so it captures the beam-shaping-relevant curvature rather than an absolute
wavefront.

---

## 6. Secondary Grating for Crosstalk Suppression

```
     THE PROBLEM                              THE SOLUTION
     ━━━━━━━━━━━                              ━━━━━━━━━━━━
     
     Beam at IP (log scale):                  Add secondary beam for interference:
     
       0 dB ┤    ╭──╮                          0 dB ┤    ╭──╮
            │   ╱    ╲                              │   ╱    ╲
      -20 dB┤  ╱      ╲                       -20 dB┤  ╱      ╲
            │ ╱        ╲                            │ ╱        ╲
    -42.6dB ┤╱──────────╲─ ← IX baseline      -42.6 ┤╱          ╲
            │            ↑                          │       ╭╮   ╲── suppressed!
      -50 dB┤     neighbor here               -50 dB┤       ╰╯    ← IX ≲ 10⁻⁵ (−50 dB)
            ├──┬────┬────┬──                        ├──┬────┬────┬──
              x₀  x₀+4w                              x₀  x₀+4w
     
     
     DMD STATE (FP):
     ━━━━━━━━━━━━━━━
     
     ┌──────────────────────────────────────────────────────────────────────┐
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
     │ ░░░░░░ PRIMARY GRATING (IFTA) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
     │ ░░░░░░░░░░░░░░░░░░░░░░██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░ │ ← secondary
     │ ░░░░░░░░░░░░░░░░░░░░░░██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░ │   grating
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   (m=2 × l=460 px)
     └──────────────────────────────────────────────────────────────────────┘
     
     
     INTERFERENCE AT NEIGHBOR (paper notation: A_s, Φ_s):
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     E_total(4w) = Ã₁·e^(iΦ₁)  +  Ã₂·e^(iΦ_s)
                   ──────────      ──────────
                   primary tail    secondary beam
     
     I = Ã₁² + Ã₂² + 2Ã₁Ã₂·cos(Φ₁ − Φ_s)
     
     Optimize (measured optima from the paper):
       ① Scan Φ_s: 0 → 4π  → Φ_s = 2.77π  (from cosine fit, Fig. 2c)
       ② Scan A_s at optimal Φ_s → A_s = 0.38  (from quadratic fit, Fig. 2d)
       → baseline −42.6 dB → −48 dB (single hologram, ~5 dB gain)
       → multiplexed → I_X ≲ −50 dB (10⁻⁵)
```

### 6.1 The Problem: Residual Crosstalk at the Nearest Neighbor

After IFTA optimization, the primary beam has a Gaussian intensity profile:

```
I_primary(x) = A₁² · exp(−2(x − x₀)² / w²)
```

At the nearest neighbor position x = x₀ + a (where a = 4w is the ion spacing):

```
I(x₀ + a) = A₁² · exp(−2 × 16) = A₁² × 10⁻¹⁴ (ideal Gaussian)
```

In practice, binarization artifacts and aberration residuals raise this to ~10⁻⁴ of the peak — 10 orders of magnitude worse than the ideal Gaussian tail.

### 6.2 The Idea: Destructive Interference

Create a secondary beam at the neighbor position with controlled amplitude and phase. If the secondary beam's field exactly opposes the primary's tail:

```
E_total(x₀ + a) = E_primary(x₀ + a) + E_secondary(x₀ + a) = 0
```

### 6.3 The Secondary Grating Function

A rectangular window of dimensions l × m (pixels) on the Fourier plane carries a secondary
grating. This is Eq. (1) of the paper (notation aligned):

```
F_s(x) = η · |rect(x/l, y/m) / E_in(x)| · (A_s/2) · [cos(2π x_a·x/(λf) + Φ_s − Φ_in(x)) + 1]
```

where:
- A_s: controllable amplitude of the secondary hologram (0 ≤ A_s ≤ 1);
       set physically by the ON-mirror density in the window
- Φ_s: controllable phase, set by lateral displacement of the grating
- x_a: spatial-frequency vector placing the auxiliary beam at X₀ + a in the image plane
- Φ_in(x): input aberration phase map (in-situ characterized)
- 1/|E_in(x)|: compensates spatial nonuniformity of the incident field across the DMD
- rect(x/l, y/m): confines the grating to a rectangular window
- η: normalization enforcing 0 ≤ F_s ≤ 1

**Window size (paper):** for trapped-ion addressing along a linear chain, m = 2 DMD pixels
(width, along the transverse axis) and l = 460 DMD pixels (length, along the ion axis). The
narrow width in the Fourier plane produces a large transverse spread of the auxiliary beam
at the image plane, which is acceptable as long as it does not illuminate nearby structures
(e.g. trap electrodes). The secondary grating is generated with the **random binarization**
method.

### 6.4 The Secondary Beam at the IP

The secondary beam at the neighbor position is:

```
E_s(x₀ + a) = A₂ · l · sinc(0) · e^(iφ₂) = Ã₂ · e^(iφ₂)
```

where Ã₂ = A₂ · l (amplitude depends on both grating amplitude and window size).

The sinc function evaluates to 1 at the target position (by design of the periodicity), and falls off away from it. The secondary beam is localized — it doesn't corrupt other ion positions.

### 6.5 Resultant Intensity

```
I(x₀ + a) = |Ã₁ e^(iφ₁) + Ã₂ e^(iφ₂)|²
           = Ã₁² + Ã₂² + 2Ã₁Ã₂ cos(φ₁ − φ₂)
```

**Minimum condition:**
```
φ₁ − φ₂ = (2n+1)π     (destructive interference)
Ã₂ = Ã₁               (equal amplitudes)

→ I_min = (Ã₁ − Ã₂)² = 0
```

In practice, achieving exactly Ã₂ = Ã₁ is difficult. The paper reports a baseline of
−42.6 dB from the primary beam alone, reduced to **−48 dB** by a single optimized secondary
hologram (about **5 dB** average improvement), with **up to 10 dB** relative suppression
possible.

### 6.6 Periodicity Calculation

The grating periodicity sets the **absolute position** of the secondary beam measured from the zeroth order. The secondary beam must land at the neighbor position, which is the primary beam position minus a small offset (4w at IP1). Let x_sec be that absolute position along the diffraction axis:

```
x_sec = x_first_order − 4w_IP1     (position of the secondary beam from zeroth order)

p_secondary = cos(θ) × λ × f / (x_sec × pixel_size)
```

The x-component of the first-order origin is (from Section 3.3):

```
x_first_order = cos(π/4) × λf / (4 × pixel_size) = 0.707 × 3.05 mm = 2.16 mm
```

The neighbor offset at IP1 is 4w_IP1 = 4 × 9 μm = 36 μm, so:

```
x_sec = 2.16 mm − 36 μm ≈ 2.124 mm

p_secondary = cos(π/4) × 369e-9 × 0.25 / (2.124e-3 × 7.56e-6)
            = 0.707 × 9.225e-8 / (1.606e-8)
            ≈ 4.06 pixels per period
```

Note: the secondary grating periodicity (~4 pixels) is nearly identical to the primary grating (4 pixels) — this makes sense because the secondary beam sits right next to the primary beam. The tiny difference (4.06 vs 4.00) is what shifts the beam by exactly 4w to land on the neighbor. This is why the secondary grating must occupy a physically distinct window on the DMD: its period is too close to the primary's to separate them within the same region.

### 6.7 Optimization Procedure

1. **Measure baseline:** record I_X at the target location from the primary beam alone
   (−42.6 dB in the paper).
2. **Phase scan:** fix A_s = 0.70. Scan Φ_s from 0 to 4π. Fit the linear-scale data to a
   cosine model to extract the optimum Φ_s = 2.77π (Fig. 2c).
3. **Amplitude scan:** fix Φ_s = 2.77π. Scan A_s from 0 to 1; fit to a quadratic model
   (excluding A_s ≥ 0.9, which deviates from the quadratic trend). The minimum yields the
   optimum A_s = 0.38 (Fig. 2d).

The 4π range (instead of 2π) accounts for phase-wrapping ambiguity in the grating implementation.

### 6.8 Multiplexing Multiple Secondary Holograms

The Fourier plane can be **multiplexed** with several secondary holograms to suppress
crosstalk at multiple sites simultaneously. The paper demonstrates six secondary holograms
targeting ±4w, ±8w, and ±12w, achieving I_X ≲ −50 dB (10⁻⁵) at all six sites.

Practical rules from the paper:
- Estimate each required auxiliary amplitude from the measured primary-beam I_X at that site.
- When two holograms need comparable amplitudes, overlay them on the same pixels (removes as
  little of the primary IFTA hologram as possible).
- **Do not overlay more than two** secondary holograms on the same DMD region — doing so
  degrades independent amplitude/phase control.
- For more than two, or very different amplitudes, stack their windows along the y direction
  in the Fourier plane.
- Scan each hologram's phase independently, then do a fine amplitude scan of each at its
  optimum phase.

**Scaling limit:** performance degrades noticeably beyond ~8 secondary holograms. Two causes:
(1) diffraction sidelobes from the rectangular window (Eq. 1) cause the auxiliary beams to
overlap — could be mitigated by smoothing the window; (2) each added hologram removes more
Fourier components from the primary beam, degrading the main addressing spot.

---

## 7. Double-Pass Pupil Filtering

```
     SINGLE PASS (standard)                   DOUBLE PASS (with pupil)
     ━━━━━━━━━━━━━━━━━━━━━━                   ━━━━━━━━━━━━━━━━━━━━━━━━
     
     Input → DMD(FP) → lens → IP1             Input → DMD(FP) → retro → DMD(IP1) → relay → IP2
                        │                                         │            │
                        ▼                                         ▼            ▼
               ┌─────────────────┐                       ┌──────────────┐  ┌──────────┐
               │  Beam with      │                       │  Beam with   │  │  Beam    │
               │  tails at 10⁻⁴  │                       │  full tails  │  │  WITHOUT │
               │                 │                       │  visible     │  │  tails   │
               │ ════╤════       │                       │ ════╤════    │  │ ════╤════│
               │     │  tail→    │                       │     │pupil   │  │     │    │
               │     │     →     │                       │     │clips→  │  │     │    │
               └─────────────────┘                       └──────────────┘  └──────────┘
               IX ~ 10⁻⁴ everywhere                    IP1 SQUARE pupil    IX < −50 dB >14w'
                                                       (ON) blocks tails   → −60 dB >30w'
     
     
     DMD PIXEL LAYOUT (per the paper — 2560 columns):
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Column:  0                    2060           2560
              │                     │              │
              ▼                     ▼              ▼
     ┌──────────────────────────────┬──────────────────┐
     │                              │                  │
     │   FP1  (Fourier plane)       │  IP1 (image      │
     │   1600 × 2060 pixels         │  plane region)   │
     │   IFTA hologram + secondary  │  1600 × 500 px   │
     │   multiplexing               │    ┌────────┐    │
     │                              │    │████████│    │ ← reflective
     │   (hologram in 0–1960; ~100  │    │█ pupil █│    │   SQUARE pupil
     │    px guard region to 2060)  │    │████████│    │   of size d
     │                              │    └────────┘    │
     └──────────────────────────────┴──────────────────┘
     Pink dashed line at col 2060 = FP1/IP1 demarcation
     
     Light hits FP1 → diffracts → retro-reflector bends it back
     → lands on IP1 region → only ON mirrors (square pupil) reflect
     → relay images IP1 onto IP2 with demagnification 0.6 (w' = 0.6 w)
     
     
     OPTICAL PATH (Fig. 1b of the paper):
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     fiber(370nm) → L1 collimate (waist 10 mm) → AS1 iris (illuminate FP1 only)
       → DMD FP1 → L2 (focal length f, on translation stage)
       → DMD is simultaneously at FP and IP of L2
       → DMD IP1 region [reflective pupil] → D-shaped mirror
       → AS2 iris at FP2 (blocks unwanted 2nd-pass diffraction orders)
       → two-lens relay (250 mm + 150 mm, demag 0.6) → IP2
     Monitoring: C1/C2 CMOS cameras (IP1', IP2), PD photodiode (IP2').
```

### 7.1 The Problem: Asymptotic Crosstalk Floor

IFTA optimizes the beam within a finite signal window D. Outside D, binarization artifacts
create a residual background floor (a nonzero far-wing crosstalk floor). This background
illumination accumulates across many exposed qubits, contributing an error that grows with
system size.

### 7.2 The Concept: Spatial Filtering at an Intermediate Image Plane

The DMD is reused in a **double-pass** configuration: the first pass (FP1 region) implements
the multiplexed Fourier-plane hologram; the second pass (IP1 region) implements a
programmable **reflective square pupil** at an intermediate image plane. ("Double-pass" here
means the beam interacts twice with different regions of the same reflective DMD.) The pupil
function is:

```
A_pupil(x) = { 1  for |x| ≤ d/2    (within pupil)
             { 0  for |x| > d/2    (blocked)
```

The field after the pupil:

```
E'_IP1(x) = A_pupil(x) × E_IP1(x)
```

For a Gaussian beam with waist w, the intensity outside the pupil drops to the diffraction limit of the relay optics (orders of magnitude below the binarization noise floor).

### 7.3 Diffraction-Limited Performance of the Pupil

The pupil acts as a rectangular (or circular) aperture. Its Fourier transform sets the minimum achievable spot size at IP2:

```
Airy radius at IP2 = 1.22 λ f₂ / d_pupil
```

The relay from IP1 to IP2 uses two lenses (250 mm and 150 mm) giving a demagnification of
**0.6**, so the waist at IP2 is w' = 0.6·w (e.g. w = 15 μm at IP1 → w' = 9 μm at IP2). The
imaged pupil is broadened and its edge softened by aberrations and diffraction in the relay,
so the effective aperture differs from the geometric-optics prediction.

### 7.4 The DMD as a Dynamic Pupil

Instead of a fixed mechanical iris, the unused IP1 region of the DMD serves as a
**programmable reflective square pupil**:

**DMD layout (per the paper):**
```
FP1: columns 0–2060  (1600 × 2060 px) — Fourier-plane hologram
                       (IFTA in 0–1960, ~100 px guard region up to 2060)
IP1: columns 2060–2560 (1600 × 500 px) — image-plane reflective pupil
```

The retro-reflector bends the first-order beam from FP1 back onto the IP1 region of the same
DMD chip. Only mirrors within the square pupil are ON (reflect toward the relay); mirrors
outside are OFF (tail light dumped).

**Beam-center calibration on IP1 (two steps):**
1. **Coarse search:** turn on successively smaller blocks of mirrors to narrow the beam
   location.
2. **Fine linear scan:** turn on individual micromirrors one by one; determine the center
   from the camera signal at IP2 (a photodiode at IP2' is used to locate the beam center).

**Advantages:** dynamic (position/size adjustable per site, no moving parts); fast (same
switching speed as the hologram, ~77 μs); no extra hardware (reuses the DMD).

### 7.5 Aberration in Double-Pass

The second pass introduces additional aberrations (Φ₂), so the FP1 hologram uses an aberration
map characterized all the way to IP2:

```
input_profile = exp(1j × (−Φ₀ − Φ₁ + Φ₂))
```

The sign convention accounts for the reversed beam direction on the second pass. If the signs
are wrong (e.g. +Φ₀ instead of −Φ₀), the aberration **doubles** instead of cancelling — a
common alignment pitfall.

### 7.6 Effective Aperture

The effective aperture d' at IP2 is **defined** (paper's benchmark) as the distance along the
ion axis at which the relative intensity crosstalk I_X falls below −50 dB. Because of finite
relay NA, d' > d always. As the pupil d shrinks, d' shrinks but **saturates at ≈ 14 w'**:

```
d ≈ 20w  →  d' ≈ 19w'
d ≈ 10w  →  d' ≈ 15w'
d ≈ 5w   →  d' ≈ 14w'   (Fig. 3a: pupil d = 5w gives d' ≈ 14w')
d ≈ 2.5w →  d' ≈ 13w'   (floor)
```

So the minimum effective aperture is ≈ 13–14 w'. Beyond ~14 w' the double pass drives
I_X below −50 dB; beyond ~30 w' it approaches −60 dB (10⁻⁶), near the detector noise floor.

### 7.7 AS2 Iris and Degradation from the Intermediate Image Plane

**AS1 / AS2 irises.** AS1 (at the input) ensures selective illumination of the FP1 region;
AS2 (at the intermediate Fourier plane FP2) blocks the unwanted diffraction orders generated
during the second pass.

**Degradation introduced by the double pass.** Comparing the single-pass (Fig. 2f) and
double-pass (Fig. 3a) results, the near-field crosstalk **increases by ~6 dB at 4w** when the
intermediate image plane is introduced. Causes identified in the paper:
- The IP1 beam waist is very small (~2 DMD pixels), making it hard to block multiple DMD
  diffraction orders through AS2 while still passing the desired Fourier components.
- Scattering from the DMD mirror surfaces at IP1.
- The ON mirrors do not form a continuous plane, introducing additional aberrations.

Crucially, the secondary holograms can still cancel this extra near-field crosstalk by
destructive interference — demonstrating the robustness of combining both techniques. The
paper notes this could be further improved by adding aberration compensation between IP1 and
IP2 (e.g. a deformable mirror).

### 7.8 Combined Strategy and Multi-Qubit Extension

The combined approach — Fourier-plane multiplexing (near sites, within d') plus image-plane
filtering (far tail) — maintains I_X ≤ −50 dB (10⁻⁵) across the full field and reaches
≈ −60 dB (10⁻⁶) beyond ~30 w'. The scheme extends to multiple qubits without hardware
changes: multiple pupils can independently filter well-separated qubits, while a single pupil
combined with multiplexed secondary holograms can cover several nearby qubits.

---

## 8. Intensity Crosstalk and Measurement Error

```
     THE ION CHAIN AND ADDRESSING BEAM
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Addressing beam intensity profile:
     
                                  ╭──────╮
                                 ╱        ╲
                                ╱          ╲
                               ╱            ╲
                         ─────╱──────────────╲─────────────────── noise floor
                             ╱                ╲
     ━━━━━━━━━━━━━━━━━━━━━━━╱━━━━━━━━━━━━━━━━━━╲━━━━━━━━━━━━━━━━━━━
     ions:   ●       ●       ●       ●       ●       ●       ●
            -3a     -2a     -a      0 (x₀)   +a     +2a     +3a
                                    ▲         ▲
                                    │         │
                              process ion   asset ion
                              (addressed)   (must be preserved)
     
     IX = I(x₀+a) / I(x₀) = intensity at asset / intensity at process
     
     
     SOURCES OF ERROR AT THE ASSET ION:
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     ┌────────────────────────────────────────────────────────────────┐
     │  Source 1: INTENSITY CROSSTALK (optical)                       │
     │                                                                │
     │  Leaked photons from imperfect beam hit the asset ion          │
     │  n_scattered = (Γ/2) × IX × τ_detection                       │
     │  P_AQM ∝ IX × τ_det                                           │
     │                                                                │
     │  ← This is what we minimize with IFTA, secondary grating,     │
     │     and double-pass pupil                                      │
     ├────────────────────────────────────────────────────────────────┤
     │  Source 2: INTER-ION SCATTERING (fundamental, irreducible)     │
     │                                                                │
     │  Process ion scatters photons in all directions                │
     │  Some hit the asset ion at distance a:                         │
     │                                                                │
     │       ● ─── scattered photon (all polarizations) ───► ●       │
     │    process                    4 μm                   asset     │
     │                                                                │
     │  I_abs = f_pol × f_angle × hν×R_sc / (4πa²)                   │
     │        = (1/3) × 1 × ... ≈ 2.14×10⁻⁵ I_sat (detection)       │
     │        = (2/3) × (1/2) × ... ≈ 2.92×10⁻⁶ I_sat (reset)       │
     │                                                                │
     │  ← This CANNOT be reduced by any optical technique.            │
     │     It sets the fundamental floor.                             │
     └────────────────────────────────────────────────────────────────┘
     
     
     PERFORMANCE EVOLUTION:
     ━━━━━━━━━━━━━━━━━━━━━
     
       0 dB ┤ ╭──╮        IFTA        +SecGrating(multiplexed)   +DoublePass
            │╱    ╲
      -20 dB┤      ╲
            │       ╲
    -42.6dB ┤        ╲──── baseline ────
            │
      -50 dB┤          multiplexed ≲ −50 dB (10⁻⁵) across field
            │
      -60 dB┤                                          −60 dB (10⁻⁶) >30w'──
            ├──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──
              0  4w  8w  12w 14w      20w         30w
              
              ◄── multiplexed secondary gratings (±4w,±8w,±12w) ──►
                                    ◄─── double-pass pupil (>14w') ───►
```

### 8.1 Definition of Intensity Crosstalk

```
IX = I_asset / I_process = I(x₀ + a) / I(x₀)
```

where x₀ is the process ion position and a is the inter-ion spacing.

### 8.2 Scattering Rate at the Asset Ion

For a two-level atom illuminated with intensity I:

```
R_sc = (Γ/2) × (I/I_sat) / (1 + 4(Δ/Γ)² + I/I_sat)
```

For detection (Δ ≈ 0, I_process = I_sat):

```
R_sc,asset ≈ (Γ/2) × IX / (1 + IX)  ≈  (Γ/2) × IX    (since IX ≪ 1)
```

The number of photons scattered at the asset ion during detection time τ_det:

```
n_photons = R_sc,asset × τ_det = (Γ/2) × IX × τ_det
```

### 8.3 Probability of Accidental Quantum Measurement

Each scattered photon has a probability of projecting the asset qubit into a definite state (collapsing the superposition). The probability of AQM after scattering n photons:

```
P_AQM = 1 − (1 − p_collapse)^n ≈ n × p_collapse   (for small n)
```

For detection: p_collapse ≈ 1 per photon (each 369 nm photon can cause a state-changing transition). Therefore:

```
P_AQM ∝ IX × τ_det
```

### 8.4 Inter-Ion Scattering (Fundamental Limit)

Even with IX = 0 (perfect addressing beam), the process ion scatters photons in all directions. Some are absorbed by the asset ion:

```
I_absorbed = f_pol × f_angle × (hν × R_sc,process) / (4π a²)
```

For ¹⁷¹Yb⁺ detection (π polarization affects asset, σ±/π illumination):
- f_pol = 1/3 (fraction with π polarization)
- f_angle = sin²(θ_B) = 1 (B-field perpendicular to chain)
- a = 4 μm

Result: I_abs ≈ 2.14 × 10⁻⁵ I_sat

This sets the absolute floor. No optical technique can do better than this. The
secondary-grating / multiplexing method (IX ≲ 10⁻⁵, −50 dB) approaches this limit.

### 8.5 Cumulative Error in an Ion Chain

For N ions in a chain, each at distance d_i from the process ion:

```
P_AQM,total = Σᵢ P_AQM,i = Σᵢ c × IX(d_i) × τ_det
```

If IX saturates at IX_∞ beyond some distance:

```
P_AQM,total ≈ N × c × IX_∞ × τ_det
```

Using the per-ion relation P_AQM ≈ 10⁻³ at IX = 10⁻⁴ (from Motlakunta 2024; the detection value can be up to ~4×10⁻³ at 11 μs, reset is ~10⁻³):

For N = 30, IX_∞ = 10⁻⁴:
- P_AQM,total ≈ 30 × 10⁻³ ≈ 0.03 (≈ 3% — unacceptable for error correction)

With double-pass pupil (IX_∞ = 10⁻⁶, a 100× reduction):
- P_AQM,total ≈ 30 × 10⁻⁵ ≈ 3×10⁻⁴ (≈ 0.03% — excellent)

(This is an upper bound: it assumes every ion sits at the asymptotic floor IX_∞. In reality, near neighbors dominate and the far ions contribute less, so the true cumulative error is somewhat lower.)

### 8.6 Error Correction Requirements

For a surface code with minimum weight perfect matching (MWPM) decoder:
- Threshold: P_measurement_error < 0.57%
- Including all ions in chain: P_total must satisfy this

This motivates the combined approach: IFTA for the signal window, secondary grating for nearest neighbors, double-pass pupil for long-range.

---

## 9. High Dynamic Range Imaging

```
     THE DYNAMIC RANGE PROBLEM
     ━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Single exposure (12-bit camera):          Need to measure:
     
     ┌─────────────────────────┐               ┌─────────────────────────┐
     │ ████████                │               │                         │
     │ ████████ ← saturated    │               │ 10⁰  (peak)             │
     │ ████████                │               │ 10⁻¹                    │
     │ ████████                │               │ 10⁻²                    │
     │ ▓▓▓▓▓▓▓▓                │               │ 10⁻³                    │
     │ ░░░░░░░░ ← noise floor  │               │ 10⁻⁴  (IFTA limit)      │
     │          (can't see     │               │ 10⁻⁵  (scattering)      │
     │           below here)   │               │ 10⁻⁶  (double-pass)     │
     └─────────────────────────┘               └─────────────────────────┘
     Dynamic range: ~10³                       Required range: 10⁶
     
     
     MULTI-EXPOSURE HDR SOLUTION:
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Exposure:   120 μs      1.2 ms      12 ms      120 ms     1.2 s      12 s
                 ──────      ──────      ─────      ──────     ─────      ────
     Captures:   peak        mid         shoulder   tail       far tail   floor
     
     ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
     │█████│    │█████│    │▓▓▓▓▓│    │░░▓▓░│    │░░░▓░│    │░░░░░│
     │█peak│    │▓▓▓▓▓│    │░░▓░░│    │░░░░░│    │░░░░░│    │░░░░▓│
     │█████│    │░░░░░│    │░░░░░│    │░░░░░│    │░░░░░│    │░░░░░│
     └─────┘    └─────┘    └─────┘    └─────┘    └─────┘    └─────┘
     
     Each: foreground (DMD on) + background (DMD off) × 3 iterations
     
     Stitched result:
     ┌────────────────────────────────────────────────────────────┐
     │  10⁰ ─ from 120 μs exposure (peak not saturated)           │
     │  10⁻² ─ from 12 ms exposure (good S/N in shoulder)         │
     │  10⁻⁴ ─ from 1.2 s exposure (tail visible above noise)     │
     │  10⁻⁶ ─ from 12 s exposure (noise floor measurement)       │
     └────────────────────────────────────────────────────────────┘
     
     → Complete intensity profile spanning 6 orders of magnitude
```

### 9.1 The Dynamic Range Problem

A CMOS camera (FLIR BFS-PGE-120S4M-CS) has:
- Bit depth: 12 bits → 4096 gray levels
- Practical dynamic range: ~10³ (limited by read noise, dark current)

To measure IX = 10⁻⁶, we need intensity measurement spanning 6 orders of magnitude — far exceeding a single exposure's capability.

### 9.2 Multi-Exposure HDR Technique

Capture images at geometrically spaced exposure times:

```
τ_exp ∈ {120 μs, 1.2 ms, 12 ms, 120 ms, 1.2 s, 12 s}
```

Each exposure is 10× longer than the previous, covering one additional order of magnitude.

For each exposure:
1. **Background (DMD OFF):** Captures camera noise + stray ambient light
2. **Foreground (DMD ON):** Captures beam + noise

The beam intensity at each pixel:

```
I_corrected(x, τ) = [I_foreground(x, τ) − I_background(x, τ)] / τ
```

### 9.3 Stitching

The HDR profile is constructed by:
1. Using short-exposure data where the peak is not saturated
2. Using long-exposure data where the tails have sufficient signal-to-noise
3. Normalizing each exposure by its duration to get intensity (counts/second)
4. Selecting the best-exposed pixels from each layer

The result: a single intensity profile from I_peak (10⁰) down to the noise floor (10⁻⁶).

### 9.4 Camera Linearity

The camera's response must be linear (pixel value ∝ incident photons). This is verified by:
- Fixing exposure time
- Varying input power (via neutral density filters)
- Confirming linear relationship between pixel value and power

The FLIR BFS-PGE-120S4M-CS has been confirmed linear across its full range.

### 9.5 Error Sources in HDR

- **Shot noise:** √N statistics at low photon counts (long exposures, tail regions)
- **Mechanical drift:** DMD or camera moves between exposures (mitigate with rigid mounting)
- **Beam pointing fluctuation:** Laser pointing varies shot-to-shot (~1 pixel jitter observed)
- **Background subtraction residuals:** Stray light that varies with DMD state

Typical measurement uncertainty: ±1 dB in the tail region (limited by shot noise at 12 s exposures).

---

## Summary of Physical Parameters

```
     COMPLETE SYSTEM EVOLUTION — FROM CONCEPT TO ION ADDRESSING
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

     LEVEL 0: BASIC CONCEPT
     ┌──────────────┐    ┌────┐    ┌──────────────┐
     │  369 nm      │───►│lens│───►│  Ion chain   │
     │  laser       │    └────┘    │  ● ● ● ● ●   │
     │  (global)    │              └──────────────┘
     └──────────────┘              Cannot address single ion!

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 1: ADD DMD + FOURIER HOLOGRAPHY
     ┌──────────┐    ┌─────┐    ┌────┐    ┌──────────────┐
     │  369 nm  │───►│ DMD │───►│lens│───►│  Ion chain   │
     │  laser   │    │(FP) │    └────┘    │  ● ● ◉ ● ●   │
     └──────────┘    └─────┘              └──────────────┘
                     Binary grating        Beam on ONE ion
                     IX ~ 10⁻² (poor — aberrations dominate)

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 2: ADD ABERRATION COMPENSATION
     ┌──────────┐    ┌─────┐    ┌────┐    ┌──────────────┐
     │  369 nm  │───►│ DMD │───►│lens│───►│  Ion chain   │
     │  laser   │    │(FP) │    └────┘    │  ● ● ◉ ● ●   │
     └──────────┘    │+Φ_in│              └──────────────┘
                     └─────┘              Clean Gaussian!
                     Aberration map        IX ~ 10⁻³ (better)
                     encoded in grating

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 3: ADD IFTA (ITERATIVE OPTIMIZATION)
     ┌──────────┐    ┌──────┐    ┌────┐    ┌──────────────┐
     │  369 nm  │───►│ DMD  │───►│lens│───►│  Ion chain   │
     │  laser   │    │IFTA  │    └────┘    │  ● ● ◉ ● ●   │
     └──────────┘    │+aberr│              └──────────────┘
                     └──────┘              Optimized in window
                     2000 iterations       IX < 10⁻⁴ (state of art)
                     on GPU

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 4: ADD SECONDARY GRATING (nearest neighbor)
     ┌──────────┐    ┌─────────┐  ┌────┐  ┌───────────────────┐
     │  369 nm  │───►│DMD      │─►│lens│─►│  Ion chain        │
     │  laser   │    │ ┌─────┐ │  └────┘  │  ● ● ◉ ● ●        │
     └──────────┘    │ │2ndry│ │          │      ↑ destructive│
                     │ │grat │ │          │      interference │
                     │ └─────┘ │          └───────────────────┘
                     └─────────┘          IX ≲ 10⁻⁵ (−50 dB) at 4w
                     Primary + secondary   (−42.6→−48 dB single; ≲−50 dB multiplexed)

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 5: ADD DOUBLE PASS PUPIL (long range)
     ┌────────┐   ┌──────────────────────────────┐  ┌─────┐  ┌────────┐
     │ 370 nm │──►│ DMD                          │  │relay│  │  IP2   │
     │ laser  │   │ ┌──────────┐  ┌────────────┐ │─►│0.6× │─►│ ●●◉●●  │
     └────────┘   │ │  FP1     │  │  IP1 pupil │ │  └─────┘  └────────┘
                  │ │(hologram)│  │  ┌───────┐ │ │
                  │ │          │◄─┤  │███████│ │ │ ← retro-reflected
                  │ └──────────┘  │  │█square█│ │ │    beam lands here
                  │               │  │███████│ │ │
                  │               │  └───────┘ │ │
                  │               └────────────┘ │
                  └──────────────────────────────┘
                  
                  IX < −50 dB beyond ~14w' ; → −60 dB (10⁻⁶) beyond ~30w'
                  Approaches detector noise floor (near inter-ion scattering limit)

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 6: INTEGRATE WITH ARTIQ CONTROL SYSTEM
     ┌──────────────────────────────────────────────────────────┐
     │  ARTIQ experiment                                        │
     │                                                          │
     │  prepare():                                              │
     │    self.dmd.prepare_flut_sequence(...)  ← RPC to server  │
     │                                                          │
     │  @kernel run():                                          │
     │    self.dmd_advance()  ← TTL trigger (80 μs switching)   │
     │                                                          │
     │  All levels (1–5) wrapped in a single server call.       │
     │  Hologram cache avoids recomputation.                    │
     │  FLUT enables arbitrary shot ordering.                   │
     │  Deterministic real-time triggering via Kasli FPGA.      │
     └──────────────────────────────────────────────────────────┘
```

| Parameter | Symbol | Value | Origin |
|-----------|--------|-------|--------|
| Wavelength | λ | 369.5 nm (paper: ≈370 nm; code uses 369 nm) | Yb⁺ ²S₁/₂ → ²P₁/₂ |
| Focal length (L2) | f | 150 mm or 250 mm | depends on configuration (paper Fig. 2/3) |
| Pixel pitch | Δ | 7.56 μm (paper: 7.6 μm) | DLP9000XUV datasheet |
| Array size | N_x × N_y | 2560 × 1600 | DLP9000XUV; physical 19.5 mm × 12.1 mm |
| FP1 region | — | 1600 × 2060 px | Fourier-plane hologram (paper) |
| IP1 region | — | 1600 × 500 px | image-plane reflective pupil (paper) |
| Input collimated waist | — | 10 mm | L1 collimation onto DMD (paper) |
| Grating periodicity | p | 4 pixels | efficiency vs. separation trade-off |
| Grating angle | θ | −π/4 rad | diamond-lattice mirror tilt axis |
| Mirror tilt | — | ±12° | DLP9000XUV |
| IP1→IP2 demagnification | — | 0.6 | two-lens relay (250 mm + 150 mm) |
| Beam waist at IP1 | w | 9–30 μm | configuration-dependent (paper) |
| Beam waist at IP2 | w′ = 0.6w | e.g. 9 μm (from w=15 μm) | after 0.6 relay |
| Beam waist at ions | w_ion | 1 μm | downstream objective (thesis; not in this paper) |
| Ion–ion separation | a | 4 μm | Bloodstone trap (nearest neighbor = 4w) |
| Secondary window | m × l | 2 × 460 px | along transverse × ion axis (paper) |
| Optimal secondary phase | Φ_s | 2.77π | Fig. 2c fit |
| Optimal secondary amplitude | A_s | 0.38 | Fig. 2d fit |
| Effective aperture (min) | d′ | ≈14 w′ | saturates as pupil shrinks (paper Fig. 3b) |
| Scaling factor | Λ = λf | 92.25 μm·mm (f=250) | FP↔IP mapping |
| Min picture time | — | 77 μs | DDR→DMD transfer (hardware) |
| Mirror settling | — | ~20 μs | MEMS transition |
| Saturation intensity | I_sat | 51 mW/cm² | Yb⁺ ²S₁/₂ → ²P₁/₂ |
| Linewidth | Γ | 2π × 19.6 MHz | ²P₁/₂ natural linewidth |
| Detection time | τ_det | 11–20 μs | limited by photon collection |
| Reset time | τ_reset | 1–10 μs | optical pumping to \|↓⟩ |

---

## References

0. **Mahato, S. & Islam, R. "Achieving 10⁻⁵ level relative intensity crosstalk in optical holographic qubit addressing via a double-pass digital micromirror device." arXiv:2512.13882v1 (2025). — primary reference for the double-pass and multiplexing results.**
1. **Shih, C.-Y. et al. "Reprogrammable and high-precision holographic optical addressing of trapped ions for scalable quantum control." *npj Quantum Information* 7, 57 (2021). https://www.nature.com/articles/s41534-021-00396-0 — foundational reference: high-precision IFTA (>1 order of magnitude accuracy gain over prior algorithms), in-situ aberration characterization using the ions as the wavefront sensor (baseline IX ~ 10⁻⁴), and DMD+AOM multi-frequency zone addressing.**
2. Motlakunta, S. et al. "Preserving a qubit during state-destroying operations on an adjacent qubit at a few micrometers distance." *Nature Communications* 15, 6575 (2024).
3. Mahato, S. "Mitigating Optical Crosstalk for In-Situ Mid-Circuit Measurement and Reset in a Trapped-Ion Quantum Simulator." MSc Thesis, University of Waterloo, 2025.
4. Zupancic, P. et al. "Ultra-precise holographic beam shaping for microscopic quantum control." *Optics Express* 24(13), 13881–13893 (2016).
5. Shih, C.-Y. "Holographic Optical Manipulation of Trapped Ions for Quantum Simulation." MSc Thesis, University of Waterloo, 2019.
6. Gaunt, A. L. & Hadzibabic, Z. "Robust digital holography for ultracold atom trapping." *Scientific Reports* 2, 721 (2012).
7. Lee, W.-H. "Computer-generated holograms: Techniques and applications." *Progress in Optics* 16, 119–232 (1978).
8. Wyrowski, F. "Iterative quantization of digital amplitude holograms." *Applied Optics* 28(18), 3864–3870 (1989).
9. Pasienski, M. & DeMarco, B. "A high-accuracy algorithm for designing arbitrary holographic atom traps." *Optics Express* 16(3), 2176–2190 (2008).
