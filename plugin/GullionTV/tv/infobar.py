# -*- coding: utf-8 -*-
"""The channel banner shown over live TV.

Replaces the active skin's InfoBar layout, so the box's own banner behaviour is
kept: it shows on every channel change, hides after the usual timeout, and OK
toggles it. Takes effect when enigma2 next starts.
"""
import os
import sys

try:
	import xml.etree.cElementTree as ET
except ImportError:
	import xml.etree.ElementTree as ET

from .. import theme
from ..ui import scale

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_Y = 810
PANEL_H = 234

ICON_SLOTS = 6
# The signal gauge sits at the right end of the Next line; the icons pack up against it.
SIGNAL_X = 1640
ICONS_RIGHT = SIGNAL_X - 20


def _icons_skin():
	"""The programme's icons on the right of the Next line, packed against the right edge."""
	return "".join(
		'<widget source="session.Event_Now" render="GullionIcon" position="%d,981" size="40,40" alphatest="blend" zPosition="2">'
		'<convert type="GullionServiceInfo">Icon:%d</convert></widget>' % (ICONS_RIGHT - 40 - (slot - 1) * 52, slot)
		for slot in range(1, ICON_SLOTS + 1))


SKIN = """
<screen name="InfoBar" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="#ff000000">
	<eLabel position="60,%(panel_y)d" size="1800,%(panel_h)d" backgroundColor="%(panel)s" />

	<widget source="session.CurrentService" render="Picon" position="90,836" size="220,132" zPosition="2" alphatest="blend">
		<convert type="ServiceName">Reference</convert>
	</widget>

	<widget source="session.CurrentService" render="Label" position="340,832" size="110,62" font="Regular;48" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Number</convert>
	</widget>
	<widget source="session.CurrentService" render="Label" position="460,832" size="850,62" font="Regular;48" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Name</convert>
	</widget>
	<widget source="session.RecordState" render="FixedLabel" text="Recording" position="1330,843" size="180,40" font="Regular;26" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(red)s" zPosition="2">
		<convert type="ConditionalShowHide" />
	</widget>
	<widget source="global.CurrentTime" render="Label" position="1530,832" size="300,62" font="Regular;48" halign="right" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>

	<eLabel text="Now" position="340,906" size="110,50" font="Regular;32" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
	<widget source="session.Event_Now" render="Label" position="460,906" size="110,50" font="Regular;36" valign="center" foregroundColor="%(accent)s" transparent="1" zPosition="2">
		<convert type="EventTime">StartTime</convert>
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>
	<widget source="session.Event_Now" render="Label" position="580,904" size="940,54" font="Regular;40" valign="center" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="EventName">Name</convert>
	</widget>
	<widget source="session.Event_Now" render="Label" position="1530,906" size="300,50" font="Regular;30" halign="right" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Remaining</convert>
	</widget>
	<widget source="session.Event_Now" render="Progress" position="340,964" size="1490,6" foregroundColor="%(text)s" backgroundColor="%(divider)s" zPosition="2">
		<convert type="EventTime">Progress</convert>
	</widget>

	<eLabel text="Next" position="340,980" size="110,42" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
	<widget source="session.Event_Next" render="Label" position="460,980" size="110,42" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="EventTime">StartTime</convert>
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>
	<widget source="session.Event_Next" render="Label" position="580,980" size="720,42" font="Regular;30" valign="center" noWrap="1" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="EventName">Name</convert>
	</widget>
	%(icons)s
	<widget source="session.FrontendStatus" render="Progress" position="%(signal_x)d,998" size="110,8" foregroundColor="%(live)s" backgroundColor="%(divider)s" zPosition="2">
		<convert type="FrontendInfo">SNR</convert>
	</widget>
	<widget source="session.FrontendStatus" render="Label" position="%(signal_text_x)d,980" size="76,42" font="Regular;26" halign="right" valign="center" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="FrontendInfo">SNR</convert>
	</widget>
</screen>""" % {
	"panel_y": PANEL_Y, "panel_h": PANEL_H, "panel": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
	"divider": theme.DIVIDER, "accent": theme.ACCENT, "red": theme.KEY_RED,
	"light": theme.CARD_SELECTED, "card": theme.CARD, "on_light": theme.TEXT_ON_SELECTED,
	"icons": _icons_skin(), "signal_x": SIGNAL_X, "signal_text_x": SIGNAL_X + 114, "live": theme.LIVE,
}

# Typing a channel number on live TV. The widget names are the image's own:
# number on every image, servicename where it shows the channel's name.
NUMBER_ZAP = """
<screen name="NumberZap" position="1400,60" size="460,210" flags="wfNoBorder" backgroundColor="%(panel)s">
	%(frame)s
	<eLabel text="Channel" position="36,26" size="388,34" font="Regular;26" foregroundColor="%(muted)s" transparent="1" />
	<widget name="number" position="36,62" size="388,90" font="Regular;80" valign="center" foregroundColor="%(text)s" transparent="1" />
	<widget name="servicename" position="36,152" size="388,40" font="Regular;30" valign="center" foregroundColor="%(text)s" transparent="1" conditional="servicename" />
</screen>""" % {"panel": theme.BACKGROUND, "frame": theme.frame(460, 210), "text": theme.TEXT, "muted": theme.TEXT_MUTED}

# The volume pop-up: Volume is the bar; VolumeText, the number, isn't on every image.
VOLUME = """
<screen name="Volume" position="1400,60" size="460,120" flags="wfNoBorder" backgroundColor="%(panel)s" zPosition="99">
	%(frame)s
	<eLabel text="Volume" position="36,22" size="250,44" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" />
	<widget name="VolumeText" position="286,22" size="138,44" font="Regular;40" halign="right" valign="center" foregroundColor="%(text)s" transparent="1" conditional="VolumeText" />
	<widget name="Volume" position="36,80" size="388,10" foregroundColor="%(text)s" backgroundColor="%(divider)s" zPosition="1" />
</screen>""" % {"panel": theme.BACKGROUND, "frame": theme.frame(460, 120), "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER}


def register_converter():
	"""Make GullionServiceInfo and GullionIcon loadable by the skin engine like built-in ones."""
	import Components.Converter
	import Components.Renderer
	from . import converter, renderer
	sys.modules["Components.Converter.GullionServiceInfo"] = converter
	Components.Converter.GullionServiceInfo = converter
	sys.modules["Components.Renderer.GullionIcon"] = renderer
	Components.Renderer.GullionIcon = renderer


def install():
	"""Swap in the banner, number entry and volume layouts. Must run before InfoBar
	and the volume control are created (session start)."""
	import skin
	register_converter()
	# The table of loaded skin screens: domScreens on OpenATV 6.4, dom_screens on newer images.
	screens = getattr(skin, "domScreens", None)
	if screens is None:
		screens = skin.dom_screens
	for text in (SKIN, NUMBER_ZAP, VOLUME):
		element = ET.fromstring(scale.skin(text))
		name = element.get("name")
		existing = screens.get(name, screens.get("InfoBar"))
		# Entries are (element, skin directory); some older images keep the bare element.
		if existing is None or isinstance(existing, tuple):
			screens[name] = (element, PLUGIN_DIR)
		else:
			screens[name] = element
