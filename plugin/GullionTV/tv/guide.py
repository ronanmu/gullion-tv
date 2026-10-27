# -*- coding: utf-8 -*-
"""TV guide: programme details and live picture on top, a day bar, and a
two-hour grid of six channels underneath."""
import os
import time

from enigma import eListboxPythonMultiContent, ePoint, eRect, eTimer, gFont, gRGB, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend, MultiContentEntryText
from Components.Pixmap import Pixmap
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from . import epg, picon, serviceinfo
from .. import theme
from ..recordings import store as recordings
from ..ui.popups import EventDetails, GullionChoice
from ..ui import icons, scale, tiles

ROWS = 6
ROW_H = 75
CELL_H = 72
GAP = 3
WINDOW = 2 * 3600
STEP = 1800
DAYS = 7

GRID_X, GRID_Y, GRID_W = 90, 556, 1740
CHANNEL_W = 380
CELLS_X = CHANNEL_W + 10  # inside the grid widget
CELLS_W = GRID_W - CELLS_X
PX_PER_SECOND = CELLS_W / float(WINDOW)
RULER_Y = 512
NOW_Y = 542  # the now marker sits under the ruler times, clear of programme titles
DAY_X, DAY_W = 640, 150
IMAGES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
ICON = 26
REC_ICON_SIZES = (10, 13, 17, 26, 52)  # made by tools/make_images.py, one per common skin size


def rec_icon_path():
	"""The red clock drawn at the size nearest the skin's: list cells can't scale a picture."""
	size = min(REC_ICON_SIZES, key=lambda candidate: abs(candidate - scale.px(ICON)))
	return os.path.join(IMAGES, "rec_clock_%d.png" % size)

_FLAGS = RT_HALIGN_LEFT | RT_VALIGN_CENTER


def _day_bar_skin():
	keys = [(theme.KEY_RED, "-24h"), (theme.KEY_GREEN, "+24h"), (theme.KEY_YELLOW, "List"), (theme.KEY_BLUE, "Now")]
	parts = []
	for i, (colour, text) in enumerate(keys):
		x = 110 + i * 114
		parts.append('<eLabel position="%d,468" size="16,16" backgroundColor="%s" zPosition="1" />' % (x, colour))
		parts.append('<eLabel text="%s" position="%d,456" size="80,40" font="Regular;24" valign="center" foregroundColor="%s" transparent="1" zPosition="1" />'
			% (text, x + 24, theme.TEXT_MUTED))
	for i in range(DAYS):
		parts.append('<widget name="day%d" position="%d,456" size="%d,40" font="Regular;26" halign="center" valign="center" foregroundColor="%s" backgroundColor="%s" zPosition="1" />'
			% (i, DAY_X + i * DAY_W, DAY_W - 10, theme.TEXT_MUTED, theme.DAY_BAR))
	for i in range(WINDOW // STEP):
		parts.append('<widget name="time%d" position="%d,%d" size="200,40" font="Regular;28" foregroundColor="%s" transparent="1" />'
			% (i, GRID_X + CELLS_X + int(i * STEP * PX_PER_SECOND), RULER_Y, theme.TEXT))
	return "".join(parts)


HINTS = 3
HINT_X, HINT_Y, HINT_W, KEY_W, KEY_H = 340, 386, 330, 96, 40


def _key_hints_skin():
	"""OK, REC and INFO drawn as outlined keys, each followed by what it does."""
	parts = []
	for i in range(HINTS):
		x = HINT_X + i * HINT_W
		parts.append('<widget name="hint%d_edge" position="%d,%d" size="%d,%d" backgroundColor="%s" zPosition="1" />'
			% (i, x, HINT_Y, KEY_W, KEY_H, theme.TEXT_MUTED))
		parts.append('<widget name="hint%d_key" position="%d,%d" size="%d,%d" font="Regular;24" halign="center" valign="center" '
			'foregroundColor="%s" backgroundColor="%s" zPosition="2" />' % (i, x + 2, HINT_Y + 2, KEY_W - 4, KEY_H - 4, theme.TEXT, theme.BACKGROUND))
		parts.append('<widget name="hint%d" position="%d,%d" size="%d,%d" font="Regular;26" valign="center" foregroundColor="%s" transparent="1" />'
			% (i, x + KEY_W + 14, HINT_Y, HINT_W - KEY_W - 24, KEY_H, theme.TEXT))
	return "".join(parts)


CODE_ICONS = 4  # subtitles, audio description, sign language, repeat
CODE_ICONS_RIGHT = 1320


def _code_icons_skin():
	"""The programme's access codes as icons, right-aligned on its title line."""
	return "".join('<widget name="code%d" position="%d,156" size="40,40" alphatest="blend" zPosition="2" />'
		% (i, CODE_ICONS_RIGHT - 40 - i * 52) for i in range(CODE_ICONS))


class Guide(Screen):
	skin = """
	<screen name="GullionGuide" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="TV Guide" position="90,44" size="500,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<eLabel position="760,67" size="18,18" backgroundColor="%(yellow)s" />
		<widget name="list_name" position="792,50" size="520,50" font="Regular;32" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>

		<widget name="picon_fallback" position="90,150" size="220,132" font="Regular;30" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(card)s" zPosition="1" />
		<widget name="picon" position="90,150" size="220,132" alphatest="blend" zPosition="2" />
		<widget name="chan_num" position="90,294" size="220,50" font="Regular;34" halign="center" foregroundColor="%(muted)s" transparent="1" />
		<widget name="ev_title" position="340,146" size="760,60" font="Regular;46" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		%(code_icons)s
		<widget name="ev_time" position="340,212" size="660,42" font="Regular;30" foregroundColor="%(accent)s" transparent="1" />
		<widget name="ev_rec" position="1000,212" size="320,42" font="Regular;30" halign="right" foregroundColor="%(red)s" transparent="1" />
		<widget name="ev_desc" position="340,264" size="980,110" font="Regular;28" foregroundColor="%(text)s" transparent="1" />
		%(key_hints)s

		<widget source="session.VideoPicture" render="Pig" position="1370,150" size="460,259" zPosition="1" backgroundColor="#ff000000" />
		<widget name="pig_name" position="1370,371" size="300,38" font="Regular;24" foregroundColor="%(text)s" backgroundColor="%(bg)s" zPosition="3" />
		<widget name="number_entry" position="1370,150" size="460,90" font="Regular;48" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(card)s" zPosition="4" />

		<eLabel position="90,450" size="1740,52" backgroundColor="%(daybar_bg)s" />
		%(daybar_markup)s

		<widget name="grid" position="%(gx)d,%(gy)d" size="%(gw)d,%(gh)d" backgroundColor="%(bg)s" scrollbarMode="showNever" transparent="1" />
		<widget name="now_line" position="%(gx)d,%(ny)d" size="4,%(nh)d" backgroundColor="%(live)s" zPosition="5" />

		<widget name="footer" position="90,1022" size="1200,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="storage_note" position="1300,1022" size="530,36" font="Regular;24" halign="right" foregroundColor="%(yellow)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "card": theme.CARD,
		"accent": theme.ACCENT, "red": theme.KEY_RED, "yellow": theme.KEY_YELLOW, "live": theme.LIVE,
		"daybar_bg": theme.DAY_BAR, "daybar_markup": _day_bar_skin(), "key_hints": _key_hints_skin(), "code_icons": _code_icons_skin(),
		"gx": GRID_X, "gy": GRID_Y, "gw": GRID_W, "gh": ROWS * ROW_H, "ry": RULER_Y,
		"ny": NOW_Y, "nh": GRID_Y - NOW_Y,
	}

	last_list = 0

	skin = scale.skin(skin)

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("TV Guide")

		for name in ("list_name", "chan_num", "ev_title", "ev_time", "ev_rec", "ev_desc", "hints", "pig_name", "now_line", "picon_fallback", "footer", "storage_note", "number_entry"):
			self[name] = Label()
		for i in range(CODE_ICONS):
			self["code%d" % i] = Pixmap()
		for i in range(HINTS):
			for name in ("hint%d_edge", "hint%d_key", "hint%d"):
				self[name % i] = Label()
		self["picon"] = Pixmap()
		self.rec_icon = LoadPixmap(rec_icon_path(), cached=True)
		self.picons = tiles.Pictures(220, 132)
		for i in range(DAYS):
			self["day%d" % i] = Label()
		for i in range(WINDOW // STEP):
			self["time%d" % i] = Label()
		self["grid"] = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
		self["grid"].l.setItemHeight(scale.px(ROW_H))
		self["grid"].l.setFont(0, gFont("Regular", scale.px(30)))
		self["grid"].l.setFont(1, gFont("Regular", scale.px(26)))
		self["grid"].l.setSelectionClip(eRect(0, 0, 0, 0), False)

		# Checked each time the guide opens: is there a drive to record to?
		self.storage, free = recordings.storage()
		self.lists = epg.channel_lists()
		self.list_index = min(Guide.last_list, max(0, len(self.lists) - 1))
		self.row = 0
		self.top = 0
		self.selected_eid = None
		self.cache = {}
		self.now = time.time()
		self.window_start = self.earliest()
		self.focus = self.now
		self.open_on_current_channel()

		# Typing a channel number jumps to it, as it does on live TV.
		self.typed = ""
		self.number_timer = eTimer()
		self.number_timer.callback.append(self.go_to_number)
		self.hide_timer = eTimer()
		self.hide_timer.callback.append(self.hide_number)

		actions = dict((str(n), lambda n=n: self.type_digit(n)) for n in range(10))
		self["numbers"] = ActionMap(["NumberActions"], actions, -1)
		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ColorActions", "EPGSelectActions", "InfobarInstantRecord", "MenuActions"], {
			"up": lambda: self.move_row(-1),
			"down": lambda: self.move_row(1),
			"left": self.previous_event,
			"right": self.next_event,
			# CH+/- page: nextBouquet/prevBouquet on OpenATV 6.4, nextService/prevService on 7.x.
			"nextBouquet": lambda: self.move_row(-ROWS),
			"prevBouquet": lambda: self.move_row(ROWS),
			"nextService": lambda: self.move_row(-ROWS),
			"prevService": lambda: self.move_row(ROWS),
			"red": lambda: self.shift_day(-1),
			"green": lambda: self.shift_day(1),
			"yellow": self.next_list,
			"blue": self.jump_to_now,
			"ok": self.ok,
			"info": self.show_details,
			"instantRecord": self.record_key,
			"cancel": self.cancel,
			"menu": self.close,
		}, -1)

		self.clock = eTimer()
		self.clock.callback.append(self.tick)
		self.onLayoutFinish.append(self.layout_finished)
		self.onShow.append(lambda: self.clock.start(30000, False))
		self.onHide.append(self.clock.stop)

	# Data

	@property
	def channels(self):
		return self.lists[self.list_index][2] if self.lists else []

	@property
	def window_end(self):
		return self.window_start + WINDOW

	def earliest(self):
		return int(self.now) // STEP * STEP

	def row_events(self, row):
		channel = self.channels[row]
		key = (channel.ref, self.window_start)
		if key not in self.cache:
			if len(self.cache) > 200:
				self.cache = {}
			self.cache[key] = epg.events(channel.ref, self.window_start, 4 * 60)
		return self.cache[key]

	def selected_event(self):
		if not self.channels:
			return None
		events = self.row_events(self.row)
		for event in events:
			if event.eid == self.selected_eid:
				return event
		return None

	def select_at(self, moment):
		"""Select the event on the current row airing at moment, or the nearest one."""
		events = self.row_events(self.row) if self.channels else []
		chosen = None
		for event in events:
			if event.end > moment:
				chosen = event
				break
		if chosen is None and events:
			chosen = events[-1]
		self.selected_eid = chosen and chosen.eid

	def open_on_current_channel(self):
		current = epg.current_ref(self.session)
		if not self.show_channel(lambda channel: channel.ref == current):
			self.select_at(self.focus)

	def show_channel(self, wanted):
		"""Put the first channel wanted(channel) is true for on screen, in whichever list has it."""
		for index, (bouquet, name, channels) in enumerate(self.lists):
			for row, channel in enumerate(channels):
				if wanted(channel):
					self.list_index, self.row = index, row
					self.top = max(0, min(row - 2, len(channels) - ROWS))
					self.select_at(self.focus)
					return True
		return False

	# Channel numbers

	def type_digit(self, n):
		if not self.typed and n == 0:
			return  # there's no channel 0
		self.typed += str(n)
		self["number_entry"].setText("Channel %s" % self.typed)
		self["number_entry"].show()
		# Go straight there once another digit couldn't make a channel that exists.
		highest = max([channel.number for bouquet, name, channels in self.lists for channel in channels] or [0])
		if int(self.typed) * 10 > highest:
			self.go_to_number()
		else:
			self.number_timer.start(2000, True)

	def go_to_number(self):
		self.number_timer.stop()
		typed, self.typed = self.typed, ""
		if not typed:
			return
		number = int(typed)
		if self.show_channel(lambda channel: channel.number == number):
			Guide.last_list = self.list_index
			self["number_entry"].hide()
			self.redraw()
		else:
			self["number_entry"].setText("No channel %d" % number)
			self.hide_timer.start(2000, True)

	def hide_number(self):
		if not self.typed:
			self["number_entry"].hide()

	def cancel(self):
		if self.typed:
			self.number_timer.stop()
			self.typed = ""
			self["number_entry"].hide()
			return
		self.close()

	# Navigation

	def move_row(self, step):
		if not self.channels:
			return
		self.row = max(0, min(len(self.channels) - 1, self.row + step))
		if self.row < self.top:
			self.top = self.row
		elif self.row >= self.top + ROWS:
			self.top = self.row - ROWS + 1
		self.select_at(self.focus)
		self.redraw()

	def next_event(self):
		current = self.selected_event()
		if current is None:
			self.shift_window(STEP)
			return
		later = [event for event in self.row_events(self.row) if event.begin >= current.end]
		if not later:
			self.window_start += STEP
			later = [event for event in self.row_events(self.row) if event.begin >= current.end]
			if not later:
				self.window_start -= STEP
				return
		self.choose(later[0])

	def previous_event(self):
		current = self.selected_event()
		events = self.row_events(self.row) if self.channels else []
		earlier = [event for event in events if current is None or event.end <= current.begin]
		if earlier and earlier[-1].end > self.earliest():
			self.choose(earlier[-1])
		elif self.window_start > self.earliest():
			self.shift_window(-STEP)

	def choose(self, event):
		while event.begin >= self.window_end:
			self.window_start += STEP
		while event.end <= self.window_start and self.window_start > self.earliest():
			self.window_start -= STEP
		self.selected_eid = event.eid
		self.focus = max(event.begin, self.window_start)
		self.redraw()

	def shift_window(self, seconds):
		self.window_start = max(self.earliest(), self.window_start + seconds)
		self.focus = self.window_start
		self.select_at(self.focus)
		self.redraw()

	def shift_day(self, days):
		target = self.window_start + days * 86400
		last = self.earliest() + (DAYS - 1) * 86400
		if target < self.earliest():
			self.jump_to_now()
			return
		self.window_start = min(target, last)
		self.focus = max(self.window_start, min(self.focus + days * 86400, self.window_end - 1))
		self.select_at(self.focus)
		self.redraw()

	def jump_to_now(self):
		self.window_start = self.earliest()
		self.focus = self.now
		self.select_at(self.focus)
		self.redraw()

	def next_list(self):
		if len(self.lists) < 2:
			return
		self.list_index = (self.list_index + 1) % len(self.lists)
		Guide.last_list = self.list_index
		self.row = self.top = 0
		self.select_at(self.focus)
		self.redraw()

	# Actions

	def ok(self):
		event = self.selected_event()
		# A programme that has already finished can't be watched or recorded.
		if event is None or event.over(self.now):
			return
		if event.airing(self.now):
			bouquet = self.lists[self.list_index][0]
			epg.zap(self.session, self.channels[self.row].ref, bouquet)
			self.close("watch")
			return
		timer = epg.find_timer(self.session, self.channels[self.row].ref, event)
		if timer:
			options = [("Don't record", "remove"), ("Keep the recording", None)]
		elif not recordings.can_record(self.storage):
			self.cannot_record()
			return
		else:
			options = [("Record this", "record"), ("Cancel", None)]
		self.session.openWithCallback(self.choice_made, GullionChoice, event.title, options, self.when(event))

	def record_key(self):
		event = self.selected_event()
		if event is None or event.over(self.now):
			return
		if epg.find_timer(self.session, self.channels[self.row].ref, event):
			self.session.openWithCallback(self.choice_made, GullionChoice, event.title,
				[("Don't record", "remove"), ("Keep the recording", None)], self.when(event))
		elif not recordings.can_record(self.storage):
			self.cannot_record()
		else:
			self.choice_made("record")

	def cannot_record(self):
		if self.storage == recordings.FULL:
			heading, detail = "The recording drive is full", "Delete some old recordings to make room."
		else:
			heading, detail = "This box can't record right now", "Ask Tech Support to check the recording drive."
		self.session.open(GullionChoice, heading, [("OK", None)], detail)

	def choice_made(self, choice=None):
		event = self.selected_event()
		if event is None or choice is None:
			return
		ref = self.channels[self.row].ref
		if choice == "record":
			if not recordings.can_record(self.storage):
				self.cannot_record()
			elif not epg.add_timer(self.session, ref, event):
				self.session.open(GullionChoice, "Couldn't set this recording",
					[("OK", None)], "Another recording at the same time is in the way.")
		elif choice == "remove":
			timer = epg.find_timer(self.session, ref, event)
			if timer:
				epg.remove_timer(self.session, timer)
		self.redraw()

	def show_details(self):
		event = self.selected_event()
		if event is not None:
			self.session.open(EventDetails, event.title, self.when(event), serviceinfo.split_codes(event.description)[0])

	# Drawing

	def layout_finished(self):
		if self["grid"].instance is not None:
			self["grid"].instance.setSelectionEnable(False)
		self["number_entry"].hide()
		self.redraw()

	def tick(self):
		self.now = time.time()
		self.redraw()

	def redraw(self):
		self.draw_header()
		self.draw_footer()
		self.draw_days()
		self.draw_ruler()
		self["grid"].setList([self.build_row(row) for row in range(self.top, min(self.top + ROWS, len(self.channels)))])
		self.draw_details()

	def draw_footer(self):
		able = recordings.can_record(self.storage)
		self["footer"].setText("Arrows to move   ·   CH + / - to page   ·   OK to watch%s   ·   BACK for home" % (" or record" if able else ""))
		self["storage_note"].setText({
			recordings.LOW: "Recording space is low",
			recordings.FULL: "The recording drive is full",
			recordings.MISSING: "Recording isn't available",
		}.get(self.storage, ""))

	def draw_header(self):
		self["list_name"].setText(self.lists[self.list_index][1] if self.lists else "No channel lists yet")
		self["pig_name"].setText("  " + self.playing_name())

	def playing_name(self):
		current = epg.current_ref(self.session)
		for bouquet, name, channels in self.lists:
			for channel in channels:
				if channel.ref == current:
					return channel.name
		return ""

	def draw_days(self):
		shown = (_midnight(self.window_start) - _midnight(self.now)) // 86400
		for i in range(DAYS):
			day = time.localtime(self.now + i * 86400)
			self["day%d" % i].setText("Today" if i == 0 else time.strftime("%a", day))
			chosen = i == shown
			_colour(self["day%d" % i], theme.CARD if chosen else theme.DAY_BAR, theme.TEXT if chosen else theme.TEXT_MUTED)

	def draw_ruler(self):
		for i in range(WINDOW // STEP):
			self["time%d" % i].setText(_clock(self.window_start + i * STEP))
		line = self["now_line"]
		if self.window_start <= self.now < self.window_end:
			if line.instance is not None:
				line.instance.move(ePoint(scale.px(GRID_X + CELLS_X + int((self.now - self.window_start) * PX_PER_SECOND)), scale.px(NOW_Y)))
			line.show()
		else:
			line.hide()

	def build_row(self, row):
		channel = self.channels[row]
		chosen_row = row == self.row
		row_bg = theme.ROW_SELECTED if chosen_row else theme.CARD
		entries = [None,
			_text(0, 0, CHANNEL_W, CELL_H, "", 1, theme.TEXT, row_bg),
			_text(20, 0, 80, CELL_H, str(channel.number), 1, theme.TEXT_MUTED, row_bg),
			_text(100, 0, CHANNEL_W - 110, CELL_H, channel.name, 0, theme.TEXT, row_bg),
		]
		events = [event for event in self.row_events(row) if event.end > self.window_start and event.begin < self.window_end]
		if not events:
			entries.append(_text(CELLS_X, 0, CELLS_W, CELL_H, "   No programme information", 0, theme.TEXT_MUTED, row_bg))
			return entries
		for event in events:
			left = CELLS_X + int((max(event.begin, self.window_start) - self.window_start) * PX_PER_SECOND)
			right = CELLS_X + int((min(event.end, self.window_end) - self.window_start) * PX_PER_SECOND)
			width = right - left - GAP
			if width < 4:
				continue
			if chosen_row and event.eid == self.selected_eid:
				bg, fg = theme.CARD_SELECTED, theme.TEXT_ON_SELECTED
			elif event.end <= self.now:
				bg, fg = theme.CELL_PAST, theme.TEXT_MUTED
			else:
				bg, fg = row_bg, theme.TEXT
			entries.append(_text(left, 0, width, CELL_H, "", 0, fg, bg))
			inset = 16
			if epg.find_timer(self.session, channel.ref, event):
				top = (CELL_H - ICON) // 2
				if self.rec_icon:
					entries.append(MultiContentEntryPixmapAlphaBlend(pos=(scale.px(left + inset), scale.px(top)),
						size=(scale.px(ICON), scale.px(ICON)), png=self.rec_icon))
				else:
					entries.append(_text(left + inset, top, ICON, ICON, "", 0, fg, theme.KEY_RED))
				inset += ICON + 12
			if width > inset + 24:
				entries.append(_text(left + inset, 0, width - inset - 8, CELL_H, event.title, 0, fg, bg))
		return entries

	def draw_details(self):
		event = self.selected_event()
		channel = self.channels[self.row] if self.channels else None
		# Just the number: the picon (or the name card in its place) says which channel.
		self["chan_num"].setText(str(channel.number) if channel else "")
		self.draw_picon(channel)
		if event is None:
			self["ev_title"].setText("No programme information" if channel else "No channels yet")
			for name in ("ev_time", "ev_rec", "ev_desc", "hints"):
				self[name].setText("")
			self.draw_hints([])
			self.draw_codes("")
			return
		self["ev_title"].setText(event.title)
		self["ev_time"].setText(self.when(event))
		# "(HD, S)" and "[S,AD] [HD]" become icons rather than text.
		self["ev_desc"].setText(serviceinfo.split_codes(event.description)[0])
		self.draw_codes(event.description)
		airing = event.airing(self.now)
		if not event.over(self.now) and epg.find_timer(self.session, channel.ref, event):
			self["ev_rec"].setText("Recording" if airing else "Will record")
		else:
			self["ev_rec"].setText("")
		able = recordings.can_record(self.storage) and not event.over(self.now)
		hints = [("OK", "Watch")] if airing else ([("OK", "Record options")] if able else [])
		if able:
			hints.append(("REC", "Record"))
		hints.append(("INFO", "More details"))
		self["hints"].setText("          ".join("%s  %s" % hint for hint in hints))
		self.draw_hints(hints)

	def draw_codes(self, description):
		"""Packed from the right, in the broadcaster's order."""
		names = [serviceinfo.BADGE_ICONS[code] for code in serviceinfo.badges(description)]
		for i in range(CODE_ICONS):
			widget = self["code%d" % i]
			name = names[len(names) - 1 - i] if i < len(names) else None
			if name and widget.instance is not None:
				widget.instance.setPixmap(LoadPixmap(icons.icon_path(name), cached=True))
				widget.show()
			else:
				widget.hide()

	def draw_hints(self, hints):
		for i in range(HINTS):
			key, label = hints[i] if i < len(hints) else ("", "")
			self["hint%d_key" % i].setText(key)
			self["hint%d" % i].setText(label)
			for name in ("hint%d_edge", "hint%d_key"):
				if key:
					self[name % i].show()
				else:
					self[name % i].hide()

	def draw_picon(self, channel):
		"""The channel's logo, or its name on a card when there's no picon for it."""
		path = channel and picon.picon_path(channel.ref)
		pixmap = path and self.picons.get(path)
		if pixmap and self["picon"].instance is not None:
			self["picon"].instance.setPixmap(pixmap)
			self["picon"].show()
			self["picon_fallback"].hide()
		else:
			self["picon"].hide()
			self["picon_fallback"].setText(channel.name if channel else "")
			self["picon_fallback"].show()

	def when(self, event):
		span = "%s – %s" % (_clock(event.begin), _clock(event.end))
		if event.airing(self.now):
			minutes = int(event.end - self.now) // 60
			return "%s   ·   %d min left" % (span, minutes)
		if _midnight(event.begin) == _midnight(self.now):
			return span
		day = time.localtime(event.begin)
		return "%s %d %s   ·   %s" % (time.strftime("%a", day), day.tm_mday, time.strftime("%b", day), span)


def _text(x, y, w, h, text, font, fg, bg, flags=_FLAGS):
	"""A grid cell, laid out at the design size and scaled to the skin."""
	return MultiContentEntryText(pos=(scale.px(x), scale.px(y)), size=(scale.px(w), scale.px(h)), font=font, flags=flags, text=text,
		color=theme.rgb(fg), color_sel=theme.rgb(fg), backcolor=theme.rgb(bg), backcolor_sel=theme.rgb(bg))


def _colour(widget, background, foreground):
	if widget.instance is None:
		return
	widget.instance.setBackgroundColor(gRGB(theme.rgb(background)))
	widget.instance.setForegroundColor(gRGB(theme.rgb(foreground)))
	widget.instance.invalidate()


def _clock(timestamp):
	return time.strftime("%H:%M", time.localtime(timestamp))


def _midnight(timestamp):
	day = time.localtime(timestamp)
	return int(time.mktime((day.tm_year, day.tm_mon, day.tm_mday, 0, 0, 0, 0, 0, -1)))
