# -*- coding: utf-8 -*-
"""Skin renderer for the banner's icons, registered as Components.Renderer.GullionIcon
by infobar.install(). Its source's text names an icon ("hd", "subtitles"); empty hides it."""
from enigma import ePixmap
from Components.Renderer.Renderer import Renderer
from Tools.LoadPixmap import LoadPixmap

from ..ui import icons


class GullionIcon(Renderer):
	GUI_WIDGET = ePixmap

	def changed(self, what):
		if self.instance is None:
			return
		name = self.source.text
		if name:
			self.instance.setPixmap(LoadPixmap(icons.icon_path(name), cached=True))
			self.instance.show()
		else:
			self.instance.hide()

	def onShow(self):
		self.changed(None)
