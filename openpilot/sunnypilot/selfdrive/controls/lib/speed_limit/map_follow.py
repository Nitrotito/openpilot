"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

HW1 fork, map follow (Zoltan, tg 23758-23776, 2026-11-22).

On this car the cruise set speed lives in the car (DI_digitalSpeed) and openpilot only reads
it as the ceiling of its own plan. The stock speed limit assist works inside that ceiling, so
it asks the driver to pull the stalk up to 120 or 130 km/h first ("set to X to engage"), and
asks again when the limit crosses 80 km/h. Nothing in the car or in the panda safety caps the
commanded speed at the stalk value (tesla_legacy.h only checks the accel range; the HW1
DAS_control carries setSpeed 0 or V_CRUISE_MAX and the accel), so the ceiling is a software
choice, and this class makes it:

- With a valid map limit the ceiling is the map limit (with the owner's limit offset, as the
  resolver gives it), capped at MapFollowMaxKph. Up and down, with no confirmation.
- Without map data the stalk rules, as before.
- When the driver moves the stalk while following, the stalk rules until the next limit
  change, then the map takes over again. A wrong map limit is one stalk click away.
- A map gap shorter than MAP_FOLLOW_HOLD_TIME keeps the last limit, so a short gap does not
  pull the car down towards the stalk.
"""
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot import PARAMS_UPDATE_PERIOD
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit import MAP_FOLLOW_HOLD_TIME, MAP_FOLLOW_MAX_KPH_DEFAULT
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.common import Mode

# The stalk moves the cluster set speed during engagement itself; changes in this window
# after the long control turns on are the engagement, not an override.
ENGAGE_GUARD_TIME = 0.5  # s
MAX_KPH_MIN = 30
MAX_KPH_MAX = 150


class MapFollow:
  def __init__(self, params: Params | None = None):
    self.params = params if params is not None else Params()
    self.frame = -1
    self.enabled = True
    self.sla_mode_assist = False
    self.max_kph = MAP_FOLLOW_MAX_KPH_DEFAULT

    self.active = False
    self.ceiling = 0.  # m/s, valid while active
    self.override = False
    self._override_limit_kph = 0
    self._limit = 0.  # m/s, last map limit seen (held through short gaps)
    self._limit_kph = 0
    self._hold_frames = 0
    self._prev_cluster_kph: int | None = None
    self._long_enabled_prev = False
    self._guard_frames = 0

  def update_params(self) -> None:
    if self.frame % int(PARAMS_UPDATE_PERIOD / DT_MDL) == 0:
      self.enabled = self.params.get_bool("MapFollowEnabled")
      self.sla_mode_assist = self.params.get("SpeedLimitMode", return_default=True) == Mode.assist
      try:
        max_kph = int(self.params.get("MapFollowMaxKph", return_default=True))
      except (TypeError, ValueError):
        max_kph = MAP_FOLLOW_MAX_KPH_DEFAULT
      self.max_kph = max(MAX_KPH_MIN, min(MAX_KPH_MAX, max_kph))

  def _update_map_limit(self, map_limit: float, map_limit_valid: bool) -> None:
    if map_limit_valid and map_limit > 0.:
      self._limit = map_limit
      self._limit_kph = round(map_limit * CV.MS_TO_KPH)
      self._hold_frames = int(MAP_FOLLOW_HOLD_TIME / DT_MDL)
    elif self._hold_frames > 0:
      self._hold_frames -= 1
    else:
      self._limit = 0.
      self._limit_kph = 0

  def _update_override(self, long_enabled: bool, cluster_kph: int) -> None:
    if long_enabled and not self._long_enabled_prev:
      # a fresh engagement starts on the map
      self.override = False
      self._guard_frames = int(ENGAGE_GUARD_TIME / DT_MDL)
      self._prev_cluster_kph = cluster_kph
    elif not long_enabled:
      self.override = False
      self._prev_cluster_kph = None
    else:
      if self._guard_frames > 0:
        self._guard_frames -= 1
      elif self._prev_cluster_kph is not None and cluster_kph != self._prev_cluster_kph and self._limit_kph > 0:
        # the driver moved the stalk while the map was in charge: the stalk rules until the next limit
        self.override = True
        self._override_limit_kph = self._limit_kph
      self._prev_cluster_kph = cluster_kph

      if self.override and self._limit_kph > 0 and self._limit_kph != self._override_limit_kph:
        self.override = False

    self._long_enabled_prev = long_enabled

  def update(self, long_enabled: bool, force_decel: bool, v_cruise_cluster: float, map_limit: float, map_limit_valid: bool) -> None:
    """map_limit in m/s (with the owner's limit offset), valid only when it comes from the map."""
    self.frame += 1
    self.update_params()

    cluster_kph = round(v_cruise_cluster * CV.MS_TO_KPH)
    self._update_map_limit(map_limit, map_limit_valid)
    self._update_override(long_enabled, cluster_kph)

    cap = self.max_kph * CV.KPH_TO_MS  # the cap is always km/h, whatever the display unit
    self.active = bool(self.enabled and self.sla_mode_assist and long_enabled and not force_decel
                       and not self.override and self._limit > 0.)
    self.ceiling = min(self._limit, cap) if self.active else 0.
