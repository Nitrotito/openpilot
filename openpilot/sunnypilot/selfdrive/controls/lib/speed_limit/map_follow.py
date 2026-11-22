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

# After engagement the stalk value counts as the driver's only once the cluster shows a valid
# set speed (not unset/255, not -1, not 0), plus a few frames for the car's own settling.
# Measured on 0000049c (2026-11-22): at both engagements the cluster already showed the set
# speed before the enable edge and did not change in the next 3 s, so the guard is short.
ENGAGE_GUARD_FRAMES = 3
# The caller passes the UNCLIPPED carState.vCruiseCluster: the planner clips it to V_CRUISE_MAX
# (145), which would turn the unset value 255 into a valid-looking 145 (lektor 5104 X3).
V_CRUISE_CLUSTER_VALID_KPH = (1, 254)
# An override is cleared by a limit change only once the new limit has held this long, so a
# one-frame map flicker (50 -> 70 -> 50) does not hand the ceiling back to the map.
OVERRIDE_CLEAR_STABLE_TIME = 1.5  # s
# Measured on 0000049c (2026-11-22): 67641 engaged carState frames, vCruiseCluster changed 8
# times, all 5 km/h stalk steps, no drift by itself; the HW1 carState carries no buttonEvents,
# so a stalk move is recognised as a change of at least this much.
STALK_CHANGE_MIN_KPH = 1
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
    self._override_limit_kph = 0  # the limit the driver overrode (the last one seen, even before a map gap)
    self._limit = 0.  # m/s, last map limit seen (held through short gaps)
    self._limit_kph = 0
    self._last_seen_limit_kph = 0  # last valid map limit, NOT cleared by a gap
    self._hold_frames = 0
    self._prev_cluster_kph: int | None = None
    self._long_enabled_prev = False
    self._guard_frames = 0
    self._guard_armed = False  # waiting for the first valid cluster value after engagement
    self._clear_candidate_kph = 0
    self._clear_stable_frames = 0
    self._override_base_pending = False  # override made with no limit: the first limit to arrive becomes its base

  def update_params(self) -> None:
    if self.frame % int(PARAMS_UPDATE_PERIOD / DT_MDL) == 0:
      self.enabled = self.params.get_bool("MapFollowEnabled")
      self.sla_mode_assist = self.params.get("SpeedLimitMode", return_default=True) == Mode.assist
      try:
        max_kph = int(self.params.get("MapFollowMaxKph", return_default=True))
      except (TypeError, ValueError):
        max_kph = MAP_FOLLOW_MAX_KPH_DEFAULT
      self.max_kph = max(MAX_KPH_MIN, min(MAX_KPH_MAX, max_kph))

  def _update_map_limit(self, map_limit: float, map_limit_valid: bool) -> int:
    """Updates the held limit; returns the raw (unheld) valid limit in km/h, 0 when there is none."""
    if map_limit_valid and map_limit > 0.:
      self._limit = map_limit
      self._limit_kph = round(map_limit * CV.MS_TO_KPH)
      self._last_seen_limit_kph = self._limit_kph
      self._hold_frames = int(MAP_FOLLOW_HOLD_TIME / DT_MDL)
      return self._limit_kph
    if self._hold_frames > 0:
      self._hold_frames -= 1
    else:
      self._limit = 0.
      self._limit_kph = 0
    return 0

  def _set_override(self) -> None:
    self.override = True
    # B1 (lektor 5102) and X1/X2 (lektor 5104): a stalk move with no map limit right now (no map
    # yet, or a gap longer than the hold) still counts. Its base is the first limit that arrives
    # afterwards, whatever it is, so a returning or newly appearing limit never takes the ceiling
    # away from the stalk by itself; only a later, different limit that holds does.
    if self._limit_kph > 0:
      self._override_limit_kph = self._limit_kph
      self._override_base_pending = False
    else:
      self._override_limit_kph = 0
      self._override_base_pending = True
    self._clear_candidate_kph = 0
    self._clear_stable_frames = 0

  def _update_override_clear(self, raw_limit_kph: int) -> None:
    if not self.override:
      return
    if self._override_base_pending:
      if raw_limit_kph > 0:
        self._override_limit_kph = raw_limit_kph
        self._override_base_pending = False
      return
    if raw_limit_kph <= 0 or raw_limit_kph == self._override_limit_kph:
      self._clear_candidate_kph = 0
      self._clear_stable_frames = 0
      return
    if raw_limit_kph == self._clear_candidate_kph:
      self._clear_stable_frames += 1
    else:
      self._clear_candidate_kph = raw_limit_kph
      self._clear_stable_frames = 1
    if self._clear_stable_frames * DT_MDL >= OVERRIDE_CLEAR_STABLE_TIME:
      # a new limit (a new sign, or a different one after a gap) that has held: the map takes over again
      self.override = False

  def _update_override(self, long_enabled: bool, cluster_kph: int, raw_limit_kph: int) -> None:
    cluster_valid = V_CRUISE_CLUSTER_VALID_KPH[0] <= cluster_kph <= V_CRUISE_CLUSTER_VALID_KPH[1]
    if long_enabled and not self._long_enabled_prev:
      # a fresh engagement starts on the map
      self.override = False
      self._guard_armed = True
      self._guard_frames = ENGAGE_GUARD_FRAMES
      self._prev_cluster_kph = None
    elif not long_enabled:
      self.override = False
      self._guard_armed = False
      self._prev_cluster_kph = None

    if long_enabled:
      if self._guard_armed:
        # K1 (lektor 5102): no fixed time window; wait for the first valid cluster value, then a few frames
        if cluster_valid:
          self._guard_frames -= 1
          if self._guard_frames <= 0:
            self._guard_armed = False
          self._prev_cluster_kph = cluster_kph
      elif cluster_valid:
        if self._prev_cluster_kph is not None and abs(cluster_kph - self._prev_cluster_kph) >= STALK_CHANGE_MIN_KPH:
          # the driver moved the stalk: the stalk rules until a new limit (see _update_override_clear)
          self._set_override()
        self._prev_cluster_kph = cluster_kph

      self._update_override_clear(raw_limit_kph)

    self._long_enabled_prev = long_enabled

  def update(self, long_enabled: bool, force_decel: bool, v_cruise_cluster: float, map_limit: float, map_limit_valid: bool) -> None:
    """map_limit in m/s (with the owner's limit offset), valid only when it comes from the map."""
    self.frame += 1
    self.update_params()

    cluster_kph = round(v_cruise_cluster * CV.MS_TO_KPH)
    raw_limit_kph = self._update_map_limit(map_limit, map_limit_valid)
    self._update_override(long_enabled, cluster_kph, raw_limit_kph)

    cap = self.max_kph * CV.KPH_TO_MS  # the cap is always km/h, whatever the display unit
    self.active = bool(self.enabled and self.sla_mode_assist and long_enabled and not force_decel
                       and not self.override and self._limit > 0.)
    self.ceiling = min(self._limit, cap) if self.active else 0.
