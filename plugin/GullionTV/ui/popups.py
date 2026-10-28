# -*- coding: utf-8 -*-
"""Themed pop-ups: a short list of choices, and a programme's full details."""
from enigma import gRGB
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from Screens.Screen import Screen

from .. import theme
from . import icons, scale
from ..tv import serviceinfo

MAX_OPTIONS = 3
_POPUP = {"card": theme.POPUP, "border": theme.POPUP_BORDER, "frame_900_520": theme.frame(900, 520), "frame_1300_700": theme.frame(1300, 700), "text": theme.TEXT, "muted": theme.TEXT_MUTED}


class GullionChoice(Screen):
	"""Up to three options. Closes with the chosen option's key, or None on BACK."""

	skin = """
	<screen name="GullionChoice" position="center,center" size="900,520" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame_900_520)s
		<widget name="heading" position="60,50" size="780,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		<widget name="detail" position="60,112" size="780,80" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		%(options)s
		<eLabel text="OK to choose   ·   BACK to cancel" position="60,456" size="780,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % dict(_POPUP, options="".join(
		'<widget name="option%d_bg" position="60,%d" size="780,64" backgroundColor="%s" zPosition="1" />'
		'<widget name="option%d" position="88,%d" size="740,64" font="Regular;32" valign="center" '
		'foregroundColor="%s" transparent="1" zPosition="2" />' % (i, 210 + i * 78, theme.POPUP, i, 210 + i * 78, theme.TEXT)
		for i in range(MAX_OPTIONS)))

	skin = scale.skin(skin)

	def __init__(self, session, heading, options, detail=""):
		"""options: [(label, key)]"""
		Screen.__init__(self, session)
		self.setTitle(heading)
		self.options = options[:MAX_OPTIONS]
		self.selected = 0
		self["heading"] = Label(heading)
		self["detail"] = Label(detail)
		for i in range(MAX_OPTIONS):
			self["option%d_bg" % i] = Label()
			self["option%d" % i] = Label(self.options[i][0] if i < len(self.options) else "")
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
			"ok": lambda: self.close(self.options[self.selected][1]),
			"cancel": lambda: self.close(None),
			"up": lambda: self.move(-1),
			"down": lambda: self.move(1),
		}, -1)
		self.onLayoutFinish.append(self.paint)

	def move(self, step):
		self.selected = max(0, min(len(self.options) - 1, self.selected + step))
		self.paint()

	def paint(self):
		for i in range(MAX_OPTIONS):
			chosen = i == self.selected and i < len(self.options)
			background = self["option%d_bg" % i].instance
			text = self["option%d" % i].instance
			if background is None or text is None:
				continue
			background.setBackgroundColor(gRGB(theme.rgb(theme.CARD_SELECTED if chosen else theme.POPUP)))
			background.invalidate()
			text.setForegroundColor(gRGB(theme.rgb(theme.TEXT_ON_SELECTED if chosen else theme.TEXT)))
			text.invalidate()


class EventDetails(Screen):
	"""Full programme description, opened with INFO in the guide."""

	skin = """
	<screen name="GullionEventDetails" position="center,center" size="1300,700" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame_1300_700)s
		<widget name="heading" position="60,50" size="1180,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget name="when" position="60,120" size="840,44" font="Regular;30" foregroundColor="%(accent)s" transparent="1" />
		%(icons)s
		<widget name="description" position="60,190" size="1180,420" font="Regular;30" foregroundColor="%(text)s" transparent="1" />
		<eLabel text="BACK to close" position="60,636" size="1180,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % dict(_POPUP, accent=theme.ACCENT, icons="".join(
		'<widget name="icon%d" position="%d,132" size="40,40" alphatest="blend" />'
		% (i, 1200 - i * 52) for i in range(6)))

	skin = scale.skin(skin)

	def __init__(self, session, heading, when, description, channel_ref=""):
		Screen.__init__(self, session)
		self.setTitle(heading)
		self["heading"] = Label(heading)
		self["when"] = Label(when)
		self["description"] = Label(serviceinfo.split_codes(description)[0] or "No more details for this programme.")
		# This is the selected channel, which may differ from the live preview.
		self.icon_names = serviceinfo.icon_row(channel_ref, -1, description)
		for i in range(6):
			self["icon%d" % i] = Pixmap()
		self.onLayoutFinish.append(self.draw_icons)
		self["actions"] = ActionMap(["OkCancelActions", "EPGSelectActions"], {
			"ok": self.close,
			"cancel": self.close,
			"info": self.close,
		}, -1)

	def draw_icons(self):
		for i in range(6):
			widget = self["icon%d" % i]
			if i < len(self.icon_names) and widget.instance is not None:
				widget.instance.setPixmap(LoadPixmap(icons.icon_path(self.icon_names[-1 - i]), cached=True))
				widget.show()
			else:
				widget.hide()
