"""Owner settings: the two knobs that are backed by a plain file instead of a Params key.

Params keys are registered in params_keys.h, which is compiled into params_pyx.so, so
adding one would need a full rebuild on the device for a single number. Both consumers
already read a file -- the longitudinal planner for the set speed offset, the camera view
for the preview gamma -- so the file stays the source of truth and this panel just writes
it. Both are re-read while driving, no restart needed.
"""
import os

from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigMultiToggle, BigParamControl, GreyBigButton
from openpilot.system.ui.lib.multilang import tr
from openpilot.sunnypilot.owner_files import CRUISE_SPEED_OFFSET_PATH, DISPLAY_GAMMA_PATH


class BigMultiFileToggle(BigMultiToggle):
  """Multi option toggle persisted to a plain file.

  labels and values are parallel: labels are shown, values are what gets written.
  """

  def __init__(self, text: str, path: str, labels: list[str], values: list[str], default_index: int):
    assert len(labels) == len(values)
    super().__init__(text, labels)
    self._path = path
    self._values = values
    self._default_index = default_index
    self.set_value(self._options[self._read_index()])

  def _read_index(self) -> int:
    try:
      with open(self._path) as f:
        current = float(f.read().strip())
    except (OSError, ValueError):
      return self._default_index

    for i, value in enumerate(self._values):
      if abs(float(value) - current) < 1e-6:
        return i
    return self._default_index

  def _handle_mouse_release(self, mouse_pos):
    super()._handle_mouse_release(mouse_pos)
    value = self._values[self._options.index(self.value)]
    # write via a temporary file: the reader parses with float() on a running car
    try:
      tmp = self._path + ".tmp"
      with open(tmp, "w") as f:
        f.write(value)
      os.replace(tmp, self._path)
    except OSError:
      pass


class BigMultiParamValueToggle(BigMultiToggle):
  """Multi option toggle over a Params integer that stores a VALUE, not an index.

  The mici set already has BigMultiParamToggle, but that writes the option index. Keys like
  SpeedLimitValueOffset (-30..30) or AutoLaneChangeTimer (-1..5) carry the value itself, so
  the index would silently mean something else.
  """

  def __init__(self, text: str, param: str, labels: list[str], values: list[int]):
    assert len(labels) == len(values)
    super().__init__(text, labels)
    self._param = param
    self._values = values
    self._params = Params()
    self.set_value(self._options[self._read_index()])

  def _read_index(self) -> int:
    try:
      current = int(self._params.get(self._param, return_default=True))
    except (TypeError, ValueError):
      return 0
    return self._values.index(current) if current in self._values else 0

  def _handle_mouse_release(self, mouse_pos):
    super()._handle_mouse_release(mouse_pos)
    self._params.put(self._param, self._values[self._options.index(self.value)])


class OwnSettingsLayoutMici(NavScroller):
  def __init__(self):
    super().__init__()

    speed_offset = BigMultiFileToggle(
      tr("set speed offset"), CRUISE_SPEED_OFFSET_PATH,
      ["0", "-1", "-2", "-3"], ["0", "-1", "-2", "-3"], 0,
    )
    preview_brightness = BigMultiFileToggle(
      tr("preview brightness"), DISPLAY_GAMMA_PATH,
      [tr("original"), tr("light"), tr("medium"), tr("strong")], ["1.0", "1.2", "1.45", "1.7"], 2,
    )

    # the mici widget set already has a Params backed boolean with a single pill: an on/off
    # knob drawn with one pill per option reads as two separate lamps
    road_edge = BigParamControl(tr("road edge lane change"), "RoadEdgeLaneChangeEnabled")

    curve_map = BigParamControl(tr("curve slowdown from map"), "SmartCruiseControlMap")
    curve_vision = BigParamControl(tr("curve slowdown from camera"), "SmartCruiseControlVision")

    speed_limit_mode = BigMultiParamValueToggle(
      tr("speed limit assist"), "SpeedLimitMode",
      [tr("off"), tr("show"), tr("warn"), tr("assist")], [0, 1, 2, 3],
    )
    speed_limit_offset = BigMultiParamValueToggle(
      tr("speed limit offset"), "SpeedLimitValueOffset",
      ["0", "-1", "-2", "-3", "-5"], [0, -1, -2, -3, -5],
    )

    mads = BigParamControl(tr("steering without the pedals"), "Mads")
    mads_brake = BigMultiParamValueToggle(
      tr("on braking"), "MadsSteeringMode",
      [tr("stays on"), tr("pauses"), tr("turns off")], [0, 1, 2],
    )

    lane_change_timer = BigMultiParamValueToggle(
      tr("auto lane change"), "AutoLaneChangeTimer",
      [tr("off"), tr("nudge"), tr("at once"), "0.5 s", "1 s", "2 s", "3 s"], [-1, 0, 1, 2, 3, 4, 5],
    )

    self._scroller.add_widgets([
      speed_offset,
      GreyBigButton("", tr("The set speed on the screen stays, only the speed held moves.")),
      preview_brightness,
      GreyBigButton("", tr("Only the camera image on the screen changes, never what the car sees.")),
      road_edge,
      GreyBigButton("", tr("On: no lane change towards a road edge on the signaled side.")),
      curve_map,
      curve_vision,
      GreyBigButton("", tr("Map: slows down for a curve drawn on the map. Camera: slows down for the curve it sees.")),
      speed_limit_mode,
      speed_limit_offset,
      GreyBigButton("", tr("Assist adjusts the set speed to the sign, by the offset. Show and warn only tell you.")),
      mads,
      mads_brake,
      GreyBigButton("", tr("Steering can stay on without cruise control. This is what happens to it when you brake.")),
      lane_change_timer,
      GreyBigButton("", tr("Nudge: it waits for your hand on the wheel. A time: it changes lane on its own after the blinker.")),
    ])
