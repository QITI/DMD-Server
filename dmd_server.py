"""
DMD NDSP Server for Bloodstone ARTIQ Control System

This server exposes RPC methods for controlling the Vialux DLP9000XUV DMD
via the sipyco protocol, following the same pattern as the Spectrum AWG server.

Usage:
    python dmd_server.py [--port 12345] [--bind 0.0.0.0]

Requirements:
    - Windows OS (ALP4lib DLL dependency)
    - pySLM2 (hologram computation)
    - ALP4lib (Vialux hardware control)
    - TensorFlow with GPU (for IFTA acceleration)
    - sipyco (ARTIQ RPC transport)
"""

import argparse
import hashlib
import time
import os
import ctypes as ct

import numpy as np

from sipyco.pc_rpc import simple_server_loop

# Conditional imports for hardware that may not be present during development
try:
    from ALP4 import (
        ALP4, ALP_OK, ALP_DEFAULT, ALP_ENABLE,
        ALP_AVAIL_MEMORY, ALP_DEV_DISPLAY_WIDTH, ALP_DEV_DISPLAY_HEIGHT,
        ALP_DEV_DMDTYPE, ALP_DEVICE_NUMBER, ALP_VERSION,
        ALP_PCB_TEMPERATURE,
        ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED,
        ALP_PROJ_MODE, ALP_MASTER, ALP_SLAVE,
        ALP_TRIGGER_EDGE, ALP_EDGE_RISING, ALP_EDGE_FALLING,
        ALP_MIN_PICTURE_TIME, ALP_SYNCH_POLARITY, ALP_LEVEL_HIGH, ALP_LEVEL_LOW,
        ALP_FLUT_MODE, ALP_FLUT_NONE, ALP_FLUT_9BIT,
        ALP_FLUT_ENTRIES9, ALP_FLUT_MAX_ENTRIES9,
        ALP_FLUT_WRITE_9BIT, tFlutWrite,
        ALP_PROJ_INVERSION,
    )
    ALP_AVAILABLE = True
except ImportError:
    ALP_AVAILABLE = False

try:
    import pySLM2
    from pySLM2 import DLP9000, HermiteGaussian, RectangularWindowRectangle
    PYSLM2_AVAILABLE = True
except ImportError:
    PYSLM2_AVAILABLE = False

try:
    import PySpin
    PYSPIN_AVAILABLE = True
except ImportError:
    PYSPIN_AVAILABLE = False


# ==========================================
# Hologram Cache
# ==========================================

class HologramCache:
    """In-memory cache for computed holograms keyed by parameters."""

    def __init__(self):
        self._store = {}

    def _make_key(self, positions, beam_waist, method, aberration_hash):
        pos_tuple = tuple(sorted(tuple(p) for p in positions))
        return (pos_tuple, beam_waist, method, aberration_hash)

    def get(self, positions, beam_waist, method, aberration_hash):
        key = self._make_key(positions, beam_waist, method, aberration_hash)
        return self._store.get(key, None)

    def put(self, positions, beam_waist, method, aberration_hash, state):
        key = self._make_key(positions, beam_waist, method, aberration_hash)
        self._store[key] = state

    def clear(self):
        self._store.clear()

    @property
    def entries(self):
        return len(self._store)

    @property
    def memory_bytes(self):
        total = 0
        for v in self._store.values():
            total += v.nbytes if hasattr(v, 'nbytes') else 0
        return total


# ==========================================
# Secondary Grating Generator
# ==========================================

class SecondaryGratingGenerator:
    """Generates a secondary grating pattern for crosstalk suppression."""

    def __init__(self, focal_length, amplitude, periodicity, negative_order,
                 phase_in, phase_out, center_row, width, center_col, length):
        self.focal_length = focal_length
        self.amplitude = amplitude
        self.periodicity = periodicity
        self.negative_order = negative_order
        self.phase_in = phase_in
        self.phase_out = phase_out
        self.center_row = center_row
        self.width = width
        self.center_col = center_col
        self.length = length

    def generate(self):
        """Compute the secondary grating binary state."""
        if not PYSLM2_AVAILABLE:
            raise RuntimeError("pySLM2 not available for secondary grating generation")

        dmd = DLP9000(
            wavelength=369e-9,
            focal_length=self.focal_length,
            periodicity=self.periodicity,
            theta=-np.pi / 4,
            negative_order=self.negative_order
        )
        dmd.set_dmd_state_off()
        dmd.set_dmd_grating_state(
            amp=self.amplitude,
            phase_in=self.phase_in,
            phase_out=self.phase_out,
            method='random'
        )

        # Extract only the rectangular window region
        a, d, b, l = self.center_row, self.width, self.center_col, self.length
        if d % 2 != 0:
            slit = dmd.dmd_state[a - d // 2: a + d // 2 + 1, b - l: b + l].copy()
        else:
            slit = dmd.dmd_state[a - d // 2: a + d // 2, b - l: b + l].copy()

        # Create clean output with only the secondary grating region
        output = np.zeros((1600, 2560), dtype=bool)
        if d % 2 != 0:
            output[a - d // 2: a + d // 2 + 1, b - l: b + l] = slit
        else:
            output[a - d // 2: a + d // 2, b - l: b + l] = slit

        return output


# ==========================================
# DMD Server
# ==========================================

class DMDServer:
    """
    NDSP server for the Vialux DLP9000XUV DMD.

    Exposes RPC methods for hologram computation, frame upload,
    sequence control, aberration management, and diagnostics.
    """

    MAX_UINT8 = 255
    WAVELENGTH = 369e-9
    DEFAULT_FOCAL_LENGTH = 250e-3
    DEFAULT_PERIODICITY = 4
    DEFAULT_THETA = -np.pi / 4

    def __init__(self):
        # Internal state
        self._mode = "idle"
        self._n_loaded_frames = 0
        self._flut_enabled = False
        self._flut_entries = 0
        self._frame_counter = 0
        self._synch_config = None

        # Aberration maps
        self._phi_zeroth = None
        self._phi_first = None
        self._phi_second = None
        self._aberration_hash = None
        self._aberration_paths = {}

        # Secondary grating config
        self._secondary_grating_config = None

        # Double-pass pupil config
        self._pupil_config = None

        # Cache
        self._cache = HologramCache()

        # ALP hardware
        self._alp = None
        self._resolution = (2560, 1600)  # (Nx, Ny)
        self._memory_capacity = 0

        # Initialize hardware
        self._init_hardware()

    # ==========================================
    # Task 2: Hardware Initialization
    # ==========================================

    def _init_hardware(self):
        """Initialize the Vialux ALP board."""
        if not ALP_AVAILABLE:
            print("WARNING: ALP4lib not available. Running in SIMULATION mode.")
            self._resolution = (2560, 1600)
            self._memory_capacity = 16000
            return

        try:
            self._alp = ALP4(version='4.3')
            self._alp.Initialize()

            nx = self._alp.DevInquire(ALP_DEV_DISPLAY_WIDTH)
            ny = self._alp.DevInquire(ALP_DEV_DISPLAY_HEIGHT)
            self._resolution = (nx, ny)
            self._memory_capacity = self._alp.DevInquire(ALP_AVAIL_MEMORY)

            print(f"ALP board initialized: {nx}x{ny}, {self._memory_capacity} frames available")

        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize ALP board: {e}. "
                "Check USB connection and Vialux drivers."
            )

    def _cleanup_sequence(self):
        """Free the last allocated sequence to avoid memory leaks."""
        if self._alp is not None and self._alp._lastDDRseq is not None:
            try:
                self._alp.Halt()
                self._alp.FreeSeq()
            except Exception:
                pass

    # ==========================================
    # Task 2 & 10: Lifecycle & Diagnostics
    # ==========================================

    def ping(self):
        """Check server responsiveness."""
        return True

    def get_device_info(self):
        """Return hardware identification."""
        return {
            "resolution": list(self._resolution),
            "Nx": self._resolution[0],
            "Ny": self._resolution[1],
            "memory_capacity_frames": self._memory_capacity,
            "hardware_connected": self._alp is not None,
            "pixel_size_um": 7.56,
            "model": "DLP9000XUV",
            "controller": "Vialux ALP 4.3",
            "wavelength_nm": 369,
            "focal_length_mm": 250,
        }

    def get_memory_status(self):
        """Return DDR memory capacity and availability."""
        if self._alp is not None:
            available = self._alp.DevInquire(ALP_AVAIL_MEMORY)
        else:
            available = self._memory_capacity - self._n_loaded_frames
        return {
            "total_frames": self._memory_capacity,
            "available_frames": available,
            "loaded_frames": self._n_loaded_frames,
        }

    def get_status(self):
        """Return current operating status."""
        status = {
            "mode": self._mode,
            "n_loaded_frames": self._n_loaded_frames,
            "flut_enabled": self._flut_enabled,
            "flut_entries": self._flut_entries,
            "frame_counter": self._frame_counter,
            "hardware_connected": self._alp is not None,
            "aberration_loaded": self._phi_zeroth is not None,
            "secondary_grating_enabled": self._secondary_grating_config is not None,
            "double_pass_pupil_enabled": self._pupil_config is not None,
            "cache_entries": self._cache.entries,
            "synch_config": self._synch_config,
        }
        if self._alp is not None:
            try:
                raw_temp = self._alp.DevInquire(ALP_PCB_TEMPERATURE)
                status["temperature_C"] = raw_temp / 256.0
            except Exception:
                status["temperature_C"] = None
        return status

    def get_frame_counter(self):
        """Return the number of trigger-advances since last arm."""
        return self._frame_counter

    def halt(self):
        """Stop any active sequence."""
        if self._alp is not None:
            self._alp.Halt()
        self._mode = "idle"
        return True

    def close(self):
        """Cleanly shut down hardware."""
        if self._alp is not None:
            try:
                self._alp.Halt()
                if self._alp._lastDDRseq is not None:
                    self._alp.FreeSeq()
                self._alp.Free()
            except Exception as e:
                print(f"Shutdown error: {e}")
            self._alp = None
        self._mode = "idle"
        print("DMD server shut down.")

    # ==========================================
    # Task 3: Static Display
    # ==========================================

    def display_static(self, dmd_state=None):
        """Display a single static frame (alignment mode)."""
        if self._alp is None:
            self._mode = "displaying"
            return True

        self._cleanup_sequence()

        if dmd_state is None:
            dmd_state = np.zeros((self._resolution[1], self._resolution[0]), dtype=bool)
        else:
            dmd_state = np.asarray(dmd_state, dtype=bool)

        self._alp.SeqAlloc(nbImg=1, bitDepth=1)
        self._alp.SeqControl(ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED)
        self._alp.SeqPut(imgData=dmd_state.astype(np.uint8) * self.MAX_UINT8)
        self._alp.SetTiming()
        self._alp.Run(loop=True)

        self._mode = "displaying"
        self._n_loaded_frames = 1
        return True

    def display_number(self, index):
        """Display a numbered test pattern."""
        if PYSLM2_AVAILABLE:
            from pySLM2.util.sample import number_image
            img = number_image(index, self._resolution[0], self._resolution[1])
            return self.display_static(img)
        else:
            # Fallback: create simple pattern
            state = np.zeros((self._resolution[1], self._resolution[0]), dtype=bool)
            # Draw the number as a block in the center
            cy, cx = self._resolution[1] // 2, self._resolution[0] // 2
            state[cy - 50:cy + 50, cx - 50:cx + 50] = True
            return self.display_static(state)

    # ==========================================
    # Task 4: Aberration Map Management
    # ==========================================

    def load_aberration_maps(self, phi_zeroth_path, phi_first_path, phi_second_path=None):
        """Load aberration phase maps from disk."""
        if not os.path.exists(phi_zeroth_path):
            raise FileNotFoundError(f"phi_zeroth not found: {phi_zeroth_path}")
        if not os.path.exists(phi_first_path):
            raise FileNotFoundError(f"phi_first not found: {phi_first_path}")
        if phi_second_path and not os.path.exists(phi_second_path):
            raise FileNotFoundError(f"phi_second not found: {phi_second_path}")

        self._phi_zeroth = np.load(phi_zeroth_path)
        self._phi_first = np.load(phi_first_path)
        self._phi_second = np.load(phi_second_path) if phi_second_path else None

        self._aberration_paths = {
            "phi_zeroth": phi_zeroth_path,
            "phi_first": phi_first_path,
            "phi_second": phi_second_path,
        }
        self._aberration_hash = self._compute_aberration_hash()
        self._cache.clear()

        print(f"Aberration maps loaded. Hash: {self._aberration_hash[:8]}")
        return True

    def set_aberration_maps(self, phi_zeroth, phi_first, phi_second=None):
        """Set aberration maps from numpy arrays directly."""
        self._phi_zeroth = np.asarray(phi_zeroth)
        self._phi_first = np.asarray(phi_first)
        self._phi_second = np.asarray(phi_second) if phi_second is not None else None
        self._aberration_paths = {"phi_zeroth": "memory", "phi_first": "memory", "phi_second": "memory"}
        self._aberration_hash = self._compute_aberration_hash()
        self._cache.clear()
        return True

    def get_aberration_info(self):
        """Return info about loaded aberration maps."""
        info = {
            "loaded": self._phi_zeroth is not None,
            "paths": self._aberration_paths,
            "hash": self._aberration_hash,
        }
        if self._phi_zeroth is not None:
            info["phi_zeroth_shape"] = list(self._phi_zeroth.shape)
            info["phi_first_shape"] = list(self._phi_first.shape)
            info["phi_second_shape"] = list(self._phi_second.shape) if self._phi_second is not None else None
        return info

    def _compute_aberration_hash(self):
        """Compute MD5 hash of loaded aberration maps for cache keying."""
        parts = []
        if self._phi_zeroth is not None:
            parts.append(self._phi_zeroth.tobytes())
        if self._phi_first is not None:
            parts.append(self._phi_first.tobytes())
        if self._phi_second is not None:
            parts.append(self._phi_second.tobytes())
        if not parts:
            return "none"
        return hashlib.md5(b"".join(parts)).hexdigest()[:12]

    # ==========================================
    # Task 5: Hologram Computation
    # ==========================================

    def compute_hologram(self, positions, beam_waist=15e-6, method="random",
                         N=2000, r=10, double_pass=False):
        """
        Compute a binary hologram for the given ion positions.

        Parameters
        ----------
        positions : list of (x, y) tuples in meters
        beam_waist : float, beam waist in meters
        method : "ifta" or "random"
        N : int, IFTA iterations
        r : int, random method steepness
        double_pass : bool, use DLP9000_FP variant

        Returns
        -------
        dmd_state : list (flattened bool array, serialized for RPC)
        """
        if not PYSLM2_AVAILABLE:
            raise RuntimeError("pySLM2 not available. Cannot compute holograms.")

        if self._phi_zeroth is None or self._phi_first is None:
            raise RuntimeError("Aberration maps not loaded. Call load_aberration_maps() first.")

        # Check cache
        cached = self._cache.get(positions, beam_waist, method, self._aberration_hash)
        if cached is not None:
            return cached.tolist()

        # Build input profile with aberration correction
        if double_pass and self._phi_second is not None:
            aberration = -self._phi_zeroth - self._phi_first + self._phi_second
        else:
            aberration = self._phi_zeroth + self._phi_first

        input_profile = np.exp(1j * aberration)

        # Create DMD model
        dmd = DLP9000(
            wavelength=self.WAVELENGTH,
            focal_length=self.DEFAULT_FOCAL_LENGTH,
            periodicity=self.DEFAULT_PERIODICITY,
            theta=self.DEFAULT_THETA,
            negative_order=True
        )

        # Build output profile (sum of Gaussians at each position)
        if len(positions) == 0:
            raise ValueError("positions list cannot be empty")

        output_profile = HermiteGaussian(
            -positions[0][0], -positions[0][1], 1, beam_waist, n=0, m=0
        )
        for pos in positions[1:]:
            output_profile = output_profile + HermiteGaussian(
                -pos[0], -pos[1], 1, beam_waist, n=0, m=0
            )
        # Rotate for DMD 45° mounting
        output_profile = output_profile.rotate(-np.pi / 4)

        # Compute hologram
        if method == "ifta":
            x0, y0 = dmd.first_order_origin
            signal_window = RectangularWindowRectangle(-x0, -y0, 2000e-6, 500e-6)
            dmd.calculate_dmd_state(
                input_profile, output_profile,
                method='ifta', signal_window=signal_window, N=N
            )
        else:
            dmd.calculate_dmd_state(
                input_profile, output_profile,
                method='random', r=r
            )

        state = dmd.dmd_state.copy()

        # Apply secondary grating if configured
        if self._secondary_grating_config is not None:
            sg_state = self._generate_secondary_grating(aberration)
            state = np.logical_or(state, sg_state)

        # Apply double-pass pupil if configured
        if double_pass and self._pupil_config is not None:
            state = self._apply_pupil(state)

        # Cache the result
        self._cache.put(positions, beam_waist, method, self._aberration_hash, state)

        return state.tolist()

    # ==========================================
    # Task 6: Cache Management
    # ==========================================

    def clear_cache(self):
        """Clear the hologram cache."""
        self._cache.clear()
        return True

    def cache_status(self):
        """Return cache statistics."""
        return {
            "entries": self._cache.entries,
            "memory_bytes": self._cache.memory_bytes,
        }

    # ==========================================
    # Task 7: Frame Upload
    # ==========================================

    def upload_single(self, dmd_state):
        """Upload and display a single frame (static, master mode)."""
        return self.display_static(dmd_state)

    def upload_sequence(self, dmd_states):
        """
        Upload multiple frames and configure for TTL-triggered playback.

        Parameters
        ----------
        dmd_states : list of 2D bool arrays (each 1600x2560)
        """
        n_frames = len(dmd_states)

        if self._alp is None:
            self._n_loaded_frames = n_frames
            self._mode = "armed"
            self._frame_counter = 0
            return {"n_frames": n_frames, "mode": "armed (simulation)"}

        # Check memory
        available = self._alp.DevInquire(ALP_AVAIL_MEMORY)
        if n_frames > available:
            raise RuntimeError(
                f"Not enough DDR memory: requested {n_frames} frames, "
                f"only {available} available."
            )

        self._cleanup_sequence()

        # Allocate and upload
        self._alp.SeqAlloc(nbImg=n_frames, bitDepth=1)
        self._alp.SeqControl(ALP_BIN_MODE, ALP_BIN_UNINTERRUPTED)

        # Concatenate all frames
        concat = np.concatenate(
            [np.asarray(s, dtype=np.uint8) * self.MAX_UINT8 for s in dmd_states]
        )
        self._alp.SeqPut(imgData=concat)

        # Configure slave mode
        self._alp.ProjControl(ALP_PROJ_MODE, ALP_SLAVE)
        self._alp.DevControl(ALP_TRIGGER_EDGE, ALP_EDGE_RISING)
        self._alp.SetTiming(pictureTime=self._alp.SeqInquire(ALP_MIN_PICTURE_TIME))
        self._alp.Run()

        self._n_loaded_frames = n_frames
        self._mode = "armed"
        self._frame_counter = 0
        self._flut_enabled = False

        return {"n_frames": n_frames, "mode": "armed"}

    # ==========================================
    # Task 8: FLUT Programming
    # ==========================================

    def program_flut(self, frame_order):
        """
        Program the Frame Look-Up Table for non-linear playback.

        Parameters
        ----------
        frame_order : list of int, frame indices in desired playback order
        """
        # Validate
        if len(frame_order) > 4096:
            raise ValueError(
                f"FLUT supports max 4096 entries, got {len(frame_order)}"
            )
        for idx in frame_order:
            if idx >= self._n_loaded_frames or idx < 0:
                raise ValueError(
                    f"Invalid frame index {idx}. "
                    f"Only {self._n_loaded_frames} frames loaded (0–{self._n_loaded_frames - 1})."
                )

        if self._alp is None:
            self._flut_enabled = True
            self._flut_entries = len(frame_order)
            self._mode = "armed"
            self._frame_counter = 0
            return {"flut_entries": len(frame_order), "mode": "armed (simulation)"}

        # Must halt before reprogramming
        self._alp.Halt()

        # Enable FLUT 9-bit mode
        self._alp.SeqControl(ALP_FLUT_MODE, ALP_FLUT_9BIT)
        self._alp.SeqControl(ALP_FLUT_ENTRIES9, len(frame_order))

        # Build FLUT struct
        flut = tFlutWrite()
        flut.nOffset = 0
        flut.nSize = len(frame_order)
        for i, frame_idx in enumerate(frame_order):
            flut.FrameNumbers[i] = frame_idx

        # Write FLUT (NOTE: requires patched ProjControlEx in ALP4lib)
        self._alp.ProjControlEx(ALP_FLUT_WRITE_9BIT, ct.byref(flut))

        # Re-arm slave mode
        self._alp.ProjControl(ALP_PROJ_MODE, ALP_SLAVE)
        self._alp.DevControl(ALP_TRIGGER_EDGE, ALP_EDGE_RISING)
        self._alp.SetTiming(pictureTime=self._alp.SeqInquire(ALP_MIN_PICTURE_TIME))
        self._alp.Run()

        self._flut_enabled = True
        self._flut_entries = len(frame_order)
        self._mode = "armed"
        self._frame_counter = 0

        return {"flut_entries": len(frame_order), "mode": "armed"}

    # ==========================================
    # Task 9: Slave Mode & Synch
    # ==========================================

    def arm_slave_mode(self, trigger_edge="rising"):
        """Arm the DMD in slave mode waiting for TTL triggers."""
        if self._alp is None:
            self._mode = "armed"
            return True

        edge = ALP_EDGE_RISING if trigger_edge == "rising" else ALP_EDGE_FALLING
        self._alp.ProjControl(ALP_PROJ_MODE, ALP_SLAVE)
        self._alp.DevControl(ALP_TRIGGER_EDGE, edge)
        self._alp.SetTiming(pictureTime=self._alp.SeqInquire(ALP_MIN_PICTURE_TIME))
        self._alp.Run()

        self._mode = "armed"
        self._frame_counter = 0
        return True

    def configure_synch_output(self, pulse_width=10, polarity="high"):
        """Configure the Synch OUT BNC signal."""
        if self._alp is not None:
            pol = ALP_LEVEL_HIGH if polarity == "high" else ALP_LEVEL_LOW
            self._alp.DevControl(ALP_SYNCH_POLARITY, pol)
            self._alp.SetTiming(synchPulseWidth=pulse_width)

        self._synch_config = {"pulse_width_us": pulse_width, "polarity": polarity}
        return True

    # ==========================================
    # Task 11: Batch Preparation
    # ==========================================

    def prepare_ion_sequence(self, ion_positions_list, beam_waist=15e-6, method="random", N=2000, r=10):
        """
        Compute and upload holograms for a list of ion position sets.

        Parameters
        ----------
        ion_positions_list : list of lists of (x, y) tuples
            Each entry is the set of ion positions for one frame.
        beam_waist : float
        method : "ifta" or "random"

        Returns
        -------
        dict with n_frames, prep_time_seconds, cache_hits, cache_misses
        """
        t_start = time.time()
        states = []
        cache_hits = 0
        cache_misses = 0

        for positions in ion_positions_list:
            cached = self._cache.get(positions, beam_waist, method, self._aberration_hash)
            if cached is not None:
                states.append(cached)
                cache_hits += 1
            else:
                # compute_hologram returns a list (for RPC), convert back
                state_list = self.compute_hologram(
                    positions, beam_waist=beam_waist, method=method, N=N, r=r
                )
                state = np.array(state_list, dtype=bool).reshape(
                    self._resolution[1], self._resolution[0]
                )
                states.append(state)
                cache_misses += 1

        # Upload
        self.upload_sequence(states)

        t_elapsed = time.time() - t_start
        return {
            "n_frames": len(states),
            "prep_time_seconds": round(t_elapsed, 2),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        }

    def prepare_flut_sequence(self, ion_positions_list, playback_order,
                              beam_waist=15e-6, method="random", N=2000, r=10):
        """
        Compute unique holograms, upload, and program FLUT with playback order.

        Parameters
        ----------
        ion_positions_list : list of unique position sets (frames to upload)
        playback_order : list of int indices into ion_positions_list
        """
        t_start = time.time()

        # Compute unique frames
        states = []
        cache_hits = 0
        for positions in ion_positions_list:
            cached = self._cache.get(positions, beam_waist, method, self._aberration_hash)
            if cached is not None:
                states.append(cached)
                cache_hits += 1
            else:
                state_list = self.compute_hologram(
                    positions, beam_waist=beam_waist, method=method, N=N, r=r
                )
                state = np.array(state_list, dtype=bool).reshape(
                    self._resolution[1], self._resolution[0]
                )
                states.append(state)

        # Upload unique frames
        self.upload_sequence(states)

        # Program FLUT
        self.program_flut(playback_order)

        t_elapsed = time.time() - t_start
        return {
            "n_unique_frames": len(states),
            "flut_entries": len(playback_order),
            "prep_time_seconds": round(t_elapsed, 2),
            "cache_hits": cache_hits,
        }

    # ==========================================
    # Task 12: Secondary Grating
    # ==========================================

    def configure_secondary_grating(self, phase, amplitude, position_offset,
                                    window_length=400, window_width=3,
                                    center_row=800, center_col=980):
        """
        Configure secondary grating for crosstalk suppression.

        Parameters
        ----------
        phase : float, grating phase (0 to 4*pi)
        amplitude : float, grating amplitude (0 to 1)
        position_offset : float, target position offset in meters from first-order
        window_length : int, half-length of grating window in pixels
        window_width : int, width of grating window in pixels
        """
        # Calculate periodicity from position offset
        periodicity = (
            np.cos(np.pi / 4) * self.WAVELENGTH * self.DEFAULT_FOCAL_LENGTH
        ) / (position_offset * 7.56e-6)

        self._secondary_grating_config = {
            "phase": phase,
            "amplitude": amplitude,
            "periodicity": periodicity,
            "position_offset": position_offset,
            "window_length": window_length,
            "window_width": window_width,
            "center_row": center_row,
            "center_col": center_col,
        }
        # Invalidate cache since hologram output changes
        self._cache.clear()
        return self._secondary_grating_config

    def disable_secondary_grating(self):
        """Disable secondary grating overlay."""
        self._secondary_grating_config = None
        self._cache.clear()
        return True

    def scan_secondary_grating(self, phase_steps=20, amp_steps=1,
                               amplitude=0.7, position_offset=None,
                               window_length=400, window_width=3,
                               center_row=800, center_col=980):
        """
        Generate a sequence scanning secondary grating phase from 0 to 4π.

        Returns the sequence upload result.
        """
        if self._phi_zeroth is None:
            raise RuntimeError("Aberration maps not loaded.")
        if position_offset is None:
            raise ValueError("position_offset is required.")

        phases = np.linspace(0, 4 * np.pi, phase_steps)
        states = []

        aberration = self._phi_zeroth + self._phi_first

        periodicity = (
            np.cos(np.pi / 4) * self.WAVELENGTH * self.DEFAULT_FOCAL_LENGTH
        ) / (position_offset * 7.56e-6)

        # Compute base hologram (primary grating only)
        # Temporarily disable secondary grating for base
        saved_config = self._secondary_grating_config
        self._secondary_grating_config = None

        for phase in phases:
            sg = SecondaryGratingGenerator(
                focal_length=self.DEFAULT_FOCAL_LENGTH,
                amplitude=amplitude,
                periodicity=periodicity,
                negative_order=True,
                phase_in=aberration,
                phase_out=phase,
                center_row=center_row,
                width=window_width,
                center_col=center_col,
                length=window_length,
            )
            sg_state = sg.generate()
            states.append(sg_state)

        self._secondary_grating_config = saved_config

        # Upload as triggered sequence
        return self.upload_sequence(states)

    def _generate_secondary_grating(self, aberration):
        """Generate secondary grating state from current config."""
        cfg = self._secondary_grating_config
        sg = SecondaryGratingGenerator(
            focal_length=self.DEFAULT_FOCAL_LENGTH,
            amplitude=cfg["amplitude"],
            periodicity=cfg["periodicity"],
            negative_order=True,
            phase_in=aberration,
            phase_out=cfg["phase"],
            center_row=cfg["center_row"],
            width=cfg["window_width"],
            center_col=cfg["center_col"],
            length=cfg["window_length"],
        )
        return sg.generate()

    # ==========================================
    # Task 13: Double-Pass Pupil
    # ==========================================

    def configure_double_pass_pupil(self, center_row, center_col, radius):
        """
        Configure the IP1 pupil for double-pass mode.

        Parameters
        ----------
        center_row : int, row center of pupil in DMD pixels
        center_col : int, column center (must be in range 2060–2560)
        radius : int, pupil radius in pixels
        """
        if center_col < 2060 or center_col > 2560:
            raise ValueError(
                f"center_col must be in range [2060, 2560], got {center_col}"
            )
        self._pupil_config = {
            "center_row": center_row,
            "center_col": center_col,
            "radius": radius,
        }
        self._cache.clear()
        return self._pupil_config

    def disable_double_pass_pupil(self):
        """Disable the double-pass pupil."""
        self._pupil_config = None
        self._cache.clear()
        return True

    def _apply_pupil(self, state):
        """Apply circular pupil mask to the IP1 region of the DMD state."""
        cfg = self._pupil_config
        if cfg is None:
            return state

        # Create circular mask for the IP1 region (columns 2060–2560)
        ny, nx = state.shape
        rows = np.arange(ny)
        cols = np.arange(2060, min(2560, nx))
        rr, cc = np.meshgrid(rows, cols, indexing='ij')

        dist = np.sqrt(
            (rr - cfg["center_row"]) ** 2 + (cc - cfg["center_col"]) ** 2
        )
        mask = dist <= cfg["radius"]

        # Set IP1 region: within pupil = ON, outside = OFF
        state[:, 2060:2560] = 0
        state[:, 2060:2560][:, :mask.shape[1]] = mask

        return state

    # ==========================================
    # Task 14: HDR Beam Characterization
    # ==========================================

    def hdr_acquire(self, dmd_state, exposure_settings=None, iterations=3, camera_serial="22532077"):
        """
        Acquire HDR images coordinating DMD states with FLIR camera.

        Parameters
        ----------
        dmd_state : 2D bool array or None (uses current)
        exposure_settings : list of exposure times in microseconds
        iterations : int, shots per exposure
        camera_serial : str, FLIR camera serial number

        Returns
        -------
        dict mapping exposure → {"foreground": [...], "background": [...]}
        """
        if not PYSPIN_AVAILABLE:
            raise RuntimeError("PySpin not available. FLIR camera cannot be accessed.")

        if exposure_settings is None:
            exposure_settings = [120, 1200, 12000, 120000, 1200000, 12000000]

        # Initialize camera
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        cam = cam_list.GetBySerial(camera_serial)
        cam.Init()
        cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        cam.Gain.SetValue(0)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
        cam.BeginAcquisition()

        # Off state
        off_state = np.zeros((self._resolution[1], self._resolution[0]), dtype=bool)

        results = {}
        try:
            for exposure in exposure_settings:
                cam.ExposureTime.SetValue(float(exposure))
                time.sleep(1)

                # Background (DMD off)
                self.display_static(off_state)
                time.sleep(1)
                bg_images = []
                for _ in range(iterations):
                    cam.TriggerSoftware.Execute()
                    img_result = cam.GetNextImage(1000)
                    if not img_result.IsIncomplete():
                        bg_images.append(img_result.GetNDArray().tolist())
                    img_result.Release()
                    time.sleep(0.1)

                # Foreground (DMD on)
                if dmd_state is not None:
                    self.display_static(dmd_state)
                time.sleep(1)
                fg_images = []
                for _ in range(iterations):
                    cam.TriggerSoftware.Execute()
                    img_result = cam.GetNextImage(1000)
                    if not img_result.IsIncomplete():
                        fg_images.append(img_result.GetNDArray().tolist())
                    img_result.Release()
                    time.sleep(0.1)

                results[exposure] = {
                    "foreground": fg_images,
                    "background": bg_images,
                }

        finally:
            cam.EndAcquisition()
            cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            cam.DeInit()
            cam_list.Clear()
            system.ReleaseInstance()

        return results


# ==========================================
# Main Entry Point
# ==========================================

def get_argparser():
    parser = argparse.ArgumentParser(description="DMD NDSP Server for Bloodstone ARTIQ")
    parser.add_argument("--port", type=int, default=12345,
                        help="TCP port (default: 12345)")
    parser.add_argument("--bind", type=str, default="0.0.0.0",
                        help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--simulation", action="store_true",
                        help="Run without hardware (for development)")
    return parser


def main():
    args = get_argparser().parse_args()

    print("=" * 60)
    print("  DMD NDSP Server for Bloodstone ARTIQ Control System")
    print("=" * 60)
    print(f"  Port:       {args.port}")
    print(f"  Bind:       {args.bind}")
    print(f"  Simulation: {args.simulation}")
    print("=" * 60)

    if args.simulation:
        # Force simulation mode
        global ALP_AVAILABLE
        ALP_AVAILABLE = False

    server = DMDServer()

    info = server.get_device_info()
    print(f"\n  Hardware:   {'CONNECTED' if info['hardware_connected'] else 'SIMULATION'}")
    print(f"  Resolution: {info['Nx']}x{info['Ny']}")
    print(f"  Memory:     {info['memory_capacity_frames']} frames")
    print(f"\n  Connect with: sipyco_rpctool <host> {args.port} call ping")
    print()

    try:
        simple_server_loop({"dmd": server}, args.bind, args.port)
    finally:
        server.close()


if __name__ == "__main__":
    main()
