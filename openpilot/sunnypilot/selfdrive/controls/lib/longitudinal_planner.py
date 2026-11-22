"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from openpilot.cereal import messaging, custom
from opendbc.car import structs
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot import PARAMS_UPDATE_PERIOD
from openpilot.selfdrive.car.cruise import V_CRUISE_MAX
from openpilot.selfdrive.controls.lib.accel_boost import AccelBoost
from openpilot.sunnypilot.selfdrive.controls.lib.accel_boost import AccelBoostSP
from openpilot.sunnypilot.selfdrive.controls.lib.dec.dec import DynamicExperimentalController
from openpilot.sunnypilot.selfdrive.controls.lib.e2e_alerts_helper import E2EAlertsHelper
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control.smart_cruise_control import SmartCruiseControl
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.speed_limit_assist import SpeedLimitAssist, V_CRUISE_UNSET
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.speed_limit_resolver import SpeedLimitResolver
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.map_follow import MapFollow
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit import LIMIT_ADAPT_ACC, LIMIT_MIN_ACC
from openpilot.sunnypilot.selfdrive.selfdrived.events import EventsSP
from openpilot.sunnypilot.models.helpers import get_active_bundle
from openpilot.sunnypilot.owner_files import CRUISE_SPEED_OFFSET_PATH, CRUISE_SPEED_OFFSET_LIMIT

DecState = custom.LongitudinalPlanSP.DynamicExperimentalControl.DynamicExperimentalControlState
LongitudinalPlanSource = custom.LongitudinalPlanSP.LongitudinalPlanSource
SpeedLimitSource = custom.LongitudinalPlanSP.SpeedLimit.Source

# Constant offset applied to the speed the car actually holds: to the MANUALLY set cruise
# speed, and to the speed limit assist's output. The set speed shown on screen and on the
# dash is unchanged, and so is the speed limit the assist reads off the map; only the held
# speed moves by this much. The assist's own SpeedLimitValueOffset is deliberately NOT used
# for this, because it rewrites the resolved limit and would drag the assist's own
# thresholds with it (see update_targets).
#
# Read from a plain file instead of a Params key on purpose: params_keys.h is compiled
# into params_pyx.so, so a new key would need a full rebuild on the device.
# Units follow IsMetric (km/h, or mph when imperial). Empty/missing/invalid file = 0.
# The path and the clamp live in owner_files, so the settings panel writes exactly what
# this reads.


class LongitudinalPlannerSP:
  def __init__(self, CP: structs.CarParams, CP_SP: structs.CarParamsSP, mpc):
    self.events_sp = EventsSP()
    self.resolver = SpeedLimitResolver()
    self.dec = DynamicExperimentalController(CP, mpc)
    self.scc = SmartCruiseControl()
    self.resolver = SpeedLimitResolver()
    self.sla = SpeedLimitAssist(CP, CP_SP)
    self.map_follow = MapFollow()
    # HW1 fork: braking floor for the main planner's cruise candidate when the target was lowered
    # by a speed limit, None otherwise (then the planner's own A_CRUISE_MIN applies); set in update_targets
    self.speed_limit_accel_min: float | None = None
    self.generation = int(model_bundle.generation) if (model_bundle := get_active_bundle()) else None
    self.source = LongitudinalPlanSource.cruise
    self.e2e_alerts_helper = E2EAlertsHelper()
    self.accel_boost_sp = AccelBoostSP()
    self.openpilot_longitudinal = CP.openpilotLongitudinalControl

    self.output_v_target = 0.
    self.output_a_target = 0.

    self.params = Params()
    self.frame = 0
    self.cruise_speed_offset = 0.  # m/s, signed

  def _read_cruise_speed_offset(self) -> float:
    """Signed offset in m/s for the manual set speed. 0 on any problem."""
    try:
      with open(CRUISE_SPEED_OFFSET_PATH) as f:
        raw = float(f.read().strip())
    except (OSError, ValueError):
      return 0.
    raw = max(-CRUISE_SPEED_OFFSET_LIMIT, min(CRUISE_SPEED_OFFSET_LIMIT, raw))
    conv = CV.KPH_TO_MS if self.params.get_bool("IsMetric") else CV.MPH_TO_MS
    return raw * conv

  def update_params(self) -> None:
    if self.frame % int(PARAMS_UPDATE_PERIOD / DT_MDL) == 0:
      self.cruise_speed_offset = self._read_cruise_speed_offset()
    self.frame += 1

  def is_e2e(self, sm: messaging.SubMaster) -> bool:
    # Upstream deprecated selfdriveState.experimentalMode (#39097) and runs end to end always
    # with openpilot longitudinal; before that selfdrived published it as exactly this.
    experimental_mode = self.openpilot_longitudinal
    if not self.dec.active():
      return experimental_mode

    return experimental_mode and self.dec.mode() == "blended"

  def update_targets(self, sm: messaging.SubMaster, v_ego: float, a_ego: float, v_cruise: float) -> tuple[float, float]:
    self.update_params()
    CS = sm['carState']
    v_cruise_cluster_kph = min(CS.vCruiseCluster, V_CRUISE_MAX)
    v_cruise_cluster = v_cruise_cluster_kph * CV.KPH_TO_MS

    long_enabled = sm['carControl'].enabled
    long_override = sm['carControl'].cruiseControl.override

    # Smart Cruise Control
    self.scc.update(sm, long_enabled, long_override, v_ego, a_ego, v_cruise)

    # Speed Limit Resolver
    self.resolver.update(v_ego, sm)

    # HW1 fork, map follow: with a map limit the map is the ceiling instead of the stalk (see map_follow.py)
    map_limit_valid = self.resolver.speed_limit_valid and self.resolver.source == SpeedLimitSource.map
    # the unclipped cluster value: clipped to V_CRUISE_MAX, the unset 255 would look like a valid 145
    self.map_follow.update(long_enabled, sm['controlsState'].forceDecel, CS.vCruiseCluster * CV.KPH_TO_MS,
                           self.resolver.speed_limit_final, map_limit_valid)
    self.sla.map_follow_active = self.map_follow.active

    # Speed Limit Assist
    has_speed_limit = self.resolver.speed_limit_valid or self.resolver.speed_limit_last_valid
    self.sla.update(long_enabled, long_override, v_ego, a_ego, v_cruise_cluster, self.resolver.speed_limit,
                    self.resolver.speed_limit_final_last, has_speed_limit, self.resolver.distance, self.events_sp)

    # The same manual offset also applies to the speed limit assist, but only to its OUTPUT.
    # The resolved limit itself is left untouched, so the assist keeps seeing the real sign
    # value: the 80 km/h confirmation threshold and the 120/130 required set speed derived
    # from it behave exactly as they do with no offset. Subtracting inside the resolver
    # instead (SpeedLimitValueOffset) would shift those thresholds too, which would turn
    # every 80 sign into a 79 and start demanding confirmation on roads that need none.
    sla_v_target = self.sla.output_v_target
    if sla_v_target < V_CRUISE_UNSET:
      sla_v_target = max(0., sla_v_target + self.cruise_speed_offset)

    # While the map follows, its ceiling replaces the stalk value as the cruise target, with
    # the same manual offset the stalk value gets. forceDecel (v_cruise 0) is never replaced.
    cruise_ceiling = self.map_follow.ceiling if self.map_follow.active else v_cruise
    targets = {
      LongitudinalPlanSource.cruise: (max(0., cruise_ceiling + self.cruise_speed_offset), a_ego),
      LongitudinalPlanSource.sccVision: (self.scc.vision.output_v_target, self.scc.vision.output_a_target),
      LongitudinalPlanSource.sccMap: (self.scc.map.output_v_target, self.scc.map.output_a_target),
      LongitudinalPlanSource.speedLimitAssist: (sla_v_target, self.sla.output_a_target),
    }

    self.source = min(targets, key=lambda k: targets[k][0])
    self.output_v_target, self.output_a_target = targets[self.source]
    self.speed_limit_accel_min = self._speed_limit_accel_min(v_ego)
    return self.output_v_target, self.output_a_target

  def _speed_limit_accel_min(self, v_ego: float) -> float | None:
    """HW1 fork: how hard the cruise candidate may brake towards a target lowered by a speed limit.

    None when the target does not come from a speed limit: then the main planner keeps its own
    gentle A_CRUISE_MIN (-0.5, the owner's choice for manual reductions, tg 23743). A target
    lowered by a speed limit (the assist, or the map follow ceiling) may brake at LIMIT_ADAPT_ACC
    (-1.0), because the new limit has to be reached before the sign's line; when the
    announcement came too late for that, up to LIMIT_MIN_ACC (-1.5), so the overrun past the
    line stays small instead of growing with a gentle floor.
    """
    from_limit = self.source == LongitudinalPlanSource.speedLimitAssist or \
      (self.source == LongitudinalPlanSource.cruise and self.map_follow.active)
    if not from_limit or self.output_v_target >= v_ego:
      return None

    floor = LIMIT_ADAPT_ACC
    # resolver.distance runs to the point the limit should be reached by (the line minus the
    # margin); once inside the margin, aim at the line itself
    distance = self.resolver.distance
    if distance < 1. and self.resolver.source == SpeedLimitSource.map:
      distance = self.resolver.distance_to_line
    if distance > 0.:
      needed = (self.output_v_target ** 2 - v_ego ** 2) / (2. * distance)
      floor = min(floor, needed)
    return max(floor, LIMIT_MIN_ACC)

  def update(self, sm: messaging.SubMaster) -> None:
    if self.accel_boost_sp.update_params():
      self.accel_boost = self.accel_boost_sp if self.accel_boost_sp.enabled and self.openpilot_longitudinal else AccelBoost()

    self.events_sp.clear()
    self.dec.update(sm)
    self.e2e_alerts_helper.update(sm, self.events_sp)

  def publish_longitudinal_plan_sp(self, sm: messaging.SubMaster, pm: messaging.PubMaster) -> None:
    plan_sp_send = messaging.new_message('longitudinalPlanSP')

    plan_sp_send.valid = sm.all_checks(service_list=['carState', 'controlsState'])

    longitudinalPlanSP = plan_sp_send.longitudinalPlanSP
    longitudinalPlanSP.longitudinalPlanSource = self.source
    longitudinalPlanSP.vTarget = float(self.output_v_target)
    longitudinalPlanSP.aTarget = float(self.output_a_target)
    longitudinalPlanSP.events = self.events_sp.to_msg()

    # Dynamic Experimental Control
    dec = longitudinalPlanSP.dec
    dec.state = DecState.blended if self.dec.mode() == 'blended' else DecState.acc
    dec.enabled = self.dec.enabled()
    dec.active = self.dec.active()

    # Smart Cruise Control
    smartCruiseControl = longitudinalPlanSP.smartCruiseControl
    # Vision Control
    sccVision = smartCruiseControl.vision
    sccVision.state = self.scc.vision.state
    sccVision.vTarget = float(self.scc.vision.output_v_target)
    sccVision.aTarget = float(self.scc.vision.output_a_target)
    sccVision.currentLateralAccel = float(self.scc.vision.current_lat_acc)
    sccVision.maxPredictedLateralAccel = float(self.scc.vision.max_pred_lat_acc)
    sccVision.enabled = self.scc.vision.is_enabled
    sccVision.active = self.scc.vision.is_active
    # Map Control
    sccMap = smartCruiseControl.map
    sccMap.state = self.scc.map.state
    sccMap.vTarget = float(self.scc.map.output_v_target)
    sccMap.aTarget = float(self.scc.map.output_a_target)
    sccMap.enabled = self.scc.map.is_enabled
    sccMap.active = self.scc.map.is_active

    # Speed Limit
    speedLimit = longitudinalPlanSP.speedLimit
    resolver = speedLimit.resolver
    resolver.speedLimit = float(self.resolver.speed_limit)
    resolver.speedLimitLast = float(self.resolver.speed_limit_last)
    resolver.speedLimitFinal = float(self.resolver.speed_limit_final)
    resolver.speedLimitFinalLast = float(self.resolver.speed_limit_final_last)
    resolver.speedLimitValid = self.resolver.speed_limit_valid
    resolver.speedLimitLastValid = self.resolver.speed_limit_last_valid
    resolver.speedLimitOffset = float(self.resolver.speed_limit_offset)
    resolver.distToSpeedLimit = float(self.resolver.distance)
    resolver.source = self.resolver.source
    assist = speedLimit.assist
    assist.state = self.sla.state
    assist.enabled = self.sla.is_enabled
    assist.active = self.sla.is_active
    assist.vTarget = float(self.sla.output_v_target)
    assist.aTarget = float(self.sla.output_a_target)

    # E2E Alerts
    e2eAlerts = longitudinalPlanSP.e2eAlerts
    e2eAlerts.greenLightAlert = self.e2e_alerts_helper.green_light_alert
    e2eAlerts.leadDepartAlert = self.e2e_alerts_helper.lead_depart_alert

    pm.send('longitudinalPlanSP', plan_sp_send)
