# -*- coding: utf-8 -*-
"""Recordings: the box's recorded programmes as a list, with a large picture and the
details of the one chosen beside it.

	UP/DOWN  choose (CH+/- a page at a time)    OK    watch, or carry on from where it was left
	BLUE     change the order                    RED   delete

The YELLOW Recordings card on Home opens this list.
"""
import time

from enigma import eServiceReference
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from . import store as recordings, thumbnails
from .. import theme
from ..tv import picon, serviceinfo
from ..ui import icons, scale, tiles
from ..ui.background import Background
from ..ui.popups import GullionChoice

FRAME_LIMIT = 20  # newest recordings given a picture each time the list opens

# The list on the left: a frame from each recording, its name and when.
ROWS = 5
LIST_X, LIST_Y, LIST_W = 60, 176, 980
ROW_H, ROW_STEP = 148, 160
THUMB_W, THUMB_H = 240, 135
LOGO_W, LOGO_H = 180, 108
EDGE = 4  # the chosen row's outline

# The chosen recording on the right.
DETAIL_X, DETAIL_W = 1110, 750
PICTURE_Y, PICTURE_H = 60, 422
BIG_LOGO_W, BIG_LOGO_H = 330, 198
CODE_ICONS = 4
FOOTER_Y = 1004
RECORD_SIZES = (13, 17, 26, 52)  # the red record mark, when there's no picture or logo

STATUS_COLOURS = {"New": theme.ACCENT, "Part watched": theme.ACCENT, "Recording now": theme.KEY_RED}


def _channel_name(ref):
	from ServiceReference import ServiceReference
	return ServiceReference(ref).getServiceName().replace("\xc2\x86", "").replace("\xc2\x87", "")


def read_recordings():
	"""(recordings, drive state). Runs in the background: the drive may need to spin up."""
	return recordings.list_recordings(channel_name=_channel_name), recordings.storage()[0]


def empty_message(state):
	if state == recordings.MISSING:
		return "Recording isn't set up on this box. Ask Tech Support to check the recording drive."
	return "No recordings yet. Press REC while watching, or record from the TV Guide."


def make_frames(background, found, reread):
	"""Make pictures for recordings that don't have one, then show them. Once every
	picture exists (or ffmpeg isn't installed) nothing more happens."""
	if any(thumbnails.needs_frame(recording) for recording in found[:FRAME_LIMIT]):
		background.run(lambda: thumbnails.make_missing(found, FRAME_LIMIT), lambda made, error: made and reread())


def play_recording(session, recording, done, from_start=False):
	from .player import RecordingPlayer

	if from_start:
		# The player offers to carry on from the last stop; forget it so it starts at the top.
		recordings.forget_position(recording)
	session.openWithCallback(done, RecordingPlayer, eServiceReference(recording.service_ref), recording)


def recording_now(session, recording):
	"""True while the box is still recording this file."""
	try:
		from timer import TimerEntry
		timers = session.nav.RecordTimer.timer_list
	except Exception:
		return False
	for timer in timers:
		if timer.state == TimerEntry.StateRunning and (getattr(timer, "Filename", "") or "") + ".ts" == recording.path:
			return True
	return False


def status(recording, recording_now=False):
	if recording_now:
		return "Recording now"
	if recording.watched:
		return "Watched"
	if recording.in_progress:
		return "Part watched"
	if not recording.position:
		return "New"
	return ""


def minutes(seconds):
	total = max(1, int(seconds) // 60) if seconds else 0
	if total >= 60:
		return "%d hr %d min" % (total // 60, total % 60) if total % 60 else "%d hr" % (total // 60)
	return "%d min" % total


def short_when(recording):
	"""Tue 27 Oct  ·  20:00, including the year when it isn't this year."""
	day = time.localtime(recording.begin)
	date = "%s %d %s" % (time.strftime("%a", day), day.tm_mday, time.strftime("%b", day))
	if day.tm_year != time.localtime().tm_year:
		date += " %d" % day.tm_year
	parts = [date, time.strftime("%H:%M", day)]
	if recording.duration:
		parts.append(minutes(recording.duration))
	return "  ·  ".join(parts)


def long_when(recording):
	"""Recorded Tuesday 27 October at 20:00, with a year for older recordings."""
	day = time.localtime(recording.begin)
	date = "%s %d %s" % (time.strftime("%A", day), day.tm_mday, time.strftime("%B", day))
	if day.tm_year != time.localtime().tm_year:
		date += " %d" % day.tm_year
	return "Recorded %s at %s" % (date, time.strftime("%H:%M", day))


def watched_line(recording):
	"""35 min watched  ·  23 min left, or None when it hasn't been started."""
	if not recording.in_progress:
		return None
	return "%s watched  ·  %s left" % (minutes(recording.position), minutes(recording.duration - recording.position))


def _row_skin(i):
	y = LIST_Y + i * ROW_STEP
	tx = LIST_X + EDGE + 12 + THUMB_W + 28
	tw = LIST_X + LIST_W - tx - 20
	ty = y + EDGE + (ROW_H - 2 * EDGE - THUMB_H) // 2
	tleft = LIST_X + EDGE + 12
	return """
		<widget name="row%(i)d_edge" position="%(x)d,%(y)d" size="%(w)d,%(h)d" backgroundColor="%(accent)s" zPosition="1" />
		<widget name="row%(i)d_bg" position="%(ix)d,%(iy)d" size="%(iw)d,%(ih)d" backgroundColor="%(bg)s" zPosition="2" />
		<widget name="row%(i)d_backdrop" position="%(tl)d,%(ty)d" size="%(tw0)d,%(th)d" backgroundColor="%(card)s" zPosition="3" />
		<widget name="row%(i)d_logo" position="%(lx)d,%(ly)d" size="%(lw)d,%(lh)d" alphatest="blend" zPosition="4" />
		<widget name="row%(i)d_icon" position="%(cx)d,%(cy)d" size="52,52" alphatest="blend" zPosition="4" />
		<widget name="row%(i)d_image" position="%(tl)d,%(ty)d" size="%(tw0)d,%(th)d" alphatest="blend" zPosition="5" />
		<widget name="row%(i)d_progress" position="%(tl)d,%(py)d" size="%(tw0)d,6" foregroundColor="%(accent)s" backgroundColor="%(divider)s" borderWidth="0" zPosition="6" />
		<widget name="row%(i)d_title" position="%(tx)d,%(t1)d" size="%(tw)d,50" font="Regular;38" noWrap="1" foregroundColor="%(text)s" transparent="1" zPosition="3" />
		<widget name="row%(i)d_when" position="%(tx)d,%(t2)d" size="%(tw)d,40" font="Regular;29" noWrap="1" foregroundColor="%(muted)s" transparent="1" zPosition="3" />
		<widget name="row%(i)d_status" position="%(tx)d,%(t3)d" size="%(tw)d,38" font="Regular;28" noWrap="1" foregroundColor="%(accent)s" transparent="1" zPosition="3" />""" % {
		"i": i, "x": LIST_X, "y": y, "w": LIST_W, "h": ROW_H,
		"ix": LIST_X + EDGE, "iy": y + EDGE, "iw": LIST_W - 2 * EDGE, "ih": ROW_H - 2 * EDGE,
		"tl": tleft, "ty": ty, "tw0": THUMB_W, "th": THUMB_H, "py": ty + THUMB_H - 6,
		"lx": tleft + (THUMB_W - LOGO_W) // 2, "ly": ty + (THUMB_H - LOGO_H) // 2, "lw": LOGO_W, "lh": LOGO_H,
		"cx": tleft + (THUMB_W - 52) // 2, "cy": ty + (THUMB_H - 52) // 2,
		"tx": tx, "tw": tw, "t1": y + 14, "t2": y + 64, "t3": y + 102,
		"accent": theme.ACCENT, "bg": theme.BACKGROUND, "card": theme.CARD, "divider": theme.DIVIDER,
		"text": theme.TEXT, "muted": theme.TEXT_MUTED,
	}


def _code_icons_skin(y):
	return "".join('<widget name="code%d" position="%d,%d" size="40,40" alphatest="blend" zPosition="2" />'
		% (i, DETAIL_X + DETAIL_W - 40 - i * 52, y) for i in range(CODE_ICONS))


class Recordings(Screen):
	skin = """
	<screen name="GullionRecordings" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="Recordings" position="60,34" size="900,76" font="Regular;64" foregroundColor="%(text)s" transparent="1" />
		<widget name="count" position="60,112" size="980,44" font="Regular;32" foregroundColor="%(muted)s" transparent="1" />
		%(rows)s
		<widget name="empty" position="60,200" size="980,200" font="Regular;34" foregroundColor="%(muted)s" transparent="1" />
		<widget name="page" position="640,118" size="400,36" font="Regular;28" halign="right" foregroundColor="%(muted)s" transparent="1" />

		<eLabel position="1074,60" size="2,900" backgroundColor="%(divider)s" />

		<widget name="picture_backdrop" position="%(dx)d,%(py)d" size="%(dw)d,%(ph)d" backgroundColor="%(card)s" zPosition="1" />
		<widget name="picture_logo" position="%(blx)d,%(bly)d" size="%(blw)d,%(blh)d" alphatest="blend" zPosition="2" />
		<widget name="picture_icon" position="%(bix)d,%(biy)d" size="52,52" alphatest="blend" zPosition="2" />
		<widget name="picture" position="%(dx)d,%(py)d" size="%(dw)d,%(ph)d" alphatest="blend" zPosition="3" />
		<widget name="rec_pill" position="%(pill_x)d,%(pill_y)d" size="96,40" alphatest="blend" zPosition="4" />

		<widget name="title" position="%(dx)d,508" size="%(dw)d,64" font="Regular;52" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		<widget name="channel" position="%(dx)d,580" size="%(lw)d,42" font="Regular;30" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		%(codes)s
		<widget name="when" position="%(dx)d,622" size="%(dw)d,42" font="Regular;30" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		<widget name="length" position="%(dx)d,664" size="%(dw)d,42" font="Regular;30" noWrap="1" foregroundColor="%(muted)s" transparent="1" />
		<widget name="description" position="%(dx)d,720" size="%(dw)d,148" font="Regular;30" foregroundColor="%(text)s" transparent="1" />
		<widget name="progress" position="%(dx)d,880" size="%(dw)d,10" foregroundColor="%(accent)s" backgroundColor="%(divider)s" borderWidth="0" />
		<widget name="watched" position="%(dx)d,898" size="%(dw)d,36" font="Regular;26" foregroundColor="%(muted)s" transparent="1" />

		<eLabel position="60,978" size="1800,1" backgroundColor="%(divider)s" />
		<ePixmap pixmap="%(red)s" position="60,%(dot_y)d" size="24,24" alphatest="blend" />
		<eLabel text="Delete" position="100,%(footer_y)d" size="240,44" font="Regular;28" valign="center" foregroundColor="%(text)s" transparent="1" />
		<ePixmap pixmap="%(blue)s" position="380,%(dot_y)d" size="24,24" alphatest="blend" />
		<eLabel text="Sort" position="420,%(footer_y)d" size="180,44" font="Regular;28" valign="center" foregroundColor="%(text)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER,
		"card": theme.CARD, "accent": theme.ACCENT,
		"rows": "".join(_row_skin(i) for i in range(ROWS)),
		"dx": DETAIL_X, "dw": DETAIL_W, "lw": DETAIL_W - CODE_ICONS * 52, "py": PICTURE_Y, "ph": PICTURE_H,
		"blx": DETAIL_X + (DETAIL_W - BIG_LOGO_W) // 2, "bly": PICTURE_Y + (PICTURE_H - BIG_LOGO_H) // 2,
		"blw": BIG_LOGO_W, "blh": BIG_LOGO_H,
		"bix": DETAIL_X + (DETAIL_W - 52) // 2, "biy": PICTURE_Y + (PICTURE_H - 52) // 2,
		"pill_x": DETAIL_X + 20, "pill_y": PICTURE_Y + 20,
		"codes": _code_icons_skin(581),
		"footer_y": FOOTER_Y, "dot_y": FOOTER_Y + 10,
		"red": icons.key_icon("red"), "blue": icons.key_icon("blue"),
	}

	skin = scale.skin(skin)

	def __init__(self, session, stop_live=True):
		"""stop_live: stop live TV while open and put it back on the way out. Watch
		again, which has already stopped it, passes False."""
		Screen.__init__(self, session)
		self.setTitle("Recordings")
		for i in range(ROWS):
			for part in ("edge", "bg", "backdrop", "title", "when", "status"):
				self["row%d_%s" % (i, part)] = Label()
			for part in ("logo", "icon", "image"):
				self["row%d_%s" % (i, part)] = Pixmap()
			self["row%d_progress" % i] = ProgressBar()
		for name in ("count", "empty", "page", "picture_backdrop", "title", "channel", "when", "length", "description", "watched"):
			self[name] = Label()
		for name in ("picture", "picture_logo", "picture_icon", "rec_pill"):
			self[name] = Pixmap()
		for i in range(CODE_ICONS):
			self["code%d" % i] = Pixmap()
		self["progress"] = ProgressBar()

		self.deleting = False
		self.pending_delete = None
		self.recordings = None
		self.storage = None
		self.order = recordings.NEWEST
		self.selected = 0
		self.top = 0
		self.thumbs = tiles.Pictures(THUMB_W, THUMB_H)
		self.logos = tiles.Pictures(LOGO_W, LOGO_H)
		self.big = tiles.Pictures(DETAIL_W, PICTURE_H)
		self.big_logos = tiles.Pictures(BIG_LOGO_W, BIG_LOGO_H)
		self.background = Background()
		self.live = session.nav.getCurrentlyPlayingServiceReference() if stop_live else None

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ColorActions", "MenuActions", "EPGSelectActions"], {
			"up": lambda: self.move(-1),
			"down": lambda: self.move(1),
			"left": lambda: self.move(-ROWS),
			"right": lambda: self.move(ROWS),
			# CH+/-: nextBouquet/prevBouquet on OpenATV 6.4, nextService/prevService on 7.x.
			"nextBouquet": lambda: self.move(-ROWS),
			"prevBouquet": lambda: self.move(ROWS),
			"nextService": lambda: self.move(-ROWS),
			"prevService": lambda: self.move(ROWS),
			"ok": self.ok,
			"red": self.delete_option,
			"blue": self.change_order,
			"menu": self.options,
			"cancel": self.leave,
		}, -1)
		self.onLayoutFinish.append(self.started)

	# Loading

	def started(self):
		if self.live is not None:
			self.session.nav.stopService()
		self.paint()
		self.load()

	def load(self, *args):
		self.background.run(read_recordings, self.ready)

	def ready(self, found, error):
		chosen = self.chosen()
		found, self.storage = found if found else ([], recordings.MISSING)
		self.recordings = recordings.sort(found, self.order)
		# Stay on the same recording when the list is read again.
		paths = [recording.path for recording in self.recordings]
		if chosen is not None and chosen.path in paths:
			self.select(paths.index(chosen.path))
		else:
			self.select(min(self.selected, max(0, len(self.recordings) - 1)))
		self.paint()
		make_frames(self.background, found, self.load)

	def returned(self, *args):
		# The player may have started live TV again as it closed.
		if self.live is not None:
			self.session.nav.stopService()
		self.load()

	def leave(self):
		self.background.stop()
		if self.live is not None:
			self.session.nav.playService(self.live)
		self.close()

	# Choosing

	def chosen(self):
		if not self.recordings:
			return None
		return self.recordings[self.selected]

	def select(self, index):
		self.selected = index
		if self.selected < self.top:
			self.top = self.selected
		elif self.selected >= self.top + ROWS:
			self.top = self.selected - ROWS + 1
		self.top = max(0, min(self.top, len(self.recordings or []) - ROWS))

	def move(self, step):
		if not self.recordings:
			return
		self.select(max(0, min(len(self.recordings) - 1, self.selected + step)))
		self.paint()

	def change_order(self):
		self.order = recordings.SORTS[(recordings.SORTS.index(self.order) + 1) % len(recordings.SORTS)]
		if self.recordings:
			self.recordings = recordings.sort(self.recordings, self.order)
			# Show the beginning of every new order so the change is immediately clear.
			self.top = 0
			self.select(0)
		self.paint()

	def ok(self):
		if self.deleting:
			return
		recording = self.chosen()
		if recording is not None:
			play_recording(self.session, recording, self.returned)

	def options(self):
		if self.deleting:
			return
		recording = self.chosen()
		if recording is None:
			return
		choices = [("Watch from the start", "start")] if recording.in_progress else []
		if not recording_now(self.session, recording):
			choices.append(("Delete", "delete"))
		choices.append(("Cancel", None))
		self.session.openWithCallback(self.option_chosen, GullionChoice, recording.title, choices,
			"%s  ·  %s" % (short_when(recording), recordings.file_size(recording.size)))

	def delete_option(self):
		"""RED goes straight to the safe delete confirmation for the chosen recording."""
		if self.deleting:
			return
		recording = self.chosen()
		if recording is None or self.delete_blocked(recording):
			return
		self.pending_delete = recording
		self.session.openWithCallback(self.delete_chosen, GullionChoice, "Delete %s?" % recording.title,
			[("Delete", "delete"), ("Keep it", None)], "It goes to the recycle bin, so Tech Support can bring it back.")

	def option_chosen(self, choice=None):
		if self.deleting:
			return
		recording = self.chosen()
		if recording is None:
			return
		if choice == "start":
			play_recording(self.session, recording, self.returned, from_start=True)
		elif choice == "delete":
			if self.deleting or self.delete_blocked(recording):
				return
			self.pending_delete = recording
			self.session.openWithCallback(self.delete_chosen, GullionChoice, "Delete %s?" % recording.title,
				[("Delete", "delete"), ("Keep it", None)], "It goes to the recycle bin, so Tech Support can bring it back.")

	def delete_blocked(self, recording):
		if not recording_now(self.session, recording):
			return False
		self.session.open(GullionChoice, "Still recording", [("OK", None)],
			"Wait until this programme has finished recording before deleting it.")
		return True

	def delete_chosen(self, choice=None):
		recording = self.pending_delete
		self.pending_delete = None
		if choice != "delete" or recording is None or self.deleting:
			return
		# Recheck after confirmation: a timer may have started while it was open.
		if self.delete_blocked(recording):
			return
		self.deleting = True
		self.background.run(lambda: recordings.move_to_trash(recording), self.deleted)

	def deleted(self, result, error):
		self.deleting = False
		if error is not None:
			detail = "Please try again, or ask Tech Support to check the recording drive."
			if getattr(error, "recovery_needed", False):
				detail = "Some files are in the recycle bin. Ask Tech Support to restore them."
			self.session.open(GullionChoice, "Could not delete recording", [("OK", None)], detail)
		self.load()

	# Drawing

	def paint(self):
		found = self.recordings or []
		if self.recordings is None:
			self["count"].setText("Looking for recordings...")
		elif not found:
			self["count"].setText("")
		else:
			count = "1 programme" if len(found) == 1 else "%d programmes" % len(found)
			self["count"].setText("%s  ·  %s" % (count, recordings.SORT_NAMES[self.order]))
		self["empty"].setText("" if found or self.recordings is None else empty_message(self.storage))
		for i in range(ROWS):
			index = self.top + i
			if index < len(found):
				self.draw_row(i, found[index], index == self.selected)
			else:
				for part in ("edge", "bg", "backdrop", "logo", "icon", "image", "progress", "title", "when", "status"):
					self["row%d_%s" % (i, part)].hide()
		pages = (len(found) + ROWS - 1) // ROWS
		self["page"].setText("%d of %d" % (self.selected + 1, len(found)) if pages > 1 else "")
		self.draw_details(self.chosen())

	def draw_row(self, i, recording, chosen):
		prefix = "row%d_" % i
		for part in ("bg", "backdrop", "title", "when", "status"):
			self[prefix + part].show()
		if chosen:
			self[prefix + "edge"].show()
		else:
			self[prefix + "edge"].hide()
		tiles.colour(self[prefix + "bg"], background=theme.ROW_SELECTED if chosen else theme.BACKGROUND)
		self[prefix + "title"].setText(recording.title)
		self[prefix + "when"].setText(short_when(recording))
		state = status(recording, recording_now(self.session, recording))
		self[prefix + "status"].setText(state)
		tiles.colour(self[prefix + "status"], foreground=STATUS_COLOURS.get(state, theme.TEXT_MUTED))
		self.draw_picture(prefix + "image", prefix + "logo", prefix + "icon", recording, self.thumbs, self.logos)
		if recording.in_progress:
			self[prefix + "progress"].setValue(int(recording.progress * 100))
			self[prefix + "progress"].show()
		else:
			self[prefix + "progress"].hide()

	def draw_picture(self, image, logo, icon, recording, pictures, logos):
		"""A frame from the recording; until there is one, the channel's logo; failing that, a record mark."""
		if _show(self[image], pictures.get(recording.image)):
			self[logo].hide()
			self[icon].hide()
		elif _show(self[logo], logos.get(picon.picon_path(recording.channel_ref))):
			self[icon].hide()
		else:
			_show(self[icon], LoadPixmap(icons.icon_path("record", 52, RECORD_SIZES), cached=True))

	def draw_details(self, recording):
		parts = ("picture_backdrop", "picture", "picture_logo", "picture_icon", "rec_pill", "title", "channel", "when",
			"length", "description", "progress", "watched")
		if recording is None:
			for name in parts:
				self[name].hide()
			for i in range(CODE_ICONS):
				self["code%d" % i].hide()
			return
		for name in ("picture_backdrop", "title", "channel", "when", "length", "description"):
			self[name].show()
		self.draw_picture("picture", "picture_logo", "picture_icon", recording, self.big, self.big_logos)
		if recording_now(self.session, recording):
			_show(self["rec_pill"], LoadPixmap(icons.rec_pill(), cached=True))
		else:
			self["rec_pill"].hide()
		description, codes = serviceinfo.split_codes(recording.description)
		self["title"].setText(recording.title)
		self["channel"].setText(recording.channel)
		self["when"].setText(long_when(recording))
		self["length"].setText("  ·  ".join(part for part in (minutes(recording.duration), recordings.file_size(recording.size)) if part))
		self["description"].setText(description or "No description for this recording.")
		# The access codes as icons at the end of the channel line, packed from the right.
		names = [serviceinfo.BADGE_ICONS[code] for code in codes if code in serviceinfo.BADGE_ICONS]
		for i in range(CODE_ICONS):
			name = names[len(names) - 1 - i] if i < len(names) else None
			if name:
				_show(self["code%d" % i], LoadPixmap(icons.icon_path(name), cached=True))
			else:
				self["code%d" % i].hide()
		line = watched_line(recording)
		if line:
			self["progress"].setValue(int(recording.progress * 100))
			self["progress"].show()
			self["watched"].setText(line)
			self["watched"].show()
		else:
			self["progress"].hide()
			self["watched"].setText("Watched" if recording.watched else "")
			self["watched"].show()


def _show(widget, picture):
	if picture is None or widget.instance is None:
		widget.hide()
		return False
	widget.instance.setPixmap(picture)
	widget.show()
	return True
