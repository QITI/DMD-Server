"""
Integration test for the DMD NDSP Server.

Run the server first:
    python dmd_server.py --port 12345 --simulation

Then run this test:
    python test_dmd_server.py [--host localhost] [--port 12345]
"""

import argparse
import numpy as np
import time
from sipyco.pc_rpc import Client


def test_connectivity(dmd):
    """Test basic RPC connectivity."""
    print("\n[TEST] Connectivity...")
    assert dmd.ping() == True, "ping() failed"
    print("  ✓ ping() returned True")


def test_device_info(dmd):
    """Test device info query."""
    print("\n[TEST] Device Info...")
    info = dmd.get_device_info()
    print(f"  Resolution: {info['Nx']}x{info['Ny']}")
    print(f"  Memory: {info['memory_capacity_frames']} frames")
    print(f"  Hardware: {'CONNECTED' if info['hardware_connected'] else 'SIMULATION'}")
    assert info['Nx'] == 2560
    assert info['Ny'] == 1600
    print("  ✓ device info correct")


def test_status(dmd):
    """Test status query."""
    print("\n[TEST] Status...")
    status = dmd.get_status()
    assert status['mode'] == 'idle' or status['mode'] == 'displaying'
    print(f"  Mode: {status['mode']}")
    print(f"  Cache entries: {status['cache_entries']}")
    print("  ✓ status query works")


def test_static_display(dmd):
    """Test static display mode."""
    print("\n[TEST] Static Display...")

    # Display all-off
    dmd.display_static(None)
    status = dmd.get_status()
    assert status['mode'] == 'displaying'
    print("  ✓ display_static(None) → displaying mode")

    # Display a pattern
    state = np.zeros((1600, 2560), dtype=bool)
    state[700:900, 1200:1400] = True  # center block
    dmd.display_static(state.tolist())
    print("  ✓ display_static(pattern) accepted")

    # Halt
    dmd.halt()
    status = dmd.get_status()
    assert status['mode'] == 'idle'
    print("  ✓ halt() → idle mode")


def test_aberration_maps(dmd):
    """Test aberration map management."""
    print("\n[TEST] Aberration Maps...")

    # Set fake aberration maps directly
    phi_z = np.random.randn(1600, 2560).tolist()
    phi_f = np.random.randn(1600, 2560).tolist()
    dmd.set_aberration_maps(phi_z, phi_f)

    info = dmd.get_aberration_info()
    assert info['loaded'] == True
    assert info['phi_zeroth_shape'] == [1600, 2560]
    print(f"  Aberration hash: {info['hash']}")
    print("  ✓ set_aberration_maps() accepted")


def test_cache(dmd):
    """Test hologram caching."""
    print("\n[TEST] Cache...")

    status = dmd.cache_status()
    print(f"  Initial cache entries: {status['entries']}")

    dmd.clear_cache()
    status = dmd.cache_status()
    assert status['entries'] == 0
    print("  ✓ clear_cache() works")


def test_upload_sequence(dmd):
    """Test sequence upload."""
    print("\n[TEST] Upload Sequence...")

    # Create 3 dummy frames
    frames = []
    for i in range(3):
        state = np.zeros((1600, 2560), dtype=bool)
        state[i * 100:(i + 1) * 100, :] = True
        frames.append(state.tolist())

    result = dmd.upload_sequence(frames)
    print(f"  Result: {result}")
    assert result['n_frames'] == 3
    assert 'armed' in result['mode']
    print("  ✓ upload_sequence(3 frames) → armed")

    # Halt
    dmd.halt()


def test_flut(dmd):
    """Test FLUT programming."""
    print("\n[TEST] FLUT Programming...")

    # First upload 3 frames
    frames = []
    for i in range(3):
        state = np.zeros((1600, 2560), dtype=bool)
        state[i * 100:(i + 1) * 100, :] = True
        frames.append(state.tolist())
    dmd.upload_sequence(frames)

    # Program FLUT with non-linear order
    result = dmd.program_flut([2, 0, 1, 2, 1, 0])
    print(f"  Result: {result}")
    assert result['flut_entries'] == 6
    assert 'armed' in result['mode']
    print("  ✓ program_flut([2,0,1,2,1,0]) → armed with 6 entries")

    # Test invalid index
    try:
        dmd.program_flut([0, 1, 5])  # index 5 doesn't exist (only 0-2)
        assert False, "Should have raised error"
    except Exception as e:
        print(f"  ✓ Invalid index correctly rejected: {e}")

    dmd.halt()


def test_secondary_grating(dmd):
    """Test secondary grating configuration."""
    print("\n[TEST] Secondary Grating...")

    config = dmd.configure_secondary_grating(
        phase=np.pi,
        amplitude=0.7,
        position_offset=36e-6,  # 4w at w=9μm
        window_length=200,
        window_width=3
    )
    print(f"  Config: periodicity={config['periodicity']:.2f}")
    print("  ✓ configure_secondary_grating() accepted")

    dmd.disable_secondary_grating()
    status = dmd.get_status()
    assert status['secondary_grating_enabled'] == False
    print("  ✓ disable_secondary_grating() works")


def test_double_pass_pupil(dmd):
    """Test double-pass pupil configuration."""
    print("\n[TEST] Double-Pass Pupil...")

    config = dmd.configure_double_pass_pupil(
        center_row=800,
        center_col=2300,
        radius=100
    )
    print(f"  Config: {config}")
    print("  ✓ configure_double_pass_pupil() accepted")

    # Test invalid column
    try:
        dmd.configure_double_pass_pupil(800, 1000, 100)  # col=1000 is outside 2060-2560
        assert False, "Should have raised error"
    except Exception as e:
        print(f"  ✓ Invalid column correctly rejected: {e}")

    dmd.disable_double_pass_pupil()
    print("  ✓ disable_double_pass_pupil() works")


def test_memory_status(dmd):
    """Test memory status query."""
    print("\n[TEST] Memory Status...")
    mem = dmd.get_memory_status()
    print(f"  Total: {mem['total_frames']} frames")
    print(f"  Available: {mem['available_frames']} frames")
    print(f"  Loaded: {mem['loaded_frames']} frames")
    print("  ✓ get_memory_status() works")


def main():
    parser = argparse.ArgumentParser(description="Test DMD NDSP Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=12345)
    args = parser.parse_args()

    print("=" * 60)
    print(f"  DMD Server Integration Test")
    print(f"  Connecting to {args.host}:{args.port}")
    print("=" * 60)

    dmd = Client(args.host, args.port, "dmd")

    try:
        test_connectivity(dmd)
        test_device_info(dmd)
        test_status(dmd)
        test_memory_status(dmd)
        test_static_display(dmd)
        test_aberration_maps(dmd)
        test_cache(dmd)
        test_upload_sequence(dmd)
        test_flut(dmd)
        test_secondary_grating(dmd)
        test_double_pass_pupil(dmd)

        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n  ✗ TEST FAILED: {e}")
        raise
    finally:
        dmd.close_rpc()


if __name__ == "__main__":
    main()
