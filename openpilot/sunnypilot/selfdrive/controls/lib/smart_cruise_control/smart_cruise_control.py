"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import openpilot.cereal.messaging as messaging
from openpilot.common.gps import get_gps_location_service
from openpilot.common.params import Params
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control.vision_controller import SmartCruiseControlVision
from openpilot.sunnypilot.selfdrive.controls.lib.smart_cruise_control.map_controller import SmartCruiseControlMap


class SmartCruiseControl:
  def __init__(self):
    self.vision = SmartCruiseControlVision()
    self.map = SmartCruiseControlMap()
    self.gps_location_service = get_gps_location_service(Params())

  def _gps_fix_ok(self, sm: messaging.SubMaster) -> bool:
    # HW1 fork: the map controller locates itself from LastGPSPosition, which keeps the last
    # good position after the GNSS fix is lost. Without a live fix it slows down for curves
    # that are not there (measured 2026-10-04: 55 min on the motorway, turning at 96 km/h).
    try:
      return bool(sm.alive[self.gps_location_service] and sm[self.gps_location_service].hasFix)
    except KeyError:
      return True

  def update(self, sm: messaging.SubMaster, long_enabled: bool, long_override: bool, v_ego: float, a_ego: float, v_cruise: float) -> None:
    self.map.update(long_enabled, long_override, v_ego, a_ego, v_cruise, gps_ok=self._gps_fix_ok(sm))
    self.vision.update(sm, long_enabled, long_override, v_ego, a_ego, v_cruise)
