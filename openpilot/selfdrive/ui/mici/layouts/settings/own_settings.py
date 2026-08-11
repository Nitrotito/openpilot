"""Owner settings: the two knobs that are backed by a plain file instead of a Params key.

Params keys are registered in params_keys.h, which is compiled into params_pyx.so, so
adding one would need a full rebuild on the device for a single number. Both consumers
already read a file -- the longitudinal planner for the set speed offset, the camera view
for the preview gamma -- so the file stays the source of truth and this panel just writes
it. Both are re-read while driving, no restart needed.
"""
import os

from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.selfdrive.ui.mici.widgets.button import BigMultiToggle, GreyBigButton
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

    self._scroller.add_widgets([
      speed_offset,
      GreyBigButton("", tr("The dash keeps showing the speed you set. Only the speed the car actually holds moves.")),
      preview_brightness,
      GreyBigButton("", tr("Only the camera image on the screen changes, never what the car sees.")),
    ])
