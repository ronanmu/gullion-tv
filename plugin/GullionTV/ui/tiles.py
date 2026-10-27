# -*- coding: utf-8 -*-
"""Picture tiles shared by Watch again, All recordings and the Plex library views.

A tile is a picture with a name and one line under it. It can also carry a
small text badge (Plex, Watched), a channel logo badge, and a thin bar showing
how far through something you are. When there's only a portrait poster for a
landscape tile, the poster sits at the left of the tile instead of being
squashed or letterboxed.
"""
from enigma import ePicLoad, gRGB
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar

from .. import theme
from . import scale

PARTS = ("frame", "backdrop", "initial", "image", "poster", "logo", "badge", "progress", "band", "name", "sub")
LOGO_W, LOGO_H = 92, 55  # picons are 220x132
PLEX_BADGE = "#00e5a00d"


class Tile(object):
	def __init__(self, title, subtitle="", image=None, progress=None, payload=None, highlight=False,
			badge="", badge_colour=None, logo=None, poster=None):
		self.title = title
		self.subtitle = subtitle
		self.image = image  # local file, or None
		self.progress = progress
		self.payload = payload
		self.highlight = highlight  # subtitle in the live colour
		self.badge = badge
		self.badge_colour = badge_colour or theme.TEXT
		self.logo = logo  # channel picon shown in the corner
		self.poster = poster  # portrait picture, used when there's no landscape one


def skin(prefix, x, y, width, image_height, band_height=72, badge_width=96, name_font=28, name_lines=1, sub_font=22):
	"""Narrow poster tiles use a smaller font and two lines so titles aren't cut short."""
	poster_width = image_height * 2 // 3
	name_height = int(name_font * 1.25) * name_lines
	values = {
		"p": prefix, "x": x, "y": y, "fx": x - 5, "fy": y - 5, "fw": width + 10, "fh": image_height + band_height + 10,
		"w": width, "ih": image_height, "by": y + image_height, "bh": band_height, "py": y + image_height - 6,
		"tx": x + 18, "tw": width - 36, "ny": y + image_height + 8, "sy": y + image_height + 12 + name_height,
		"nh": name_height, "nf": name_font, "sf": sub_font, "sh": int(sub_font * 1.3),
		"cx": x + 12, "cy": y + 12, "bw": badge_width, "lw": LOGO_W, "lh": LOGO_H, "pw": poster_width,
		"bg": theme.BACKGROUND, "card": theme.CARD, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
		"live": theme.LIVE, "divider": theme.DIVIDER,
	}
	return """
		<widget name="%(p)s_frame" position="%(fx)d,%(fy)d" size="%(fw)d,%(fh)d" backgroundColor="%(bg)s" zPosition="1" />
		<widget name="%(p)s_backdrop" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" backgroundColor="%(card)s" zPosition="2" />
		<widget name="%(p)s_initial" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" font="Regular;24" halign="center" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="3" />
		<widget name="%(p)s_image" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" zPosition="4" alphatest="blend" />
		<widget name="%(p)s_poster" position="%(x)d,%(y)d" size="%(pw)d,%(ih)d" zPosition="4" alphatest="blend" />
		<widget name="%(p)s_logo" position="%(cx)d,%(cy)d" size="%(lw)d,%(lh)d" zPosition="5" alphatest="blend" />
		<widget name="%(p)s_badge" position="%(cx)d,%(cy)d" size="%(bw)d,34" font="Regular;22" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(bg)s" zPosition="5" />
		<widget name="%(p)s_progress" position="%(x)d,%(py)d" size="%(w)d,6" foregroundColor="%(live)s" backgroundColor="%(divider)s" borderWidth="0" zPosition="5" />
		<widget name="%(p)s_band" position="%(x)d,%(by)d" size="%(w)d,%(bh)d" backgroundColor="%(card)s" zPosition="2" />
		<widget name="%(p)s_name" position="%(tx)d,%(ny)d" size="%(tw)d,%(nh)d" font="Regular;%(nf)d" foregroundColor="%(text)s" transparent="1" zPosition="3" />
		<widget name="%(p)s_sub" position="%(tx)d,%(sy)d" size="%(tw)d,%(sh)d" font="Regular;%(sf)d" foregroundColor="%(muted)s" transparent="1" zPosition="3" />""" % values


def add_widgets(screen, prefix):
	for part in PARTS:
		if part in ("image", "poster", "logo"):
			screen["%s_%s" % (prefix, part)] = Pixmap()
		elif part == "progress":
			screen["%s_%s" % (prefix, part)] = ProgressBar()
		else:
			screen["%s_%s" % (prefix, part)] = Label()


def hide(screen, prefix):
	for part in PARTS:
		screen["%s_%s" % (prefix, part)].hide()


def draw(screen, prefix, tile, chosen, pictures):
	for part in PARTS:
		screen["%s_%s" % (prefix, part)].show()
	screen[prefix + "_name"].setText(tile.title)
	screen[prefix + "_sub"].setText(tile.subtitle)

	shown = _show(screen[prefix + "_image"], pictures.image.get(tile.image))
	if shown:
		screen[prefix + "_poster"].hide()
	else:
		shown = _show(screen[prefix + "_poster"], pictures.poster.get(tile.poster))
	screen[prefix + "_initial"].setText("" if shown or tile.image or tile.poster else "No picture")
	if not _show(screen[prefix + "_logo"], pictures.logo.get(tile.logo)):
		screen[prefix + "_logo"].hide()

	badge = screen[prefix + "_badge"]
	badge.setText(tile.badge)
	if tile.badge:
		colour(badge, foreground=tile.badge_colour)
	else:
		badge.hide()

	if tile.progress:
		screen[prefix + "_progress"].setValue(int(tile.progress * 100))
	else:
		screen[prefix + "_progress"].hide()

	if chosen:
		band, name, sub = theme.CARD_SELECTED, theme.TEXT_ON_SELECTED, theme.LIVE_ON_LIGHT if tile.highlight else theme.TEXT_ON_SELECTED_MUTED
	else:
		band, name, sub = theme.CARD, theme.TEXT, theme.LIVE if tile.highlight else theme.TEXT_MUTED
	colour(screen[prefix + "_frame"], background=theme.CARD_SELECTED if chosen else theme.BACKGROUND)
	colour(screen[prefix + "_band"], background=band)
	colour(screen[prefix + "_name"], foreground=name)
	colour(screen[prefix + "_sub"], foreground=sub)


def _show(widget, picture):
	if picture is None or widget.instance is None:
		widget.hide()
		return False
	widget.instance.setPixmap(picture)
	return True


def colour(widget, background=None, foreground=None):
	instance = widget.instance
	if instance is None:
		return
	if background is not None:
		instance.setBackgroundColor(gRGB(theme.rgb(background)))
	if foreground is not None:
		instance.setForegroundColor(gRGB(theme.rgb(foreground)))
	instance.invalidate()


class Pictures(object):
	"""Decoded pictures, scaled to fit a given design size (scaled to the skin) with their
	shape kept. Transparent parts are filled with the background colour on OpenATV 6.4;
	7.x leaves them clear, so picture widgets blend over the card behind them."""

	def __init__(self, width, height, background=theme.CARD):
		self.cache = {}
		self.picload = ePicLoad()
		self.picload.setPara((scale.px(width), scale.px(height), 1, 1, False, 1, theme.opaque(background)))

	def get(self, path):
		if not path:
			return None
		if path not in self.cache:
			self.cache[path] = self.picload.getData() if self.picload.startDecode(path, 0, 0, False) == 0 else None
		return self.cache[path]


class TilePictures(object):
	"""The three picture sizes a tile uses: the main picture, a poster and a channel logo."""

	def __init__(self, width, image_height):
		self.image = Pictures(width, image_height)
		self.poster = Pictures(image_height * 2 // 3, image_height)
		self.logo = Pictures(LOGO_W, LOGO_H)
