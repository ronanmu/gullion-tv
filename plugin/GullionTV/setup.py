from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen

from . import settings  # noqa: F401  registers config.plugins.gulliontv
from .ui.pin import weak
from .ui.popups import GullionChoice


class GullionTVSetup(Screen, ConfigListScreen):
	"""Tech Support settings, reached from the stock Plugins menu."""

	skin = """
	<screen name="GullionTVSetup" position="center,center" size="1200,500" title="Gullion TV">
		<widget name="config" position="30,30" size="1140,360" itemHeight="50" font="Regular;30" scrollbarMode="showOnDemand" />
		<ePixmap pixmap="skin_default/buttons/red.png" position="30,430" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="200,430" size="140,40" alphatest="on" />
		<widget source="key_red" render="Label" position="30,430" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
		<widget source="key_green" render="Label" position="200,430" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="1030,430" size="140,40" alphatest="on" />
		<widget source="key_blue" render="Label" position="1030,430" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("Gullion TV")
		self["key_red"] = StaticText("Cancel")
		self["key_green"] = StaticText("Save")
		self["key_blue"] = StaticText("Plex")

		entries = [
			getConfigListEntry("Open Gullion TV with MENU", config.plugins.gulliontv.enabled),
			getConfigListEntry("Large channel banner (after restart)", config.plugins.gulliontv.infobar),
			getConfigListEntry("Tech Support PIN", config.plugins.gulliontv.pin),
		]
		ConfigListScreen.__init__(self, entries, session=session)

		self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
			"save": self.save,
			"ok": self.save,
			"cancel": self.keyCancel,
			"red": self.keyCancel,
			"green": self.save,
			"blue": self.open_plex,
		}, -2)

	def save(self):
		pin = config.plugins.gulliontv.pin
		if pin.isChanged():
			if weak("%04d" % int(pin.value)):
				self.session.open(GullionChoice, "That PIN is too easy to guess", [("OK", None)], "Choose one that isn't 0000, 1234 or similar.")
				return
			config.plugins.gulliontv.pin_set.value = True
			config.plugins.gulliontv.pin_set.save()
		self.keySave()

	def open_plex(self):
		from .plex.setup import PlexSetup
		self.session.open(PlexSetup)
