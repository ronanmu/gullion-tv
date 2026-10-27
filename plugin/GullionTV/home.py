# -*- coding: utf-8 -*-
import time

from enigma import eTimer, gRGB
from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from ServiceReference import ServiceReference
from Screens.Screen import Screen

from . import theme
from .plex import client as plex
from .tv.guide import Guide
from .tv.serviceinfo import remaining
from .ui.pin import PinChooser, TechSupportPin
from .ui.placeholder import ComingSoon
from .watchagain import WatchAgain
from .webcams.screens import WebcamList

# (title, subtitle, remote colour key, colour) in on-screen order. The colours run
# left to right in the order they sit on the remote.
CARDS = [
	("Watch TV", "Your channels", "red", theme.KEY_RED),
	("TV guide", "Tonight and this week", "green", theme.KEY_GREEN),
	("Watch again", "Recorded TV", "yellow", theme.KEY_YELLOW),
	("Webcams", "Live cameras", "blue", theme.KEY_BLUE),
]
SETTINGS = len(CARDS)

CARD_Y = 730
CARD_W = 412
CARD_H = 250
CARD_GAP = 30
LEFT = 90


def _card_skin(index, colour):
	x = LEFT + index * (CARD_W + CARD_GAP)
	return """
		<widget name="card%(i)d" position="%(x)d,%(y)d" size="%(w)d,%(h)d" backgroundColor="%(card)s" zPosition="1" />
		<eLabel position="%(dx)d,%(dy)d" size="18,18" backgroundColor="%(dot)s" zPosition="2" />
		<widget name="card%(i)d_title" position="%(tx)d,%(ty)d" size="%(tw)d,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" zPosition="2" />
		<widget name="card%(i)d_sub" position="%(tx)d,%(sy)d" size="%(tw)d,40" font="Regular;28" foregroundColor="%(muted)s" transparent="1" zPosition="2" />""" % {
		"i": index, "x": x, "y": CARD_Y, "w": CARD_W, "h": CARD_H,
		"dx": x + CARD_W - 50, "dy": CARD_Y + 32,
		"tx": x + 32, "ty": CARD_Y + 140, "sy": CARD_Y + 196, "tw": CARD_W - 64,
		"card": theme.CARD, "dot": colour, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
	}


class GullionHome(Screen):
	skin = """
	<screen name="GullionHome" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<widget name="date" position="90,62" size="900,44" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1430,44" size="400,70" font="Regular;56" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%H:%%M</convert>
		</widget>
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />

		<widget source="session.VideoPicture" render="Pig" position="90,170" size="880,495" zPosition="1" backgroundColor="#ff000000" />
		<widget name="live_tag" position="110,605" size="500,44" font="Regular;26" foregroundColor="%(text)s" backgroundColor="%(bg)s" zPosition="3" />

		<widget name="now_label" position="1030,230" size="800,40" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		<widget name="event_name" position="1030,276" size="800,140" font="Regular;54" foregroundColor="%(text)s" transparent="1" />
		<widget name="event_time" position="1030,430" size="800,44" font="Regular;32" foregroundColor="%(text)s" transparent="1" />
		<widget name="progress" position="1030,492" size="800,6" foregroundColor="%(text)s" backgroundColor="%(divider)s" borderWidth="0" />
		<widget name="event_next" position="1030,530" size="800,44" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		%(cards)s
		<widget name="hint" position="90,1010" size="1000,40" font="Regular;26" foregroundColor="%(muted)s" transparent="1" />
		<widget name="settings" position="1630,1000" size="200,52" font="Regular;28" halign="center" valign="center" foregroundColor="%(muted)s" backgroundColor="%(bg)s" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER,
		"cards": "".join(_card_skin(i, card[3]) for i, card in enumerate(CARDS)),
	}

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("Home")

		self["date"] = Label()
		self["live_tag"] = Label()
		self["now_label"] = Label()
		self["event_name"] = Label()
		self["event_time"] = Label()
		self["event_next"] = Label()
		self["progress"] = ProgressBar()
		self["hint"] = Label("OK to open   ·   BACK to return to TV")
		self["settings"] = Label("Settings")
		for i, card in enumerate(CARDS):
			self["card%d" % i] = Label()
			self["card%d_title" % i] = Label(card[0])
			self["card%d_sub" % i] = Label(card[1])
		if plex.is_configured(plex.load_settings()):
			self["card2_sub"].setText("Recorded TV & Plex")

		self.selected = 0
		self.last_card = 0

		actions = {
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"ok": self.ok,
			"cancel": self.close,
			"menu": self.close,
		}
		for index, card in enumerate(CARDS):
			actions[card[2]] = lambda index=index: self.open_item(index)
		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ColorActions", "MenuActions"], actions, -1)

		self.refresh_timer = eTimer()
		self.refresh_timer.callback.append(self.refresh)
		self.onLayoutFinish.append(self.paint_selection)
		self.onShow.append(self.start_refresh)
		self.onHide.append(self.refresh_timer.stop)

	# Navigation

	def left(self):
		if self.selected < SETTINGS and self.selected > 0:
			self.move_to(self.selected - 1)

	def right(self):
		if self.selected < SETTINGS - 1:
			self.move_to(self.selected + 1)

	def down(self):
		if self.selected < SETTINGS:
			self.last_card = self.selected
			self.move_to(SETTINGS)

	def up(self):
		if self.selected == SETTINGS:
			self.move_to(self.last_card)

	def move_to(self, index):
		self.selected = index
		self.paint_selection()

	def ok(self):
		self.open_item(self.selected)

	def open_item(self, index):
		if index == 0:
			self.close("tv")
		elif index == 1:
			self.session.openWithCallback(self.guide_closed, Guide)
		elif index == 2:
			self.session.open(WatchAgain)
		elif index == 3:
			self.session.open(WebcamList)
		elif index == SETTINGS:
			if config.plugins.gulliontv.pin_set.value:
				self.session.openWithCallback(self.pin_entered, TechSupportPin)
			else:
				PinChooser(self.session, self.pin_entered).start()
		else:
			self.session.open(ComingSoon, CARDS[index][0])

	def guide_closed(self, result=None):
		# The guide has already switched channel; go straight to full-screen TV.
		if result == "watch":
			self.close()

	def pin_entered(self, ok=False):
		if ok:
			self.close("techsupport")

	# Drawing

	def paint_selection(self):
		for i in range(len(CARDS)):
			chosen = i == self.selected
			self._colour("card%d" % i, background=theme.CARD_SELECTED if chosen else theme.CARD)
			self._colour("card%d_title" % i, foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT)
			self._colour("card%d_sub" % i, foreground=theme.TEXT_ON_SELECTED_MUTED if chosen else theme.TEXT_MUTED)
		chosen = self.selected == SETTINGS
		self._colour("settings",
			background=theme.CARD_SELECTED if chosen else theme.BACKGROUND,
			foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT_MUTED)

	def _colour(self, name, background=None, foreground=None):
		instance = self[name].instance
		if instance is None:
			return
		if background is not None:
			instance.setBackgroundColor(gRGB(theme.rgb(background)))
		if foreground is not None:
			instance.setForegroundColor(gRGB(theme.rgb(foreground)))
		instance.invalidate()

	# Now and next

	def start_refresh(self):
		self.refresh()
		self.refresh_timer.start(15000, False)

	def refresh(self):
		now = time.time()
		local = time.localtime(now)
		self["date"].setText("%s %d %s" % (time.strftime("%A", local), local.tm_mday, time.strftime("%B", local)))

		channel = self.channel_name()
		self["live_tag"].setText("  Live · %s" % channel if channel else "")
		self["now_label"].setText("On now · %s" % channel if channel else "On now")

		info = self.service_info()
		event = info and info.getEvent(0)
		if event:
			begin = event.getBeginTime()
			end = begin + event.getDuration()
			self["event_name"].setText(event.getEventName())
			self["event_time"].setText("%s – %s   ·   %s" % (_clock(begin), _clock(end), remaining(end - now)))
			duration = max(1, end - begin)
			self["progress"].setValue(int(min(100, max(0, (now - begin) * 100 / duration))))
		else:
			self["event_name"].setText("No programme details")
			self["event_time"].setText("")
			self["progress"].setValue(0)

		upcoming = info and info.getEvent(1)
		if upcoming:
			self["event_next"].setText("Next · %s  %s" % (_clock(upcoming.getBeginTime()), upcoming.getEventName()))
		else:
			self["event_next"].setText("")

	def service_info(self):
		service = self.session.nav.getCurrentService()
		return service and service.info()

	def channel_name(self):
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		if ref is None:
			return ""
		# Strip the DVB emphasis control characters some channels use.
		return ServiceReference(ref).getServiceName().replace("\xc2\x86", "").replace("\xc2\x87", "")


def _clock(timestamp):
	return time.strftime("%H:%M", time.localtime(timestamp))

