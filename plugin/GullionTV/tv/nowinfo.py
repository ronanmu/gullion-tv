# -*- coding: utf-8 -*-
"""INFO on live TV: what's on now on this channel, and the next few programmes."""
import time

from enigma import eTimer, iServiceInformation
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from . import epg, picon, serviceinfo
from .. import theme
from ..ui import icons, scale, tiles

COMING_UP = 5
ROW_H = 56
ICON_SLOTS = 6
SIGNAL_LINES = 7
SIGNAL_Y, SIGNAL_H = 256, 30
# The programme's icons, right-aligned on the "On now" line.
ICON_RIGHT, LINE_Y = 1140, 28


def _icons_skin():
	return "".join('<widget name="icon%d" position="%d,%d" size="40,40" alphatest="blend" zPosition="2" />'
		% (slot, ICON_RIGHT - 40 - slot * 52, LINE_Y) for slot in range(ICON_SLOTS))


def _signal_skin():
	"""The tuner's details under the picon: a label on the left, its value on the right."""
	return "".join(
		'<widget name="signal%d_label" position="30,%d" size="120,%d" font="Regular;22" valign="center" foregroundColor="%s" transparent="1" />'
		'<widget name="signal%d" position="150,%d" size="100,%d" font="Regular;22" halign="right" valign="center" foregroundColor="%s" transparent="1" />'
		% (i, SIGNAL_Y + i * SIGNAL_H, SIGNAL_H, theme.TEXT_MUTED, i, SIGNAL_Y + i * SIGNAL_H, SIGNAL_H, theme.TEXT)
		for i in range(SIGNAL_LINES))


def _clock(moment):
	return time.strftime("%H:%M", time.localtime(moment))


class ChannelInfo(Screen):
	skin = """
	<screen name="GullionChannelInfo" position="60,560" size="1800,484" flags="wfNoBorder" backgroundColor="%(bg)s">
		<widget name="picon_fallback" position="30,30" size="220,132" font="Regular;30" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(card)s" zPosition="1" />
		<widget name="picon" position="30,30" size="220,132" alphatest="blend" zPosition="2" />
		<widget name="channel" position="30,176" size="220,70" font="Regular;26" halign="center" foregroundColor="%(muted)s" transparent="1" />
		%(signal)s

		<eLabel text="On now" position="280,30" size="400,36" font="Regular;26" valign="center" foregroundColor="%(muted)s" transparent="1" />
		%(icons)s
		<widget name="title" position="280,68" size="860,60" font="Regular;46" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		<widget name="when" position="280,134" size="860,42" font="Regular;30" foregroundColor="%(accent)s" transparent="1" />
		<widget name="progress" position="280,186" size="860,6" foregroundColor="%(text)s" backgroundColor="%(divider)s" />
		<widget name="description" position="280,210" size="860,200" font="Regular;28" foregroundColor="%(text)s" transparent="1" />
		<eLabel text="BACK to close" position="280,430" size="860,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />

		<eLabel position="1180,30" size="1,424" backgroundColor="%(divider)s" />
		<eLabel text="Coming up" position="1220,30" size="550,36" font="Regular;26" foregroundColor="%(muted)s" transparent="1" />
		%(rows)s
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "card": theme.CARD,
		"accent": theme.ACCENT, "divider": theme.DIVIDER, "icons": _icons_skin(), "signal": _signal_skin(),
		"rows": "".join(
			'<widget name="next%d_time" position="1220,%d" size="110,%d" font="Regular;30" valign="center" foregroundColor="%s" transparent="1" />'
			'<widget name="next%d" position="1340,%d" size="430,%d" font="Regular;30" valign="center" noWrap="1" foregroundColor="%s" transparent="1" />'
			% (i, 80 + i * ROW_H, ROW_H, theme.ACCENT, i, 80 + i * ROW_H, ROW_H, theme.TEXT)
			for i in range(COMING_UP)),
	}

	skin = scale.skin(skin)

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("What's on")
		for name in ("picon_fallback", "channel", "title", "when", "description"):
			self[name] = Label()
		for slot in range(ICON_SLOTS):
			self["icon%d" % slot] = Pixmap()
		for i in range(SIGNAL_LINES):
			self["signal%d_label" % i] = Label()
			self["signal%d" % i] = Label()
		for i in range(COMING_UP):
			self["next%d_time" % i] = Label()
			self["next%d" % i] = Label()
		self["picon"] = Pixmap()
		self["progress"] = ProgressBar()
		self.picons = tiles.Pictures(220, 132)
		self.ref = epg.current_ref(session)
		self["actions"] = ActionMap(["OkCancelActions", "EPGSelectActions"], {
			"ok": self.close,
			"cancel": self.close,
			"info": self.close,
		}, -1)
		self.onLayoutFinish.append(self.fill)
		# The signal changes all the time; the programme details don't.
		self.signal_timer = eTimer()
		self.signal_timer.callback.append(self.draw_signal)
		self.onLayoutFinish.append(self.start_signal)
		self.onClose.append(self.signal_timer.stop)

	def channel(self):
		key = serviceinfo.key(self.ref)
		for bouquet, name, channels in epg.channel_lists():
			for channel in channels:
				if serviceinfo.key(channel.ref) == key:
					return channel
		return None

	def fill(self):
		now = time.time()
		channel = self.channel()
		self["channel"].setText("%d  %s" % (channel.number, channel.name) if channel else "")
		self.draw_picon(channel)
		events = epg.events(self.ref, now, 24 * 60) if self.ref else []
		current = events[0] if events and events[0].airing(now) else None
		later = events[1:] if current else events
		if current is None:
			self["title"].setText("No programme information")
			self["when"].setText("")
			self["description"].setText("")
			self["progress"].hide()
		else:
			self["title"].setText(current.title)
			self["when"].setText("%s – %s   ·   %s" % (_clock(current.begin), _clock(current.end),
				serviceinfo.remaining(current.end - now)))
			self["description"].setText(serviceinfo.split_codes(current.description)[0])
			self["progress"].setValue(int((now - current.begin) * 100 / max(1, current.duration)))
		self.draw_icons(current.description if current else "")
		self.draw_signal()
		for i in range(COMING_UP):
			event = later[i] if i < len(later) else None
			self["next%d_time" % i].setText(_clock(event.begin) if event else "")
			self["next%d" % i].setText(event.title if event else "")

	def start_signal(self):
		# A method, not a lambda: enigma2 runs anything else in onLayoutFinish as code text.
		self.signal_timer.start(1000, False)

	def draw_signal(self):
		service = self.session.nav.getCurrentService()
		frontend = service and hasattr(service, "frontendInfo") and service.frontendInfo()
		status = transponder = None
		if frontend:
			try:
				status = frontend.getFrontendStatus()
				transponder = frontend.getTransponderData(True)
			except Exception:
				pass
		lines = serviceinfo.signal_details(status, transponder)
		for i in range(SIGNAL_LINES):
			label, value = lines[i] if i < len(lines) else ("", "")
			self["signal%d_label" % i].setText(label)
			self["signal%d" % i].setText(value)

	def draw_icons(self, description):
		"""Packed from the right: ... subtitles, audio description, hd, then the delivery icon."""
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		height = info.getInfo(iServiceInformation.sVideoHeight) if info else -1
		names = serviceinfo.icon_row(self.ref, height, description)
		for slot in range(ICON_SLOTS):
			icon = self["icon%d" % slot]
			name = names[len(names) - 1 - slot] if slot < len(names) else ""
			if name and icon.instance is not None:
				icon.instance.setPixmap(LoadPixmap(icons.icon_path(name), cached=True))
				icon.show()
			else:
				icon.hide()

	def draw_picon(self, channel):
		path = self.ref and picon.picon_path(self.ref)
		pixmap = path and self.picons.get(path)
		if pixmap and self["picon"].instance is not None:
			self["picon"].instance.setPixmap(pixmap)
			self["picon"].show()
			self["picon_fallback"].hide()
		else:
			self["picon"].hide()
			self["picon_fallback"].setText(channel.name if channel else "")
			self["picon_fallback"].show()
