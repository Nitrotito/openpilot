from openpilot.common.params import Params
from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.mici.layouts.settings.toggles import TogglesLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.network.network_layout import NetworkLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.device import DeviceLayoutMici, PairBigButton
from openpilot.selfdrive.ui.mici.layouts.settings.developer import DeveloperLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.software import SoftwareLayoutMici
from openpilot.selfdrive.ui.mici.layouts.settings.firehose import FirehoseLayout
from openpilot.selfdrive.ui.mici.layouts.settings.own_settings import OwnSettingsLayoutMici
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.lib.multilang import tr


class SettingsBigButton(BigButton):
  # Translated labels are longer than the English ones: "firehose" fits at 64, "adatgyujtes"
  # does not, and a single word that overruns the label box wraps mid-word and lands under
  # the icon. Step the size down until the widest word fits on one line.
  FONT_SIZES = (64, 56, 48, 42)

  def _get_label_font_size(self):
    budget = self._rect.width - self.LABEL_HORIZONTAL_PADDING * 2
    font = gui_app.font(FontWeight.BOLD)
    words = self.text.split() or [self.text]
    for size in self.FONT_SIZES:
      if all(measure_text_cached(font, word, size).x <= budget for word in words):
        return size
    return self.FONT_SIZES[-1]


class SettingsLayout(NavScroller):
  def __init__(self):
    super().__init__()
    self._params = Params()

    toggles_panel = TogglesLayoutMici()
    toggles_btn = SettingsBigButton(tr("toggles"), "", gui_app.texture("icons_mici/settings.png", 64, 64))
    toggles_btn.set_click_callback(lambda: gui_app.push_widget(toggles_panel))

    network_panel = NetworkLayoutMici()
    network_btn = SettingsBigButton(tr("network"), "", gui_app.texture("icons_mici/settings/network/wifi_strength_full.png", 76, 56))
    network_btn.set_click_callback(lambda: gui_app.push_widget(network_panel))

    device_panel = DeviceLayoutMici()
    device_btn = SettingsBigButton(tr("device"), "", gui_app.texture("icons_mici/settings/device_icon.png", 72, 58))
    device_btn.set_click_callback(lambda: gui_app.push_widget(device_panel))

    software_panel = SoftwareLayoutMici()
    software_btn = SettingsBigButton(tr("software"), "", gui_app.texture("icons_mici/settings/software.png", 64, 75))
    software_btn.set_click_callback(lambda: gui_app.push_widget(software_panel))

    developer_panel = DeveloperLayoutMici()
    developer_btn = SettingsBigButton(tr("developer"), "", gui_app.texture("icons_mici/settings/developer_icon.png", 64, 60))
    developer_btn.set_click_callback(lambda: gui_app.push_widget(developer_panel))

    firehose_panel = FirehoseLayout()
    firehose_btn = SettingsBigButton(tr("firehose"), "", gui_app.texture("icons_mici/settings/firehose.png", 52, 62))
    firehose_btn.set_click_callback(lambda: gui_app.push_widget(firehose_panel))

    own_panel = OwnSettingsLayoutMici()
    own_btn = SettingsBigButton(tr("my settings"), "", gui_app.texture("icons/tesla_mark.png", 60, 60))
    own_btn.set_click_callback(lambda: gui_app.push_widget(own_panel))

    self._scroller.add_widgets([
      toggles_btn,
      network_btn,
      device_btn,
      software_btn,
      PairBigButton(),
      #BigDialogButton(tr("manual"), "", "icons_mici/settings/manual_icon.png", "Check out the mici user\nmanual at comma.ai/setup"),
      firehose_btn,
      developer_btn,
      own_btn,
    ])

    self._font_medium = gui_app.font(FontWeight.MEDIUM)
