"""Paths for the two owner settings that live in a plain file instead of a Params key.

params_keys.h is compiled into params_pyx.so, so registering a key would mean a full
rebuild on the device for a single number. A file costs nothing, is readable while the
car is running, and falls back to the default when it is missing or garbage.

Deliberately free of imports so the UI, the planner and the camera view can all use it.
"""

# Signed offset for the manually set cruise speed, in the user's display units.
# The dash still shows what the driver set; only the speed actually held moves.
CRUISE_SPEED_OFFSET_PATH = "/data/cruise_speed_offset"
CRUISE_SPEED_OFFSET_LIMIT = 5.0

# Gamma applied to the camera preview on the device screen only. Higher = brighter.
DISPLAY_GAMMA_PATH = "/data/display_gamma"
DISPLAY_GAMMA_DEFAULT = 1.45
DISPLAY_GAMMA_MIN = 1.0
DISPLAY_GAMMA_MAX = 2.0
