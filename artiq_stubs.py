"""
ARTIQ Kernel Stubs for DMD Integration

Add these to Bloodstone-Control-Artiq/config.py in the Bloodstone_Experiment class.
Also add "DMD_TTL": "ttl7" and "dmd": "dmd" to the mapping_dict.

These stubs run on the Kasli FPGA with nanosecond timing precision.
The actual hologram computation and upload happens via host-side RPC to the DMD server
BEFORE these kernel functions execute.
"""

# ==========================================
# Add to config.py mapping_dict:
# ==========================================
#
#   "DMD_TTL": "ttl7",      # Choose an available TTL output channel
#   "dmd": "dmd",           # NDSP controller
#
# Add type annotation to Bloodstone_Experiment:
#
#   DMD_TTL: TTLOut
#

# ==========================================
# Add to device_db.py:
# ==========================================
#
# device_db["dmd"] = {
#     "type": "controller",
#     "host": "192.168.1.XXX",  # GPU PC IP address
#     "port": 12345
# }
#

# ==========================================
# Kernel stubs (add to config.py):
# ==========================================

"""
@kernel
def dmd_advance(self):
    '''Advance DMD to the next frame in sequence/FLUT. 
    
    Fires a single TTL pulse and waits for mirror settling.
    Total time: ~100 μs (1 μs pulse + 76 μs transfer + 20 μs settle + margin).
    
    The AOM must be OFF during this call (mirrors transitioning).
    Gate the addressing AOM AFTER this returns.
    '''
    self.DMD_TTL.pulse(1*us)
    delay(100*us)


@kernel
def dmd_select_frame(self, target_frame, current_frame, n_frames):
    '''Advance to a specific frame by firing multiple rapid triggers.
    
    Parameters
    ----------
    target_frame : int, desired frame index
    current_frame : int, current counter position
    n_frames : int, total frames in sequence (for modular arithmetic)
    
    Timing: (steps * 77 μs) + 20 μs settle
    Average for 30 frames: ~1.14 ms
    
    Call this only when adaptive frame selection is needed.
    For predetermined sequences, use dmd_advance() instead.
    '''
    steps = (target_frame - current_frame) % n_frames
    if steps > 0:
        for i in range(steps):
            self.DMD_TTL.pulse(1*us)
            delay(76*us)  # minimum picture time (77 μs total with pulse)
        delay(20*us)  # final mirror settle


@kernel 
def dmd_advance_and_gate(self, addressing_time):
    '''Advance DMD frame, wait for settle, then gate the addressing AOM.
    
    This is the typical per-shot sequence for MCMR:
    1. Advance DMD (mirrors transition, AOM is OFF)
    2. Wait for settle
    3. Gate addressing AOM for the detection/reset pulse
    
    Parameters
    ----------
    addressing_time : float, duration to keep AOM on (detection or reset time)
    '''
    self.DMD_TTL.pulse(1*us)
    delay(100*us)  # mirror settle
    # Gate the addressing laser
    # self.addressing_AOM.pulse(addressing_time)  # uncomment when AOM is wired
"""

# ==========================================
# Example experiment usage:
# ==========================================

EXAMPLE_EXPERIMENT = '''
from artiq.experiment import *
from config import *
from compiler import install_awg_program

class MCMRExperiment(Bloodstone_Experiment):
    """Example: Address ions 5, 12, 5, 0 in sequence."""
    
    def prepare(self):
        """Host-side: compute and upload holograms."""
        self.init()
        
        # Define which ions to address (in microns from center)
        ion_positions = [
            [(5e-6, 0)],    # ion 5
            [(12e-6, 0)],   # ion 12  
            [(5e-6, 0)],    # ion 5 again
            [(0, 0)],       # ion 0
        ]
        
        # Compute, upload, and program FLUT
        result = self.dmd.prepare_flut_sequence(
            ion_positions_list=[[(5e-6, 0)], [(12e-6, 0)], [(0, 0)]],  # 3 unique
            playback_order=[0, 1, 0, 2],  # maps to: ion5, ion12, ion5, ion0
            beam_waist=1e-6,
            method="ifta",
            N=2000
        )
        print(f"DMD prepared: {result}")
        
        self.n_shots = 4
    
    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        
        for shot in range(self.n_shots):
            # Cooling
            self.doppler_cooling()
            
            # State preparation
            self.pumping()
            
            # DMD frame advance (triggers next FLUT entry)
            self.dmd_advance()
            
            # Address the ion (gate AOM after DMD settles)
            # self.addressing_AOM.pulse(20*us)  # detection time
            
            # Detection
            self.global_pmt_detection()
'''
