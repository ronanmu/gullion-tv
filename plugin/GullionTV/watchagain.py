# -*- coding: utf-8 -*-
"""Watch again: recorded TV and, once Tech Support has set it up, Plex.

	Continue watching   Plex and recordings left part-way, most recent first
	Recently added      new films and episodes on Plex (titled "Recently added to Plex")
	Recorded TV         the box's latest recordings
	Browse              Films, TV programmes, All recordings
"""
from enigma import eServiceReference
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from . import theme
from .plex import client as plex
from .recordings import store as recordings, thumbnails
from .tv import picon
from .ui import tiles
from .ui.background import Background
from .ui.popups import GullionChoice
from .webcams import sources
from .ui import scale

PER_ROW = 5
TILE_W, IMAGE_H, BAND_H = 328, 184, 72
GAP, LEFT = 24, 90
SLOT_Y = (150, 474)  # two rows of tiles on screen at a time
BROWSE_Y = 800
BUTTON_W, BUTTON_H, MAX_BUTTONS = 560, 110, 3
ROW_LIMIT = 20
PLEX_THUMBS = "/tmp/gulliontv/plex"
FRAME_LIMIT = 20  # newest recordings given a picture each time Watch again opens


def _channel_name(ref):
	from ServiceReference import ServiceReference
	return ServiceReference(ref).getServiceName().replace("\xc2\x86", "").replace("\xc2\x87", "")


def read_recordings():
	"""(recordings, drive state). Runs in the background: the drive may need to spin up."""
	return recordings.list_recordings(channel_name=_channel_name), recordings.storage()[0]


def empty_message(state):
	if state == recordings.MISSING:
		return "Recording isn't set up on this box. Ask Tech Support to check the recording drive."
	return "No recordings yet. Press REC while watching, or record from the TV guide."


def recording_tile(recording, continuing=False):
	parts = [recording.channel] if recording.channel else []
	if continuing:
		parts.append("%d min left" % max(1, (recording.duration - recording.position) // 60))
	else:
		parts.append(recording.when())
	# A frame from the recording, with the channel's logo in the corner. Until
	# there's a frame (or without ffmpeg), the logo fills the tile instead.
	logo = picon.picon_path(recording.channel_ref)
	frame = recording.image
	return tiles.Tile(recording.title, "  ·  ".join(parts), frame or logo,
		recording.progress if recording.position > 60 else None, ("recording", recording), logo=logo if frame else None)


def plex_tile(item, continuing=False):
	"""Plex tiles say so in their corner, so they're told apart from recordings."""
	subtitle = item.subheading
	if continuing and item.kind != "episode" and item.duration:
		subtitle = "%d min left" % max(1, (item.duration - item.position) // 60)
	return tiles.Tile(item.heading, subtitle, getattr(item, "picture", None), item.progress if continuing else None,
		("plex", item), badge="Plex", badge_colour=tiles.PLEX_BADGE, poster=getattr(item, "poster_picture", None))


def plex_pictures(client, items):
	"""Landscape art for each item, or its poster when there isn't any. Runs in the background."""
	for item in items:
		item.picture = item.poster_picture = None
		if item.landscape:
			item.picture = sources.download(client.image_url(item.landscape, TILE_W, IMAGE_H), PLEX_THUMBS)
		if item.picture is None and item.poster:
			item.poster_picture = sources.download(client.image_url(item.poster, IMAGE_H * 2 // 3, IMAGE_H), PLEX_THUMBS)


class WatchAgain(Screen):
	skin = """
	<screen name="GullionWatchAgain" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="Watch again" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />
		%(slots)s
		<eLabel text="Browse" position="90,%(browse_y)d" size="600,40" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		%(buttons)s
		<eLabel text="Arrows to choose   ·   OK to watch   ·   BACK for home" position="90,1030" size="900,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="note" position="1000,1030" size="830,36" font="Regular;22" halign="right" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER, "browse_y": BROWSE_Y,
		"slots": "".join(
			'<widget name="slot%d_title" position="90,%d" size="1200,40" font="Regular;30" foregroundColor="%s" transparent="1" />'
			'<widget name="slot%d_empty" position="90,%d" size="1740,%d" font="Regular;28" valign="center" foregroundColor="%s" transparent="1" />'
			% (slot, y, theme.TEXT_MUTED, slot, y + 46, IMAGE_H, theme.TEXT_MUTED)
			+ "".join(tiles.skin("slot%d_tile%d" % (slot, i), LEFT + i * (TILE_W + GAP), y + 46, TILE_W, IMAGE_H, BAND_H) for i in range(PER_ROW))
			for slot, y in enumerate(SLOT_Y)),
		"buttons": "".join(
			'<widget name="button%d" position="%d,%d" size="%d,%d" font="Regular;34" halign="center" valign="center" foregroundColor="%s" backgroundColor="%s" />'
			% (i, LEFT + i * (BUTTON_W + 30), BROWSE_Y + 46, BUTTON_W, BUTTON_H, theme.TEXT, theme.CARD)
			for i in range(MAX_BUTTONS)),
	}

	skin = scale.skin(skin)

	def __init__(self, session, plex_settings=None):
		Screen.__init__(self, session)
		self.setTitle("Watch again")
		for slot in range(len(SLOT_Y)):
			self["slot%d_title" % slot] = Label()
			self["slot%d_empty" % slot] = Label()
			for i in range(PER_ROW):
				tiles.add_widgets(self, "slot%d_tile%d" % (slot, i))
		for i in range(MAX_BUTTONS):
			self["button%d" % i] = Label()
		self["note"] = Label()

		self.plex_settings = plex_settings if plex_settings is not None else plex.load_settings()
		self.with_plex = plex.is_configured(self.plex_settings)
		self.recordings = None
		self.storage = None
		self.plex_rows = ([], [])
		self.pictures = tiles.TilePictures(TILE_W, IMAGE_H)
		self.background = Background()
		self.buttons = ([("Films", "films"), ("TV programmes", "shows")] if self.with_plex else []) + [("All recordings", "recordings")]
		self.sections = []
		self.row = 0  # index into self.sections, or len(self.sections) for Browse
		self.top = 0
		self.columns = {}
		self.offsets = {}
		self.button = 0
		self.moved = False
		self.build()

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "MenuActions"], {
			"left": lambda: self.move_across(-1),
			"right": lambda: self.move_across(1),
			"up": lambda: self.move_down(-1),
			"down": lambda: self.move_down(1),
			"ok": self.ok,
			"cancel": self.leave,
			"menu": self.leave,
		}, -1)
		self.onLayoutFinish.append(self.started)

	# Loading

	def started(self):
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
		self.close()

	# Rows

	def build(self):
		continuing, recently_added = self.plex_rows
		started = [recording for recording in self.recordings or [] if recording.in_progress]
		mixed = [(item.viewed_at, plex_tile(item, True)) for item in continuing]
		mixed += [(recording.viewed_at, recording_tile(recording, True)) for recording in started]
		mixed.sort(key=lambda pair: pair[0], reverse=True)

		sections = []
		if mixed:
			sections.append({"title": "Continue watching", "tiles": [tile for _, tile in mixed][:ROW_LIMIT]})
		if recently_added:
			sections.append({"title": "Recently added to Plex", "tiles": [plex_tile(item) for item in recently_added]})
		if self.recordings is None:
			empty = "Looking for recordings..."
		else:
			empty = empty_message(self.storage)
		sections.append({"title": "Recorded TV", "tiles": [recording_tile(r) for r in (self.recordings or [])[:ROW_LIMIT]], "empty": empty})

		# Until the viewer moves, stay on the top row (Continue watching once it loads).
		# After that, keep the same row (or Browse) selected while rows appear above it.
		if not self.moved:
			self.sections, self.row, self.top = sections, 0, 0
			return
		was_browsing = bool(self.sections) and self.browsing
		chosen = self.sections[self.row]["title"] if self.row < len(self.sections) else None
		self.sections = sections
		titles = [section["title"] for section in sections]
		if was_browsing:
			self.row = len(self.sections)
		elif chosen in titles:
			self.row = titles.index(chosen)
		elif self.row >= len(self.sections) and chosen is not None:
			self.row = len(self.sections) - 1
		self.top = max(0, min(self.top, len(self.sections) - len(SLOT_Y)))
		if self.row < len(self.sections):
			self.top = min(self.top, self.row)
			self.top = max(self.top, self.row - len(SLOT_Y) + 1)

	@property
	def browsing(self):
		return self.row >= len(self.sections)

	# Navigation

	def move_across(self, step):
		self.moved = True
		if self.browsing:
			self.button = max(0, min(len(self.buttons) - 1, self.button + step))
		else:
			title = self.sections[self.row]["title"]
			count = len(self.sections[self.row]["tiles"])
			column = max(0, min(count - 1, self.columns.get(title, 0) + step))
			self.columns[title] = column
			offset = self.offsets.get(title, 0)
			if column < offset:
				offset = column
			elif column >= offset + PER_ROW:
				offset = column - PER_ROW + 1
			self.offsets[title] = offset
		self.paint()

	def move_down(self, step):
		self.moved = True
		self.row = max(0, min(len(self.sections), self.row + step))
		if not self.browsing:
			if self.row < self.top:
				self.top = self.row
			elif self.row >= self.top + len(SLOT_Y):
				self.top = self.row - len(SLOT_Y) + 1
		self.paint()

	def selected_tile(self):
		if self.browsing:
			return None
		section = self.sections[self.row]
		column = self.columns.get(section["title"], 0)
		return section["tiles"][column] if column < len(section["tiles"]) else None

	def ok(self):
		if self.browsing:
			action = self.buttons[self.button][1]
			if action == "recordings":
				self.session.openWithCallback(self.reload, AllRecordings)
			else:
				from .plex.library import PlexLibrary
				self.session.open(PlexLibrary, self.plex_settings, plex.MOVIE if action == "films" else plex.SHOW)
			return
		tile = self.selected_tile()
		if tile is None:
			return
		kind, thing = tile.payload
		if kind == "recording":
			play_recording(self.session, thing, self.reload)
		else:
			self.session.open(GullionChoice, thing.heading, [("OK", None)], "Playing from Plex arrives in the next update.")

	def reload(self, *args):
		self.load()

	# Drawing

	def paint(self):
		for slot in range(len(SLOT_Y)):
			index = self.top + slot
			prefix = "slot%d" % slot
			if index >= len(self.sections):
				self[prefix + "_title"].setText("")
				self[prefix + "_empty"].setText("")
				for i in range(PER_ROW):
					tiles.hide(self, "%s_tile%d" % (prefix, i))
				continue
			section = self.sections[index]
			self[prefix + "_title"].setText(section["title"])
			self[prefix + "_empty"].setText(section.get("empty", "") if not section["tiles"] else "")
			offset = self.offsets.get(section["title"], 0)
			column = self.columns.get(section["title"], 0)
			for i in range(PER_ROW):
				position = offset + i
				if position < len(section["tiles"]):
					tiles.draw(self, "%s_tile%d" % (prefix, i), section["tiles"][position], index == self.row and position == column, self.pictures)
				else:
					tiles.hide(self, "%s_tile%d" % (prefix, i))
		for i in range(MAX_BUTTONS):
			button = self["button%d" % i]
			if i < len(self.buttons):
				button.setText(self.buttons[i][0])
				button.show()
				chosen = self.browsing and i == self.button
				tiles.colour(button, background=theme.CARD_SELECTED if chosen else theme.CARD,
					foreground=theme.TEXT_ON_SELECTED if chosen else theme.TEXT)
			else:
				button.hide()


class AllRecordings(Screen):
	"""Every recording as a grid of pictures. RED moves one to the recycle bin."""

	COLS, ROWS = 5, 3
	TOP = 160

	skin = """
	<screen name="GullionAllRecordings" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="All recordings" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />
		%(tiles)s
		<widget name="empty" position="90,300" size="1740,64" font="Regular;36" foregroundColor="%(muted)s" transparent="1" />
		<eLabel position="90,1040" size="16,16" backgroundColor="%(red)s" />
		<eLabel text="Delete   ·   OK to watch   ·   BACK to go back" position="114,1030" size="900,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="page" position="1580,1030" size="250,36" font="Regular;24" halign="right" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER, "red": theme.KEY_RED,
		"tiles": "".join(tiles.skin("tile%d" % i, LEFT + (i % 5) * (TILE_W + GAP), 160 + (i // 5) * (IMAGE_H + BAND_H + 30), TILE_W, IMAGE_H, BAND_H)
			for i in range(15)),
	}

	skin = scale.skin(skin)

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle("All recordings")
		for i in range(self.COLS * self.ROWS):
			tiles.add_widgets(self, "tile%d" % i)
		self["empty"] = Label("Looking for recordings...")
		self["page"] = Label()
		self.recordings = []
		self.storage = None
		self.selected = 0
		self.pictures = tiles.TilePictures(TILE_W, IMAGE_H)
		self.background = Background()
		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ColorActions", "MenuActions"], {
			"left": lambda: self.move(-1),
			"right": lambda: self.move(1),
			"up": lambda: self.move(-self.COLS),
			"down": lambda: self.move(self.COLS),
			"ok": self.ok,
			"red": self.delete,
			"cancel": self.leave,
			"menu": self.leave,
		}, -1)
		self.onLayoutFinish.append(self.load)

	def load(self, *args):
		self.background.run(read_recordings, self.ready)

	def ready(self, found, error):
		self.recordings, self.storage = found if found else ([], recordings.MISSING)
		self.selected = min(self.selected, max(0, len(self.recordings) - 1))
		self.paint()
		make_frames(self.background, self.recordings, self.load)

	def leave(self):
		self.background.stop()
		self.close()

	def move(self, step):
		target = self.selected + step
		if 0 <= target < len(self.recordings):
			self.selected = target
			self.paint()

	def ok(self):
		if self.recordings:
			play_recording(self.session, self.recordings[self.selected], self.load)

	def delete(self):
		if not self.recordings:
			return
		recording = self.recordings[self.selected]
		self.session.openWithCallback(self.delete_chosen, GullionChoice, "Delete %s?" % recording.title,
			[("Delete", "delete"), ("Keep it", None)], "It goes to the recycle bin, so Tech Support can bring it back.")

	def delete_chosen(self, choice=None):
		if choice == "delete" and self.recordings:
			recordings.move_to_trash(self.recordings[self.selected])
			self.load()

	def paint(self):
		per_page = self.COLS * self.ROWS
		self["empty"].setText("" if self.recordings else empty_message(self.storage))
		first = self.selected // per_page * per_page
		for i in range(per_page):
			index = first + i
			if index < len(self.recordings):
				tiles.draw(self, "tile%d" % i, recording_tile(self.recordings[index]), index == self.selected, self.pictures)
			else:
				tiles.hide(self, "tile%d" % i)
		pages = (len(self.recordings) + per_page - 1) // per_page
		self["page"].setText("Page %d of %d" % (self.selected // per_page + 1, pages) if pages > 1 else "")


def make_frames(background, found, reread):
	"""Make pictures for recordings that don't have one, then show them. Once every
	picture exists (or ffmpeg isn't installed) nothing more happens."""
	if any(recording.image is None for recording in found[:FRAME_LIMIT]):
		background.run(lambda: thumbnails.make_missing(found, FRAME_LIMIT), lambda made, error: made and reread())


def play_recording(session, recording, done):
	from Screens.InfoBar import MoviePlayer

	class RecordingPlayer(MoviePlayer):
		"""The box's player, but stopping always goes straight back here, never to the
		stock recordings list or an 'are you sure?' question."""

		def handleLeave(self, how, *args):
			MoviePlayer.handleLeave(self, "quit", *args)

	session.openWithCallback(done, RecordingPlayer, eServiceReference(recording.service_ref))
