# -*- coding: utf-8 -*-
"""Films and TV programmes from Plex, as pages of posters.

Pages come from the server 16 at a time, so a big library never has to be held
on the box at once. GREEN switches between A to Z and newest first, YELLOW
between everything and unwatched only, and BLUE moves to the next library when
Tech Support chose more than one of the same kind.
"""
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from . import client as plex
from .. import theme
from ..ui import tiles
from ..ui.background import Background
from ..ui.popups import GullionChoice
from ..webcams import sources

COLS, ROWS = 8, 2
PER_PAGE = COLS * ROWS
POSTER_W, POSTER_H, BAND_H = 200, 300, 96
GAP_X, GAP_Y, LEFT, TOP = 20, 20, 90, 196
POSTERS = "/tmp/gulliontv/posters"
# heading, one, many, kind of library
WORDS = {plex.MOVIE: ("Films", "film", "films", "film"), plex.SHOW: ("TV programmes", "programme", "programmes", "TV")}


def library_tile(item):
	"""A poster with its name, year (or series), and whether it's been watched."""
	badge, badge_colour = "", None
	if item.kind == plex.SHOW:
		if item.episodes and not item.to_watch:
			badge, badge_colour = "Watched", theme.TEXT_MUTED
		elif item.episodes_watched and item.to_watch:
			badge, badge_colour = "%d to watch" % item.to_watch, theme.LIVE
	elif item.watched:
		badge, badge_colour = "Watched", theme.TEXT_MUTED
	return tiles.Tile(item.title, item.subheading, getattr(item, "picture", None), item.progress,
		("plex", item), badge=badge, badge_colour=badge_colour)


def _key_hints():
	parts = []
	for i, (colour, name) in enumerate(((theme.KEY_GREEN, "green"), (theme.KEY_YELLOW, "yellow"), (theme.KEY_BLUE, "blue"))):
		x = 1050 + i * 260
		parts.append('<widget name="key_%s_dot" position="%d,1040" size="16,16" backgroundColor="%s" />' % (name, x, colour))
		parts.append('<widget name="key_%s" position="%d,1030" size="230,36" font="Regular;24" foregroundColor="%s" transparent="1" />'
			% (name, x + 24, theme.TEXT_MUTED))
	return "".join(parts)


class PlexLibrary(Screen):
	skin = """
	<screen name="GullionPlexLibrary" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<widget name="heading" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />
		<eLabel text="Plex" position="90,144" size="70,34" font="Regular;22" halign="center" valign="center" foregroundColor="%(plex)s" backgroundColor="%(card)s" />
		<widget name="summary" position="176,142" size="1200,38" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		<widget name="page" position="1430,142" size="400,38" font="Regular;28" halign="right" foregroundColor="%(muted)s" transparent="1" />
		%(tiles)s
		<widget name="empty" position="90,320" size="1740,64" font="Regular;36" foregroundColor="%(muted)s" transparent="1" />
		<eLabel text="OK to open   ·   CH + / - to page   ·   BACK to go back" position="90,1030" size="940,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		%(keys)s
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER, "card": theme.CARD,
		"plex": tiles.PLEX_BADGE, "keys": _key_hints(),
		"tiles": "".join(tiles.skin("tile%d" % i, LEFT + (i % COLS) * (POSTER_W + GAP_X), TOP + (i // COLS) * (POSTER_H + BAND_H + GAP_Y),
			POSTER_W, POSTER_H, BAND_H, badge_width=140, name_font=24, name_lines=2, sub_font=20) for i in range(PER_PAGE)),
	}

	def __init__(self, session, settings, kind, request=None):
		Screen.__init__(self, session)
		self.kind = kind
		self.words = WORDS[kind]
		self.setTitle(self.words[0])
		self.client = plex.Client(settings, request)
		self["heading"] = Label(self.words[0])
		for name in ("summary", "page", "empty", "key_green", "key_yellow", "key_blue", "key_green_dot", "key_yellow_dot", "key_blue_dot"):
			self[name] = Label()
		for i in range(PER_PAGE):
			tiles.add_widgets(self, "tile%d" % i)
		self.pictures = tiles.TilePictures(POSTER_W, POSTER_H)
		self.background = Background()
		self.libraries = []
		self.library = 0
		self.newest_first = False
		self.unwatched_only = False
		self.pages = {}
		self.loading = set()
		self.total = None
		self.selected = 0
		self.problem = ""
		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ColorActions", "EPGSelectActions", "MenuActions"], {
			"left": lambda: self.move(-1),
			"right": lambda: self.move(1),
			"up": lambda: self.move(-COLS),
			"down": lambda: self.move(COLS),
			"nextBouquet": lambda: self.move(-PER_PAGE),
			"prevBouquet": lambda: self.move(PER_PAGE),
			"green": self.toggle_order,
			"yellow": self.toggle_unwatched,
			"blue": self.next_library,
			"ok": self.ok,
			"cancel": self.leave,
			"menu": self.leave,
		}, -1)
		self.onLayoutFinish.append(self.started)

	# Loading

	def started(self):
		self.paint()
		self.background.run(self.find_libraries, self.libraries_found)

	def find_libraries(self):
		chosen = set(self.client.settings["sections"])
		return [section for section in self.client.sections() if section["type"] == self.kind and section["key"] in chosen]

	def libraries_found(self, libraries, error):
		if error is not None:
			self.problem = "Plex isn't reachable right now"
		elif not libraries:
			self.problem = "Tech Support hasn't chosen a %s library" % self.words[3]
		self.libraries = libraries or []
		self.restart()

	def restart(self):
		self.pages = {}
		self.loading = set()
		self.total = None
		self.selected = 0
		self.fetch(0)
		self.paint()

	def fetch(self, page):
		if not self.libraries or page in self.pages or page in self.loading:
			return
		if self.total is not None and page * PER_PAGE >= self.total:
			return
		self.loading.add(page)
		key = self.libraries[self.library]["key"]
		settings = (self.newest_first, self.unwatched_only, self.library)

		def work():
			items, total = self.client.library(key, self.newest_first, self.unwatched_only, page * PER_PAGE, PER_PAGE)
			for item in items:
				url = self.client.image_url(item.poster, POSTER_W, POSTER_H)
				item.picture = url and sources.download(url, POSTERS)
			return items, total

		def done(result, error):
			self.loading.discard(page)
			if settings != (self.newest_first, self.unwatched_only, self.library):
				return  # the view changed while this page was on its way
			if error is not None:
				self.problem = "Plex isn't reachable right now"
			else:
				self.problem = ""
				self.pages[page], self.total = result
				if page == self.selected // PER_PAGE:
					self.fetch(page + 1)  # have the next page ready, but only that one
			self.paint()

		self.background.run(work, done)

	def leave(self):
		self.background.stop()
		self.close()

	# Navigation

	def move(self, step):
		if not self.total:
			return
		target = max(0, min(self.total - 1, self.selected + step))
		if target == self.selected:
			return
		self.selected = target
		self.fetch(target // PER_PAGE)
		self.paint()

	def toggle_order(self):
		self.newest_first = not self.newest_first
		self.restart()

	def toggle_unwatched(self):
		self.unwatched_only = not self.unwatched_only
		self.restart()

	def next_library(self):
		if len(self.libraries) > 1:
			self.library = (self.library + 1) % len(self.libraries)
			self.restart()

	def ok(self):
		item = self.selected_item()
		if item is None:
			return
		if self.kind == plex.SHOW:
			detail = "Opening a programme to choose a series and episode comes next."
		else:
			detail = "Film details and playing from Plex come next."
		self.session.open(GullionChoice, item.title, [("OK", None)], detail)

	def selected_item(self):
		items = self.pages.get(self.selected // PER_PAGE) or []
		index = self.selected % PER_PAGE
		return items[index] if index < len(items) else None

	# Drawing

	def paint(self):
		page = self.selected // PER_PAGE
		items = self.pages.get(page)
		for i in range(PER_PAGE):
			if items is not None and i < len(items):
				tiles.draw(self, "tile%d" % i, library_tile(items[i]), page * PER_PAGE + i == self.selected, self.pictures)
			else:
				tiles.hide(self, "tile%d" % i)

		if self.problem:
			empty = self.problem
		elif items is None:
			empty = "Loading..."
		elif not items and self.unwatched_only:
			empty = "You've watched everything here. YELLOW shows everything again."
		elif not items:
			empty = "There's nothing in this library yet."
		else:
			empty = ""
		self["empty"].setText(empty)

		parts = []
		if len(self.libraries) > 1:
			parts.append(self.libraries[self.library]["title"])
		if self.total is not None:
			noun = self.words[1] if self.total == 1 else self.words[2]
			parts.append("%d %s%s" % (self.total, "unwatched " if self.unwatched_only else "", noun))
		parts.append("Newest first" if self.newest_first else "A to Z")
		self["summary"].setText("  ·  ".join(parts))
		pages = (self.total + PER_PAGE - 1) // PER_PAGE if self.total else 0
		self["page"].setText("Page %d of %d" % (page + 1, pages) if pages > 1 else "")

		self["key_green"].setText("A to Z" if self.newest_first else "Newest first")
		self["key_yellow"].setText("Everything" if self.unwatched_only else "Unwatched only")
		self["key_blue"].setText("Next library" if len(self.libraries) > 1 else "")
		if len(self.libraries) > 1:
			self["key_blue_dot"].show()
		else:
			self["key_blue_dot"].hide()
