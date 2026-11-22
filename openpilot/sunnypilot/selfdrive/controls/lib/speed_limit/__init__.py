"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
LIMIT_ADAPT_ACC = -1.  # m/s^2 Ideal acceleration for the adapting (braking) phase when approaching speed limits.
LIMIT_MAX_MAP_DATA_AGE = 10.  # s Maximum time to hold to map data, then consider it invalid inside limits controllers.
LIMIT_MIN_ACC = -1.5  # m/s^2 Hardest braking a limit controller may ask for (same value as speed_limit_assist.LIMIT_MIN_ACC).

# HW1 fork, map follow (Zoltan, tg 23758-23776): in Hungary the new limit applies from the
# sign's line, so a lower limit ahead is reached this much BEFORE the line: the GPS fix,
# the map's sign position and the cruise controller's own settling all cost a few metres.
LIMIT_AHEAD_MARGIN_TIME = 1.5  # s of travel at the current speed
LIMIT_AHEAD_MARGIN_MIN = 20.  # m, the margin never gets shorter than this
# The map's current limit drops out for a few seconds now and then (OSM ways without a
# maxspeed tag between two that have one). Map follow keeps the last limit this long
# before it falls back to the stalk, so a gap does not brake the car towards the stalk.
MAP_FOLLOW_HOLD_TIME = 5.  # s
MAP_FOLLOW_MAX_KPH_DEFAULT = 130

# Speed Limit Assist constants
PCM_LONG_REQUIRED_MAX_SET_SPEED = {
  True: (33.3333, 36.1111),  # km/h, (120, 130)
  False: (31.2928, 35.7632),  # mph, (70, 80)
}

CONFIRM_SPEED_THRESHOLD = {
  True: 80,   # km/h
  False: 50,  # mph
}
