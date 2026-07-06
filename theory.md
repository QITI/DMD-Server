# Optical Theory of DMD-Based Holographic Beam Shaping

This document provides the complete optical and mathematical background for every capability implemented in the DMD server. It is intended as a self-contained reference for anyone working on or extending the system.

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
     │ █░█░█░█░█░█░█░█░█░█░█░ │  ──►    │  (2×aberr)  (residual)   │
     │ ░█░█░█░█░█░█░█░█░█░█░█ │  lens   │     ●          ●         │
     │ █░█░█░█░█░█░█░█░█░█░█░ │         │                     ●    │
     │ ░█░█░█░█░█░█░█░█░█░█░█ │         │                   m=+1   │
     │ █░█░█░█░█░█░█░█░█░█░█░ │         │             (aberr-free!)│
     └────────────────────────┘         │                 ← USED   │
                                        └──────────────────────────┘
     period = 4 pixels
     (ON/OFF alternating                  Three orders separated by
      with phase modulation)              x₁ = λf/p = 3.05 mm
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

where A_in(k) is the (real) amplitude profile of the illumination (typically Gaussian).

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

### 5.5 Multi-Stage Aberration Characterization

The total aberration is measured in stages:

**Φ₀ (zeroth-order map):** Measures aberrations from the input source through the lens to the camera. Both patches have trivial (no-grating) patterns. The fringe encodes path-length differences.

**Φ₁ (first-order map):** Patches now display grating patterns that produce first-order beams. This adds the aberration from the diffraction process itself (e.g., the non-flat DMD surface affects different orders differently).

**Φ₂ (second-pass map, double-pass only):** Same process but after the retro-reflected beam returns to the DMD. Captures additional aberrations from the retro-reflector optics.

**Combined correction:**
- Single pass: input_profile = exp(1j × (Φ₀ + Φ₁))
- Double pass: input_profile = exp(1j × (−Φ₀ − Φ₁ + Φ₂))

The sign flip in double-pass is because the light traverses the system in reverse on the second pass.

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

The DMD pixel pitch (7.56 μm) sets the resolution of the aberration map. The patch size used for measurement (typically 8×8 pixels) and grid spacing (typically 20 pixels) determine:

```
Phase map resolution = grid_spacing × pixel_size = 20 × 7.56 μm = 151 μm
```

This is much finer than a Shack-Hartmann wavefront sensor (micro-lens diameter > 150 μm). The DMD-based measurement resolves aberrations at a scale matched to the hologram pixel size.

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
      -40 dB┤╱──────────╲─── ← IX=10⁻⁴        -40 dB┤╱          ╲
            │            ↑                          │       ╭╮   ╲── suppressed!
      -60 dB┤     neighbor here               -50 dB┤       ╰╯    ← IX=10⁻⁴·⁹
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
     │ ░░░░░░░░░░░░░░░░░░░░░░██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░ │   (3×400 px)
     │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
     └──────────────────────────────────────────────────────────────────────┘
     
     
     INTERFERENCE AT NEIGHBOR:
     ━━━━━━━━━━━━━━━━━━━━━━━━━
     
     E_total(4w) = Ã₁·e^(iφ₁)  +  Ã₂·e^(iφ₂)
                   ──────────      ──────────
                   primary tail    secondary beam
     
     I = Ã₁² + Ã₂² + 2Ã₁Ã₂·cos(φ₁ − φ₂)
     
     Optimize:
       ① Scan φ₂: 0 → 4π  → find destructive condition (φ₁−φ₂ = π)
       ② Scan Ã₂ at optimal φ₂ → match amplitudes (Ã₂ ≈ Ã₁)
       → I_min = (Ã₁ − Ã₂)² → 0
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

A rectangular window of dimensions l × m (pixels) on the FP carries a secondary grating:

```
F_s(k) = (η / E_in(k)) × A'₂ × rect(k/l) × ½ × [cos(2π k_a·k/(λf) + Φ_in − φ₂) + 1]
```

where:
- A'₂: controllable amplitude (0 to 1)
- k_a: spatial frequency corresponding to position x₀ + a
- φ₂: controllable phase
- rect(k/l): confines the grating to a small window

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

In practice, achieving exactly Ã₂ = Ã₁ is difficult, but significant suppression (6+ dB) is achievable.

### 6.6 Periodicity Calculation

The secondary beam must appear at distance Δx from the first-order origin. The required grating periodicity (in physical units) is:

```
p_secondary = cos(θ) × λ × f / (Δx × pixel_size)
```

For Δx = 4w = 4 × 9 μm = 36 μm (at IP1, where the beam waist is 9 μm before demagnification):

```
p_secondary = cos(π/4) × 369e-9 × 0.25 / (36e-6 × 7.56e-6)
            = 0.707 × 9.225e-8 / 2.72e-10
            ≈ 240 (pixels per period, non-integer → produces a smooth variation)
```

Note: the periodicity is large because the secondary beam needs to be close to the primary beam.

### 6.7 Optimization Procedure

1. **Phase scan:** Fix A'₂ = 0.7 (arbitrary starting point). Scan φ₂ from 0 to 4π. Plot I(x₀+a) vs φ₂. The minimum gives φ₂,opt.

2. **Amplitude scan:** Fix φ₂ = φ₂,opt. Scan A'₂ from 0 to 1. Fine-tune for lowest I(x₀+a).

The 4π range (instead of 2π) accounts for potential phase wrapping ambiguities in the grating implementation.

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
               IX ~ 10⁻⁴ everywhere                      IP1 pupil (ON)    IX ~ 10⁻⁶
                                                         blocks tails      beyond 14w
     
     
     DMD PIXEL LAYOUT (2560 columns):
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Column:  0            1960  2060          2560
              │              │    │              │
              ▼              ▼    ▼              ▼
     ┌────────────────────────┬──┬──────────────────┐
     │                        │  │                  │
     │   FOURIER PLANE (FP)   │BF│  IMAGE PLANE 1   │
     │   IFTA hologram        │  │  (IP1 PUPIL)     │
     │   (primary grating)    │UF│                  │
     │                        │  │    ┌─────────┐   │
     │   1960 × 1600 pixels   │FE│    │ ○○○○○○  │   │
     │                        │  │    │ ○pupil○ │   │
     │   Generates the beam   │R │    │ ○○○○○○  │   │
     │                        │  │    └─────────┘   │
     │                        │  │                  │
     └────────────────────────┴──┴──────────────────┘
     
     BF = 100-pixel buffer (all OFF, optical separation)
     
     Light hits FP → diffracts → retro-reflector bends it back
     → lands on IP1 region → only ON mirrors (pupil) reflect
     → relay lens images to IP2 (ion plane)
     
     
     OPTICAL PATH:
     ━━━━━━━━━━━━━
     
                ┌─────────────────────────────────────────┐
                │                                         │
     Input ──►  │  DMD (FP region)                        │
     beam       │      │                                  │
                │      ▼ first-order diffraction          │
                │      │                                  │
                │  Retro-reflector board                  │
                │  (250mm lens + 2 mirrors)               │
                │      │                                  │
                │      ▼ beam returns to DMD              │
                │                                         │
                │  DMD (IP1 region) ← PUPIL HERE          │
                │      │                                  │
                └──────┼──────────────────────────────────┘
                       │
                       ▼ D-shaped mirror reflects
                       │
                    f₁=250mm lens → FP2 iris → f₂=150mm lens
                       │
                       ▼
                    IP2 (camera or ion plane)
```

### 7.1 The Problem: Asymptotic Crosstalk Floor

IFTA optimizes the beam within a finite signal window D. Outside D, binarization artifacts create a uniform noise floor at ~10⁻⁴. For a chain of N ions, the cumulative measurement error grows as N × 10⁻³.

### 7.2 The Concept: Spatial Filtering at an Intermediate Image Plane

Place a sharp aperture (pupil) at an intermediate image plane (IP1). The pupil function is:

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

For the relay system (f₁ = 250 mm, f₂ = 150 mm) and pupil size d = 2w:
- The beam at IP2 has an effective aperture d' slightly larger than d due to finite relay NA
- Measured: d' ≈ 10–14w for the smallest practical pupil sizes

### 7.4 The DMD as a Dynamic Pupil

Instead of a fixed mechanical iris, we use unused DMD pixels as the pupil:

**DMD layout:**
```
Columns 0–1960:    Fourier Plane hologram (primary grating)
Columns 1960–2060: Buffer zone (all OFF)
Columns 2060–2560: Image Plane 1 pupil
```

The retro-reflector board bends the first-order beam from the FP hologram back onto the IP1 region of the same DMD chip. Only mirrors within the pupil circle are turned ON — they reflect the beam toward the relay optics. Mirrors outside the pupil are OFF — the tail light is dumped.

**Advantages:**
- Dynamic: pupil position and size can be adjusted per-ion without mechanical changes
- Fast: same switching speed as the hologram (~77 μs)
- No extra hardware: reuses the existing DMD

### 7.5 Aberration in Double-Pass

The second pass through the retro-reflector introduces additional aberrations (Φ₂). The total aberration correction becomes:

```
For the FP hologram (first pass):
  input_profile = exp(1j × (−Φ₀ − Φ₁ + Φ₂))
```

The sign convention accounts for the reversed beam direction on the second pass. If the signs are wrong (e.g., using +Φ₀ instead of −Φ₀), the aberration **doubles** instead of canceling — a common alignment pitfall.

### 7.6 Effective Aperture

Due to the finite numerical aperture of the f₁+f₂ relay, the effective aperture d' at IP2 is always larger than the physical pupil d at IP1:

```
d'(w) > d(w)  for all practical d
```

Empirically measured relationship:
- d = 20w → d' ≈ 20w (relay is wide enough, negligible diffraction)
- d = 5w → d' ≈ 13w (diffraction broadening becomes significant)
- d = 2w → d' ≈ 10w (diffraction-limited, minimum effective aperture)

The minimum effective aperture (10–14w) determines the range beyond which IX drops to the noise floor (~10⁻⁶). This corresponds to beyond the third nearest neighbor.

### 7.7 FP2 Iris Filtering

An additional iris at the Fourier plane of the f₁+f₂ relay (FP2) further reduces noise:
- Blocks higher diffraction orders from the DMD micro-mirror structure
- Reduces scattered light from gaps between mirrors
- Narrowing from 10 mm to 7 mm diameter significantly improves the noise floor

---

## 8. Intensity Crosstalk and Measurement Error

```
     THE ION CHAIN AND ADDRESSING BEAM
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     Addressing beam intensity profile:
     
                        ╭────╮
                       ╱      ╲
                      ╱        ╲
                     ╱          ╲
              ─────╱──────────────╲─────────────────── noise floor
                  ╱                ╲
     ━━━━━━━━━━━╱━━━━━━━━━━━━━━━━━━╲━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
     
       0 dB ┤ ╭──╮           IFTA            +SecGrating     +DoublPass
            │╱    ╲
      -20 dB┤      ╲
            │       ╲
      -40 dB┤        ╲───── 10⁻⁴ ────────── 10⁻⁴·⁹ ──
            │
      -50 dB┤                                          ── inter-ion limit
            │
      -60 dB┤                                                    10⁻⁶ ──
            ├──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──
              0  2w 4w 6w 8w 10w 12w 14w 16w 18w 20w
              
              ◄─── secondary grating ───►
                   helps here
                                         ◄─── double-pass pupil ───►
                                               helps here
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

This sets the absolute floor. No optical technique can do better than this. The secondary grating method (IX → 10⁻⁴·⁹) approaches this limit.

### 8.5 Cumulative Error in an Ion Chain

For N ions in a chain, each at distance d_i from the process ion:

```
P_AQM,total = Σᵢ P_AQM,i = Σᵢ c × IX(d_i) × τ_det
```

If IX saturates at IX_∞ beyond some distance:

```
P_AQM,total ≈ N × c × IX_∞ × τ_det
```

For N = 30, IX_∞ = 10⁻⁴, τ_det = 11 μs:
- P_AQM,total ≈ 30 × 4×10⁻³ ≈ 0.12 (12% — unacceptable)

With double-pass pupil (IX_∞ = 10⁻⁶):
- P_AQM,total ≈ 30 × 4×10⁻⁵ ≈ 0.0012 (0.12% — excellent)

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
                     └─────────┘          IX ~ 10⁻⁴·⁹ at 4w
                     Primary + secondary   (+6 dB suppression)

     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     
     LEVEL 5: ADD DOUBLE PASS PUPIL (long range)
     ┌────────┐   ┌──────────────────────────────┐  ┌─────┐  ┌────────┐
     │ 369 nm │──►│ DMD                          │  │f1+f │  │  Ions  │
     │ laser  │   │ ┌──────────┐  ┌────────────┐ │─►│relay│─►│ ●●◉●●  │
     └────────┘   │ │  FP      │  │  IP1 pupil │ │  └─────┘  └────────┘
                  │ │(hologram)│  │  ┌───────┐ │ │
                  │ │          │◄─┤  │○○○○○○○│ │ │ ← retro-reflected
                  │ └──────────┘  │  │○pupil○│ │ │    beam lands here
                  │               │  │○○○○○○○│ │ │
                  │               │  └───────┘ │ │
                  │               └────────────┘ │
                  └──────────────────────────────┘
                  
                  IX < 10⁻⁶ beyond 14w (noise floor limited)
                  Approaches fundamental inter-ion scattering limit

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
| Wavelength | λ | 369 nm | Yb⁺ ²S₁/₂ → ²P₁/₂ transition |
| Focal length | f | 250 mm | Fourier lens |
| Pixel pitch | Δ | 7.56 μm | DLP9000XUV spec |
| Array size | N_x × N_y | 2560 × 1600 | DLP9000XUV spec |
| Grating periodicity | p | 4 pixels | Design choice (trade-off: efficiency vs. separation) |
| Grating angle | θ | −π/4 rad | Diamond lattice mirror tilt axis |
| Beam waist (at IP1) | w_IP1 | 9 μm | = 9× demag from w_ion = 1 μm |
| Beam waist (at ions) | w_ion | 1 μm | ≈ a/4 for 4 μm spacing |
| Ion-ion separation | a | 4 μm | Trap design (Bloodstone) |
| Nearest neighbor distance | 4w | 4 μm | = a (by design of w) |
| Scaling factor | Λ = λf | 92.25 μm·mm | Sets FP↔IP coordinate mapping |
| Min picture time | — | 77 μs | DDR→DMD transfer (hardware limit) |
| Mirror settling | — | ~20 μs | Mechanical MEMS transition |
| Saturation intensity | I_sat | 51 mW/cm² | Yb⁺ ²S₁/₂ → ²P₁/₂ |
| Linewidth | Γ | 2π × 19.6 MHz | ²P₁/₂ natural linewidth |
| Detection time | τ_det | 11–20 μs | Limited by photon collection |
| Reset time | τ_reset | 1–10 μs | Optical pumping to |↓⟩ |

---

## References

1. Shih, C.-Y. et al. "Reprogrammable and high-precision holographic optical addressing of trapped ions for scalable quantum control." *npj Quantum Information* 7, 57 (2021).
2. Motlakunta, S. et al. "Preserving a qubit during state-destroying operations on an adjacent qubit at a few micrometers distance." *Nature Communications* 15, 6575 (2024).
3. Mahato, S. "Mitigating Optical Crosstalk for In-Situ Mid-Circuit Measurement and Reset in a Trapped-Ion Quantum Simulator." MSc Thesis, University of Waterloo, 2025.
4. Zupancic, P. et al. "Ultra-precise holographic beam shaping for microscopic quantum control." *Optics Express* 24(13), 13881–13893 (2016).
5. Shih, C.-Y. "Holographic Optical Manipulation of Trapped Ions for Quantum Simulation." MSc Thesis, University of Waterloo, 2019.
6. Gaunt, A. L. & Hadzibabic, Z. "Robust digital holography for ultracold atom trapping." *Scientific Reports* 2, 721 (2012).
7. Lee, W.-H. "Computer-generated holograms: Techniques and applications." *Progress in Optics* 16, 119–232 (1978).
8. Wyrowski, F. "Iterative quantization of digital amplitude holograms." *Applied Optics* 28(18), 3864–3870 (1989).
9. Pasienski, M. & DeMarco, B. "A high-accuracy algorithm for designing arbitrary holographic atom traps." *Optics Express* 16(3), 2176–2190 (2008).
