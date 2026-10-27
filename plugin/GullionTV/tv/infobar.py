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
PANEL_Y = 760

SKIN = """
<screen name="InfoBar" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="#ff000000">
	<eLabel position="60,%(panel_y)d" size="1800,284" backgroundColor="%(panel)s" />

	<widget source="session.CurrentService" render="Picon" position="90,790" size="220,132" zPosition="2" alphatest="blend">
		<convert type="ServiceName">Reference</convert>
	</widget>
	<eLabel text="Signal" position="90,938" size="120,32" font="Regular;24" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
	<widget source="session.FrontendStatus" render="Label" position="190,938" size="120,32" font="Regular;24" halign="right" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="FrontendInfo">SNR</convert>
	</widget>
	<widget source="session.FrontendStatus" render="Progress" position="90,978" size="220,8" foregroundColor="%(live)s" backgroundColor="%(divider)s" zPosition="2">
		<convert type="FrontendInfo">SNR</convert>
	</widget>

	<widget source="session.CurrentService" render="Label" position="340,782" size="110,62" font="Regular;48" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Number</convert>
	</widget>
	<widget source="session.CurrentService" render="Label" position="460,782" size="1050,62" font="Regular;48" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Name</convert>
	</widget>
	<widget source="global.CurrentTime" render="Label" position="1530,782" size="300,62" font="Regular;48" halign="right" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>

	<widget source="session.CurrentService" render="FixedLabel" text="HD" position="340,856" size="76,40" font="Regular;26" halign="center" valign="center" foregroundColor="%(on_light)s" backgroundColor="%(light)s" zPosition="2">
		<convert type="GullionServiceInfo">IsHD</convert>
		<convert type="ConditionalShowHide" />
	</widget>
	<widget source="session.CurrentService" render="FixedLabel" text="SD" position="340,856" size="76,40" font="Regular;26" halign="center" valign="center" foregroundColor="%(muted)s" backgroundColor="%(card)s" zPosition="2">
		<convert type="GullionServiceInfo">IsHD</convert>
		<convert type="ConditionalShowHide">Invert</convert>
	</widget>
	<widget source="session.CurrentService" render="Label" position="460,856" size="800,40" font="Regular;28" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Delivery</convert>
	</widget>
	<widget source="session.RecordState" render="FixedLabel" text="Recording" position="1650,856" size="180,40" font="Regular;26" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(red)s" zPosition="2">
		<convert type="ConditionalShowHide" />
	</widget>

	<eLabel text="Now" position="340,914" size="110,50" font="Regular;32" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
	<widget source="session.Event_Now" render="Label" position="460,914" size="110,50" font="Regular;36" valign="center" foregroundColor="%(accent)s" transparent="1" zPosition="2">
		<convert type="EventTime">StartTime</convert>
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>
	<widget source="session.Event_Now" render="Label" position="580,912" size="940,54" font="Regular;40" valign="center" foregroundColor="%(text)s" transparent="1" zPosition="2">
		<convert type="EventName">Name</convert>
	</widget>
	<widget source="session.Event_Now" render="Label" position="1530,914" size="300,50" font="Regular;30" halign="right" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="GullionServiceInfo">Remaining</convert>
	</widget>
	<widget source="session.Event_Now" render="Progress" position="340,972" size="1490,6" foregroundColor="%(text)s" backgroundColor="%(divider)s" zPosition="2">
		<convert type="EventTime">Progress</convert>
	</widget>

	<eLabel text="Next" position="340,988" size="110,42" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
	<widget source="session.Event_Next" render="Label" position="460,988" size="110,42" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="EventTime">StartTime</convert>
		<convert type="ClockToText">Format:%%H:%%M</convert>
	</widget>
	<widget source="session.Event_Next" render="Label" position="580,988" size="1250,42" font="Regular;30" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="2">
		<convert type="EventName">Name</convert>
	</widget>
</screen>""" % {
	"panel_y": PANEL_Y, "panel": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
	"divider": theme.DIVIDER, "live": theme.LIVE, "accent": theme.ACCENT, "red": theme.KEY_RED,
	"light": theme.CARD_SELECTED, "card": theme.CARD, "on_light": theme.TEXT_ON_SELECTED,
}


def register_converter():
	"""Make GullionServiceInfo loadable by the skin engine like a built-in converter."""
	import Components.Converter
	from . import converter
	sys.modules["Components.Converter.GullionServiceInfo"] = converter
	Components.Converter.GullionServiceInfo = converter


def install():
	"""Swap in the banner layout. Must run before InfoBar is created (session start)."""
	import skin
	register_converter()
	element = ET.fromstring(scale.skin(SKIN))
	# The table of loaded skin screens: domScreens on OpenATV 6.4, dom_screens on newer images.
	screens = getattr(skin, "domScreens", None)
	if screens is None:
		screens = skin.dom_screens
	existing = screens.get("InfoBar")
	# Entries are (element, skin directory); some older images keep the bare element.
	if existing is None or isinstance(existing, tuple):
		screens["InfoBar"] = (element, PLUGIN_DIR)
	else:
		screens["InfoBar"] = element
