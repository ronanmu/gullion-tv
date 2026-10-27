# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Screens.Screen import Screen

from .. import settings  # noqa: F401  registers config.plugins.gulliontv
from .. import theme
from . import scale

PIN_LENGTH = 4
MAX_TRIES = 3


class PinEntry(Screen):
	"""Four-digit PIN prompt.

	With check(entered) -> bool, it closes with True once the PIN is right, or
	False after MAX_TRIES wrong ones. Without check, it closes with the digits.
	"""

	skin = """
	<screen name="GullionPinEntry" position="center,center" size="900,500" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame_900_500)s
		<widget name="heading" position="60,50" size="780,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		<widget name="detail" position="60,116" size="780,72" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		%(boxes)s
		<widget name="message" position="60,370" size="780,40" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		<eLabel text="BACK to cancel" position="60,430" size="780,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"card": theme.POPUP, "border": theme.POPUP_BORDER, "frame_900_500": theme.frame(900, 500), "text": theme.TEXT, "muted": theme.TEXT_MUTED,
		"boxes": "".join(
			'<widget name="digit%d" position="%d,226" size="100,110" font="Regular;110" halign="center" valign="center" '
			'foregroundColor="%s" backgroundColor="%s" />' % (i, 60 + i * 130, theme.TEXT, theme.BACKGROUND)
			for i in range(PIN_LENGTH)),
	}

	skin = scale.skin(skin)

	def __init__(self, session, heading, detail="Enter the 4-digit PIN with the number buttons", check=None):
		Screen.__init__(self, session)
		self.setTitle(heading)
		self.check_pin = check
		self["heading"] = Label(heading)
		self["detail"] = Label(detail)
		self.entered = ""
		self.tries = 0
		for i in range(PIN_LENGTH):
			self["digit%d" % i] = Label()
		self["message"] = Label()

		actions = {"cancel": lambda: self.close(False if check else None), "left": self.backspace}
		for n in range(10):
			actions[str(n)] = lambda n=n: self.digit(n)
		self["actions"] = ActionMap(["NumberActions", "OkCancelActions", "DirectionActions"], actions, -1)

	def digit(self, n):
		if len(self.entered) >= PIN_LENGTH:
			return
		self.entered += str(n)
		self.show_entered()
		if len(self.entered) == PIN_LENGTH:
			self.check()

	def backspace(self):
		self.entered = self.entered[:-1]
		self.show_entered()

	def show_entered(self):
		for i in range(PIN_LENGTH):
			self["digit%d" % i].setText("•" if i < len(self.entered) else "")

	def check(self):
		if self.check_pin is None:
			self.close(self.entered)
			return
		if self.check_pin(self.entered):
			self.close(True)
			return
		self.tries += 1
		if self.tries >= MAX_TRIES:
			self.close(False)
			return
		self.entered = ""
		self.show_entered()
		self["message"].setText("That PIN isn't right. Try again.")


class TechSupportPin(PinEntry):
	"""The PIN in front of the settings. Closes with True when it matches."""

	def __init__(self, session):
		PinEntry.__init__(self, session, "Settings are for Tech Support",
			check=lambda entered: int(entered) == int(config.plugins.gulliontv.pin.value))


def weak(entered):
	"""Too easy to guess: all one digit (0000) or a run (1234, 9876)."""
	return len(set(entered)) == 1 or entered in "0123456789" or entered in "9876543210"


def save_pin(entered):
	from Components.config import configfile
	config.plugins.gulliontv.pin.value = int(entered)
	config.plugins.gulliontv.pin_set.value = True
	config.plugins.gulliontv.pin.save()
	config.plugins.gulliontv.pin_set.save()
	configfile.save()


class PinChooser(object):
	"""First use of Settings: choose the Tech Support PIN, then type it again.
	Calls done(True) once it's saved, or done(False) if it's abandoned."""

	def __init__(self, session, done):
		self.session = session
		self.done = done

	def start(self, detail="This is the first time Settings has been opened. Choose a 4-digit PIN for Tech Support."):
		self.session.openWithCallback(self.chosen, PinEntry, "Choose a Tech Support PIN", detail)

	def chosen(self, entered=None):
		if not entered:
			return self.done(False)
		if weak(entered):
			return self.start("That PIN is too easy to guess. Choose another.")
		self.session.openWithCallback(lambda again: self.confirmed(entered, again), PinEntry,
			"Enter the PIN again", "To make sure it's right")

	def confirmed(self, entered, again=None):
		if not again:
			return self.done(False)
		if again != entered:
			return self.start("Those didn't match. Choose a PIN again.")
		save_pin(entered)
		self.done(True)
