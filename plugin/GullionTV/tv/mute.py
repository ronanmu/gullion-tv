# -*- coding: utf-8 -*-
"""Persistent Gullion mute alert, shown by Enigma2's global volume control."""
import os
import xml.etree.ElementTree as ET

from .. import theme
from ..ui import icons, scale

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MUTE = """
<screen name="Mute" position="60,60" size="280,112" flags="wfNoBorder" backgroundColor="%(panel)s" zPosition="99">
	%(frame)s
	<ePixmap position="24,16" size="80,80" pixmap="%(icon)s" alphatest="blend" zPosition="1" />
	<eLabel text="Muted" position="120,24" size="130,64" font="Regular;34" valign="center" foregroundColor="%(text)s" transparent="1" zPosition="1" />
</screen>""" % {
	"panel": theme.BACKGROUND, "frame": theme.frame(280, 112), "text": theme.TEXT,
	"icon": icons.icon_path("volume_mute", 80),
}


def install():
	"""Replace the stock global Mute skin before VolumeControl creates its dialog."""
	import skin
	screens = getattr(skin, "domScreens", None)
	if screens is None:
		screens = skin.dom_screens
	element = ET.fromstring(scale.skin(MUTE))
	existing = screens.get("Mute", screens.get("InfoBar"))
	if existing is None or isinstance(existing, tuple):
		screens["Mute"] = (element, PLUGIN_DIR)
	else:
		screens["Mute"] = element
