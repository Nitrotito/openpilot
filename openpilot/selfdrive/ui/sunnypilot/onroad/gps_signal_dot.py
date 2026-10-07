"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

A small dot in the top right corner that says, at a glance, whether the GPS fix
is good enough to trust. It started in the top left (2026-09-17) and moved on
2026-09-19: the top left is where the mici HUD draws the MAX set-speed box
(hud_renderer._draw_set_speed anchors at rect.x, rect.y), so the dot sat on top
of it. The top right is the only free corner: the steering wheel is bottom left,
the model-source icon is bottom right, and the right blind-spot icon starts
100 px below the top edge, well clear of this dot.

The device does not publish a boolean "signal ok", it publishes a horizontal
accuracy in metres, so the dot has to draw a line somewhere: that line is
GOOD_ACCURACY / FAIR_ACCURACY below.

The dot is always drawn while onroad. That is deliberate: a dot that disappears
on a bad fix looks exactly like a dot that is broken, and the owner would have
no way to tell the two apart.

2026-10-04 (Zoltan, tg 10563): while engaged the dot grows into a badge with the
speed the planner is actually aiming for (longitudinalPlanSP.vTarget) in it, and
the badge colour is the same GPS colour as before. On that day the map curve
controller held the car at 96 km/h with the cruise set to 130 and no GPS fix, and
nothing on the screen said so. A dark badge with a number lower than the set speed
now says exactly that. Disengaged, it is the plain dot again.

2026-10-07 (Zoltan, tg 11772): on the road the badge was too small and the white
number on green/amber was unreadable. It is now drawn like a speed limit sign:
a white disc with a thick ring in the GPS colour and a bold black number, half
again as large. The top margin shrinks so the badge still ends at y = 100, above
the right blind-spot icon.
"""
import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.onroad.developer_ui.elements import GpsInfoElement
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached

# Distance from the top RIGHT corner of the camera view, in pixels.
# MARGIN_X is measured from the right edge, MARGIN_Y from the top edge.
MARGIN_X = 28
MARGIN_Y = 28
RADIUS = 9

# Target speed badge (engaged only), drawn like a speed limit sign. It ends at
# y = BADGE_MARGIN_Y + 2 * BADGE_RADIUS + 2 = 100, where the right blind-spot icon starts.
BADGE_RADIUS = 44
BADGE_MARGIN_Y = 10
BADGE_RING = 8
BADGE_FONT_SIZE = 50
# Above this the planner has no target of its own (V_CRUISE_UNSET is 255 km/h).
MAX_SHOWN_KPH = 200.

# Horizontal accuracy thresholds, in metres (Zoltan's call, 2026-09-17).
GOOD_ACCURACY = 5.0
FAIR_ACCURACY = 20.0

GREEN = rl.Color(0, 200, 90, 255)
AMBER = rl.Color(235, 170, 0, 255)
DARK = rl.Color(70, 70, 70, 180)


class GpsSignalDot:
  """Top right corner dot: green = good fix, amber = usable, dark = do not trust."""

  def __init__(self):
    self._color: rl.Color = DARK
    self._target_text: str = ""
    self._font: rl.Font | None = None

  def update(self) -> None:
    self._color = self._color_for(self._accuracy())
    self._target_text = self._target_speed_text()

  @staticmethod
  def _target_speed_text() -> str:
    """The planner's target speed while engaged, or "" when there is nothing to show."""
    sm = ui_state.sm
    try:
      if not sm['selfdriveState'].enabled:
        return ""
      v_target = float(sm['longitudinalPlanSP'].vTarget)
    except (KeyError, AttributeError):
      return ""
    kph = v_target * CV.MS_TO_KPH
    if not 0. < kph < MAX_SHOWN_KPH:
      return ""
    return str(round(kph if ui_state.is_metric else kph * CV.KPH_TO_MPH))

  def _accuracy(self) -> float:
    """Horizontal accuracy in metres, or -1.0 when there is no usable fix."""
    sm = ui_state.sm
    gps_data, valid = GpsInfoElement.get_gps_data(sm)
    if not valid or gps_data is None:
      return -1.0
    if not getattr(gps_data, 'hasFix', True):
      # a valid packet without a fix still carries a stale accuracy; do not show it as usable
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
    badge = bool(self._target_text)
    radius = BADGE_RADIUS if badge else RADIUS
    margin_y = BADGE_MARGIN_Y if badge else MARGIN_Y
    center = rl.Vector2(int(rect.x + rect.width - MARGIN_X - radius), int(rect.y + margin_y + radius))
    # A dark ring under the dot keeps it readable over a bright road.
    rl.draw_circle_v(center, radius + 2, rl.Color(0, 0, 0, 120))
    rl.draw_circle_v(center, radius, self._color)
    if not badge:
      return

    # Speed limit sign: the GPS colour stays as the ring, the inside is white.
    rl.draw_circle_v(center, radius - BADGE_RING, rl.WHITE)

    if self._font is None:
      self._font = gui_app.font(FontWeight.BOLD)
    font_size = BADGE_FONT_SIZE
    size = measure_text_cached(self._font, self._target_text, font_size)
    # Three digits (100+) do not fit the white inside at full size; shrink just enough.
    max_width = 2 * (BADGE_RADIUS - BADGE_RING) - 8
    if size.x > max_width:
      font_size = int(font_size * max_width / size.x)
      size = measure_text_cached(self._font, self._target_text, font_size)
    pos = rl.Vector2(center.x - size.x / 2, center.y - size.y / 2)
    rl.draw_text_ex(self._font, self._target_text, pos, font_size, 0, rl.BLACK)
