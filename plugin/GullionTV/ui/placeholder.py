# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from .. import theme
from . import scale


class ComingSoon(Screen):
	"""Stand-in for the guide, recordings and church screens while they're built."""

	skin = """
	<screen name="GullionComingSoon" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<widget name="heading" position="90,62" size="1740,70" font="Regular;56" foregroundColor="%(text)s" transparent="1" />
		<eLabel position="90,150" size="1740,1" backgroundColor="%(divider)s" />
		<eLabel text="This part isn't ready yet." position="90,220" size="1740,50" font="Regular;36" foregroundColor="%(muted)s" transparent="1" />
		<eLabel text="BACK to return home" position="90,1010" size="1000,40" font="Regular;26" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER}

	skin = scale.skin(skin)

	def __init__(self, session, title):
		Screen.__init__(self, session)
		self.setTitle(title)
		self["heading"] = Label(title)
		self["actions"] = ActionMap(["OkCancelActions", "MenuActions"], {
			"cancel": self.close,
			"ok": self.close,
			"menu": self.close,
		}, -1)
