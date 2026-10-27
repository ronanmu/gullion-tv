# -*- coding: utf-8 -*-
"""YELLOW (or AUDIO, or SUBTITLE) on live TV: choose the sound track and the subtitles."""
import re

from enigma import gRGB
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from .. import theme
from ..ui import icons, scale

MAX_TRACKS = 4
MAX_SUBTITLES = 4
ROWS = MAX_SUBTITLES + 1  # a column's rows: the subtitles and Off; tracks need no more
SOUND, SUBTITLES = 0, 1

# Two columns side by side, Sound on the left and Subtitles on the right.
WIDTH, HEIGHT = 1200, 640
COLUMN_X, COLUMN_W = (60, 630), 510
HEADING_Y, ROW_Y, ROW_H, ROW_STEP = 128, 204, 64, 72
FOOTER_Y = 580

LANGUAGES = {
	"eng": "English", "en": "English", "gle": "Irish", "ga": "Irish", "gla": "Gaelic", "gd": "Gaelic",
	"wel": "Welsh", "cym": "Welsh", "cy": "Welsh", "fra": "French", "fre": "French", "fr": "French",
	"deu": "German", "ger": "German", "de": "German", "spa": "Spanish", "es": "Spanish",
	"ita": "Italian", "it": "Italian", "pol": "Polish", "pl": "Polish", "por": "Portuguese",
	"nld": "Dutch", "dut": "Dutch",
}
# Audio description goes by several codes: "nar" (narration), "qad", or "AD" in the name.
_DESCRIBED = ("nar", "qad", "ad")
_DOLBY = ("AC3", "AC-3", "E-AC3", "EAC3", "DD", "DOLBY")


def language_name(code):
	return LANGUAGES.get((code or "").strip().lower()[:3], LANGUAGES.get((code or "").strip().lower()[:2], ""))


def track_label(language, codec):
	"""A sound track in plain words: "Audio description", "English · Dolby", "Main sound"."""
	text = ("%s %s" % (language or "", codec or "")).lower()
	if any(word in _DESCRIBED for word in re.split(r"[^a-z]+", text)) or "audio description" in text:
		return "Audio description"
	name = language_name(language) or "Main sound"
	if any(mark in ("%s %s" % (language or "", codec or "")).upper() for mark in _DOLBY):
		return "%s  ·  Dolby" % name
	return name


def subtitle_label(subtitle):
	"""(type, pid or page, ..., language) as enigma2 lists them. Type 1 is teletext."""
	language = subtitle[4] if len(subtitle) > 4 else ""
	name = language_name(language) or (language.strip().title() if language and language.strip() else "Subtitles")
	return "%s  ·  Teletext" % name if subtitle[0] == 1 else name


NOTE = object()


def _column_skin(c):
	x = COLUMN_X[c]
	parts = ['<widget name="col%d_icon" position="%d,%d" size="40,40" alphatest="blend" zPosition="2" />' % (c, x, HEADING_Y + 2),
		'<widget name="col%d_heading" position="%d,%d" size="%d,44" font="Regular;30" valign="center" foregroundColor="%s" transparent="1" zPosition="2" />'
		% (c, x + 56, HEADING_Y, COLUMN_W - 56, theme.TEXT_MUTED),
		'<eLabel position="%d,%d" size="%d,2" backgroundColor="%s" />' % (x, HEADING_Y + 56, COLUMN_W, theme.POPUP_BORDER)]
	for i in range(ROWS):
		y = ROW_Y + i * ROW_STEP
		parts.append('<widget name="col%d_row%d_bg" position="%d,%d" size="%d,%d" backgroundColor="%s" zPosition="1" />'
			% (c, i, x, y, COLUMN_W, ROW_H, theme.CARD))
		parts.append('<widget name="col%d_row%d_icon" position="%d,%d" size="40,40" alphatest="blend" zPosition="2" />'
			% (c, i, x + 20, y + (ROW_H - 40) // 2))
		parts.append('<widget name="col%d_row%d" position="%d,%d" size="%d,%d" font="Regular;30" valign="center" noWrap="1" foregroundColor="%s" transparent="1" zPosition="2" />'
			% (c, i, x + 76, y, COLUMN_W - 76 - 72, ROW_H, theme.TEXT))
		parts.append('<widget name="col%d_row%d_tick" position="%d,%d" size="40,40" alphatest="blend" zPosition="2" />'
			% (c, i, x + COLUMN_W - 60, y + (ROW_H - 40) // 2))
	return "".join(parts)


def _keys_skin():
	"""OK, the arrows and BACK as outlined keys, as the guide draws them."""
	parts = []
	for x, key, label in ((60, "OK", "Choose"), (330, "◀ ▶", "Sound or subtitles"), (750, "BACK", "Close")):
		parts.append('<eLabel position="%d,%d" size="96,40" backgroundColor="%s" />' % (x, FOOTER_Y, theme.TEXT_MUTED))
		parts.append('<eLabel text="%s" position="%d,%d" size="92,36" font="Regular;24" halign="center" valign="center" foregroundColor="%s" backgroundColor="%s" />'
			% (key, x + 2, FOOTER_Y + 2, theme.TEXT, theme.POPUP))
		parts.append('<eLabel text="%s" position="%d,%d" size="300,40" font="Regular;26" valign="center" foregroundColor="%s" transparent="1" />'
			% (label, x + 110, FOOTER_Y, theme.TEXT))
	return "".join(parts)


def _set_icon(widget, name):
	if name and widget.instance is not None:
		widget.instance.setPixmap(LoadPixmap(icons.icon_path(name), cached=True))
		widget.show()
	else:
		widget.hide()


def _colour(widget, background=None, foreground=None):
	instance = widget.instance
	if instance is None:
		return
	if background is not None:
		instance.setBackgroundColor(gRGB(theme.rgb(background)))
	if foreground is not None:
		instance.setForegroundColor(gRGB(theme.rgb(foreground)))
	instance.invalidate()


class SoundAndSubtitles(Screen):
	"""LEFT/RIGHT picks the column, UP/DOWN the row, OK switches to it straight away;
	what's playing has a tick."""

	skin = """
	<screen name="GullionSoundAndSubtitles" position="center,center" size="%(w)d,%(h)d" flags="wfNoBorder" backgroundColor="%(card)s">
		%(frame)s
		<eLabel text="Sound and subtitles" position="60,40" size="800,56" font="Regular;40" foregroundColor="%(text)s" transparent="1" />
		%(columns)s
		%(keys)s
	</screen>""" % {
		"w": WIDTH, "h": HEIGHT, "card": theme.POPUP, "frame": theme.frame(WIDTH, HEIGHT), "text": theme.TEXT,
		"columns": "".join(_column_skin(c) for c in (SOUND, SUBTITLES)), "keys": _keys_skin(),
	}

	skin = scale.skin(skin)

	def __init__(self, session, infobar, focus="audio"):
		Screen.__init__(self, session)
		self.setTitle("Sound and subtitles")
		self.infobar = infobar
		for c in (SOUND, SUBTITLES):
			self["col%d_icon" % c] = Pixmap()
			self["col%d_heading" % c] = Label(("Sound", "Subtitles")[c])
			for i in range(ROWS):
				self["col%d_row%d_bg" % (c, i)] = Label()
				self["col%d_row%d_icon" % (c, i)] = Pixmap()
				self["col%d_row%d" % (c, i)] = Label()
				self["col%d_row%d_tick" % (c, i)] = Pixmap()
		self.columns = None
		self.column = SUBTITLES if focus == "subtitles" else SOUND
		self.row = [0, 0]
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"], {
			"ok": self.choose,
			"cancel": self.close,
			"yellow": self.close,
			"up": lambda: self.move(-1),
			"down": lambda: self.move(1),
			"left": lambda: self.switch(SOUND),
			"right": lambda: self.switch(SUBTITLES),
		}, -1)
		self.onLayoutFinish.append(self.refresh)

	# What the service offers

	def service(self):
		return self.session.nav.getCurrentService()

	def tracks(self):
		service = self.service()
		audio = service and service.audioTracks()
		if not audio:
			return [], -1
		found = []
		for i in range(min(audio.getNumberOfTracks(), MAX_TRACKS)):
			info = audio.getTrackInfo(i)
			found.append((i, track_label(info.getLanguage(), info.getDescription())))
		return found, audio.getCurrentTrack()

	def subtitles(self):
		subtitle = None
		getter = getattr(self.infobar, "getCurrentServiceSubtitle", None)
		if getter is not None:
			subtitle = getter()
		listed = subtitle and subtitle.getSubtitleList() or []
		current = getattr(self.infobar, "selected_subtitle", None)
		return [tuple(entry) for entry in listed][:MAX_SUBTITLES], current and tuple(current)

	def build(self):
		"""[sound rows, subtitle rows], each row (label, value, playing, icon name or None).
		A column with nothing to choose has a single note row whose value is the marker NOTE."""
		tracks, current_track = self.tracks()
		if len(tracks) > 1:
			sound = [(label, index, index == current_track, "audio_description" if label == "Audio description" else None)
				for index, label in tracks]
		else:
			sound = [("Only one sound track", NOTE, False, None)]
		listed, current = self.subtitles()
		if listed:
			subtitles = [("Off", None, not current, "subtitles_off")]
			subtitles += [(subtitle_label(entry), entry, current is not None and entry[:4] == current[:4], "subtitles") for entry in listed]
		else:
			subtitles = [("None for this programme", NOTE, False, None)]
		return [sound, subtitles]

	def choosable(self, column):
		return self.columns and self.columns[column][0][1] is not NOTE

	# Moving and choosing

	def refresh(self):
		first = self.columns is None
		self.columns = self.build()
		if first:
			for c in (SOUND, SUBTITLES):
				playing = [i for i, row in enumerate(self.columns[c]) if row[2]]
				self.row[c] = playing[0] if playing else 0
			if not self.choosable(self.column) and self.choosable(1 - self.column):
				self.column = 1 - self.column
		self.paint()

	def move(self, step):
		rows = self.columns[self.column]
		self.row[self.column] = max(0, min(len(rows) - 1, self.row[self.column] + step))
		self.paint()

	def switch(self, column):
		if self.choosable(column):
			self.column = column
			self.paint()

	def choose(self):
		if not self.choosable(self.column):
			return
		label, value, playing, icon = self.columns[self.column][self.row[self.column]]
		if self.column == SOUND:
			audio = self.service() and self.service().audioTracks()
			if audio:
				audio.selectTrack(value)
		else:
			enable = getattr(self.infobar, "enableSubtitle", None)
			if enable is not None:
				enable(value)
		self.refresh()

	# Drawing

	def paint(self):
		for c in (SOUND, SUBTITLES):
			focused = c == self.column and self.choosable(c)
			_set_icon(self["col%d_icon" % c], "sound" if c == SOUND else "subtitles")
			_colour(self["col%d_heading" % c], foreground=theme.TEXT if focused else theme.TEXT_MUTED)
			rows = self.columns[c] if self.columns else []
			for i in range(ROWS):
				prefix = "col%d_row%d" % (c, i)
				if i >= len(rows):
					for part in ("_bg", "_icon", "", "_tick"):
						self[prefix + part].hide()
					continue
				label, value, playing, icon = rows[i]
				note = value is NOTE
				lit = focused and i == self.row[c] and not note
				self[prefix].setText(label)
				self[prefix].show()
				if note:
					self[prefix + "_bg"].hide()
				else:
					self[prefix + "_bg"].show()
					_colour(self[prefix + "_bg"], background=theme.CARD_SELECTED if lit else theme.CARD)
				_colour(self[prefix], foreground=theme.TEXT_ON_SELECTED if lit else (theme.TEXT_MUTED if note else theme.TEXT))
				_set_icon(self[prefix + "_icon"], icon and (icon + "_on_light" if lit else icon))
				_set_icon(self[prefix + "_tick"], playing and ("check_on_light" if lit else "check"))
