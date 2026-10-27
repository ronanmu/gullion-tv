# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen

from . import settings  # noqa: F401  registers config.plugins.gulliontv
from .ui.pin import weak
from .ui.popups import GullionChoice
from .weather import forecast


class GullionTVSetup(Screen, ConfigListScreen):
	"""Tech Support settings, reached from the stock Plugins menu."""

	skin = """
	<screen name="GullionTVSetup" position="center,center" size="1200,560" title="Gullion TV">
		<widget name="config" position="30,30" size="1140,300" itemHeight="50" font="Regular;30" scrollbarMode="showOnDemand" />
		<widget source="hint" render="Label" position="30,340" size="1140,70" font="Regular;22" transparent="1" />
		<widget source="credit" render="Label" position="30,420" size="1140,60" font="Regular;22" transparent="1" />
		<ePixmap pixmap="skin_default/buttons/red.png" position="30,490" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="200,490" size="140,40" alphatest="on" />
		<widget source="key_red" render="Label" position="30,490" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
		<widget source="key_green" render="Label" position="200,490" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="1030,490" size="140,40" alphatest="on" />
		<widget source="key_blue" render="Label" position="1030,490" size="140,40" zPosition="1" font="Regular;22" halign="center" valign="center" transparent="1" />
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("Gullion TV")
		self["key_red"] = StaticText("Cancel")
		self["key_green"] = StaticText("Save")
		self["key_blue"] = StaticText("Plex")
		self["hint"] = StaticText("Weather location: the house's latitude and longitude, for example 54.0830, -6.4500. "
			"In Google Maps, right-click the house to copy them. Leave it empty for no weather on Home.")
		self["credit"] = StaticText("Weather forecasts from Met Éireann open data (CC BY 4.0), with Open-Meteo "
			"(CC BY 4.0) as a backup when Met Éireann can't be reached. Weather icons by Yr (MIT).")

		entries = [
			getConfigListEntry("Open Gullion TV with MENU", config.plugins.gulliontv.enabled),
			getConfigListEntry("Large channel banner (after restart)", config.plugins.gulliontv.infobar),
			getConfigListEntry("Tech Support PIN", config.plugins.gulliontv.pin),
			getConfigListEntry("Weather location (latitude, longitude)", config.plugins.gulliontv.weather_location),
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
		location = config.plugins.gulliontv.weather_location.value.strip()
		if location and forecast.parse_location(location) is None:
			self.session.open(GullionChoice, "That weather location isn't right", [("OK", None)],
				"Enter the latitude, then the longitude, separated by a comma: for example 54.0830, -6.4500.")
			return
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
