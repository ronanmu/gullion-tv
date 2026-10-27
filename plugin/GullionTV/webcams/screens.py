# -*- coding: utf-8 -*-
"""Webcams: a grid of live cameras from webcams.yaml, and a full-screen player."""
import threading

from enigma import eServiceReference, ePicLoad, eTimer, gRGB, iServiceInformation
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen

from . import config as webcamconfig, sources
from .. import theme
from ..ui.popups import GullionChoice

COLS, ROWS = 3, 2
PER_PAGE = COLS * ROWS
TILE_W, TILE_H, IMAGE_H = 560, 410, 315
GAP, LEFT, TOP = 30, 90, 160
TILE_PARTS = ("frame", "backdrop", "initial", "image", "group", "band", "name", "status")


def _tile_skin(index):
	x = LEFT + (index % COLS) * (TILE_W + GAP)
	y = TOP + (index // COLS) * (TILE_H + GAP)
	values = {
		"i": index, "x": x, "y": y, "fx": x - 5, "fy": y - 5, "fw": TILE_W + 10, "fh": TILE_H + 10,
		"w": TILE_W, "ih": IMAGE_H, "by": y + IMAGE_H, "bh": TILE_H - IMAGE_H,
		"tx": x + 24, "tw": TILE_W - 48, "ny": y + IMAGE_H + 12, "sy": y + IMAGE_H + 56,
		"gx": x + 16, "gy": y + 16,
		"bg": theme.BACKGROUND, "card": theme.CARD, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
	}
	return """
		<widget name="tile%(i)d_frame" position="%(fx)d,%(fy)d" size="%(fw)d,%(fh)d" backgroundColor="%(bg)s" zPosition="1" />
		<widget name="tile%(i)d_backdrop" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" backgroundColor="%(card)s" zPosition="2" />
		<widget name="tile%(i)d_initial" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" font="Regular;28" halign="center" valign="center" foregroundColor="%(muted)s" transparent="1" zPosition="3" />
		<widget name="tile%(i)d_image" position="%(x)d,%(y)d" size="%(w)d,%(ih)d" zPosition="4" />
		<widget name="tile%(i)d_group" position="%(gx)d,%(gy)d" size="240,36" font="Regular;22" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(bg)s" zPosition="5" />
		<widget name="tile%(i)d_band" position="%(x)d,%(by)d" size="%(w)d,%(bh)d" backgroundColor="%(card)s" zPosition="2" />
		<widget name="tile%(i)d_name" position="%(tx)d,%(ny)d" size="%(tw)d,44" font="Regular;34" foregroundColor="%(text)s" transparent="1" zPosition="3" />
		<widget name="tile%(i)d_status" position="%(tx)d,%(sy)d" size="%(tw)d,34" font="Regular;26" foregroundColor="%(muted)s" transparent="1" zPosition="3" />""" % values


class WebcamList(Screen):
	skin = """
	<screen name="GullionWebcams" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%(bg)s">
		<eLabel text="Webcams" position="90,44" size="800,60" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget source="global.CurrentTime" render="Label" position="1330,50" size="500,50" font="Regular;32" halign="right" foregroundColor="%(text)s" transparent="1">
			<convert type="ClockToText">Format:%%a %%d %%b   %%H:%%M</convert>
		</widget>
		<eLabel position="90,130" size="1740,1" backgroundColor="%(divider)s" />
		%(tiles)s
		<widget name="empty_title" position="90,300" size="1740,64" font="Regular;44" foregroundColor="%(text)s" transparent="1" />
		<widget name="empty_detail" position="90,380" size="1740,100" font="Regular;30" foregroundColor="%(muted)s" transparent="1" />
		<eLabel text="Arrows to choose   ·   OK to watch   ·   BACK for home" position="90,1030" size="900,36" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="note" position="1000,1030" size="560,36" font="Regular;22" halign="right" foregroundColor="%(muted)s" transparent="1" />
		<widget name="page" position="1580,1030" size="250,36" font="Regular;24" halign="right" foregroundColor="%(muted)s" transparent="1" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "divider": theme.DIVIDER,
		"tiles": "".join(_tile_skin(i) for i in range(PER_PAGE)),
	}

	def __init__(self, session, config_path=webcamconfig.CONFIG_PATH):
		Screen.__init__(self, session)
		self.setTitle("Webcams")
		for i in range(PER_PAGE):
			for part in TILE_PARTS:
				self["tile%d_%s" % (i, part)] = Pixmap() if part == "image" else Label()
		for name in ("empty_title", "empty_detail", "note", "page"):
			self[name] = Label()

		entries, self.problems = webcamconfig.load(config_path)
		# Shown straight away; the background check fills in streams, pictures and status.
		self.webcams = [sources.Webcam(entry) for entry in entries]
		self.entries = entries
		self.selected = 0
		self.changes = 0
		self.painted = -1
		self.closing = False
		self.worker = None
		self.pictures = {}
		self.picload = ePicLoad()
		self.picload.setPara((TILE_W, IMAGE_H, 1, 1, False, 1, theme.CARD))

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "MenuActions"], {
			"left": lambda: self.move(-1),
			"right": lambda: self.move(1),
			"up": lambda: self.move(-COLS),
			"down": lambda: self.move(COLS),
			"ok": self.ok,
			"cancel": self.leave,
			"menu": self.leave,
		}, -1)

		self.poll = eTimer()
		self.poll.callback.append(self.repaint_if_changed)
		self.onLayoutFinish.append(self.started)

	# Background checking

	def started(self):
		self.paint()
		if self.entries:
			self.worker = threading.Thread(target=self.check_all)
			self.worker.daemon = True
			self.worker.start()
			self.poll.start(400, False)

	def check_all(self):
		webcams = sources.expand(self.entries)
		if self.closing:
			return
		if [webcam.name for webcam in webcams] != [webcam.name for webcam in self.webcams]:
			self.webcams = webcams
			self.changes += 1
		for webcam in self.webcams:
			if self.closing:
				return
			sources.check(webcam)
			sources.download_thumbnail(webcam)
			self.changes += 1

	def repaint_if_changed(self):
		if self.painted != self.changes:
			self.paint()

	def leave(self):
		self.closing = True
		self.poll.stop()
		self.close()

	# Navigation

	def move(self, step):
		if not self.webcams:
			return
		target = self.selected + step
		if 0 <= target < len(self.webcams):
			self.selected = target
		elif step == COLS and self.selected // COLS < (len(self.webcams) - 1) // COLS:
			self.selected = len(self.webcams) - 1  # down onto a short last row
		self.paint()

	def ok(self):
		if not self.webcams:
			return
		webcam = self.webcams[self.selected]
		if webcam.stream and webcam.status in (sources.LIVE, sources.READY, sources.CHECKING):
			self.play(webcam)
		elif webcam.status == sources.OFFLINE:
			self.session.openWithCallback(lambda choice: choice and self.play(webcam), GullionChoice, webcam.name,
				[("Try anyway", "play"), ("Back", None)], "This camera isn't live right now." + (" %s." % webcam.detail if webcam.detail else ""))
		elif webcam.status == sources.CHECKING:
			self.session.open(GullionChoice, webcam.name, [("OK", None)], "Still checking this camera. Try again in a moment.")
		else:
			self.session.open(GullionChoice, webcam.name, [("OK", None)],
				"Gullion TV can't reach this camera. Tech Support may need to check its link.")

	def play(self, webcam):
		self.session.open(WebcamPlayer, webcam)

	# Drawing

	def paint(self):
		self.painted = self.changes
		webcams = self.webcams
		# A playlist can turn into more (or fewer) cameras once it's been read.
		self.selected = max(0, min(self.selected, len(webcams) - 1))
		if not webcams:
			self["empty_title"].setText("No webcams yet")
			self["empty_detail"].setText("Tech Support can add them to %s" % webcamconfig.CONFIG_PATH)
			for i in range(PER_PAGE):
				self.show_tile(i, False)
		else:
			self["empty_title"].setText("")
			self["empty_detail"].setText("")
			first = self.selected // PER_PAGE * PER_PAGE
			for i in range(PER_PAGE):
				index = first + i
				if index < len(webcams):
					self.show_tile(i, True)
					self.draw_tile(i, webcams[index], index == self.selected)
				else:
					self.show_tile(i, False)
		pages = (len(webcams) + PER_PAGE - 1) // PER_PAGE
		self["page"].setText("Page %d of %d" % (self.selected // PER_PAGE + 1, pages) if pages > 1 else "")
		if self.problems:
			self["note"].setText("%d webcam%s couldn't be read  ·  %s" % (len(self.problems), "" if len(self.problems) == 1 else "s", self.problems[0]))
		else:
			self["note"].setText("")

	def show_tile(self, i, visible):
		for part in TILE_PARTS:
			widget = self["tile%d_%s" % (i, part)]
			if visible:
				widget.show()
			else:
				widget.hide()

	def draw_tile(self, i, webcam, chosen):
		self["tile%d_name" % i].setText(webcam.name)
		self["tile%d_status" % i].setText(sources.status_line(webcam))
		self["tile%d_group" % i].setText(webcam.group or "")
		if not webcam.group:
			self["tile%d_group" % i].hide()

		picture = self.picture(webcam.thumbnail)
		image = self["tile%d_image" % i]
		if picture is not None and image.instance is not None:
			image.instance.setPixmap(picture)
			self["tile%d_initial" % i].setText("")
		else:
			image.hide()
			self["tile%d_initial" % i].setText("Checking..." if webcam.status == sources.CHECKING and webcam.image else "No picture")

		live = webcam.status in (sources.LIVE, sources.READY)
		if chosen:
			band, name, status = theme.CARD_SELECTED, theme.TEXT_ON_SELECTED, theme.LIVE_ON_LIGHT if live else theme.TEXT_ON_SELECTED_MUTED
		else:
			band, name, status = theme.CARD, theme.TEXT, theme.LIVE if live else theme.TEXT_MUTED
		_colour(self["tile%d_frame" % i], background=theme.CARD_SELECTED if chosen else theme.BACKGROUND)
		_colour(self["tile%d_band" % i], background=band)
		_colour(self["tile%d_name" % i], foreground=name)
		_colour(self["tile%d_status" % i], foreground=status)

	def picture(self, path):
		if not path:
			return None
		if path not in self.pictures:
			decoded = None
			if self.picload.startDecode(path, 0, 0, False) == 0:
				decoded = self.picload.getData()
			self.pictures[path] = decoded
		return self.pictures[path]


class WebcamPlayer(Screen):
	"""Plays one webcam full screen, then puts the previous channel back."""

	skin = """
	<screen name="GullionWebcamPlayer" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="#ff000000">
		<widget name="panel" position="60,860" size="1800,180" backgroundColor="%(bg)s" zPosition="1" />
		<widget name="name" position="90,880" size="1500,60" font="Regular;46" foregroundColor="%(text)s" transparent="1" zPosition="2" />
		<widget name="source" position="90,946" size="900,40" font="Regular;28" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
		<widget name="badge" position="1650,886" size="180,44" font="Regular;26" halign="center" valign="center" foregroundColor="%(on_light)s" backgroundColor="%(live)s" zPosition="2" />
		<widget name="hint" position="1000,992" size="830,36" font="Regular;24" halign="right" foregroundColor="%(muted)s" transparent="1" zPosition="2" />
		<widget name="message" position="410,470" size="1100,140" font="Regular;34" halign="center" valign="center" foregroundColor="%(text)s" backgroundColor="%(popup)s" zPosition="3" />
	</screen>""" % {
		"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED, "live": theme.LIVE,
		"on_light": theme.TEXT_ON_SELECTED, "popup": theme.POPUP,
	}

	BANNER_SECONDS = 6
	GIVE_UP_SECONDS = 20
	BANNER = ("panel", "name", "source", "badge", "hint")

	def __init__(self, session, webcam):
		Screen.__init__(self, session)
		self.setTitle(webcam.name)
		self.webcam = webcam
		self["panel"] = Label()
		self["name"] = Label(webcam.name)
		self["source"] = Label(" · ".join(part for part in (webcam.group, webcam.source_label, webcam.detail) if part))
		self["badge"] = Label("Live" if webcam.status == sources.LIVE else "Stream")
		self["hint"] = Label("OK to show or hide this   ·   BACK to return")
		self["message"] = Label("Connecting...")
		self["actions"] = ActionMap(["OkCancelActions", "MenuActions"], {
			"ok": self.toggle_banner,
			"cancel": self.leave,
			"menu": self.leave,
		}, -1)

		self.previous = session.nav.getCurrentlyPlayingServiceReference()
		self.waited = 0
		self.banner_visible = True
		self.banner_timer = eTimer()
		self.banner_timer.callback.append(self.hide_banner)
		self.watchdog = eTimer()
		self.watchdog.callback.append(self.check_picture)
		self.onLayoutFinish.append(self.start)

	def start(self):
		self.session.nav.playService(eServiceReference(self.webcam.service_ref()))
		self.banner_timer.start(self.BANNER_SECONDS * 1000, True)
		self.watchdog.start(1000, False)

	def check_picture(self):
		self.waited += 1
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		if info and info.getInfo(iServiceInformation.sVideoHeight) > 0:
			self["message"].hide()
			self.watchdog.stop()
		elif self.waited >= self.GIVE_UP_SECONDS:
			self["message"].setText("This camera isn't sending a picture right now.\nBACK to return to webcams.")
			self["message"].show()
			self.watchdog.stop()

	def toggle_banner(self):
		if self.banner_visible:
			self.hide_banner()
		else:
			for name in self.BANNER:
				self[name].show()
			self.banner_visible = True
			self.banner_timer.start(self.BANNER_SECONDS * 1000, True)

	def hide_banner(self):
		for name in self.BANNER:
			self[name].hide()
		self.banner_visible = False

	def leave(self):
		self.banner_timer.stop()
		self.watchdog.stop()
		if self.previous is not None:
			self.session.nav.playService(self.previous)
		else:
			self.session.nav.stopService()
		self.close()


def _colour(widget, background=None, foreground=None):
	instance = widget.instance
	if instance is None:
		return
	if background is not None:
		instance.setBackgroundColor(gRGB(theme.rgb(background)))
	if foreground is not None:
		instance.setForegroundColor(gRGB(theme.rgb(foreground)))
	instance.invalidate()
