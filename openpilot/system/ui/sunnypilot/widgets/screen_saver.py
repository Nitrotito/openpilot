"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import os
import time

import pyray as rl

from openpilot.common.hardware import HARDWARE
from openpilot.common.params import Params
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

# Device-local, not in git: survives software updates, wiped only by a reflash.
PLATE_FILE = "/data/license_plate"


class ScreenSaverSP(Widget):
  def __init__(self, params: Params | None = None):
    super().__init__()
    self.set_rect(rl.Rectangle(0, 0, gui_app.width, gui_app.height))
    self._params = params or Params()
    self._is_mici = HARDWARE.get_device_type() == 'mici' or (HARDWARE.get_device_type() == "pc" and os.getenv("BIG") != "1")

    self.x = 0.0
    self.y = 100.0
    self.vx = 120.0 if self._is_mici else 300.0
    self.vy = 70.0 if self._is_mici else 200.0
    self.color = rl.WHITE

    # sunnypilot wordmark -> Tesla mark (white, no hue cycling)
    self.logo_asset = "icons/tesla_mark.png"
    # NOTE: gui_app.texture() only resizes when BOTH width and height are given,
    # so pass both. The mark is 401x400, i.e. square for practical purposes.
    self.logo_render_height = 120 if self._is_mici else 400
    self.logo_render_width = round(self.logo_render_height * 401 / 400)

    # license plate under the mark, bounces along with it.
    # NOTE: kept OUT of the source tree on purpose -- this repo is a public fork,
    # and a plate baked into the code stays readable in the git history forever.
    # The value lives in the device's own storage, which survives updates.
    self.plate_text = self._read_plate()
    self.plate_font_size = 34 if self._is_mici else 80
    self.plate_gap = 10 if self._is_mici else 28
    # fonts are only loaded once the window exists, so resolve them lazily
    self._plate_font = None
    self._plate_size = rl.Vector2(0, 0)

    self._start_time = None
    self._dismiss = False
    self._screensaver_timeout = 300
    self._hit_last_frame = False

  @staticmethod
  def _read_plate() -> str:
    """Read the plate from the device, or return '' if it was never set.

    Empty is a valid state: the screensaver then shows only the mark.
    """
    try:
      with open(PLATE_FILE) as f:
        return f.read().strip()
    except OSError:
      return ""

  @property
  def is_active(self) -> bool:
    return self._start_time is not None and not self._dismiss

  @property
  def was_dismissed(self) -> bool:
    return self._dismiss

  def initialize(self):
    self._screensaver_timeout = self._params.get("ScreenSaverTimeout", return_default=True)
    if self._start_time is None:
      self._start_time = time.monotonic()
    self._dismiss = False

  def hide_event(self):
    super().hide_event()
    self._dismiss = False
    self._start_time = None

  def _handle_mouse_release(self, mouse_pos):
    self._dismiss = True
    self._start_time = None
    gui_app.pop_widget()
    return super()._handle_mouse_release(mouse_pos)

  def _update_state(self):
    super()._update_state()

    self._logo = gui_app.texture(self.logo_asset, self.logo_render_width, self.logo_render_height)
    self.logo_width = self._logo.width
    self.logo_height = self._logo.height

    if self._plate_font is None:
      self._plate_font = gui_app.font(FontWeight.BOLD)
      if self.plate_text:
        self._plate_size = measure_text_cached(self._plate_font, self.plate_text, self.plate_font_size)

    # logo and plate travel together as one block
    self.block_width = max(self.logo_width, self._plate_size.x)
    self.block_height = self.logo_height + (self.plate_gap + self._plate_size.y if self.plate_text else 0)

    if self._start_time and time.monotonic() - self._start_time > self._screensaver_timeout:
      self._dismiss = True
      self._start_time = None

    dt = rl.get_frame_time()

    self.x += self.vx * dt
    self.y += self.vy * dt

    hit_x = hit_y = False
    if self.x + self.block_width > self.rect.width:
      self.vx *= -1
      self.x = self.rect.width - self.block_width
      hit_x = True
    elif self.x < 0:
      self.vx *= -1
      self.x = 0
      hit_x = True

    if self.y + self.block_height > self.rect.height:
      self.vy *= -1
      self.y = self.rect.height - self.block_height
      hit_y = True
    elif self.y < 0:
      self.vy *= -1
      self.y = 0
      hit_y = True

    self._hit_last_frame = hit_x or hit_y

  def _render(self, rect: rl.Rectangle):
    self.set_rect(rect)
    rl.clear_background(rl.BLACK)
    logo_x = self.x + (self.block_width - self.logo_width) / 2
    rl.draw_texture(self._logo, int(logo_x), int(self.y), self.color)

    if self.plate_text:
      plate_pos = rl.Vector2(self.x + (self.block_width - self._plate_size.x) / 2,
                             self.y + self.logo_height + self.plate_gap)
      rl.draw_text_ex(self._plate_font, self.plate_text, plate_pos, self.plate_font_size, 0, self.color)
    return -1
