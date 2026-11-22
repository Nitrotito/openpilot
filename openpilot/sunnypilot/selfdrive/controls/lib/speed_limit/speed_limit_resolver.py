"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import time

import openpilot.cereal.messaging as messaging
from openpilot.cereal import custom
from openpilot.common.constants import CV
from openpilot.common.gps import get_gps_location_service
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot import PARAMS_UPDATE_PERIOD, get_sanitize_int_param
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit import LIMIT_MAX_MAP_DATA_AGE, LIMIT_ADAPT_ACC, \
  LIMIT_AHEAD_MARGIN_TIME, LIMIT_AHEAD_MARGIN_MIN
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.common import Policy, OffsetType

SpeedLimitSource = custom.LongitudinalPlanSP.SpeedLimit.Source

ALL_SOURCES = tuple(SpeedLimitSource.schema.enumerants.values())


class SpeedLimitResolver:
  limit_solutions: dict[custom.LongitudinalPlanSP.SpeedLimit.Source, float]
  distance_solutions: dict[custom.LongitudinalPlanSP.SpeedLimit.Source, float]
  v_ego: float
  speed_limit: float
  speed_limit_last: float
  speed_limit_final: float
  speed_limit_final_last: float
  distance: float
  source: custom.LongitudinalPlanSP.SpeedLimit.Source
  speed_limit_offset: float

  def __init__(self):
    self.params = Params()
    self.frame = -1

    self._gps_location_service = get_gps_location_service(self.params)
    self.limit_solutions = {}  # Store for speed limit solutions from different sources
    self.distance_solutions = {}  # Store for distance to current speed limit start for different sources

    self.policy = self.params.get("SpeedLimitPolicy", return_default=True)
    self.policy = get_sanitize_int_param(
      "SpeedLimitPolicy",
      Policy.min().value,
      Policy.max().value,
      self.params
    )
    self._policy_to_sources_map = {
      Policy.car_state_only: [SpeedLimitSource.car],
      Policy.map_data_only: [SpeedLimitSource.map],
      Policy.car_state_priority: [SpeedLimitSource.car, SpeedLimitSource.map],
      Policy.map_data_priority: [SpeedLimitSource.map, SpeedLimitSource.car],
      Policy.combined: [SpeedLimitSource.car, SpeedLimitSource.map],
    }
    self.source = SpeedLimitSource.none
    for source in ALL_SOURCES:
      self._reset_limit_sources(source)

    self.is_metric = self.params.get_bool("IsMetric")
    self.offset_type = get_sanitize_int_param(
      "SpeedLimitOffsetType",
      OffsetType.min().value,
      OffsetType.max().value,
      self.params
    )
    self.offset_value = self.params.get("SpeedLimitValueOffset", return_default=True)

    # HW1 fork: the lower limit ahead the resolver already switched to, and until when it holds it
    self._ahead_latch_limit = 0.
    self._ahead_latch_until = 0.
    self.distance_to_line = 0.  # m to the latched limit's sign line, 0 when nothing is latched

    self.speed_limit = 0.
    self.speed_limit_last = 0.
    self.speed_limit_final = 0.
    self.speed_limit_final_last = 0.
    self.speed_limit_offset = 0.

  def update_speed_limit_states(self) -> None:
    self.speed_limit_final = self.speed_limit + self.speed_limit_offset

    if self.speed_limit > 0.:
      self.speed_limit_last = self.speed_limit
      self.speed_limit_final_last = self.speed_limit_final

  @property
  def speed_limit_valid(self) -> bool:
    return self.speed_limit > 0.

  @property
  def speed_limit_last_valid(self) -> bool:
    return self.speed_limit_last > 0.

  def update_params(self):
    if self.frame % int(PARAMS_UPDATE_PERIOD / DT_MDL) == 0:
      self.policy = self.params.get("SpeedLimitPolicy", return_default=True)
      self.is_metric = self.params.get_bool("IsMetric")
      self.offset_type = self.params.get("SpeedLimitOffsetType", return_default=True)
      self.offset_value = self.params.get("SpeedLimitValueOffset", return_default=True)

  def _get_speed_limit_offset(self) -> float:
    if self.offset_type == OffsetType.off:
      return 0
    elif self.offset_type == OffsetType.fixed:
      return float(self.offset_value * (CV.KPH_TO_MS if self.is_metric else CV.MPH_TO_MS))
    elif self.offset_type == OffsetType.percentage:
      return float(self.offset_value * 0.01 * self.speed_limit)
    else:
      raise NotImplementedError("Offset not supported")

  def _reset_limit_sources(self, source: custom.LongitudinalPlanSP.SpeedLimit.Source) -> None:
    self.limit_solutions[source] = 0.
    self.distance_solutions[source] = 0.

  def _get_from_car_state(self, sm: messaging.SubMaster) -> None:
    self._reset_limit_sources(SpeedLimitSource.car)
    self.limit_solutions[SpeedLimitSource.car] = sm['carStateSP'].speedLimit
    self.distance_solutions[SpeedLimitSource.car] = 0.

  def _get_from_map_data(self, sm: messaging.SubMaster) -> None:
    self._reset_limit_sources(SpeedLimitSource.map)
    self.distance_to_line = 0.
    self._process_map_data(sm)

  def _process_map_data(self, sm: messaging.SubMaster) -> None:
    gps_data = sm[self._gps_location_service]
    map_data = sm['liveMapDataSP']

    # HW1 fork: the upstream age check compared time.monotonic() to the GPS unix timestamp, so it
    # could never expire, and a limit from before a GNSS loss stayed on screen for a whole drive
    # (measured 2026-10-04: 40 km/h for 55 min on the motorway). Use the receive time and the fix flag.
    if not (sm.alive[self._gps_location_service] and gps_data.hasFix):
      return
    gps_fix_age = time.monotonic() - sm.recv_time[self._gps_location_service]
    if gps_fix_age > LIMIT_MAX_MAP_DATA_AGE:
      return

    speed_limit = map_data.speedLimit if map_data.speedLimitValid else 0.
    next_speed_limit = map_data.speedLimitAhead if map_data.speedLimitAheadValid else 0.

    self._calculate_map_data_limits(sm, speed_limit, next_speed_limit)

  def _calculate_map_data_limits(self, sm: messaging.SubMaster, speed_limit: float, next_speed_limit: float) -> None:
    map_data = sm['liveMapDataSP']

    distance_since_fix = self.v_ego * (time.monotonic() - sm.recv_time[self._gps_location_service])
    distance_to_speed_limit_ahead = max(0., map_data.speedLimitAheadDistance - distance_since_fix)

    self.limit_solutions[SpeedLimitSource.map] = speed_limit
    self.distance_solutions[SpeedLimitSource.map] = 0.
    self.distance_to_line = 0.

    # HW1 fork (2026-11-22, replaces the FIXME-SP block): in Hungary the new limit applies from
    # the sign's line, so a LOWER limit ahead takes over early enough to be reached
    # LIMIT_AHEAD_MARGIN_TIME (at least LIMIT_AHEAD_MARGIN_MIN) before the line, braking at
    # LIMIT_ADAPT_ACC. Two faults of the old block are fixed here:
    # - it aimed at the line itself, so with any lag the car crossed the line still too fast;
    # - it compared the new limit with v_ego, so as soon as the car had slowed to it the
    #   condition flipped and the old, higher limit came back before the line. Once switched,
    #   the new limit is now latched until the sign is passed (the map's current limit becomes
    #   it), a different limit is announced, or the trip to the line plus a few seconds is over.
    now = time.monotonic()
    if self._ahead_latch_limit > 0.:
      passed = 0. < speed_limit <= self._ahead_latch_limit + 0.1
      replaced = 0. < next_speed_limit and abs(next_speed_limit - self._ahead_latch_limit) > 0.1
      if passed or replaced or now > self._ahead_latch_until:
        self._ahead_latch_limit = 0.

    if self._ahead_latch_limit == 0. and 0. < next_speed_limit < self.v_ego and (speed_limit == 0. or next_speed_limit < speed_limit):
      braking_distance = (self.v_ego ** 2 - next_speed_limit ** 2) / (2. * -LIMIT_ADAPT_ACC)
      margin = max(LIMIT_AHEAD_MARGIN_TIME * self.v_ego, LIMIT_AHEAD_MARGIN_MIN)
      if distance_to_speed_limit_ahead <= braking_distance + margin:
        self._ahead_latch_limit = next_speed_limit
        self._ahead_latch_until = now + distance_to_speed_limit_ahead / max(self.v_ego, 1.) + 5.

    if self._ahead_latch_limit > 0.:
      self.limit_solutions[SpeedLimitSource.map] = self._ahead_latch_limit
      # distance to the point the limit has to be reached by, not to the line
      margin = max(LIMIT_AHEAD_MARGIN_TIME * self.v_ego, LIMIT_AHEAD_MARGIN_MIN)
      self.distance_solutions[SpeedLimitSource.map] = max(distance_to_speed_limit_ahead - margin, 0.)
      self.distance_to_line = distance_to_speed_limit_ahead

  def _get_source_solution_according_to_policy(self) -> custom.LongitudinalPlanSP.SpeedLimit.Source:
    sources_for_policy = self._policy_to_sources_map[Policy(self.policy)]

    if Policy(self.policy) != Policy.combined:
      # They are ordered in the order of preference, so we pick the first that's non-zero
      for source in sources_for_policy:
        if self.limit_solutions[source] > 0.:
          return source
      return SpeedLimitSource.none

    sources_with_limits = [(s, limit) for s, limit in [(s, self.limit_solutions[s]) for s in sources_for_policy] if limit > 0.]
    if sources_with_limits:
      return min(sources_with_limits, key=lambda x: x[1])[0]

    return SpeedLimitSource.none

  def _resolve_limit_sources(self, sm: messaging.SubMaster) -> tuple[float, float, custom.LongitudinalPlanSP.SpeedLimit.Source]:
    """Get limit solutions from each data source"""
    self._get_from_car_state(sm)
    self._get_from_map_data(sm)

    source = self._get_source_solution_according_to_policy()
    speed_limit = self.limit_solutions[source] if source else 0.
    distance = self.distance_solutions[source] if source else 0.

    return speed_limit, distance, source

  def update(self, v_ego: float, sm: messaging.SubMaster) -> None:
    self.v_ego = v_ego
    self.update_params()

    self.speed_limit, self.distance, self.source = self._resolve_limit_sources(sm)
    self.speed_limit_offset = self._get_speed_limit_offset()

    self.update_speed_limit_states()

    self.frame += 1
