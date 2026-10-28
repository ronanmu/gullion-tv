# -*- coding: utf-8 -*-
"""Media: recorded TV and, once Tech Support has set it up, Plex.

Four colour-key filters rebuild two rows: Continue watching and Recently added.
The default All view combines up to three recordings with one Plex movie and one
Plex TV show in each row.
"""
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from . import theme
from .plex import client as plex
from .recordings import store as recordings
from .recordings.screen import Recordings, _channel_name, empty_message, make_frames, play_recording, read_recordings  # noqa: F401
from .tv import picon
from .ui import icons, tiles
from .ui.background import Background
from .ui.popups import GullionChoice
from .webcams import sources
from .ui import scale

VISIBLE = (4, 5)
ROW_LIMIT = (8, 10)
TILE_W = (420, 300)
IMAGE_H = (170, 320)
BAND_H = (72, 80)
GAP = (20, 60)
LEFT = 90
SLOT_Y = (210, 550)
FILTERS = ("All", "Recorded TV", "Movies on Plex", "TV Shows on Plex")
FILTER_COLOURS = ("red", "green", "yellow", "blue")
TAB_X, TAB_Y, TAB_W, TAB_H, TAB_GAP = 90, 112, 420, 70, 20
PLEX_THUMBS = "/tmp/gulliontv/plex"


def recording_tile(recording, continuing=False, portrait=False):
	parts = [recording.channel] if recording.channel else []
	if continuing:
		parts.append("%d min left" % max(1, (recording.duration - recording.position) // 60))
	else:
		parts.append(recording.when())
	# A frame from the recording, with the channel's logo in the corner. Until
	# there's a frame (or without ffmpeg), the logo fills the tile instead.
	logo = picon.picon_path(recording.channel_ref)
	frame = recording.image
	return tiles.Tile(recording.title, "  ·  ".join(parts), logo if portrait else frame or logo,
		recording.progress if recording.position > 60 else None, ("recording", recording),
		badge="Recorded TV", badge_colour=theme.KEY_RED, logo=logo if frame and not portrait else None)


def plex_tile(item, continuing=False, portrait=False):
	"""Plex tiles say so in their corner, so they're told apart from recordings."""
	subtitle = item.subheading
	if continuing and item.kind != "episode" and item.duration:
		subtitle = "%d min left" % max(1, (item.duration - item.position) // 60)
	badge = "Movie" if item.kind == plex.MOVIE else "TV Show"
	if portrait:
		picture = getattr(item, "poster_picture", None) or getattr(item, "picture", None)
	else:
		picture = getattr(item, "picture", None)
	return tiles.Tile(item.heading, subtitle, picture, item.progress if continuing else None,
		("plex", item), badge=badge, badge_colour=tiles.PLEX_BADGE, poster=getattr(item, "poster_picture", None))


def plex_pictures(client, items):
	"""Landscape art for each item, or its poster when there isn't any. Runs in the background."""
	for item in items:
		item.picture = item.poster_picture = None
		if item.landscape:
			item.picture = sources.download(client.image_url(item.landscape, TILE_W[0], IMAGE_H[0]), PLEX_THUMBS)
		if item.picture is None and item.poster:
			item.poster_picture = sources.download(client.image_url(item.poster, TILE_W[1], IMAGE_H[1]), PLEX_THUMBS)
		elif item.poster:
			item.poster_picture = sources.download(client.image_url(item.poster, TILE_W[1], IMAGE_H[1]), PLEX_THUMBS)


class WatchAgain(Screen):
	skin = """
	<screen name="GullionWatchAgain" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="Media" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>
		%(tabs)s
		%(slots)s
		<eLabel position="90,1010" size="1740,1" backgroundColor="%(divider)s" />
		<eLabel text="Arrows to choose   ·   OK to watch   ·   BACK for Home" position="90,1024" size="980,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="note" position="1010,1024" size="820,36" font="Regular;22" halign="right" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER,
		"tabs": "".join(
			'<widget name="tab%d_bg" position="%d,%d" size="%d,%d" backgroundColor="%s" />'
			'<widget name="tab%d" position="%d,%d" size="%d,%d" font="Regular;27" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
			'<ePixmap pixmap="%s" position="%d,%d" size="24,24" alphatest="blend" zPosition="2" />'
			% (i, TAB_X + i * (TAB_W + TAB_GAP), TAB_Y, TAB_W, TAB_H, theme.CARD,
				i, TAB_X + i * (TAB_W + TAB_GAP) + 24, TAB_Y, TAB_W - 82, TAB_H, theme.TEXT,
				icons.key_icon(FILTER_COLOURS[i]), TAB_X + i * (TAB_W + TAB_GAP) + TAB_W - 48, TAB_Y + 23)
			for i in range(len(FILTERS))),
		"slots": "".join(
			'<widget name="slot%d_title" position="90,%d" size="1200,40" font="Regular;30" foregroundColor="%s" transparent="1" />'
			'<widget name="slot%d_empty" position="90,%d" size="1740,%d" font="Regular;28" valign="center" foregroundColor="%s" transparent="1" />'
			% (slot, y, theme.TEXT_MUTED, slot, y + 46, IMAGE_H[slot], theme.TEXT_MUTED)
			+ "".join(tiles.skin("slot%d_tile%d" % (slot, i), LEFT + i * (TILE_W[slot] + GAP[slot]), y + 46,
				TILE_W[slot], IMAGE_H[slot], BAND_H[slot], badge_width=140,
				name_font=26 if slot == 0 else 24, sub_font=20) for i in range(VISIBLE[slot]))
			for slot, y in enumerate(SLOT_Y)),
	}

	skin = scale.skin(skin)

	def __init__(self, session, plex_settings=None):
		Screen.__init__(self, session)
		self.setTitle("Media")
		for i, title in enumerate(FILTERS):
			self["tab%d_bg" % i] = Label()
			self["tab%d" % i] = Label(title)
		for slot in range(len(SLOT_Y)):
			self["slot%d_title" % slot] = Label()
			self["slot%d_empty" % slot] = Label()
			for i in range(VISIBLE[slot]):
				tiles.add_widgets(self, "slot%d_tile%d" % (slot, i))
		self["note"] = Label()

		self.plex_settings = plex_settings if plex_settings is not None else plex.load_settings()
		self.with_plex = plex.is_configured(self.plex_settings)
		self.recordings = None
		self.storage = None
		self.plex_rows = ([], [])
		self.pictures = [tiles.TilePictures(TILE_W[i], IMAGE_H[i]) for i in range(2)]
		self.background = Background()
		self.sections = []
		self.filter = 0
		self.row = 0
		self.columns = {}
		self.offsets = {}
		# Live TV is stopped while choosing something to watch, so it can't show
		# through the pictures, and started again on the way out.
		self.live = session.nav.getCurrentlyPlayingServiceReference()
		self.build()

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "MenuActions", "ColorActions"], {
			"left": lambda: self.move_across(-1),
			"right": lambda: self.move_across(1),
			"up": lambda: self.move_down(-1),
			"down": lambda: self.move_down(1),
			"red": lambda: self.choose_filter(0),
			"green": lambda: self.choose_filter(1),
			"yellow": lambda: self.choose_filter(2),
			"blue": lambda: self.choose_filter(3),
			"ok": self.ok,
			"cancel": self.leave,
			"menu": self.open_recordings,
		}, -1)
		self.onLayoutFinish.append(self.started)

	# Loading

	def started(self):
		self.session.nav.stopService()
		self.paint()
		self.load()

	def load(self):
		self.background.run(read_recordings, self.recordings_ready)
		if self.with_plex:
			self.background.run(self.read_plex, self.plex_ready)

	def read_plex(self):
		client = plex.Client(self.plex_settings)
		client.connect()
		rows = (client.continue_watching(), client.recently_added())
		plex_pictures(client, rows[0] + rows[1])
		return rows

	def recordings_ready(self, found, error):
		self.recordings, self.storage = found if found else ([], recordings.MISSING)
		self.build()
		self.paint()
		make_frames(self.background, self.recordings, self.load_recordings)

	def load_recordings(self):
		self.background.run(read_recordings, self.recordings_ready)

	def plex_ready(self, rows, error):
		if error is not None:
			self["note"].setText("Plex isn't reachable right now")
		else:
			self.plex_rows = rows
			self["note"].setText("")
		self.build()
		self.paint()

	def leave(self):
		self.background.stop()
		if self.live is not None:
			self.session.nav.playService(self.live)
		self.close()

	# Rows

	def build(self):
		continuing, recently_added = self.plex_rows
		started = [recording for recording in self.recordings or [] if recording.in_progress]
		if self.filter == 0:
			watching = [recording_tile(r, True) for r in started[:3]] + self.one_of_each(continuing, True)
			recent = [recording_tile(r, portrait=True) for r in (self.recordings or [])[:3]] + self.one_of_each(recently_added, False, True)
		elif self.filter == 1:
			watching = [recording_tile(r, True) for r in started[:ROW_LIMIT[0]]]
			recent = [recording_tile(r, portrait=True) for r in (self.recordings or [])[:ROW_LIMIT[1]]]
		elif self.filter == 2:
			watching = [plex_tile(item, True) for item in continuing if item.kind == plex.MOVIE][:ROW_LIMIT[0]]
			recent = [plex_tile(item, portrait=True) for item in recently_added if item.kind == plex.MOVIE][:ROW_LIMIT[1]]
		else:
			watching = [plex_tile(item, True) for item in continuing if item.kind != plex.MOVIE][:ROW_LIMIT[0]]
			recent = [plex_tile(item, portrait=True) for item in recently_added if item.kind != plex.MOVIE][:ROW_LIMIT[1]]
		recording_empty = "Looking for recordings..." if self.recordings is None else empty_message(self.storage)
		plex_empty = "Plex isn't set up" if not self.with_plex else "Nothing here right now"
		self.sections = [
			{"title": "Continue watching", "tiles": watching, "empty": recording_empty if self.filter == 1 else "Nothing to continue"},
			{"title": "Recently added", "tiles": recent, "empty": recording_empty if self.filter in (0, 1) and not self.with_plex else plex_empty},
		]
		self.row = min(self.row, 1)
		for index, section in enumerate(self.sections):
			self.columns[section["title"]] = min(self.columns.get(section["title"], 0), max(0, len(section["tiles"]) - 1))
			self.offsets[section["title"]] = min(self.offsets.get(section["title"], 0), max(0, len(section["tiles"]) - VISIBLE[index]))

	def one_of_each(self, items, continuing, portrait=False):
		chosen = []
		for movie in (True, False):
			for item in items:
				if (item.kind == plex.MOVIE) == movie:
					chosen.append(plex_tile(item, continuing, portrait))
					break
		return chosen

	# Navigation

	def move_across(self, step):
		if self.row < 0:
			self.choose_filter(max(0, min(len(FILTERS) - 1, self.filter + step)), True)
			return
		title = self.sections[self.row]["title"]
		count = len(self.sections[self.row]["tiles"])
		if count:
			column = max(0, min(count - 1, self.columns.get(title, 0) + step))
			self.columns[title] = column
			offset = self.offsets.get(title, 0)
			if column < offset:
				offset = column
			elif column >= offset + VISIBLE[self.row]:
				offset = column - VISIBLE[self.row] + 1
			self.offsets[title] = offset
		self.paint()

	def move_down(self, step):
		self.row = max(-1, min(1, self.row + step))
		self.paint()

	def selected_tile(self):
		if self.row < 0:
			return None
		section = self.sections[self.row]
		column = self.columns.get(section["title"], 0)
		return section["tiles"][column] if column < len(section["tiles"]) else None

	def ok(self):
		if self.row < 0:
			self.row = 0
			self.paint()
			return
		tile = self.selected_tile()
		if tile is None:
			return
		kind, thing = tile.payload
		if kind == "recording":
			play_recording(self.session, thing, self.reload)
		else:
			self.session.open(GullionChoice, thing.heading, [("OK", None)], "Playing from Plex arrives in the next update.")

	def choose_filter(self, index, keep_filter_focus=False):
		self.filter = index
		self.row = -1 if keep_filter_focus else 0
		self.columns = {}
		self.offsets = {}
		self.build()
		self.paint()

	def open_recordings(self):
		if self.filter in (0, 1):
			self.session.openWithCallback(self.reload, Recordings, False)

	def reload(self, *args):
		# The player may have started live TV again as it closed.
		self.session.nav.stopService()
		self.load()

	# Drawing

	def paint(self):
		for i in range(len(FILTERS)):
			chosen = i == self.filter
			tiles.colour(self["tab%d_bg" % i], background=theme.CARD_SELECTED if chosen else theme.CARD)
			tiles.colour(self["tab%d" % i], foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT)
		for slot in range(len(SLOT_Y)):
			index = slot
			prefix = "slot%d" % slot
			if index >= len(self.sections):
				self[prefix + "_title"].setText("")
				self[prefix + "_empty"].setText("")
				for i in range(VISIBLE[slot]):
					tiles.hide(self, "%s_tile%d" % (prefix, i))
				continue
			section = self.sections[index]
			self[prefix + "_title"].setText(section["title"])
			self[prefix + "_empty"].setText(section.get("empty", "") if not section["tiles"] else "")
			column = self.columns.get(section["title"], 0)
			offset = self.offsets.get(section["title"], 0)
			for i in range(VISIBLE[slot]):
				position = offset + i
				if position < len(section["tiles"]):
					tiles.draw(self, "%s_tile%d" % (prefix, i), section["tiles"][position], index == self.row and position == column, self.pictures[slot])
				else:
					tiles.hide(self, "%s_tile%d" % (prefix, i))
