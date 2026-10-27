# -*- coding: utf-8 -*-
"""Themed pop-ups: a short list of choices, and a programme's full details."""
from enigma import gRGB
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from .. import theme

MAX_OPTIONS = 3
_POPUP = {"card": theme.POPUP, "border": theme.POPUP_BORDER, "text": theme.TEXT, "muted": theme.TEXT_MUTED}


class GullionChoice(Screen):
	"""Up to three options. Closes with the chosen option's key, or None on BACK."""

	skin = """
	<screen name="GullionChoice" position="center,center" size="900,520" flags="wfNoBorder" backgroundColor="%(border)s">
		<eLabel position="3,3" size="894,514" backgroundColor="%(card)s" />
		<widget name="heading" position="60,50" size="780,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		<widget name="detail" position="60,112" size="780,80" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		%(options)s
		<eLabel text="OK to choose   ·   BACK to cancel" position="60,456" size="780,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % dict(_POPUP, options="".join(
		'<widget name="option%d_bg" position="60,%d" size="780,64" backgroundColor="%s" zPosition="1" />'
		'<widget name="option%d" position="88,%d" size="740,64" font="Regular;32" valign="center" '
		'foregroundColor="%s" transparent="1" zPosition="2" />' % (i, 210 + i * 78, theme.POPUP, i, 210 + i * 78, theme.TEXT)
		for i in range(MAX_OPTIONS)))

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
	<screen name="GullionEventDetails" position="center,center" size="1300,700" flags="wfNoBorder" backgroundColor="%(border)s">
		<eLabel position="3,3" size="1294,694" backgroundColor="%(card)s" />
		<widget name="heading" position="60,50" size="1180,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget name="when" position="60,120" size="1180,44" font="Regular;30" foregroundColor="%(accent)s" transparent="1" />
		<widget name="description" position="60,190" size="1180,420" font="Regular;30" foregroundColor="%(text)s" transparent="1" />
		<eLabel text="BACK to close" position="60,636" size="1180,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % dict(_POPUP, accent=theme.ACCENT)

	def __init__(self, session, heading, when, description):
		Screen.__init__(self, session)
		self.setTitle(heading)
		self["heading"] = Label(heading)
		self["when"] = Label(when)
		self["description"] = Label(description or "No more details for this programme.")
		self["actions"] = ActionMap(["OkCancelActions", "EPGSelectActions"], {
			"ok": self.close,
			"cancel": self.close,
			"info": self.close,
		}, -1)
