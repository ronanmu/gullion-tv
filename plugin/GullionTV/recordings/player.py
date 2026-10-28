# -*- coding: utf-8 -*-
"""Recorded TV with large playback controls, using the box's player underneath."""
import time

from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Screens.InfoBar import MoviePlayer
from Tools.LoadPixmap import LoadPixmap

from .. import theme
from ..tv import serviceinfo
from ..tv.soundsubs import SoundAndSubtitles
from ..ui import icons, scale

TICKS = 90000
HIDE_AFTER = 6000
BUTTONS = ((790, 88), (916, 88), (1042, 88), (1652, 88))


def _buttons_skin():
	parts = []
	for i, (x, width) in enumerate(BUTTONS):
		parts.append('<widget name="control%d_bg" position="%d,337" size="40,4" backgroundColor="%s" />' % (i, x + (width - 40) // 2, theme.ACCENT))
		parts.append('<widget name="control%d_icon" position="%d,283" size="40,40" alphatest="blend" zPosition="2" />' % (i, x + (width - 40) // 2))
	return "".join(parts)


def clock(seconds):
	if seconds is None:
		return "--:--"
	seconds = max(0, int(seconds))
	if seconds >= 3600:
		return "%d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60, seconds % 60)
	return "%d:%02d" % (seconds // 60, seconds % 60)


def recorded_when(begin):
	day = time.localtime(begin)
	date = "%s %d %s" % (time.strftime("%A", day), day.tm_mday, time.strftime("%B", day))
	if day.tm_year != time.localtime().tm_year:
		date += " %d" % day.tm_year
	return "Recorded %s at %s" % (date, time.strftime("%H:%M", day))


class RecordingPlayer(MoviePlayer):
	"""Pause, skip or choose subtitles; stopping returns to Gullion TV."""

	skin = scale.skin('''
	<screen name="GullionRecordingPlayer" position="60,620" size="1800,400" flags="wfNoBorder" backgroundColor="%(bg)s">
		<widget name="programme" position="60,24" size="1360,60" font="Regular;46" noWrap="1" foregroundColor="%(text)s" transparent="1" />
		<widget name="playback_state" position="1440,32" size="300,44" font="Regular;30" halign="right" foregroundColor="%(accent)s" transparent="1" />
		<widget name="description" position="60,90" size="1680,72" font="Regular;28" foregroundColor="%(muted)s" transparent="1" />
		<widget name="progress_focus" position="56,174" size="1688,18" backgroundColor="%(text)s" />
		<widget name="progress" position="60,178" size="1680,10" foregroundColor="%(accent)s" backgroundColor="%(divider)s" borderWidth="0" zPosition="2" />
		<widget name="elapsed" position="60,200" size="450,36" font="Regular;26" foregroundColor="%(text)s" transparent="1" />
		<widget name="remaining" position="1200,200" size="540,36" font="Regular;26" halign="right" foregroundColor="%(muted)s" transparent="1" />
		<widget name="recorded" position="60,283" size="560,40" font="Regular;24" foregroundColor="%(muted)s" transparent="1" />
		<widget name="notice" position="60,332" size="620,40" font="Regular;22" foregroundColor="%(muted)s" transparent="1" />
		%(buttons)s
	</screen>''' % {"bg": theme.BACKGROUND, "text": theme.TEXT, "muted": theme.TEXT_MUTED,
		"accent": theme.ACCENT, "divider": theme.DIVIDER, "buttons": _buttons_skin()})

	def __init__(self, session, service, recording):
		self.controls_ready = False
		self.subtitle_dialog_open = False
		MoviePlayer.__init__(self, session, service)
		# Do not allow the active skin's MoviePlayer entry to replace this panel.
		self.skinName = "GullionRecordingPlayer"
		self.recording = recording
		self.control = 1
		self.progress_selected = False
		self.subtitle_tracks = []
		for name in ("programme", "playback_state", "description", "elapsed", "remaining", "recorded", "notice"):
			self[name] = Label()
		self["programme"].setText(recording.title)
		self["description"].setText(serviceinfo.split_codes(recording.description)[0])
		self["recorded"].setText(recorded_when(recording.begin))
		self["progress"] = ProgressBar()
		self["progress_focus"] = Label()
		for i in range(len(BUTTONS)):
			self["control%d_bg" % i] = Label()
			self["control%d_icon" % i] = Pixmap()
		self.controls_timer = eTimer()
		self.controls_timer.callback.append(self.hide_controls)
		self.progress_timer = eTimer()
		self.progress_timer.callback.append(self.refresh_playback)
		self["GullionPlaybackActions"] = ActionMap(["GullionPlaybackActions"], {
			"left": lambda: self.move_or_scrub(-1), "right": lambda: self.move_or_scrub(1),
			"up": self.select_progress, "down": self.select_controls,
			"ok": self.activate_control, "show": self.show_controls, "back": self.back,
			"pause": self.toggle_pause, "play": self.play,
			"rewind": lambda: self.skip(-30), "forward": lambda: self.skip(30),
			"subtitles": self.open_subtitles, "stop": self.stop_playback,
			"release": self.consume_release,
		}, -10)
		changed = getattr(self, "onPlayStateChanged", None)
		if changed is not None:
			changed.append(self.playback_changed)
		self.onLayoutFinish.append(self.started)
		self.onClose.append(self.cleanup)
		# The stock hide timer is replaced locally, without changing box settings.
		for name in ("hideTimer", "DimmingTimer"):
			timer = getattr(self, name, None)
			if timer is not None:
				timer.stop()

	def consume_release(self):
		# Consume key-up as well as key-down, so stock maps cannot act twice.
		return None

	def started(self):
		self.controls_ready = True
		self.progress_timer.start(1000, False)
		self.show_controls()

	def paused(self):
		return getattr(self, "seekstate", None) == getattr(self, "SEEK_STATE_PAUSE", "paused")

	def startHideTimer(self):
		if not self.controls_ready:
			return
		self.controls_timer.stop()
		if not self.paused() and not self.subtitle_dialog_open:
			self.controls_timer.start(HIDE_AFTER, True)

	def _mayShow(self):
		# Our panel replaces the separate stock pause/fast-forward badge.
		dialog = getattr(self, "pvrStateDialog", None)
		if dialog is not None:
			dialog.hide()

	def show_controls(self):
		if not self.controls_ready:
			return
		self.show()
		self.refresh_playback()
		self.startHideTimer()

	def hide_controls(self):
		self.controls_timer.stop()
		self.hide()

	def back(self):
		if getattr(self, "shown", False):
			self.hide_controls()
		else:
			self.stop_playback()

	def cleanup(self):
		self.controls_ready = False
		self.controls_timer.stop()
		self.progress_timer.stop()
		changed = getattr(self, "onPlayStateChanged", [])
		if self.playback_changed in changed:
			changed.remove(self.playback_changed)

	def handleLeave(self, how, *args):
		MoviePlayer.handleLeave(self, "quit", *args)

	def stop_playback(self):
		leave = getattr(self, "leavePlayer", None)
		if leave is not None:
			leave()  # Retain the stock resume/cue-saving path.
		else:
			self.handleLeave("quit")

	def playback_changed(self, *args):
		if self.controls_ready:
			self.show_controls()

	def playback_seek(self):
		try:
			service = self.session.nav.getCurrentService()
			getter = getattr(service, "seek", None)
			return getter() if getter else None
		except Exception:
			return None

	def read_seconds(self, seek, method):
		try:
			getter = getattr(seek, method, None)
			result = getter() if getter else None
			if result and not result[0] and result[1] >= 0:
				return result[1] // TICKS
		except Exception:
			pass
		return None

	def refresh_playback(self):
		seek = self.playback_seek()
		position = self.read_seconds(seek, "getPlayPosition")
		length = self.read_seconds(seek, "getLength")
		if not length:
			length = self.recording.duration or None
		self["elapsed"].setText("%s / %s" % (clock(position), clock(length)))
		if position is not None and length:
			self["progress"].setValue(int(min(100, max(0, position * 100 // length))))
			self["remaining"].setText("%s left" % clock(max(0, length - position)))
		else:
			self["progress"].setValue(0)
			self["remaining"].setText("")
		self["playback_state"].setText("Paused" if self.paused() else "Playing")
		self.subtitle_tracks = self.available_subtitles()
		if self.control == 3 and not self.subtitle_tracks:
			self.control = 1
		self.draw_controls()

	def move_control(self, step):
		self.progress_selected = False
		self.control = max(0, min(3 if self.subtitle_tracks else 2, self.control + step))
		self.show_controls()

	def move_or_scrub(self, step):
		if self.progress_selected:
			self.scrub(step)
		else:
			self.move_control(step)

	def select_progress(self):
		if getattr(self, "shown", False) and self.progress_selected:
			self.hide_controls()
			return
		self.progress_selected = True
		self.show_controls()

	def select_controls(self):
		if getattr(self, "shown", False) and not self.progress_selected:
			self.hide_controls()
			return
		self.progress_selected = False
		self.show_controls()

	def triggerResumeLogic(self):
		"""Resume silently at Gullion TV's saved position, without the stock question."""
		if getattr(self, "is_closing", False):
			return
		download = getattr(self, "downloadCuesheet", None)
		if download is not None:
			try:
				download()
			except Exception:
				pass
		position = int(getattr(self.recording, "position", 0) or 0)
		length = int(getattr(self.recording, "duration", 0) or 0)
		if position > 10 and (not length or position < length - 10):
			seek = self.playback_seek()
			seek_to = getattr(seek, "seekTo", None)
			if seek_to is not None:
				try:
					seek_to(position * TICKS)
				except Exception:
					pass
		hide = getattr(self, "hideAfterResume", None)
		if hide is not None:
			try:
				hide()
			except Exception:
				pass

	def activate_control(self):
		if not getattr(self, "shown", False):
			self.control = 1
			self.progress_selected = False
			self.show_controls()
		elif self.progress_selected:
			self.select_controls()
		elif self.control == 0:
			self.skip(-30)
		elif self.control == 1:
			self.toggle_pause()
		elif self.control == 2:
			self.skip(30)
		else:
			self.open_subtitles()

	def toggle_pause(self):
		self.set_playing(self.paused())

	def play(self):
		self.set_playing(True)

	def set_playing(self, playing):
		method = getattr(self, "unPauseService" if playing else "pauseService", None)
		try:
			if method is None:
				raise RuntimeError("Playback control unavailable")
			method()
			self["notice"].setText("")
		except Exception:
			self["notice"].setText("Playback control isn't available yet.")
		self.show_controls()

	def skip(self, seconds):
		seek = self.playback_seek()
		try:
			is_seekable = getattr(seek, "isCurrentlySeekable", None)
			if seek is None or (is_seekable and not is_seekable()):
				raise RuntimeError("Not seekable")
			position = self.read_seconds(seek, "getPlayPosition")
			length = self.read_seconds(seek, "getLength")
			if not length:
				raise RuntimeError("Length unavailable")
			if position is not None:
				seconds = max(-position, seconds)
				if length:
					seconds = min(seconds, max(0, length - position - 1))
			method = getattr(self, "doSeekRelative", None)
			if method is None:
				raise RuntimeError("Skip unavailable")
			method(int(seconds * TICKS))
			self["notice"].setText("")
		except Exception:
			self["notice"].setText("Skipping isn't available yet.")
		self.show_controls()

	def scrub(self, step):
		"""Move one percent of the programme per key press while the bar is selected."""
		seek = self.playback_seek()
		try:
			position = self.read_seconds(seek, "getPlayPosition")
			length = self.read_seconds(seek, "getLength")
			seek_to = getattr(seek, "seekTo", None)
			if position is None or not length or seek_to is None:
				raise RuntimeError("Scrubbing unavailable")
			target = max(0, min(length - 1, position + step * max(1, length // 100)))
			seek_to(int(target * TICKS))
			self["notice"].setText("")
		except Exception:
			self["notice"].setText("Scrubbing isn't available yet.")
		self.show_controls()

	def available_subtitles(self):
		try:
			getter = getattr(self, "getCurrentServiceSubtitle", None)
			subtitle = getter() if getter else None
			get_list = getattr(subtitle, "getSubtitleList", None)
			return get_list() if get_list else []
		except Exception:
			return []

	def open_subtitles(self):
		if not self.available_subtitles() or not callable(getattr(self, "enableSubtitle", None)):
			return
		self.subtitle_dialog_open = True
		self.controls_timer.stop()
		self.hide()
		self.session.openWithCallback(self.subtitles_closed, SoundAndSubtitles, self, focus="subtitles")

	def subtitles_closed(self, *args):
		self.subtitle_dialog_open = False
		self.show_controls()

	def draw_controls(self):
		names = ("replay_30", "play" if self.paused() else "pause", "forward_30", "subtitles")
		(self["progress_focus"].show if self.progress_selected else self["progress_focus"].hide)()
		for i in range(len(BUTTONS)):
			visible = i != 3 or bool(self.subtitle_tracks)
			self["control%d_icon" % i].show() if visible else self["control%d_icon" % i].hide()
			if not visible:
				self["control%d_bg" % i].hide()
				continue
			chosen = i == self.control and not self.progress_selected
			(self["control%d_bg" % i].show if chosen else self["control%d_bg" % i].hide)()
			widget = self["control%d_icon" % i]
			if widget.instance is not None:
				widget.instance.setPixmap(LoadPixmap(icons.icon_path(names[i]), cached=True))
