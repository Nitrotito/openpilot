"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

A small dot in the top left corner that says, at a glance, whether the GPS fix
is good enough to trust. The device does not publish a boolean "signal ok", it
publishes a horizontal accuracy in metres, so the dot has to draw a line
somewhere: that line is GOOD_ACCURACY / FAIR_ACCURACY below.

The dot is always drawn while onroad. That is deliberate: a dot that disappears
on a bad fix looks exactly like a dot that is broken, and the owner would have
no way to tell the two apart.
"""
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.onroad.developer_ui.elements import GpsInfoElement

# Distance from the top left corner of the camera view, in pixels.
MARGIN_X = 28
MARGIN_Y = 28
RADIUS = 9

# Horizontal accuracy thresholds, in metres (Zoltan's call, 2026-09-17).
GOOD_ACCURACY = 5.0
FAIR_ACCURACY = 20.0

GREEN = rl.Color(0, 200, 90, 255)
AMBER = rl.Color(235, 170, 0, 255)
DARK = rl.Color(70, 70, 70, 180)


class GpsSignalDot:
  """Top left corner dot: green = good fix, amber = usable, dark = do not trust."""

  def __init__(self):
    self._color: rl.Color = DARK

  def update(self) -> None:
    self._color = self._color_for(self._accuracy())

  def _accuracy(self) -> float:
    """Horizontal accuracy in metres, or -1.0 when there is no usable fix."""
    sm = ui_state.sm
    gps_data, valid = GpsInfoElement.get_gps_data(sm)
    if not valid or gps_data is None:
      return -1.0

    accuracy = float(getattr(gps_data, 'horizontalAccuracy', 0.0) or 0.0)
    if accuracy <= 0.0:
      # The legacy gpsLocation packet does not always carry a meaningful
      # accuracy; the developer UI has the same caveat. Treat it as "present,
      # quality unknown" rather than claiming a good fix we cannot prove.
      return FAIR_ACCURACY
    return accuracy

  @staticmethod
  def _color_for(accuracy: float) -> rl.Color:
    if accuracy < 0.0:
      return DARK
    if accuracy <= GOOD_ACCURACY:
      return GREEN
    if accuracy <= FAIR_ACCURACY:
      return AMBER
    return DARK

  def render(self, rect: rl.Rectangle) -> None:
    center = rl.Vector2(int(rect.x + MARGIN_X + RADIUS), int(rect.y + MARGIN_Y + RADIUS))
    # A dark ring under the dot keeps it readable over a bright road.
    rl.draw_circle_v(center, RADIUS + 2, rl.Color(0, 0, 0, 120))
    rl.draw_circle_v(center, RADIUS, self._color)
